"""Mikrofon yakalama: PortAudio (sounddevice) ile uygulama içinde, büyük kuyruk, WAV'a yazım.

Neden ffmpeg değil: ffmpeg'in avfoundation girişi tek bir ses tamponu tutar; video borusu süreci bir an
geciktirdiğinde o tampon düşer (cızırtı) ve düşen parçalar ses-video kaymasına birikir. Burada ses, CoreAudio /
WASAPI geri çağrısından saniyelerce yer olan bir kuyruğa alınır; ayrı bir iş parçacığı WAV'a yazar. İlk örneğin
zamanı (monotonic) ölçülür; kaydedici bunu videonun ilk karesiyle hizalayıp durdurunca tek geçişte birleştirir.
"""
from __future__ import annotations

import queue
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from matematigin_mantigi.core import crash_log


@dataclass
class AudioResult:
    path: Path
    samplerate: int
    channels: int
    samples: int
    first_sample_monotonic: float | None
    stopped_monotonic: float
    overflows: int = 0
    dropped_blocks: int = 0
    error: str | None = None          # WAV yazılamadı (disk dolu...): samples o ana dek yazılabilen ses
    last_sample_monotonic: float | None = None    # son bloğun sonu (ilk örnekle aynı zaman tabanı); bilinmiyorsa None

    @property
    def duration(self) -> float:
        return self.samples / self.samplerate if self.samplerate else 0.0

    @property
    def wall_duration(self) -> float:
        """İlk örnekten durdurmaya kadar geçen gerçek süre."""
        if self.first_sample_monotonic is None:
            return 0.0
        return max(0.0, self.stopped_monotonic - self.first_sample_monotonic)

    @property
    def heard_duration(self) -> float:
        """İlk örnekten son örneğe dek geçen gerçek süre: saat kayması bununla ölçülür. Mikrofon durdurmadan önce
        sustuysa durdurmaya dek geçen süre örnek sayısıyla karşılaştırılamaz (eksik ses kayma sanılır, O1). Son
        örneğin zamanı bilinmiyorsa wall_duration."""
        if self.first_sample_monotonic is None:
            return 0.0
        if self.last_sample_monotonic is None:
            return self.wall_duration
        return max(0.0, self.last_sample_monotonic - self.first_sample_monotonic)

    @property
    def tail_gap(self) -> float:
        """Son örnekten durdurmaya dek geçen süre. Mikrofon kesilince (kablo çekildi, AirPods koptu) CoreAudio'da akış
        açık kalır, geri çağrı gelmez: bu süre büyür. Kesilmeyen mikrofonda sürücü tamponu kadardır; bilinmiyorsa 0."""
        if self.last_sample_monotonic is None:
            return 0.0
        return max(0.0, self.stopped_monotonic - self.last_sample_monotonic)


def _reason(err: BaseException) -> str:
    """Hatanın kısa metni ('[Errno 28] No space left on device'); boşsa türün adı."""
    return str(err) or type(err).__name__


def _sd():
    import sounddevice as sd
    return sd


def _all_input_devices(sd) -> list[tuple[int, dict]]:
    """Girişi olan tüm (indeks, aygıt) çiftleri, host API'den bağımsız."""
    return [(i, d) for i, d in enumerate(sd.query_devices()) if int(d.get("max_input_channels", 0) or 0) > 0]


def _hostapi_rank(sd):
    """Host API tercih sırası (küçük = iyi): WASAPI < DirectSound < MME < WDM-KS/diğer.
    macOS'ta tek API (CoreAudio) vardır, hepsi eşit."""
    names = [h.get("name", "") for h in sd.query_hostapis()]

    def rank(hostapi_idx: int) -> int:
        n = names[hostapi_idx] if 0 <= hostapi_idx < len(names) else ""
        if "WASAPI" in n:
            return 0
        if "DirectSound" in n:
            return 1
        if "MME" in n:
            return 2
        if "Core" in n or "ALSA" in n or "JACK" in n:
            return 0          # macOS/Linux tek modern API: en iyi
        return 3
    return rank


