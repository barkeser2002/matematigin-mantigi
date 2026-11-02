import itertools
import os
import re
import signal
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from matematigin_mantigi.core import audio_capture as ac
from matematigin_mantigi.core.recorder import (MssFfmpegRecorder, NullRecorder, RecordRect, RecorderError,
                                               audio_rate_correction, ffmpeg_args, find_ffmpeg, mux_args, record_rect_for)
from matematigin_mantigi.ui.record_badge import RecordBadge
from matematigin_mantigi.ui.theme import FontFamilies


def test_record_rect_physical_is_even_and_scaled():
    r = record_rect_for((88, 0, 1831, 1079, 2.0))
    assert r == RecordRect(88, 0, 1831, 1079, 2.0)
    p = r.physical()
    assert (p.x, p.y, p.width, p.height, p.dpr) == (176, 0, 3662, 2158, 1.0)
    assert RecordRect(0, 0, 1833, 1081).physical().width == 1832
    assert r.to_mss() == {"left": 88, "top": 0, "width": 1831, "height": 1079}


def test_null_recorder_lifecycle():
    from matematigin_mantigi.core.recorder import RecorderState
    rec = NullRecorder()
    assert not rec.is_recording and rec.elapsed_seconds == 0 and rec.state is RecorderState.IDLE
    rec.start(RecordRect(0, 0, 100, 100), fps=60)
    assert rec.is_recording and rec.last_rect == RecordRect(0, 0, 100, 100) and rec.fps == 60
    assert rec.state is RecorderState.RECORDING                  # arayüz is_recording'e değil state'e bakar
    with pytest.raises(RecorderError, match="Kayıt zaten sürüyor"):
        rec.start(RecordRect(0, 0, 50, 50))                      # gerçek kaydediciyle aynı: yalnız IDLE'da başlar
    assert rec.last_rect == RecordRect(0, 0, 100, 100)
    assert rec.stop() is None and not rec.is_recording and rec.state is RecorderState.IDLE


def test_badge_text_and_ticks(qtbot):
    b = RecordBadge(FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(b)
    b.set_format(1920, 1080, 60)
    assert not b.active and b.isHidden()
    b.start()
    assert b.active and b.text() == "KAYIT · 00:00 · 1920×1080 · 60 fps"
    b.tick(); b.tick()
    assert b.text() == "KAYIT · 00:02 · 1920×1080 · 60 fps" and b.seconds == 2
    b.stop()
    assert not b.active and b.isHidden() and b.seconds == 0


def test_ffmpeg_args_video_only(tmp_path):
    out = tmp_path / "k.mp4"
    a = ffmpeg_args("ffmpeg", 640, 480, 30, out, platform="win32")
    assert a[:2] == ["ffmpeg", "-y"] and "-s" in a and a[a.index("-s") + 1] == "640x480"
    assert "libx264" in a and "yuv420p" in a and a[-1] == str(out) and "-nostats" in a
    assert a[a.index("-thread_queue_size") + 1] == "8"            # Retina'da kare ~20 MB: kuyruk küçük kalmalı
    assert "dshow" not in a and "avfoundation" not in a and "-c:a" not in a
    s = ffmpeg_args("ffmpeg", 1832, 1080, 60, out, platform="win32", out_height=1440)
    assert s[s.index("-vf") + 1] == "scale=-2:1440:flags=bilinear" and s[s.index("-framerate") + 1] == "60"
    assert "-vf" not in ffmpeg_args("ffmpeg", 1832, 1080, 60, out, platform="win32", out_height=0)


def test_mux_args_offsets_and_rate_fix(tmp_path):
    v, a, out = tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4"
    early = mux_args("ffmpeg", v, a, out, 0.25)                   # ses 250 ms önce başladı: başı atılır
    assert early[early.index("-ss") + 1] == "0.250" and "-itsoffset" not in early
    late = mux_args("ffmpeg", v, a, out, -0.1)                    # ses geç başladı: geciktirilir
    assert late[late.index("-itsoffset") + 1] == "0.100" and "-ss" not in late
    assert "-c:v" in early and early[early.index("-c:v") + 1] == "copy" and "aac" in early and early[-1] == str(out)
    fixed = mux_args("ffmpeg", v, a, out, 0.0, asetrate=48003)
    assert fixed[fixed.index("-af") + 1] == "asetrate=48003,aresample=48000,afade=t=in:st=0:d=0.01"
    plain = mux_args("ffmpeg", v, a, out, 0.0)                    # saat düzeltmesi yoksa da 10 ms fade-in (tık önler)
    assert plain[plain.index("-af") + 1] == "afade=t=in:st=0:d=0.01"


def test_mux_args_names_the_wav_demuxer_for_the_audio_input(tmp_path):
    """Ses girişi -f wav ile açılır, biçim tahmine bırakılmaz: imageio-ffmpeg 0.8.0'ın ffmpeg 9.0.2'si
    düz WAV'ı mpegts sanıp 'End of file' ile düşüyor, kayıt sessiz kalıyordu."""
    v, a, out = tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4"
    for offset in (0.25, 0.0, -0.1):                              # -ss, sıfır ve -itsoffset yolları
        args = mux_args("ffmpeg", v, a, out, offset)
        i = args.index(str(a))
        assert args[i - 3:i] == ["-f", "wav", "-i"], args
        assert args.index(str(v)) < args.index("-f")              # video girişi (mp4) tahmine açık kalır


def test_audio_rate_correction_only_for_long_clear_drift():
    from matematigin_mantigi.core.audio_capture import AudioResult
    from pathlib import Path as _P
    short = AudioResult(_P("a.wav"), 48000, 1, 48000 * 30, 0.0, 30.0 - 0.02)
    assert audio_rate_correction(short) is None                   # 30 sn: gürültü > gerçek kayma
    long_ok = AudioResult(_P("a.wav"), 48000, 1, 48000 * 1200, 0.0, 1200.0)
    assert audio_rate_correction(long_ok) is None                 # kayma yok
    drift = AudioResult(_P("a.wav"), 48000, 1, 48000 * 1200, 0.0, 1200.0 - 0.36)   # 300 ppm hızlı mikrofon saati
    assert audio_rate_correction(drift) == 48014
    broken = AudioResult(_P("a.wav"), 48000, 1, 48000 * 600, 0.0, 700.0)          # %14: ölçüm hatası, dokunma
    assert audio_rate_correction(broken) is None


def test_rate_fix_is_not_mistaken_for_a_microphone_cut_or_lost_samples():
    """O1: eksik sesi %1'e dek 'saat kayması' sayıyordu. Mikrofon dersin sonuna yakın kesilince (620 sn'de son 5 sn:
    %0,8) asetrate sesi bütün derse yayıyordu: ton düşüyor, senkron giderek kayıyor, uyarı çıkmıyordu. Şimdi (1) son
    örnek durdurmadan MIC_GAP_S'den önce geldiyse mikrofon kesilmiştir, düzeltme yok (kayma olsa bile); (2) kayma
    son örneğe dek ölçülür (durdurmaya değil: sona yakın kısa bir kesik ölçümü bozmasın); (3) 1000 ppm'den büyük fark
    saat kayması değildir (gerçek mikrofon saati onlarca, kötü durumda birkaç yüz ppm)."""
    from matematigin_mantigi.core.audio_capture import AudioResult
    a, rate = Path("a.wav"), 48000
    s2 = AudioResult(a, rate, 1, rate * 615, 0.0, 620.0, last_sample_monotonic=615.0)      # son 5 sn kesik
    assert audio_rate_correction(s2) is None                                                # eskiden 47613
    cut = AudioResult(a, rate, 1, round(48014.4 * 3597), 0.0, 3600.0, last_sample_monotonic=3597.0)
    assert audio_rate_correction(cut) is None             # 300 ppm kayma var ama mikrofon son 3 sn'de kesildi
    span = AudioResult(a, rate, 1, round(48014.4 * 1199.9), 0.0, 1200.0, last_sample_monotonic=1199.9)
    assert audio_rate_correction(span) == 48014           # kayma son örneğe dek ölçülür (durdurmaya dek değil)
    near = AudioResult(a, rate, 1, round(48000 * 1.0008 * 1200), 0.0, 1200.0, last_sample_monotonic=1200.0)
    assert audio_rate_correction(near) == 48038           # 800 ppm: gerçekçi sınırın içinde
    lost = AudioResult(a, rate, 1, round(48000 * 1.005 * 1200), 0.0, 1200.0)
    assert audio_rate_correction(lost) is None            # %0,5: saat kayması değil (eskiden 48240)


def _beep_times(exe, path, rate: int = 8000) -> list[float]:
    """Birleşik dosyanın sesindeki biplerin başlangıçları (sn): 1 sn'den uzun aralıkla ayrılmış yüksek örnekler."""
    raw = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-f", "s16le", "-ac", "1",
                          "-ar", str(rate), "-"], capture_output=True, check=True).stdout
    loud = np.flatnonzero(np.abs(np.frombuffer(raw, np.int16).astype(np.int32)) > 5000)
    starts = [loud[0]] + [loud[i] for i in range(1, loud.size) if loud[i] - loud[i - 1] > rate] if loud.size else []
    return [round(float(i) / rate, 3) for i in starts]


