import errno
import threading
import time
import wave

import numpy as np
import pytest

from matematigin_mantigi.core import audio_capture as ac


class FakeSoundDevice:
    """Gerçek AudioCapture'ı sürmek için sahte sounddevice modülü (monkeypatch ac._sd). InputStream geri çağrıyı
    ayrı iş parçacığından 20 ms'lik bloklarla besler; `blocks` blok verip susar. Mikrofon çekilince (USB kablosu,
    AirPods koptu) CoreAudio'da akış açık kalır, geri çağrı gelmez, stop() ve close() normal döner: aynısı.
    Blok sayısı sabit, beslemede bekleme yok: sonuç duvar saatine bağlı değil."""

    RATE, BLOCK = 48000, 960                          # 20 ms

    class _TimeInfo:                                  # sürücü zaman bilgisi vermiyor (0): gecikme tahminle
        inputBufferAdcTime = 0.0
        currentTime = 0.0

    def __init__(self, blocks: int):
        self.blocks = blocks
        self.fed = threading.Event()                  # bütün bloklar geri çağrıya verildi
        fake = self

        class InputStream:
            def __init__(self, device, samplerate, channels, dtype, latency, callback):
                self.cb, self.channels = callback, channels
                self._t = threading.Thread(target=self._feed, daemon=True)

            def start(self):
                self._t.start()

            def _feed(self):
                block = np.full((fake.BLOCK, self.channels), 1000, np.int16)
                for _ in range(fake.blocks):
                    self.cb(block, fake.BLOCK, fake._TimeInfo(), None)
                fake.fed.set()                        # ... ve mikrofon susar; akış yine de "açık"

            def stop(self):
                self._t.join(10)

            def close(self):
                pass
        self.InputStream = InputStream

    @staticmethod
    def query_hostapis():
        return [{"name": "Core Audio"}]

    @staticmethod
    def query_devices(*a, **k):
        d = {"name": "USB Mikrofon", "max_input_channels": 1, "hostapi": 0, "default_samplerate": 48000.0}
        return d if (a or k) else [d]


def disk_full_after(monkeypatch, nbytes: int) -> None:
    """WAV yazımı nbytes ses verisinden sonra OSError(ENOSPC) verir (disk doldu): yazıcı iş parçacığının ölümü."""
    real = wave.Wave_write.writeframes
    written = [0]

    def writeframes(self, data):
        if written[0] + len(data) > nbytes:
            raise OSError(errno.ENOSPC, "No space left on device")
        written[0] += len(data)
        return real(self, data)
    monkeypatch.setattr(wave.Wave_write, "writeframes", writeframes)


def test_list_and_resolve_prefer_wasapi_on_windows(monkeypatch):
    class SD:
        @staticmethod
        def query_hostapis():
            return [{"name": "MME"}, {"name": "Windows WASAPI"}]

        @staticmethod
        def query_devices(*a, **k):
            return [{"name": "Mik A", "max_input_channels": 1, "hostapi": 0},
                    {"name": "Hoparlör", "max_input_channels": 0, "hostapi": 1},
                    {"name": "Mik A", "max_input_channels": 2, "hostapi": 1},
                    {"name": "USB Mik", "max_input_channels": 1, "hostapi": 1}]
    monkeypatch.setattr(ac, "_sd", lambda: SD)
    assert ac.list_input_devices() == ["Mik A", "USB Mik"]
    assert ac.resolve_input_device("Mik A") == 2               # WASAPI kopyası, MME değil
    assert ac.resolve_input_device("usb") == 3                 # alt dize
    assert ac.resolve_input_device("yok böyle") is None and ac.resolve_input_device("") is None


def test_list_falls_back_when_wasapi_has_no_inputs(monkeypatch):
    """Aygıt indeksleri değişince WASAPI'de giriş kalmayabilir; liste boş kalmamalı, bir alt API'ye düşmeli."""
    class SD:
        @staticmethod
        def query_hostapis():
            return [{"name": "MME"}, {"name": "Windows DirectSound"},
                    {"name": "Windows WASAPI"}, {"name": "Windows WDM-KS"}]

        @staticmethod
        def query_devices(*a, **k):
            return [{"name": "Realtek Mik", "max_input_channels": 2, "hostapi": 0},   # MME
                    {"name": "Realtek Mik", "max_input_channels": 2, "hostapi": 1},   # DirectSound
                    {"name": "Hoparlör (WASAPI)", "max_input_channels": 0, "hostapi": 2},
                    {"name": "Realtek Mik (WDM)", "max_input_channels": 2, "hostapi": 3}]
    monkeypatch.setattr(ac, "_sd", lambda: SD)
    # WASAPI'de giriş yok -> DirectSound (rank 1) seçilir, MME (rank 2) değil
    assert ac.list_input_devices() == ["Realtek Mik"]
    assert ac.resolve_input_device("Realtek Mik") == 1          # DirectSound kopyası