def list_input_devices() -> list[str]:
    """Mikrofon adları (ayarlar listesi için). Girişi olan en iyi host API'nin aygıtları; boşsa bir alt API.
    Böylece adlar tekrarlanmaz ve tam gelir; aygıt indeksleri değişse de liste boş kalmaz."""
    try:
        sd = _sd()
        by_api: dict[int, list[str]] = {}
        for _, d in _all_input_devices(sd):
            by_api.setdefault(int(d["hostapi"]), []).append(d["name"])
        if not by_api:
            return []
        rank = _hostapi_rank(sd)
        best = min(by_api, key=rank)
        seen: set[str] = set()
        names: list[str] = []
        for name in by_api[best]:
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names
    except Exception:  # noqa: BLE001 - PortAudio yoksa / aygıt sorgusu patlarsa liste boş
        return []


def resolve_input_device(name: str | None) -> int | None:
    """Ad -> sounddevice indeksi. Tam ad önce, sonra alt dize; her ikisinde de en iyi host API'yi seçer.
    Bulunmazsa None (varsayılan giriş). Aygıtlar tüm host API'lerden aranır, böylece eski kayıtlı adlar da tutar."""
    if not name:
        return None
    try:
        sd = _sd()
        cands = _all_input_devices(sd)
        rank = _hostapi_rank(sd)
    except Exception:  # noqa: BLE001
        return None
    exact = [(rank(int(d["hostapi"])), i) for i, d in cands if d["name"] == name]
    if exact:
        return min(exact)[1]
    low = name.lower()
    sub = [(rank(int(d["hostapi"])), i) for i, d in cands
           if low in d["name"].lower() or d["name"].lower() in low]
    if sub:
        return min(sub)[1]
    return None