def _mux_lesson(tmp_path, video_s: float, heard_s: float, stop_s: float, beeps=(), skipped_s: float = 0.0):
    """Kaydedicinin kendi birleştirmesi (_mux), gerçek ffmpeg: video_s'lik küçük test videosu (2 kare/sn), mikrofonun
    heard_s'de sustuğu (son örnek) bir WAV (beeps'te 0,2 sn'lik bipler) ve stop_s'de durdurulan kayıt. skipped_s:
    kodlayıcı yetişemediği için durdurmada yazılmayan borç (video erken biter). Oturum döner."""
    from matematigin_mantigi.core.audio_capture import AudioResult
    from matematigin_mantigi.core.recorder import _Session
    exe, fps, rate = find_ffmpeg(), 2, 8000
    video, wav = tmp_path / "kayit_x.video.mp4", tmp_path / "kayit_x.wav"
    subprocess.run([exe, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc=s=64x48:r={fps}:d={video_s}", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt",
                    "yuv420p", str(video)], check=True, capture_output=True)
    pcm = np.zeros(int(heard_s * rate), np.int16)
    for beep in beeps:
        i = int(beep * rate)
        pcm[i:i + rate // 5] = (np.sin(2 * np.pi * 1000 * np.arange(rate // 5) / rate) * 15000).astype(np.int16)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm.tobytes())
    s = _Session(rect=RecordRect(0, 0, 64, 48), encoder="libx264", final_path=tmp_path / "kayit_x.mp4",
                 video_path=video, log_path=tmp_path / "kayit_x.log", wav_path=wav, fps=fps)
    t0 = 1000.0
    s.video_t0, s.stopped_at, s.duration, s.frames_skipped = t0, t0 + stop_s, stop_s, round(skipped_s * fps)
    MssFfmpegRecorder(lambda: tmp_path)._mux(s, AudioResult(wav, rate, 1, len(pcm), t0, t0 + stop_s,
                                                            last_sample_monotonic=t0 + heard_s))
    return s


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_microphone_cut_near_the_end_of_a_long_lesson_is_not_taken_for_clock_drift(tmp_path):
    """O1 (son inceleme s2): 620 sn'lik ders, mikrofon son 5 sn'de kesildi. asetrate=47613 uygulanıyordu: WAV'da 60.,
    300. ve 600. saniyedeki bipler birleşik dosyada 60,49 / 302,44 / 604,88'de; audio_error yoktu, ara dosyalar
    silindi. Şimdi düzeltme yok, bipler yerinde, uyarı kesildiği yeri söyler, eksik ses sessizlikle dolar (dosya
    videonun uzunluğunda)."""
    from matematigin_mantigi.core.recorder import media_duration
    s = _mux_lesson(tmp_path, video_s=620, heard_s=615, stop_s=620, beeps=(60.0, 300.0, 600.0))
    assert s.error is None, s.error
    assert s.audio_error == "Mikrofon kayıt sırasında kesildi (10:15. dakikadan sonra ses yok)", s.audio_error
    exe = find_ffmpeg()
    assert _beep_times(exe, s.final_path) == pytest.approx([60.0, 300.0, 600.0], abs=0.05)
    assert media_duration(exe, s.final_path) == pytest.approx(620.0, abs=0.1)
    assert not s.video_path.exists() and not s.wav_path.exists()      # birleşik dosya tam: ara dosyalar silindi


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_microphone_cut_is_reported_even_when_the_video_ended_early(tmp_path):
    """Kodlayıcı yetişemediği için video durdurmadan erken bittiyse (K1: 10 sn video, 30 sn'lik kayıt) mikrofonun
    kesildiği yer videonun sonuna değil durdurma anına göre ölçülür: ses 20. saniyede sustu, uyarı bunu söyler;
    birleşik dosya sesin sonuna dek sürer (son kare ekranda)."""
    from matematigin_mantigi.core.recorder import media_duration
    s = _mux_lesson(tmp_path, video_s=10, heard_s=20, stop_s=30, beeps=(18.0,), skipped_s=20)
    assert s.error is None, s.error
    assert s.audio_error == "Mikrofon kayıt sırasında kesildi (0:20. dakikadan sonra ses yok)", s.audio_error
    exe = find_ffmpeg()
    assert s.tail_kept and media_duration(exe, s.final_path) == pytest.approx(20.0, abs=0.1)
    assert _beep_times(exe, s.final_path) == pytest.approx([18.0], abs=0.05)


def synthetic_grabber(rect: RecordRect) -> np.ndarray:
    t = int(time.monotonic() * 20) % rect.width
    frame = np.full((rect.height, rect.width, 4), (255, 255, 255, 255), np.uint8)
    frame[20:60, t:min(rect.width, t + 40)] = (30, 60, 200, 255)
    return frame


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_mss_ffmpeg_recorder_writes_playable_mp4(tmp_path):
    import cv2
    rec = MssFfmpegRecorder(lambda: tmp_path / "oturum", fps=10, grabber=synthetic_grabber, out_height=0)
    assert not rec.is_recording
    rec.start(RecordRect(0, 0, 320, 240))
    assert rec.is_recording and rec.last_path is not None and rec.last_path.suffix == ".mp4"
    time.sleep(0.8)
    path = rec.stop()
    assert not rec.is_recording and rec.error is None, rec.error
    assert path.exists() and path.stat().st_size > 1000 and rec.frames_written >= 5
    cap = cv2.VideoCapture(str(path))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ok, frame = cap.read(); cap.release()
    assert ok and frame.shape == (240, 320, 3) and frames >= 5


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_recorder_scales_output_to_requested_height(tmp_path):
    import cv2
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=10, grabber=synthetic_grabber, out_height=480)
    rec.start(RecordRect(0, 0, 320, 240)); time.sleep(0.5); path = rec.stop()
    assert rec.error is None, rec.error
    cap = cv2.VideoCapture(str(path)); ok, frame = cap.read(); cap.release()
    assert ok and frame.shape[:2] == (480, 640)


def test_detect_encoder_prefers_hardware_when_probe_succeeds():
    from matematigin_mantigi.core.recorder import detect_encoder
    assert detect_encoder("ffmpeg", platform="darwin", runner=lambda cmd: 0) == "h264_videotoolbox"
    assert detect_encoder("ffmpeg", platform="win32", runner=lambda cmd: 0 if "h264_qsv" in cmd else 1) == "h264_qsv"
    assert detect_encoder("ffmpeg", platform="win32", runner=lambda cmd: 1) == "libx264"
    assert detect_encoder("ffmpeg", platform="linux", runner=lambda cmd: 0) == "libx264"