def test_list_never_empty_when_only_wdmks_has_inputs(monkeypatch):
    class SD:
        @staticmethod
        def query_hostapis():
            return [{"name": "MME"}, {"name": "Windows WASAPI"}, {"name": "Windows WDM-KS"}]

        @staticmethod
        def query_devices(*a, **k):
            return [{"name": "USB Mik (U850)", "max_input_channels": 1, "hostapi": 2}]  # yalnız WDM-KS
    monkeypatch.setattr(ac, "_sd", lambda: SD)
    assert ac.list_input_devices() == ["USB Mik (U850)"]
    assert ac.resolve_input_device("USB Mik (U850)") == 0


def test_start_falls_back_when_no_default_input(monkeypatch, tmp_path):
    """Varsayılan giriş -1 (PortAudioError) olduğunda ilk listelenen mikrofona düşer, çökmeden başlar."""
    import sounddevice
    calls = {"opened_device": "SENTINEL"}

    class FakeStream:
        def __init__(self, device, **k):
            calls["opened_device"] = device
        def start(self): pass
        def stop(self): pass
        def close(self): pass

    class SD:
        PortAudioError = sounddevice.PortAudioError
        InputStream = FakeStream

        @staticmethod
        def query_hostapis():
            return [{"name": "Windows WASAPI"}]

        @staticmethod
        def query_devices(device=None, kind=None):
            if device is None and kind == "input":             # varsayılan giriş yok (-1)
                raise sounddevice.PortAudioError("Error querying device -1")
            if device is None:                                 # tüm aygıtlar
                return [{"name": "Tek Mik", "max_input_channels": 1, "hostapi": 0,
                         "default_samplerate": 44100.0}]
            return {"name": "Tek Mik", "max_input_channels": 1, "hostapi": 0, "default_samplerate": 44100.0}
    monkeypatch.setattr(ac, "_sd", lambda: SD)
    cap = ac.AudioCapture(None)
    cap.start(tmp_path / "a.wav")
    assert calls["opened_device"] == 0 and cap.samplerate == 44100    # ilk mikrofon seçildi
    cap.stop()


def test_list_is_empty_without_portaudio(monkeypatch):
    def boom():
        raise OSError("PortAudio yok")
    monkeypatch.setattr(ac, "_sd", boom)
    assert ac.list_input_devices() == [] and ac.resolve_input_device("x") is None


def test_capture_writes_wav_and_measures_first_sample(tmp_path, monkeypatch):
    """Sahte PortAudio: callback'i ayrı iş parçacığından 20 ms'lik bloklarla besler."""
    import threading

    class FakeStream:
        def __init__(self, device, samplerate, channels, dtype, latency, callback):
            self.cb, self.rate, self.channels = callback, samplerate, channels
            self._run = threading.Event()

        def start(self):
            self._run.set()
            self._t = threading.Thread(target=self._feed, daemon=True); self._t.start()

        def _feed(self):
            class TI:
                inputBufferAdcTime = 0.0
                currentTime = 0.0
            block = np.full((int(self.rate * 0.02), self.channels), 1000, np.int16)
            for _ in range(25):                        # sabit 25 blok = 0,5 sn ses; duvar saatine bağlı değil
                self.cb(block, len(block), TI(), None)
                time.sleep(0.002)

        def stop(self):
            self._t.join(10)                           # tüm bloklar beslenmeden durmaz (yavaş CI'da da aynı sonuç)
            self._run.clear()

        def close(self):
            pass

    class SD:
        InputStream = FakeStream

        @staticmethod
        def query_hostapis():
            return [{"name": "CoreAudio"}]

        @staticmethod
        def query_devices(*a, **k):
            d = {"name": "MacBook Pro Microphone", "max_input_channels": 1, "hostapi": 0, "default_samplerate": 48000.0}
            return d if (a or k) else [d]
    monkeypatch.setattr(ac, "_sd", lambda: SD)
    cap = ac.AudioCapture("MacBook Pro Microphone")
    before = time.monotonic()
    cap.start(tmp_path / "a.wav")
    time.sleep(0.1)
    res = cap.stop()
    assert res.samplerate == 48000 and res.channels == 1
    # ilk örnek zamanı = geri çağrı anı - (sürücü gecikmesi + blok süresi 20 ms)
    assert res.first_sample_monotonic is not None and before - 0.05 <= res.first_sample_monotonic <= res.stopped_monotonic
    assert res.samples == 25 * 960 and abs(res.duration - 0.5) < 1e-6 and res.overflows == 0 and res.dropped_blocks == 0
    with wave.open(str(tmp_path / "a.wav")) as w:
        assert w.getframerate() == 48000 and w.getnframes() == res.samples and w.getsampwidth() == 2
    assert 0 < res.wall_duration < 5


