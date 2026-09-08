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

    @property
    def duration(self) -> float:
        return self.samples / self.samplerate if self.samplerate else 0.0

    @property
    def wall_duration(self) -> float:
        """İlk örnekten durdurmaya kadar geçen gerçek süre (saat kaymasını ölçmek için)."""
        if self.first_sample_monotonic is None:
            return 0.0
        return max(0.0, self.stopped_monotonic - self.first_sample_monotonic)


def _sd():
    import sounddevice as sd
    return sd


def _input_devices() -> list[tuple[int, dict]]:
    """(indeks, aygıt) çiftleri; Windows'ta yalnızca WASAPI (adlar üç kez tekrarlanmasın, düşük gecikme)."""
    sd = _sd()
    hostapis, devices = sd.query_hostapis(), sd.query_devices()
    preferred = next((i for i, h in enumerate(hostapis) if "WASAPI" in h["name"]), None)
    out = []
    for idx, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        if preferred is not None and d["hostapi"] != preferred:
            continue
        out.append((idx, d))
    return out


def list_input_devices() -> list[str]:
    """Mikrofon adları (ayarlar listesi için)."""
    try:
        names: list[str] = []
        for _, d in _input_devices():
            if d["name"] not in names:
                names.append(d["name"])
        return names
    except Exception:  # noqa: BLE001 - PortAudio yoksa / aygıt sorgusu patlarsa liste boş
        return []


def resolve_input_device(name: str | None) -> int | None:
    """Ad -> sounddevice indeksi. Tam ad, sonra alt dize; bulunmazsa None (varsayılan giriş)."""
    if not name:
        return None
    try:
        devs = _input_devices()
    except Exception:  # noqa: BLE001
        return None
    for idx, d in devs:
        if d["name"] == name:
            return idx
    for idx, d in devs:
        if name.lower() in d["name"].lower() or d["name"].lower() in name.lower():
            return idx
    return None


class AudioCapture:
    """Tek kayıt için mikrofon yakalayıcı: start(wav_yolu) ... stop() -> AudioResult."""

    QUEUE_BLOCKS = 8192          # ~20 ms'lik bloklar: dakikalarca yer; yazıcı iş parçacığı takılsa bile örnek düşmez

    def __init__(self, device: str | None = None, channels: int = 1):
        self.device = device
        self.channels = channels
        self.first_sample_monotonic: float | None = None
        self.samples = 0
        self.overflows = 0
        self.dropped_blocks = 0
        self.samplerate = 48000
        self._stream = None
        self._wav: wave.Wave_write | None = None
        self._q: queue.Queue = queue.Queue(maxsize=self.QUEUE_BLOCKS)
        self._stop = threading.Event()
        self._writer: threading.Thread | None = None
        self.path: Path | None = None

    def start(self, path: Path) -> None:
        sd = _sd()
        idx = resolve_input_device(self.device)
        info = sd.query_devices(idx, "input") if idx is not None else sd.query_devices(kind="input")
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

    def _callback(self, indata, frames, time_info, status) -> None:
        if status and getattr(status, "input_overflow", False):
            self.overflows += 1
        if self.first_sample_monotonic is None:
            now = time.monotonic()
            lag = None
            try:
                adc, cur = float(time_info.inputBufferAdcTime), float(time_info.currentTime)
                if adc > 0 and cur > 0 and 0.0 <= cur - adc < 0.5:
                    lag = cur - adc
            except Exception:  # noqa: BLE001 - bazı sürücüler zaman bilgisi vermez
                lag = None
            if lag is None:
                # WASAPI vb. zaman bilgisi güvenilmez: sürücünün bildirdiği gecikme + bu bloğun süresi
                lag = float(getattr(self._stream, "latency", 0.0) or 0.0) + frames / float(self.samplerate)
            self.first_sample_monotonic = now - min(max(lag, 0.0), 0.5)
        try:
            self._q.put_nowait(indata.copy())
        except queue.Full:
            self.dropped_blocks += 1

    def _write_loop(self) -> None:
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
            self._wav.close()
            self._wav = None
        return AudioResult(self.path or Path(), self.samplerate, self.channels, self.samples,
                           self.first_sample_monotonic, stopped, self.overflows, self.dropped_blocks)