def test_ffmpeg_args_encoder_selection(tmp_path):
    out = tmp_path / "k.mp4"
    a = ffmpeg_args("ffmpeg", 640, 480, 60, out, platform="win32", encoder="h264_nvenc")
    assert "h264_nvenc" in a and "libx264" not in a
    b = ffmpeg_args("ffmpeg", 640, 480, 60, out, platform="darwin", encoder="h264_videotoolbox")
    assert "h264_videotoolbox" in b


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_slow_grabber_still_keeps_real_time_duration(tmp_path):
    """Yakalama 10 kare/sn verse de 30 fps çıktı ~1 sn'lik kayıtta ~30 kare taşır (çoğaltma)."""
    def slow(rect):
        time.sleep(0.1)
        return synthetic_grabber(rect)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=30, grabber=slow, out_height=0)
    rec.start(RecordRect(0, 0, 160, 120)); time.sleep(1.0); rec.stop()
    assert rec.error is None and rec.frames_grabbed <= 14
    assert 24 <= rec.frames_written <= 40


def test_recorder_without_ffmpeg_raises(tmp_path, monkeypatch):
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "find_ffmpeg", lambda: None)
    rec = MssFfmpegRecorder(lambda: tmp_path, grabber=synthetic_grabber)
    with pytest.raises(RecorderError, match="ffmpeg"):
        rec.start(RecordRect(0, 0, 64, 48))
    assert not rec.is_recording


def test_grab_screen_returns_bgra():
    try:
        frame = __import__("matematigin_mantigi.core.recorder", fromlist=["grab_screen"]).grab_screen(RecordRect(0, 0, 64, 48))
    except Exception as err:  # noqa: BLE001 - ekran yoksa (CI)
        pytest.skip(f"ekran yakalanamadı: {err}")
    assert frame.shape == (48, 64, 4) and frame.dtype == np.uint8