# --- #1: WAV yazıcısı ölürse sebep kaydediciye ulaşır (denetim rec#1 ikinci kipi) ----------------------------

def test_writer_thread_error_reaches_stop_instead_of_dying_silently(tmp_path, monkeypatch):
    """WAV yazıcı iş parçacığı yazım hatasıyla (disk dolu) ölünce istisna yalnız iş parçacığı kancasına gidiyordu:
    stop() normal dönüyor, kaydedici sesin yarıda kaldığını bilmiyordu. Şimdi sebep AudioResult.error ile döner, o
    ana dek yazılan ses WAV'da okunur kalır, traceback hatalar.log'a gider (log_handled). İş parçacığından istisna
    kaçmaz: genel 'Beklenmeyen hata' kutusu kayıt sürerken tahtanın üstünde açılmaz, kayıt sonunda söylenir."""
    from matematigin_mantigi.core import crash_log
    leaked, logged = [], []
    monkeypatch.setattr(threading, "excepthook", lambda args: leaked.append(args.exc_value))
    monkeypatch.setattr(crash_log, "log_handled", lambda exc, where="": logged.append(exc))
    sd = FakeSoundDevice(blocks=50)
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    disk_full_after(monkeypatch, 10 * 960 * 2)                  # 10 blok (0,2 sn) yazılır, sonra disk dolu
    cap = ac.AudioCapture("USB Mikrofon")
    cap.start(tmp_path / "a.wav")
    assert sd.fed.wait(10)
    res = cap.stop()
    assert res.error == "[Errno 28] No space left on device"
    assert res.samples == 10 * 960 and res.first_sample_monotonic is not None
    with wave.open(str(tmp_path / "a.wav")) as w:
        assert w.getnframes() == 10 * 960                       # yazılabilen ses dosyada, başlık geçerli
    assert leaked == [] and len(logged) == 1 and isinstance(logged[0], OSError)


def test_wav_close_error_is_returned_not_raised(tmp_path, monkeypatch):
    """Disk doluyken WAV'ın kapanışı (tampon boşaltma, başlık) da OSError verir. stop() bunu fırlatırsa kaydedici
    'Mikrofon kapatılamadı' der, yazılmış sesi hiç birleştirmez. stop() sonucu yine döndürür, sebep error'da."""
    real_close, raised = wave.Wave_write.close, []

    def close(self):
        real_close(self)
        if not raised:                                          # yalnız ilk kapanış (__del__ yeniden çağırır)
            raised.append(True)
            raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(wave.Wave_write, "close", close)
    sd = FakeSoundDevice(blocks=10)
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    cap = ac.AudioCapture("USB Mikrofon")
    cap.start(tmp_path / "a.wav")
    assert sd.fed.wait(10)
    res = cap.stop()
    assert raised and res.error == "[Errno 28] No space left on device" and res.samples == 10 * 960


# --- O1: son örneğin zamanı: mikrofon durdurmadan önce sustu mu ------------------------------------------------

def test_capture_records_when_the_last_sample_arrived(tmp_path, monkeypatch):
    """Mikrofon durdurmadan önce susarsa (kablo çekildi, AirPods koptu) akış açık kalır, geri çağrı gelmez; örnek
    sayısı / süre oranı düşer. Kaydedici bunu saat kaymasından ancak son örneğin ne zaman geldiğini bilirse ayırır:
    sonuçta son bloğun sonunun zamanı (ilk örnekle aynı zaman tabanı) ve ondan durdurmaya dek geçen süre var."""
    sd = FakeSoundDevice(blocks=10)
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    cap = ac.AudioCapture("USB Mikrofon")
    cap.start(tmp_path / "a.wav")
    assert sd.fed.wait(10)
    fed = time.monotonic()
    time.sleep(0.3)                                             # mikrofon sustu; durdurma sonra geliyor
    res = cap.stop()
    assert res.first_sample_monotonic < res.last_sample_monotonic <= fed
    # >= 0.3 - 0.02: Windows'ta (Python 3.12) time.monotonic() ~15,6 ms adımlıdır (GetTickCount64); 0,3 sn'lik
    # uykudan sonra ölçülen fark bir adım kısa çıkabilir (Windows CI: 0.297).
    assert res.tail_gap == pytest.approx(res.stopped_monotonic - res.last_sample_monotonic)
    assert res.tail_gap >= 0.3 - 0.02