class AudioCapture:
    """Tek kayıt için mikrofon yakalayıcı: start(wav_yolu) ... stop() -> AudioResult."""

    QUEUE_BLOCKS = 8192          # ~20 ms'lik bloklar: dakikalarca yer; yazıcı iş parçacığı takılsa bile örnek düşmez

    def __init__(self, device: str | None = None, channels: int = 1):
        self.device = device
        self.channels = channels
        self.first_sample_monotonic: float | None = None
        self.last_sample_monotonic: float | None = None     # son bloğun sonu: mikrofon durdurmadan önce sustu mu
        self.samples = 0
        self.overflows = 0
        self.dropped_blocks = 0
        self.error: str | None = None          # WAV yazıcısının hatası (disk dolu...); stop() AudioResult'a taşır
        self.samplerate = 48000
        self._stream = None
        self._wav: wave.Wave_write | None = None
        self._q: queue.Queue = queue.Queue(maxsize=self.QUEUE_BLOCKS)
        self._stop = threading.Event()
        self._writer: threading.Thread | None = None
        self.path: Path | None = None

    def start(self, path: Path) -> None:
        sd = _sd()
        idx, info = self._pick_device(sd)
        self.samplerate = int(info.get("default_samplerate") or 48000)     # aygıtın kendi hızı: yeniden örnekleme yok
        channels = max(1, min(self.channels, int(info.get("max_input_channels") or 1)))
        self.channels = channels
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._wav = wave.open(str(self.path), "wb")
        self._wav.setnchannels(channels)
        self._wav.setsampwidth(2)
        self._wav.setframerate(self.samplerate)
        self._stop.clear()
        self._writer = threading.Thread(target=self._write_loop, daemon=True)
        self._writer.start()
        self._stream = sd.InputStream(device=idx, samplerate=self.samplerate, channels=channels, dtype="int16",
                                      latency="high", callback=self._callback)
        self._stream.start()

    def _pick_device(self, sd) -> tuple[int | None, dict]:
        """Aygıtı sağlam çöz: seçilen ad, sonra PortAudio varsayılanı, o da yoksa listedeki ilk mikrofon.
        Bu makinede varsayılan giriş -1 olabilir (PortAudioError); o durumda ilk mikrofona düşer."""
        idx = resolve_input_device(self.device)
        if idx is not None:
            try:
                return idx, sd.query_devices(idx, "input")
            except Exception:  # noqa: BLE001 - seçilen indeks geçersiz: varsayılana düş
                pass
        try:
            return None, sd.query_devices(kind="input")          # None = PortAudio varsayılan girişi
        except Exception:  # noqa: BLE001 - varsayılan giriş yok (-1)
            pass
        names = list_input_devices()
        fallback = resolve_input_device(names[0]) if names else None
        if fallback is None:
            raise RuntimeError("kullanılabilir mikrofon bulunamadı")
        return fallback, sd.query_devices(fallback, "input")

    def _block_lag(self, time_info, frames: int) -> float:
        """Bloğun ilk örneğinin alındığı andan geri çağrıya dek geçen süre (0-0,5 sn). Sürücünün zaman bilgisinden;
        vermiyorsa (WASAPI vb. güvenilmez) sürücünün bildirdiği gecikme + bu bloğun süresi."""
        lag = None
        try:
            adc, cur = float(time_info.inputBufferAdcTime), float(time_info.currentTime)
            if adc > 0 and cur > 0 and 0.0 <= cur - adc < 0.5:
                lag = cur - adc
        except Exception:  # noqa: BLE001 - bazı sürücüler zaman bilgisi vermez
            lag = None
        if lag is None:
            lag = float(getattr(self._stream, "latency", 0.0) or 0.0) + frames / float(self.samplerate)
        return min(max(lag, 0.0), 0.5)

    def _callback(self, indata, frames, time_info, status) -> None:
        if status and getattr(status, "input_overflow", False):
            self.overflows += 1
        start = time.monotonic() - self._block_lag(time_info, frames)       # bu bloğun ilk örneği
        if self.first_sample_monotonic is None:
            self.first_sample_monotonic = start
        self.last_sample_monotonic = start + frames / float(self.samplerate)
        try:
            self._q.put_nowait(indata.copy())
        except queue.Full:
            self.dropped_blocks += 1

    def _write_loop(self) -> None:
        """Kuyruktaki blokları WAV'a yazar. Yazım hatası (disk dolu, dosya kilitlendi) iş parçacığını sessizce
        öldürmez: sebep self.error'a, ayrıntı hatalar.log'a gider; stop() bunu AudioResult.error ile kaydediciye
        taşır. Video etkilenmez: o ana dek yazılan ses birleştirilir, kalan kısım sessizlikle dolar. İstisna bu iş
        parçacığından kaçmaz; genel uyarı kutusu kayıt sürerken tahtanın (kaydın) üstünde açılmasın."""
        try:
            while True:
                try:
                    block = self._q.get(timeout=0.2)
                except queue.Empty:
                    if self._stop.is_set():
                        return
                    continue
                if self._wav is not None:
                    self._wav.writeframes(block.tobytes())
                    self.samples += len(block)
        except Exception as err:  # noqa: BLE001 - sebep kayıt sonunda öğretmene söylenir
            self.error = _reason(err)
            crash_log.log_handled(err, "ses yazıcısı")

    def stop(self) -> AudioResult:
        stopped = time.monotonic()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        self._stop.set()
        if self._writer is not None:
            self._writer.join(timeout=15)
            self._writer = None
        if self._wav is not None:
            try:
                self._wav.close()
            except OSError as err:           # disk doluysa son tampon ve başlık da yazılamaz; yazılmış ses kalır
                self.error = self.error or _reason(err)
                crash_log.log_handled(err, "ses dosyası kapatılırken")
            self._wav = None
        return AudioResult(self.path or Path(), self.samplerate, self.channels, self.samples,
                           self.first_sample_monotonic, stopped, self.overflows, self.dropped_blocks, self.error,
                           self.last_sample_monotonic)