class FakeAudioCapture:
    """Gerçek mikrofon yerine 1 kHz sinüs üretir; ilk örnek zamanı start() anıdır. limit (sn) verilirse kayıt ne
    kadar sürerse sürsün yalnız ilk limit saniyelik ses gelir (mikrofon sonra kesildi)."""
    instances: list = []
    limit: float | None = None

    def __init__(self, device):
        self.device = device
        self.samplerate, self.channels = 48000, 1
        self.first_sample_monotonic = None
        self.path = None
        FakeAudioCapture.instances.append(self)

    def start(self, path):
        self.path = Path(path); self.first_sample_monotonic = time.monotonic()

    def stop(self):
        import wave
        from matematigin_mantigi.core.audio_capture import AudioResult
        stopped = time.monotonic()
        n = int((stopped - self.first_sample_monotonic) * self.samplerate)
        if self.limit is not None:
            n = min(n, int(self.limit * self.samplerate))
        t = np.arange(n) / self.samplerate
        pcm = (np.sin(2 * np.pi * 1000 * t) * 12000).astype(np.int16)
        with wave.open(str(self.path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.samplerate); w.writeframes(pcm.tobytes())
        return AudioResult(self.path, self.samplerate, 1, n, self.first_sample_monotonic, stopped)


def _stream_seconds(exe, path, flag):
    import re as _re
    err = subprocess.run([exe, "-hide_banner", "-i", str(path), flag, "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = _re.findall(r"time=(\d+):(\d+):([\d.]+)", err)
    h, mi, sec = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(sec)


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_recorder_muxes_audio_aligned_with_video(tmp_path):
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture)
    rec.start(RecordRect(0, 0, 160, 120)); time.sleep(1.5); path = rec.stop()
    assert rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
    assert path.exists() and rec.audio_result is not None and rec.audio_result.samples > 48000
    assert rec.av_offset_ms is not None and 0 <= rec.av_offset_ms < 500      # ses videodan önce başladı
    assert not (tmp_path / path.name.replace(".mp4", ".video.mp4")).exists()  # ara dosyalar silindi
    assert not list(tmp_path.glob("*.wav"))
    exe = find_ffmpeg()
    v, a = _stream_seconds(exe, path, "-an"), _stream_seconds(exe, path, "-vn")
    assert abs(v - a) < 0.15, (v, a)
    log = next(tmp_path.glob("kayit_*.log"))
    assert log.exists()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_recorder_keeps_video_when_microphone_fails(tmp_path):
    class Broken:
        def __init__(self, device): pass
        def start(self, path): raise RuntimeError("aygıt yok")
        def stop(self): raise AssertionError("çağrılmamalı")
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Yok", audio_factory=Broken)
    rec.start(RecordRect(0, 0, 160, 120)); time.sleep(0.5); path = rec.stop()
    assert path.exists() and rec.error is None and "Mikrofon açılamadı" in rec.audio_error


# --- #2: kayıt kapanırken yeni kayıt (denetim rec#2, app#1, e2e#2) -----------------------------------------

def stepping_clock(start: datetime = datetime(2026, 9, 23, 10, 0, 0)):
    """Her çağrı bir saniye ileri: aynı saniyede başlayan iki kaydın adı da ayrı olsun (ad çakışması ayrı madde)."""
    seconds = itertools.count()
    return lambda: start + timedelta(seconds=next(seconds))


def wait_until(cond, timeout: float = 15.0) -> None:
    """Koşul sağlanana dek bekler (süreye değil olaya bağlı; zaman aşımı yalnız asılı kalmaya karşı)."""
    deadline = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < deadline, "koşul zamanında sağlanmadı"
        time.sleep(0.01)


class SlowMux:
    """Uzun dersin ses birleştirmesini taklit eder: kaydedicinin birleştirme komutu (subprocess.run, -shortest'lı
    ffmpeg mux) test release() diyene dek bekler. entered: kapanış birleştirmeye vardı. Duvar saatine değil olaya
    bağlı. Diğer ffmpeg çağrıları (süre ölçümü) beklemeden geçer, calls'a sayılmaz."""

    def __init__(self, monkeypatch):
        self.entered, self._go = threading.Event(), threading.Event()
        self.calls = 0
        real_run = subprocess.run

        def run(args, *a, **k):
            if "-shortest" not in args:
                return real_run(args, *a, **k)
            self.calls += 1
            self.entered.set()
            assert self._go.wait(30), "test birleştirmeyi bırakmadı"
            return real_run(args, *a, **k)
        monkeypatch.setattr(subprocess, "run", run)

    def release(self) -> None:
        self._go.set()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_second_start_is_refused_while_first_recording_is_still_finalizing(tmp_path, monkeypatch):
    """Durdurma (ffmpeg kapanışı + ses birleştirme) uzun derste onlarca saniye sürer. Eskiden kaydedici bu sürede
    'kayıt yok' diyordu: ikinci start() kabul ediliyor, kapanmakta olan ilk kayıt yeni kaydın yollarını ve hata
    alanlarını devralıyordu (ilk ders hiç birleşmiyordu). Şimdi start() reddeder; ilk kayıt kendi dosyalarıyla
    biter, sonraki kayıt temiz bir oturumla başlar."""
    mux = SlowMux(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rect = RecordRect(0, 0, 160, 120)
    rec.start(rect)
    first = rec.last_path
    wait_until(lambda: rec.frames_written >= 10)
    stopped: list = []
    stopper = threading.Thread(target=lambda: stopped.append(rec.stop()), daemon=True)
    stopper.start()
    try:
        assert mux.entered.wait(20)                           # ilk kayıt birleştiriliyor: kapanış sürüyor
        assert not rec.is_recording
        with pytest.raises(RecorderError, match="Önceki kayıt hâlâ kaydediliyor"):
            rec.start(rect)
        assert rec.last_path == first                         # reddedilen start() hiçbir alana dokunmadı
    finally:
        mux.release()
        stopper.join(30)
        if rec.is_recording:                                  # (düzeltmesiz kodda ikinci kayıt açık kalmasın)
            rec.stop()
    assert stopped == [first]                                 # kapanış kendi kaydının yolunu döndürür
    assert first.exists() and rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
    assert _stream_seconds(find_ffmpeg(), first, "-vn") > 0.3  # kendi WAV'ıyla birleşti: dosyada ses var
    assert not list(tmp_path.glob("*.video.mp4")) and not list(tmp_path.glob("*.wav"))   # ara dosyalar silindi
    rec.start(rect)                                           # kapanış bitti: yeni kayıt temiz oturumla
    second = rec.last_path
    assert second != first and rec.audio_result is None and rec.error is None and rec.audio_error is None
    wait_until(lambda: rec.frames_written >= 5)
    assert rec.stop() == second and second.exists() and first.exists()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_recorder_state_goes_idle_recording_finalizing_idle(tmp_path, monkeypatch):
    """Kapanış (FINALIZING) ayrı bir durumdur; arayüz is_recording'e değil state'e bakar. Kayıt sürerken ikinci
    start() de reddedilir. Kapanış sürerken gelen ikinci stop() (pencere kapatma + arka plan işçisi) kapanışı bir
    daha yapmaz, onun bitmesini bekleyip aynı dosyayı döndürür."""
    from matematigin_mantigi.core.recorder import RecorderState
    mux = SlowMux(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rect = RecordRect(0, 0, 160, 120)
    assert rec.state is RecorderState.IDLE and rec.last_path is None and rec.stop() is None
    rec.start(rect)
    first = rec.last_path
    assert rec.state is RecorderState.RECORDING and rec.is_recording
    with pytest.raises(RecorderError, match="Kayıt zaten sürüyor"):
        rec.start(rect)
    assert rec.state is RecorderState.RECORDING and rec.last_path == first
    wait_until(lambda: rec.frames_written >= 5)
    results: list = []
    stoppers = [threading.Thread(target=lambda: results.append(rec.stop()), daemon=True) for _ in range(2)]
    stoppers[0].start()
    try:
        assert mux.entered.wait(20)
        assert rec.state is RecorderState.FINALIZING and not rec.is_recording and rec.elapsed_seconds == 0
        stoppers[1].start()
        stoppers[1].join(0.3)
        assert stoppers[1].is_alive()                         # ikinci stop() kapanışın bitmesini bekliyor
    finally:
        mux.release()
        for t in stoppers:
            t.join(30)
    assert results == [first, first] and mux.calls == 1       # birleştirme bir kez koştu
    assert rec.state is RecorderState.IDLE and first.exists()


def test_start_failure_leaves_recorder_idle_with_a_clear_error(tmp_path):
    """Kayıt klasörü açılamazsa (disk dolu, izin yok, macOS'ta Belgeler izni) ham OSError arayüze kaçıp uygulamayı
    düşürmesin: anlamlı RecorderError, kaydedici IDLE kalır, mikrofon hiç açılmaz. ffmpeg açılamazsa açılmış
    mikrofon kapatılır. İkisinde de kaydedici takılı kalmaz: sonraki deneme aynı gerçek hatayı verir."""
    from matematigin_mantigi.core.recorder import RecorderState
    mics: list = []

    class SpyMic(FakeAudioCapture):
        def __init__(self, device):
            super().__init__(device)
            self.stopped = False
            mics.append(self)

        def stop(self):
            self.stopped = True
            return super().stop()
    blocker = tmp_path / "dosya"
    blocker.write_text("klasör değil")
    rect = RecordRect(0, 0, 64, 48)
    rec = MssFfmpegRecorder(lambda: blocker / "oturum", grabber=synthetic_grabber, ffmpeg_exe="ffmpeg",
                            audio_device="Sahte Mikrofon", audio_factory=SpyMic)
    for _ in range(2):
        with pytest.raises(RecorderError, match="Kayıt klasörü oluşturulamadı"):
            rec.start(rect)
        assert rec.state is RecorderState.IDLE and not rec.is_recording and rec.last_path is None
    assert mics == []
    rec = MssFfmpegRecorder(lambda: tmp_path / "oturum", grabber=synthetic_grabber, ffmpeg_exe=str(tmp_path / "yok"),
                            audio_device="Sahte Mikrofon", audio_factory=SpyMic)
    with pytest.raises(RecorderError, match="ffmpeg başlatılamadı"):
        rec.start(rect)
    assert rec.state is RecorderState.IDLE and not rec.is_recording
    assert len(mics) == 1 and mics[0].stopped                 # açılan mikrofon kapatıldı


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_exception_while_finalizing_still_returns_recorder_to_idle(tmp_path, monkeypatch):
    """Kapanışın bir adımı patlarsa (ör. Windows'ta kullanımdaki dosyanın yeniden adlandırılması) durum FINALIZING'de
    takılı kalmamalı: yoksa uygulama yeniden açılana dek hiç kayıt başlatılamaz ('Önceki kayıt hâlâ kaydediliyor')."""
    from matematigin_mantigi.core.recorder import RecorderState

    class Broken:
        def __init__(self, device): pass
        def start(self, path): raise RuntimeError("aygıt yok")
    real_replace = Path.replace

    def busy(self, target):
        if self.name.endswith(".video.mp4"):
            raise PermissionError(13, "dosya kullanımda", str(self))
        return real_replace(self, target)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Yok", audio_factory=Broken, clock=stepping_clock())
    rect = RecordRect(0, 0, 160, 120)
    rec.start(rect)
    wait_until(lambda: rec.frames_written >= 3)
    monkeypatch.setattr(Path, "replace", busy)
    with pytest.raises(PermissionError):
        rec.stop()                                            # mikrofonsuz kayıt: .video.mp4 -> .mp4 adlandırması
    assert rec.state is RecorderState.IDLE and not rec.is_recording
    monkeypatch.undo()
    rec.start(rect)                                           # takılı kalmadı: yeni kayıt başlar
    assert rec.state is RecorderState.RECORDING
    wait_until(lambda: rec.frames_written >= 3)
    assert rec.stop().exists() and rec.state is RecorderState.IDLE


# --- #1: birleştirme videoyu asla kısaltmaz (denetim rec#1, e2e#1; kıdemli incelemenin Critical 1'i) ---------

MIC_CUT = re.compile(r"Mikrofon kayıt sırasında kesildi \(0:0[01]\. dakikadan sonra ses yok\)")


def _raw_files(path: Path) -> tuple[Path, Path]:
    """Son dosyanın ara dosyaları: kayit_<saat>.video.mp4 (ham video) ve kayit_<saat>.wav (ses)."""
    return path.with_name(path.stem + ".video.mp4"), path.with_suffix(".wav")


def _record_with_real_audio_capture(tmp_path, monkeypatch, blocks: int, seconds: float, fps: int = 20):
    """Gerçek AudioCapture (yalnız sounddevice sahte, `blocks` x 20 ms ses verip susar) + gerçek ffmpeg ile kayıt.
    Video uzunluğu yazılan kare sayısıyla beklenir (olay); duvar saatine bağlı eşik yok. Dönüş: (kaydedici, yol)."""
    from tests.test_audio_capture import FakeSoundDevice
    sd = FakeSoundDevice(blocks)
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=fps, grabber=synthetic_grabber, out_height=0,
                            audio_device="USB Mikrofon", clock=stepping_clock())        # varsayılan: AudioCapture
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= seconds * fps and sd.fed.is_set())
    return rec, rec.stop()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_microphone_that_goes_quiet_mid_lesson_does_not_cut_the_video(tmp_path, monkeypatch):
    """Mikrofon ders ortasında çekilince (USB kablosu, AirPods) PortAudio akışı açık kalır ama geri çağrı gelmez,
    stop() normal döner. -shortest birleşik dosyayı sesin bittiği yerde kesiyordu: 5 sn'lik kayıt ~1,4 sn çıkıyor,
    tam uzunluktaki ara video siliniyor, hiçbir hata bildirilmiyordu. Şimdi eksik ses sessizlikle dolar, dosya
    videonun uzunluğunda biter, ara dosyalar silinir ve öğretmen sesin nereden sonra olmadığını görür."""
    rec, path = _record_with_real_audio_capture(tmp_path, monkeypatch, blocks=75, seconds=5.0)   # 1,5 sn ses
    exe, video_s = find_ffmpeg(), rec.frames_written / 20
    v, a = _stream_seconds(exe, path, "-an"), _stream_seconds(exe, path, "-vn")
    assert abs(v - video_s) < 0.15 and abs(a - v) < 0.15, (v, a, video_s)         # düzeltmesiz: v ≈ a ≈ 1,4 sn
    assert rec.audio_result.samples == 75 * 960 and rec.error is None, rec.error
    assert MIC_CUT.fullmatch(rec.audio_error or ""), rec.audio_error
    assert not list(tmp_path.glob("*.video.mp4")) and not list(tmp_path.glob("*.wav"))    # dosya tam: silindi


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_wav_writer_that_dies_mid_lesson_is_reported_and_does_not_cut_the_video(tmp_path, monkeypatch):
    """Denetimin ikinci kipi: mikrofon canlı ama WAV yazıcı iş parçacığı 1,5 sn sonra OSError'la ölüyor (disk
    hatası). Hata yalnız iş parçacığından stderr'e gidiyor, kaydediciye ulaşmıyor, dosya ~1,4 sn'ye kesiliyordu.
    Şimdi sebep audio_error'da (kayıt bitince uyarı kutusunda), video tam uzunlukta kalır."""
    from tests.test_audio_capture import disk_full_after
    leaked = []
    monkeypatch.setattr(threading, "excepthook", lambda args: leaked.append(args.exc_value))
    disk_full_after(monkeypatch, 75 * 960 * 2)                  # 1,5 sn'lik ses yazılır, sonra disk dolu
    rec, path = _record_with_real_audio_capture(tmp_path, monkeypatch, blocks=250, seconds=5.0)  # mikrofon canlı
    exe, video_s = find_ffmpeg(), rec.frames_written / 20
    v, a = _stream_seconds(exe, path, "-an"), _stream_seconds(exe, path, "-vn")
    assert abs(v - video_s) < 0.15 and abs(a - v) < 0.15, (v, a, video_s)
    assert leaked == [] and rec.error is None and rec.audio_result.samples == 75 * 960, (leaked, rec.error)
    assert re.fullmatch(r"Ses dosyası yazılamadı: \[Errno 28\] No space left on device "
                        r"\(0:0[01]\. dakikadan sonra ses yok\)", rec.audio_error or ""), rec.audio_error


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_mux_that_comes_out_shorter_than_the_video_keeps_the_raw_files(tmp_path, monkeypatch):
    """Güvenlik ağı: birleşik dosya (başka bir ffmpeg sürümünün davranışı, bozuk giriş...) videodan kısa çıkarsa
    ara .video.mp4 ve .wav SİLİNMEZ, hata öğretmene ikisinin yerini söyler. Kısa çıktıyı gerçek ffmpeg üretir:
    komuttan ses dolgusu (apad) çıkarılınca -shortest dosyayı bugünkü kusurdaki gibi sesin sonunda keser."""
    from matematigin_mantigi.core import recorder as r
    real_mux_args = r.mux_args

    def unpadded(*a, **k):
        args = real_mux_args(*a, **k)
        i = args.index("-af") + 1
        args[i] = ",".join(f for f in args[i].split(",") if not f.startswith("apad"))
        return args

    class QuietMic(FakeAudioCapture):
        limit = 0.3                                             # 0,3 sn ses, sonra mikrofon kesildi
    monkeypatch.setattr(r, "mux_args", unpadded)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=QuietMic, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 40)               # 2 sn video
    path = rec.stop()
    video, wav = _raw_files(path)
    assert path.exists() and video.exists() and wav.exists()    # hiçbir şey silinmedi
    assert rec.error and "videodan kısa çıktı" in rec.error, rec.error
    assert str(path) in rec.error and str(video) in rec.error and str(wav) in rec.error   # öğretmen yerlerini görür
    exe = find_ffmpeg()
    assert _stream_seconds(exe, path, "-an") < 1.0 <= _stream_seconds(exe, video, "-an")   # tam video ara dosyada


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_microphone_that_gives_no_samples_at_all_keeps_the_full_video(tmp_path):
    """Mikrofon açıldı ama hiç örnek gelmedi (samples=0, ör. macOS izni ya da sürücü): birleştirme denenmez, video
    tam uzunlukta tek başına son dosya olur ve öğretmen sesin olmadığını görür."""
    class SilentMic(FakeAudioCapture):
        limit = 0.0
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=SilentMic, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 20)
    path = rec.stop()
    assert rec.error is None and rec.audio_error == "Ses kaydedilemedi (örnek yok)", (rec.error, rec.audio_error)
    assert abs(_stream_seconds(find_ffmpeg(), path, "-an") - rec.frames_written / 20) < 0.15
    assert not list(tmp_path.glob("*.video.mp4"))


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
@pytest.mark.parametrize("unmeasurable", ["ara video", "birleşik dosya"])
def test_unmeasurable_duration_keeps_the_raw_files(tmp_path, monkeypatch, unmeasurable):
    """Süre ölçülemezse (ffmpeg başlığı okuyamadı) birleşik dosyanın tam olduğu bilinmez: güvenli taraf, ara
    dosyalar silinmez ve öğretmen yerlerini öğrenir. Ara video ölçülemezse dolgu duvar süresine göre yapılır."""
    from matematigin_mantigi.core import recorder as r
    real = r.media_duration

    def media_duration(exe, path, **k):
        if path.name.endswith(".video.mp4") == (unmeasurable == "ara video"):
            return None
        return real(exe, path, **k)
    monkeypatch.setattr(r, "media_duration", media_duration)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 10)
    path = rec.stop()
    video, wav = _raw_files(path)
    assert path.exists() and video.exists() and wav.exists()
    assert rec.error and "ölçülemedi" in rec.error and str(video) in rec.error and str(wav) in rec.error, rec.error
    exe = find_ffmpeg()
    v, a = _stream_seconds(exe, path, "-an"), _stream_seconds(exe, path, "-vn")
    assert abs(v - rec.frames_written / 20) < 0.15 and abs(a - v) < 0.15, (v, a)   # birleştirme yine tam