# --- k1/k2: sürücü takılınca kapanış sınırlı, yarım açılış iz bırakmaz ---------------------------------------

def _wav_frames(path) -> int:
    with wave.open(str(path), "rb") as w:
        return w.getnframes()


@pytest.mark.parametrize("driver", ["takılıyor", "hata veriyor"])
def test_stop_keeps_the_sound_when_the_driver_hangs_or_fails_closing_the_stream(tmp_path, monkeypatch, driver):
    """k1: akışın kapanması (Pa_StopStream) kapanışın sınırsız adımıydı: USB mikrofon çekilince takılan sürücüde stop()
    hiç dönmüyor, kaydedici sonsuza dek 'kaydediliyor'da kalıyordu. Akıştan istisna gelince de (sounddevice varsayılan
    olarak yutar; başka bir sürüm fırlatabilir) stop() WAV'ı kapatmadan fırlatıyor, kaydedici sesi hiç
    birleştirmiyordu. Şimdi akış yardımcı iş parçacığında en çok STREAM_STOP_S beklenir; takılsa da hata verse de o
    ana dek gelen ses WAV'a yazılıp dosya kapanır, sonuç döner ve sorun close_error'da."""
    release = threading.Event()
    sd = FakeSoundDevice(blocks=10)

    def stop(stream):
        if driver == "takılıyor":
            release.wait(30)                                    # sürücü takıldı (test sonunda bırakılır)
        else:
            raise RuntimeError("Error stopping stream: Unanticipated host error [PaErrorCode -9999]")
    sd.InputStream.stop = stop
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    monkeypatch.setattr(ac.AudioCapture, "STREAM_STOP_S", 0.3)
    cap = ac.AudioCapture("USB Mikrofon")
    cap.start(tmp_path / "a.wav")
    assert sd.fed.wait(10)
    try:
        res = cap.stop()
    finally:
        release.set()
    assert res.samples == 10 * 960 and _wav_frames(tmp_path / "a.wav") == 10 * 960     # o ana dek gelen ses tam
    assert res.error is None                                                            # WAV sağlam
    expected = "0,3 sn içinde yanıt vermedi" if driver == "takılıyor" else "Unanticipated host error"
    assert res.close_error and expected in res.close_error, res.close_error


def test_start_that_cannot_open_the_stream_leaves_nothing_behind(tmp_path, monkeypatch):
    """k2: InputStream açılamayınca (aygıt meşgul ya da çıkarıldı: PaErrorCode -9985) WAV açık, yazıcı iş parçacığı
    canlı kalıyordu; her denemede bir tane daha, Windows'ta açık WAV kilitli, klasörde 0 B'lık WAV. Şimdi start()
    yarım açılışını temizler: istisna yine fırlar, yazıcı durur, WAV kapanıp silinir."""
    sd = FakeSoundDevice(blocks=0)

    class Busy:
        def __init__(self, *a, **k):
            raise RuntimeError("Error opening InputStream: Device unavailable [PaErrorCode -9985]")
    sd.InputStream = Busy
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    cap = ac.AudioCapture("USB Mikrofon")
    with pytest.raises(RuntimeError, match="Device unavailable"):
        cap.start(tmp_path / "a.wav")
    assert cap._writer is None or not cap._writer.is_alive()
    assert cap._wav is None and not (tmp_path / "a.wav").exists()
    assert not [t for t in threading.enumerate() if getattr(getattr(t, "_target", None), "__self__", None) is cap]


@pytest.mark.skipif(not ac.list_input_devices(), reason="mikrofon yok")
def test_real_microphone_short_capture(tmp_path):
    import sounddevice
    cap = ac.AudioCapture(None)
    try:
        cap.start(tmp_path / "real.wav")
    except (sounddevice.PortAudioError, RuntimeError) as err:
        pytest.skip(f"mikrofon açılamadı (donanım/izin): {err}")
    time.sleep(0.6)
    res = cap.stop()
    assert res.samples > res.samplerate * 0.3 and res.first_sample_monotonic is not None
    assert res.dropped_blocks == 0