def test_mux_args_pads_missing_audio_with_silence_up_to_the_video(tmp_path):
    """Mikrofon kesilince eksik ses sessizlikle dolar (apad), -shortest dosyayı videonun sonunda bitirir. Dolgu
    sınırlı (whole_dur = video + 1 sn): sınırsız apad + -shortest + -c:v copy ffmpeg 7.0.2'de hiç bitmiyor (ses
    kodlayıcısı sonsuz sessizlik üretirken çıktıya tek paket yazılmıyor). apad zincirin sonunda: hız düzeltmesi
    (asetrate/aresample) ve fade-in'den sonra; -ss / -itsoffset girişte kalır, hizaya dokunmaz."""
    v, a, out = tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4"
    for offset, rate in ((0.25, None), (0.0, None), (-0.1, None), (0.0, 48003)):
        args = mux_args("ffmpeg", v, a, out, offset, asetrate=rate, video_s=125.5)
        af = args[args.index("-af") + 1].split(",")
        assert af[-2:] == ["afade=t=in:st=0:d=0.01", "apad=whole_dur=126.500"], af
        assert "-shortest" in args and args[-1] == str(out) and args.index("-i") < args.index("-af")
    fixed = mux_args("ffmpeg", v, a, out, 0.0, asetrate=48003, video_s=10)
    assert fixed[fixed.index("-af") + 1] == \
        "asetrate=48003,aresample=48000,afade=t=in:st=0:d=0.01,apad=whole_dur=11.000"


def _write_test_media(exe, video: Path, wav: Path, video_s: float, audio_s: float) -> None:
    subprocess.run([exe, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc=s=160x120:r=20:d={video_s}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video)], check=True, capture_output=True)
    n = int(audio_s * 48000)
    pcm = (np.sin(2 * np.pi * 1000 * np.arange(n) / 48000) * 12000).astype(np.int16)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(pcm.tobytes())


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
@pytest.mark.parametrize("offset, rate", [(0.25, None), (-0.1, None), (0.0, 48480), (0.8, None)])
def test_padded_mux_ends_with_the_video_on_every_alignment_path(tmp_path, offset, rate):
    """Gerçek ffmpeg: 3 sn video + 0,5 sn ses. -ss (ses önce başladı), -itsoffset (geç başladı) ve asetrate
    yollarında çıktı videonun uzunluğunda, ses de sona dek (sessizlikle) sürer; komut zamanında biter. 0,8: sesin
    tamamı videodan önce (-ss WAV'ın sonunu aşar); ses izi yine tam uzunlukta sessizlik olur, birleştirme düşmez."""
    exe = find_ffmpeg()
    video, wav, out = tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4"
    _write_test_media(exe, video, wav, 3.0, 0.5)
    res = subprocess.run(mux_args(exe, video, wav, out, offset, asetrate=rate, video_s=3.0),
                         capture_output=True, timeout=60)
    assert res.returncode == 0, res.stderr[-300:]
    v, a = _stream_seconds(exe, out, "-an"), _stream_seconds(exe, out, "-vn")
    assert abs(v - 3.0) < 0.06 and abs(a - 3.0) < 0.1, (v, a)


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_media_duration_reads_the_container_header(tmp_path):
    """Süre ffmpeg'in başlık dökümünden okunur (ffprobe paketle gelmiyor). MP4'te yalnız moov kutusu okunur, video
    çözülmez: 60 dakikalık 60 kare/sn dosyada ~0,1 sn. Okunamayan dosyada, yok olan dosyada, ffmpeg yokken None."""
    from matematigin_mantigi.core.recorder import media_duration
    exe = find_ffmpeg()
    video, wav = tmp_path / "v.mp4", tmp_path / "a.wav"
    _write_test_media(exe, video, wav, 2.5, 1.25)
    assert media_duration(exe, video) == pytest.approx(2.5, abs=0.02)
    assert media_duration(exe, wav) == pytest.approx(1.25, abs=0.02)
    tagged = tmp_path / "etiketli.mp4"                          # etiket değerindeki "Duration:" sayılmaz
    subprocess.run([exe, "-y", "-hide_banner", "-loglevel", "error", "-i", str(video), "-c", "copy", "-metadata",
                    "comment=Duration: 09:09:09.00", str(tagged)], check=True, capture_output=True)
    assert media_duration(exe, tagged) == pytest.approx(2.5, abs=0.02)
    junk = tmp_path / "bozuk.mp4"
    junk.write_bytes(b"\0" * 4096)
    assert media_duration(exe, junk) is None and media_duration(exe, tmp_path / "yok.mp4") is None
    assert media_duration(str(tmp_path / "ffmpeg-yok"), video) is None


def test_media_duration_names_the_wav_demuxer_for_wav_files(tmp_path, monkeypatch):
    """imageio-ffmpeg 0.8.0'ın ffmpeg 9.0.2'si düz WAV'ı biçim tahminiyle tanımıyor (mpegts sanıyor, süre yok): .wav
    yolunda giriş -f wav ile açılır. MP4 tahmine açık kalır. (Gerçek ffmpeg'li başlık testi en yeni sürümler
    venv'inde bu yüzden kırmızıydı.)"""
    from matematigin_mantigi.core.recorder import media_duration
    seen = []

    def run(args, **k):
        seen.append(args)
        return subprocess.CompletedProcess(args, 1, b"", b"  Duration: 00:00:01.25, start: 0.000000\n")
    monkeypatch.setattr(subprocess, "run", run)
    wav, mp4 = tmp_path / "kayit.WAV", tmp_path / "kayit.mp4"
    assert media_duration("ffmpeg", wav) == pytest.approx(1.25) and media_duration("ffmpeg", mp4) == pytest.approx(1.25)
    wav_args, mp4_args = seen
    i = wav_args.index(str(wav))
    assert wav_args[i - 3:i] == ["-f", "wav", "-i"], wav_args
    assert "-f" not in mp4_args, mp4_args


def test_every_ffmpeg_call_hides_the_console_window_on_windows():
    """#10: paketli Windows uygulaması konsolsuz; her ffmpeg alt süreci (kayıt, birleştirme, süre ölçümü, kodlayıcı
    denemesi, kamera listesi) kendi konsol penceresini yakıp söndürüyordu. Tek yardımcı no_window(): Windows'ta
    CREATE_NO_WINDOW, başka sistemde boş. recorder ve cameras modüllerindeki her subprocess çağrısı onu kullanır;
    eklenen yeni bir çağrı da bu testi geçmek için onu kullanmak zorunda."""
    import ast
    import inspect
    from matematigin_mantigi.core import cameras, recorder
    from matematigin_mantigi.core.recorder import no_window
    assert no_window("win32") == {"creationflags": 0x08000000}                # subprocess.CREATE_NO_WINDOW
    assert no_window("darwin") == {} and no_window("linux") == {}
    assert no_window() == (no_window("win32") if sys.platform == "win32" else {})
    found = []
    for mod in (recorder, cameras):
        for node in ast.walk(ast.parse(inspect.getsource(mod))):
            func = node.func if isinstance(node, ast.Call) else None
            if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "subprocess"
                    and func.attr in {"run", "Popen", "call", "check_call", "check_output"}):
                hidden = any(k.arg is None and isinstance(k.value, ast.Call)
                             and getattr(k.value.func, "id", None) == "no_window" for k in node.keywords)
                found.append((mod.__name__.rsplit(".", 1)[-1], node.lineno, hidden))
    assert len(found) >= 5, found               # kodlayıcı denemesi, süre ölçümü, kayıt, birleştirme, kamera listesi
    assert all(hidden for *_, hidden in found), [f for f in found if not f[2]]


def test_clock_text_and_mic_cut_text():
    """Sesin kesildiği an okunur 'dakika:saniye' (toplam dakika). Uyarı yalnız ses videodan 2 sn'den fazla erken
    bitince: sürücü tamponu ve durdurma sırası (ses videodan sonra kapanır) yanlış uyarı vermesin."""
    from matematigin_mantigi.core.recorder import clock_text, mic_cut_text
    assert [clock_text(t) for t in (0, 1.4, 59.99, 61, 1215.7, 3600, 4530.2, -3)] == \
        ["0:00", "0:01", "0:59", "1:01", "20:15", "60:00", "75:30", "0:00"]
    assert mic_cut_text(3600.0, 1215.7) == "20:15. dakikadan sonra ses yok"     # 60 dk ders, 20. dakikada kesildi
    assert mic_cut_text(300.0, 297.9) == "4:57. dakikadan sonra ses yok"
    assert mic_cut_text(300.0, 298.5) is None and mic_cut_text(300.0, 300.4) is None
    assert mic_cut_text(1.5, 0.0) is None                                         # 2 sn'den kısa kayıt


def test_audio_end_in_video_follows_the_alignment_and_rate_fix():
    """Sesin birleşik dosyada bittiği an: ses önce başladıysa baştaki fark atılır (-ss), geç başladıysa ses o kadar
    geciktirilir (-itsoffset); hız düzeltmesi (asetrate) süreyi ölçülen gerçek hıza göre değiştirir."""
    from matematigin_mantigi.core.audio_capture import AudioResult
    from matematigin_mantigi.core.recorder import audio_end_in_video
    ten = AudioResult(Path("a.wav"), 48000, 1, 480000, 0.0, 10.0)
    assert audio_end_in_video(ten, 0.25) == pytest.approx(9.75)
    assert audio_end_in_video(ten, -0.1) == pytest.approx(10.1)
    assert audio_end_in_video(ten, 0.0, asetrate=48480) == pytest.approx(480000 / 48480)


# --- kapanış takılmaz, hatası görünür (bağımsız inceleme F1, F3, F4) ----------------------------------------

def fake_ffmpeg(tmp_path: Path, recording: str, other: str = "exit 1") -> Path:
    """ffmpeg yerine geçen kabuk betiği (yalnız posix; yeni testler python_ffmpeg kullanır): kayıt komutunda (giriş
    pipe:0) `recording`, diğer çağrılarda (birleştirme, süre ölçümü) `other` koşar. Kayıt sürecinin PID'i
    ffmpeg.pid'e yazılır (exec ile PID değişmez): test takılı kalan süreci kendisi öldürebilsin."""
    exe = tmp_path / "sahte-ffmpeg"
    exe.write_text(f"#!/bin/sh\ncase \"$*\" in\n  *pipe:0*) echo $$ > '{tmp_path / 'ffmpeg.pid'}'; {recording};;\n"
                   f"  *) {other};;\nesac\n")
    exe.chmod(0o755)
    return exe


def python_ffmpeg(monkeypatch, tmp_path: Path, body: str) -> list:
    """Kayıt ffmpeg'i (giriş pipe:0) yerine Python betiği: `sys.executable betik <ffmpeg argümanları>`; kabuk betiği
    (fake_ffmpeg) yalnız posix'te koşar, bu Windows CI'da da. Betikte `out` çıktı dosyasının yolu, `stdin` ham
    karelerin borusu. Diğer çağrılar (süre ölçümü, birleştirme) değişmez. Dönüş: açılan kayıt süreçleri (Popen; test
    takılanı kendisi öldürür, toplandığını returncode'dan görür; kill() Windows'ta da çalışır)."""
    import textwrap
    script = tmp_path / "sahte_ffmpeg.py"
    script.write_text("import os, sys, time\nout = sys.argv[-1]\nstdin = sys.stdin.buffer\n" + textwrap.dedent(body),
                      encoding="utf-8")
    procs: list = []
    real = subprocess.Popen

    def popen(args, *a, **k):
        if isinstance(args, list) and "pipe:0" in args:
            p = real([sys.executable, str(script), *args[1:]], *a, **k)
            procs.append(p)
            return p
        return real(args, *a, **k)
    monkeypatch.setattr(subprocess, "Popen", popen)
    return procs


def recorded_runs(monkeypatch) -> list:
    """subprocess.run çağrılarının komutları (süre ölçümü, birleştirme); çağrılar yine gerçekten koşar."""
    calls: list = []
    real = subprocess.run

    def run(args, *a, **k):
        calls.append(args)
        return real(args, *a, **k)
    monkeypatch.setattr(subprocess, "run", run)
    return calls


def _outcome(fn):
    """fn()'in sonucu ('dönüş', değer) ya da ('istisna', hata); iş parçacığından toplanır."""
    try:
        return "dönüş", fn()
    except Exception as err:  # noqa: BLE001
        return "istisna", err


def waiting_stop_signal(monkeypatch) -> threading.Event:
    """Kapanışı bekleyen ikinci stop() bekleme yoluna girince kurulan olay (bekleme sınırını hesapladığı an): testler
    kapanışı ancak ondan sonra bırakır, ikinci stop() geç kalıp kapanış bitmiş kaydı görmesin (yarış yok)."""
    from matematigin_mantigi.core import recorder as r
    entered = threading.Event()
    real = r._close_limit
    monkeypatch.setattr(r, "_close_limit", lambda duration: (entered.set(), real(duration))[1])
    return entered


def writer_blocked_in_pipe_write(rec) -> bool:
    """Kaydın yazıcı iş parçacığı ffmpeg borusuna yazarken mi bekliyor (Python yığınının tepesi _put_frame'deki
    stdin.write)? Durdurmadan önce bunu beklemek, yazıcı ilk kareyi yazmadan durdurulma yarışını önler."""
    import linecache
    s = rec._session
    th = s.thread if s is not None else None
    frame = sys._current_frames().get(th.ident) if th is not None and th.ident is not None else None
    return (frame is not None and frame.f_code.co_name == "_put_frame"
            and "stdin.write" in linecache.getline(frame.f_code.co_filename, frame.f_lineno))


# python_ffmpeg betiği: kodlayıcı açılamadı (disk dolu), ffmpeg sebebi yazıp başta çıkar
ENCODER_FAILS = "sys.stderr.write('Error while opening encoder: No space left on device\\n')\nsys.exit(1)\n"


class NoMic:
    """Açılmayan mikrofon: kayıt yalnız video (kapanışta .video.mp4 -> .mp4 adlandırması)."""
    def __init__(self, device): pass
    def start(self, path): raise RuntimeError("aygıt yok")


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_exception_while_finalizing_is_recorded_and_the_waiting_stop_sees_it(tmp_path, monkeypatch):
    """Kapanış patlayınca (Windows'ta kullanımdaki dosyanın adlandırılması) istisna yalnız kapatan stop()'a gidiyordu:
    error boş kalıyor, kapanışı bekleyen ikinci stop() (pencere kapatma) var olmayan dosyanın yolunu istisnasız
    döndürüyordu. Şimdi sebep oturuma yazılır ('Kayıt kapatılamadı: …' ve kayıt klasörü), kapatan stop() istisnayı
    yine fırlatır, bekleyen stop() aynı hatayı RecorderError ile görür."""
    real_replace = Path.replace
    entered, go = threading.Event(), threading.Event()

    def busy(self, target):
        if self.name.endswith(".video.mp4"):
            entered.set()
            assert go.wait(20)                                        # ikinci stop() FINALIZING'i görsün
            raise PermissionError(13, "dosya kullanımda", str(self))
        return real_replace(self, target)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Yok", audio_factory=NoMic, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 3)
    monkeypatch.setattr(Path, "replace", busy)
    waiter_in = waiting_stop_signal(monkeypatch)
    outcomes: list = [None, None]
    stoppers = [threading.Thread(target=lambda i=i: outcomes.__setitem__(i, _outcome(rec.stop)), daemon=True)
                for i in range(2)]
    stoppers[0].start()
    try:
        assert entered.wait(20)
        stoppers[1].start()
        assert waiter_in.wait(20)                                     # ikinci stop() kapanışın bitmesini bekliyor
    finally:
        go.set()
        for t in stoppers:
            t.join(20)
    first, second = outcomes
    assert first[0] == "istisna" and isinstance(first[1], PermissionError), first
    assert rec.error is not None and rec.error.startswith(
        "Kayıt kapatılamadı: PermissionError: [Errno 13] dosya kullanımda"), rec.error
    assert f"Kayıt klasörü: {tmp_path / 'rec'}" in rec.error, rec.error
    assert second[0] == "istisna" and isinstance(second[1], RecorderError) and str(second[1]) == rec.error, second


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_waiting_stop_gives_up_when_the_closing_exceeds_its_limit(tmp_path, monkeypatch):
    """Kapanışı bekleyen ikinci stop() sınırsız beklemez: kapanışın kendi sınırları toplamı (_close_limit) dolunca
    RecorderError ile döner. Kapanışın kendisi sürer ve kaydı bitirir."""
    from matematigin_mantigi.core import recorder as r
    from matematigin_mantigi.core.recorder import RecorderState
    mux = SlowMux(monkeypatch)
    monkeypatch.setattr(r, "_close_limit", lambda duration: 0.2)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    outcome: list = []
    closer = threading.Thread(target=lambda: outcome.append(_outcome(rec.stop)), daemon=True)
    closer.start()
    try:
        assert mux.entered.wait(20)                                     # kapanış birleştirmede bekliyor
        with pytest.raises(RecorderError, match="kapanışı .* bitmedi"):
            rec.stop()
        assert rec.state is RecorderState.FINALIZING                    # bekleyen vazgeçti, kapanış sürüyor
    finally:
        mux.release()
        closer.join(20)
    assert outcome == [("dönüş", rec.last_path)] and rec.state is RecorderState.IDLE and rec.last_path.exists()


def test_ffmpeg_that_dies_at_start_keeps_the_wav_and_says_where_it_is(tmp_path, monkeypatch):
    """Mikrofonlu kayıtta ffmpeg başta ölürse (kodlayıcı açılamadı, disk dolu) ara .video.mp4 hiç oluşmaz. _mux'taki
    korumasız video.replace FileNotFoundError fırlatıyordu: arayüz ham Errno metnini gösteriyor, sesin durduğunu
    söylemiyordu. Şimdi stop() istisnasız döner; hata ffmpeg'in sebebini ve sesin yerini söyler, WAV silinmez."""
    python_ffmpeg(monkeypatch, tmp_path, ENCODER_FAILS)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            ffmpeg_exe="sahte-ffmpeg", audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture,
                            clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.failed)                                    # yazıcı kırık boruyu gördü
    path = rec.stop()
    wav = path.with_suffix(".wav")
    assert wav.exists() and not path.exists() and not path.with_name(path.stem + ".video.mp4").exists()
    assert "No space left on device" in rec.error and "Video dosyası oluşmadı" in rec.error, rec.error
    assert str(wav) in rec.error, rec.error


def capture_logged(monkeypatch) -> list:
    """crash_log.log_handled çağrıları (istisna, yer): hatalar.log'a giden yakalanmış hatalar."""
    from matematigin_mantigi.core import crash_log
    logged: list = []
    monkeypatch.setattr(crash_log, "log_handled", lambda exc, where="": logged.append((exc, where)))
    return logged


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_unexpected_failure_after_ffmpeg_started_leaks_nothing(tmp_path, monkeypatch):
    """Popen'dan sonraki adım beklenmedik biçimde düşerse (yazıcı iş parçacığı açılamadı: "can't start new thread")
    açılan ffmpeg süreci ve mikrofon her denemede sızıyor, ham RuntimeError arayüze kaçıyordu. Şimdi açılan her şey
    kapatılır (ffmpeg öldürülüp toplanır, günlük dosyası ve mikrofon kapanır), anlamlı RecorderError fırlar, kaydedici
    IDLE kalır; sorun geçince sonraki kayıt başlar."""
    from matematigin_mantigi.core.recorder import RecorderState
    mics: list = []

    class SpyMic(FakeAudioCapture):
        def __init__(self, device):
            super().__init__(device)
            self.stopped = False
            mics.append(self)

        def stop(self):
            self.stopped = True
            return super().stop()
    procs: list = []
    real_popen = subprocess.Popen

    class SpyPopen(real_popen):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            procs.append(self)
    real_start = threading.Thread.start

    def start(self):
        if getattr(getattr(self, "_target", None), "__name__", "") == "_loop":    # kaydın yazıcı iş parçacığı
            raise RuntimeError("can't start new thread")
        return real_start(self)
    monkeypatch.setattr(subprocess, "Popen", SpyPopen)
    monkeypatch.setattr(threading.Thread, "start", start)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=SpyMic, clock=stepping_clock())
    rect = RecordRect(0, 0, 160, 120)
    with pytest.raises(RecorderError, match="Kayıt başlatılamadı: RuntimeError: can't start new thread"):
        rec.start(rect)
    assert rec.state is RecorderState.IDLE and rec.last_path is None
    assert len(procs) == 1 and procs[0].poll() is not None              # ffmpeg öldürüldü ve toplandı
    assert len(mics) == 1 and mics[0].stopped                          # mikrofon kapandı
    log = next((tmp_path / "rec").glob("kayit_*.log")).resolve()
    if Path("/proc/self/fd").is_dir():                                 # günlük dosyası açık kalmadı (Linux)
        assert all(Path(f"/proc/self/fd/{fd}").resolve() != log for fd in os.listdir("/proc/self/fd"))
    monkeypatch.setattr(threading.Thread, "start", real_start)
    rec.start(rect)                                                    # sorun geçti: kaydedici takılı değil
    wait_until(lambda: rec.frames_written >= 3)
    assert rec.stop().exists() and rec.error is None, rec.error



def test_each_recordings_result_gets_its_own_entry_in_the_error_log(tmp_path, monkeypatch):
    """hatalar.log aynı türden ve aynı kod yolundan gelen hatayı oturumda bir kez yazar, sonra yalnız 10., 100.
    tekrarı (çizim olayındaki hata diski doldurmasın). Kayıt sonuçları traceback'siz aynı türle yazıldığı için hepsi
    tek anahtara düşüyordu: oturumun ikinci kaydının hatası günlüğe hiç girmiyordu. Her kaydın sonucu kendi girdisini
    alır; aynı kaydın sonucu iki kez yazılmaz. (Gerçek CrashLog: log_handled'in traceback'siz yolu da sınanır.)"""
    from types import SimpleNamespace
    from matematigin_mantigi.core import crash_log
    log = crash_log.CrashLog(tmp_path / "hatalar.log")
    monkeypatch.setattr(crash_log, "_active", log)
    first = SimpleNamespace(final_path=tmp_path / "ders-1.mp4", error=None, audio_error="Mikrofon kesildi (00:12)",
                            video_warning=None)
    second = SimpleNamespace(final_path=tmp_path / "ders-2.mp4", error="ffmpeg hata kodu 1: disk dolu",
                             audio_error=None, video_warning=None)
    for s in (first, second, second):
        MssFfmpegRecorder._log_result(s)
    text = log.path.read_text(encoding="utf-8")
    assert "ders-1.mp4 · ses: Mikrofon kesildi (00:12)" in text
    assert "ders-2.mp4 · hata: ffmpeg hata kodu 1: disk dolu" in text, text
    assert text.count("ffmpeg hata kodu 1: disk dolu") == 1, text


def test_video_warning_reaches_the_recording_result_line(tmp_path, monkeypatch):
    """R1: görüntü kodlayıcısının uyarısı artık ses uyarısı alanında değil (video_warning); hatalar.log'daki kayıt
    sonucu satırı onu da taşır, kendi etiketiyle: öğretmen kutuyu okumadan kapatsa da sonradan görülür."""
    from types import SimpleNamespace
    logged = capture_logged(monkeypatch)
    lag = "Görüntü kodlayıcısı kayda yetişemedi: görüntü kayıt boyunca donarak ilerledi; video 8 sn erken bitiyor"
    only_video = SimpleNamespace(final_path=tmp_path / "ders-3.mp4", error=None, audio_error=None, video_warning=lag)
    both = SimpleNamespace(final_path=tmp_path / "ders-4.mp4", error=None, audio_error="Mikrofon kesildi (00:12)",
                           video_warning=lag)
    for s in (only_video, both):
        MssFfmpegRecorder._log_result(s)
    lines = [str(exc) for exc, where in logged if where == "kayıt sonucu"]
    assert lines == [f"ders-3.mp4 · görüntü: {lag}", f"ders-4.mp4 · ses: Mikrofon kesildi (00:12) · görüntü: {lag}"], \
        lines


def test_recording_errors_reach_the_error_log_as_one_line(tmp_path, monkeypatch):
    """Kaydın sonu hatayla bittiyse (error) ya da ses uyarısı varsa (audio_error) hatalar.log'a tek satır düşer:
    öğretmen 'Kayıt hatası' penceresini okumadan kapatsa da sonradan ne olduğu görülür."""
    logged = capture_logged(monkeypatch)
    python_ffmpeg(monkeypatch, tmp_path, ENCODER_FAILS)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            ffmpeg_exe="sahte-ffmpeg", audio_device="Yok", audio_factory=NoMic, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.failed)
    path = rec.stop()
    results = [(str(exc), where) for exc, where in logged if where == "kayıt sonucu"]
    assert len(results) == 1 and "\n" not in results[0][0], logged
    line = results[0][0]
    assert line.startswith(f"{path.name} · hata: ffmpeg kayıt sırasında durdu (0:0"), line
    assert "çıkış kodu 1)" in line and "ffmpeg çıktısı: Error while opening encoder" in line, line
    assert "ses: Mikrofon açılamadı: aygıt yok" in line, line


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_previous_recordings_errors_do_not_carry_over_to_the_next_one(tmp_path, monkeypatch):
    """Sonuç alanları kaydın kendi oturumunda: önceki kaydın hatası (error) ve ses uyarısı (audio_error) yeni kayda
    taşınmaz. Eskiden ortak alanlardı; temiz biten ikinci ders önceki dersin 'Kayıt hatası'yla bitebiliyordu."""
    mics = iter([NoMic, FakeAudioCapture])                              # 1. kayıtta mikrofon açılmaz, 2.'de açılır
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=lambda dev: next(mics)(dev),
                            clock=stepping_clock())
    rect = RecordRect(0, 0, 160, 120)
    real_replace = Path.replace

    def busy(self, target):
        if self.name.endswith(".video.mp4"):
            raise PermissionError(13, "dosya kullanımda", str(self))
        return real_replace(self, target)
    rec.start(rect)                                                     # 1. kayıt: ses yok, kapanış da patlıyor
    wait_until(lambda: rec.frames_written >= 3)
    monkeypatch.setattr(Path, "replace", busy)
    with pytest.raises(PermissionError):
        rec.stop()
    assert rec.error and rec.audio_error == "Mikrofon açılamadı: aygıt yok", (rec.error, rec.audio_error)
    monkeypatch.setattr(Path, "replace", real_replace)
    rec.start(rect)                                                     # 2. kayıt: temiz
    assert rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
    wait_until(lambda: rec.frames_written >= 3)
    path = rec.stop()
    assert path.exists() and rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
