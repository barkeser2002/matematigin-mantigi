"""Kayıt: RecordRect + Recorder protokolü, NullRecorder (test/taslak) ve MssFfmpegRecorder (gerçek kayıt).

MssFfmpegRecorder: ekranın tahta bölgesini mss ile yakalar, kareleri boru ile ffmpeg'e verir; ffmpeg H.264 MP4
yazar, istenirse mikrofonu da (Windows: dshow, macOS: avfoundation) aynı dosyaya karıştırır.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

import numpy as np


def _even(n: int) -> int:
    return n - (n % 2)


@dataclass(frozen=True)
class RecordRect:
    x: int
    y: int
    width: int
    height: int
    dpr: float = 1.0

    def physical(self) -> "RecordRect":
        s = self.dpr
        return RecordRect(round(self.x * s), round(self.y * s),
                          _even(round(self.width * s)), _even(round(self.height * s)), 1.0)

    def to_mss(self) -> dict[str, int]:
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}


def record_rect_for(rect5: tuple[int, int, int, int, float]) -> RecordRect:
    x, y, w, h, dpr = rect5
    return RecordRect(int(x), int(y), int(w), int(h), float(dpr))


class Recorder(Protocol):
    def start(self, rect: RecordRect, fps: int = 60) -> None: ...
    def stop(self) -> Path | None: ...
    @property
    def is_recording(self) -> bool: ...
    @property
    def elapsed_seconds(self) -> int: ...


class NullRecorder:
    def __init__(self) -> None:
        self.last_rect: RecordRect | None = None
        self.fps = 60
        self.started_at: float | None = None

    def start(self, rect: RecordRect, fps: int = 60) -> None:
        self.last_rect, self.fps, self.started_at = rect, fps, time.monotonic()

    def stop(self) -> Path | None:
        self.started_at = None
        return None

    @property
    def is_recording(self) -> bool:
        return self.started_at is not None

    @property
    def elapsed_seconds(self) -> int:
        return 0 if self.started_at is None else int(time.monotonic() - self.started_at)


# --- gerçek kayıt ------------------------------------------------------------------

class RecorderError(RuntimeError):
    pass


def find_ffmpeg() -> str | None:
    """Önce imageio-ffmpeg ile gelen ikili (paketlenmiş uygulamada da var), sonra PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - kütüphane yoksa veya ikili indirilemediyse PATH'e düş
        return shutil.which("ffmpeg")


def _new_mss():
    import mss
    return mss.MSS() if hasattr(mss, "MSS") else mss.mss()      # mss 10: MSS sınıfı; eski sürüm: mss()


def grab_screen(rect: RecordRect, sct=None) -> np.ndarray:
    """Ekran bölgesini BGRA uint8 HxWx4 olarak yakalar (mss). Windows'ta fiziksel piksel bekler."""
    own = sct is None
    if own:
        sct = _new_mss()
    try:
        shot = sct.grab(rect.to_mss())
        return np.frombuffer(shot.bgra, np.uint8).reshape(shot.height, shot.width, 4).copy()
    finally:
        if own:
            sct.close()


RESOLUTIONS: tuple[tuple[str, int], ...] = (("Doğal (ekran)", 0), ("1080p", 1080), ("2K (1440p)", 1440), ("4K (2160p)", 2160))


ENCODER_ARGS: dict[str, list[str]] = {
    "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-b:v", "16M", "-realtime", "1"],
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"],
    "h264_qsv": ["-c:v", "h264_qsv", "-global_quality", "23"],
    "h264_amf": ["-c:v", "h264_amf", "-quality", "speed"],
    "libx264": ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-crf", "22"],
}
_PREFERRED = {"darwin": ["h264_videotoolbox"], "win32": ["h264_nvenc", "h264_qsv", "h264_amf"]}
_encoder_cache: dict[str, str] = {}


def detect_encoder(exe: str, platform: str | None = None, runner=None) -> str:
    """Kullanılabilir ilk donanım H.264 kodlayıcısı; her aday 1 karelik deneme kodlamasıyla doğrulanır."""
    platform = platform or sys.platform
    key = f"{exe}|{platform}"
    if key in _encoder_cache and runner is None:
        return _encoder_cache[key]

    def default_runner(cmd: list[str]) -> int:
        try:
            return subprocess.run(cmd, capture_output=True, timeout=20).returncode
        except (OSError, subprocess.SubprocessError):
            return 1
    run = runner or default_runner
    chosen = "libx264"
    for enc in _PREFERRED.get(platform, []):
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=256x144:r=30",
               "-frames:v", "2", *ENCODER_ARGS[enc], "-f", "null", "-"]
        if run(cmd) == 0:
            chosen = enc
            break
    if runner is None:
        _encoder_cache[key] = chosen
    return chosen


def ffmpeg_args(exe: str, width: int, height: int, fps: int, out: Path, audio_device: str | None,
                platform: str | None = None, out_height: int = 0, encoder: str = "libx264") -> list[str]:
    """ffmpeg komut satırı: ham BGRA kareler stdin'den, isteğe bağlı mikrofon, H.264 + AAC MP4.
    out_height > 0 ise çıktı o yüksekliğe ölçeklenir (en-boy korunur, genişlik çift)."""
    platform = platform or sys.platform
    # thread_queue_size: ffmpeg'in giriş kuyruğu varsayılan 8 paket; video borusu bir an geciktiğinde mikrofon
    # kuyruğu taşar, örnekler düşer (cızırtı) ve ses zamanla geriye kayar. Büyük kuyruk + aresample=async bunu önler.
    args = [exe, "-y", "-hide_banner", "-loglevel", "error", "-thread_queue_size", "1024",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
    if audio_device:
        args += ["-thread_queue_size", "8192"]
        if platform == "win32":
            args += ["-f", "dshow", "-audio_buffer_size", "40", "-i", f"audio={audio_device}"]
        elif platform == "darwin":
            m = re.match(r":?\s*(\d+)", audio_device)          # ":0 MacBook Pro Microphone" -> ":0"
            dev = f":{m.group(1)}" if m else f":{audio_device.lstrip(':')}"
            args += ["-f", "avfoundation", "-i", dev]
        else:
            args += ["-f", "pulse", "-i", audio_device]
    if out_height and out_height != height:
        args += ["-vf", f"scale=-2:{out_height}:flags=bicubic"]
    args += [*ENCODER_ARGS.get(encoder, ENCODER_ARGS["libx264"]), "-pix_fmt", "yuv420p",
             "-r", str(fps), "-fps_mode", "cfr"]
    if audio_device:
        # async=1: zaman damgalarına göre boşluk doldurur / fazlayı kırpar; ses videoyla hizalı kalır
        args += ["-af", "aresample=async=1:first_pts=0", "-ar", "48000", "-ac", "2",
                 "-c:a", "aac", "-b:a", "160k", "-shortest"]
    args += ["-movflags", "+faststart", str(out)]
    return args


def list_audio_devices(exe: str | None = None, platform: str | None = None, runner=None) -> list[str]:
    """Mikrofon adları: Windows dshow (ad), macOS avfoundation (':indeks ad')."""
    exe = exe or find_ffmpeg()
    platform = platform or sys.platform
    if not exe:
        return []
    if platform == "win32":
        cmd = [exe, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
    elif platform == "darwin":
        cmd = [exe, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""]
    else:
        return ["default"]
    runner = runner or (lambda c: subprocess.run(c, capture_output=True, text=True, encoding="utf-8",
                                                 errors="replace", timeout=15).stderr)
    try:
        text = runner(cmd)
    except (OSError, subprocess.SubprocessError):
        return []
    names: list[str] = []
    if platform == "win32":
        for line in text.splitlines():
            m = re.search(r'"([^"]+)"\s*\((audio)\)', line)
            if m:
                names.append(m.group(1))
    else:
        in_audio = False
        for line in text.splitlines():
            if "AVFoundation audio devices" in line:
                in_audio = True; continue
            if in_audio:
                m = re.search(r"\[(\d+)\]\s+(.+)$", line)
                if m:
                    names.append(f":{m.group(1)} {m.group(2).strip()}")
    return names


class MssFfmpegRecorder:
    """Gerçek kaydedici. grabber(rect) -> BGRA kare; varsayılan ekran yakalama (mss)."""

    def __init__(self, output_dir: Callable[[], Path], fps: int = 60, audio_device: str | None = None,
                 ffmpeg_exe: str | None = None, grabber: Callable[[RecordRect], np.ndarray] | None = None,
                 clock: Callable[[], datetime] = datetime.now, out_height: int = 1440):
        self._output_dir = output_dir
        self.fps = fps
        self.out_height = out_height
        self.audio_device = audio_device or None
        self._ffmpeg_exe = ffmpeg_exe
        self._grabber = grabber
        self._clock = clock
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._latest: bytes = b""
        self._latest_lock = threading.Lock()
        self.last_duration = 0.0
        self.started_at: float | None = None
        self.last_path: Path | None = None
        self.frames_written = 0
        self.frames_grabbed = 0
        self.error: str | None = None
        self.encoder = "libx264"
        self.last_rect: RecordRect | None = None

    # --- Recorder ---------------------------------------------------------------
    def start(self, rect: RecordRect, fps: int | None = None) -> None:
        if self.is_recording:
            return
        fps = fps or self.fps
        exe = self._ffmpeg_exe or find_ffmpeg()
        if not exe:
            raise RecorderError("ffmpeg bulunamadı (pip install imageio-ffmpeg)")
        grab_rect = rect.physical() if sys.platform == "win32" else RecordRect(rect.x, rect.y, rect.width, rect.height, 1.0)
        try:
            first = self._grab(grab_rect)
        except Exception as err:  # noqa: BLE001
            raise RecorderError(f"Ekran yakalanamadı: {err}") from err
        h, w = _even(first.shape[0]), _even(first.shape[1])
        out_dir = Path(self._output_dir())
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"kayit_{self._clock().strftime('%Y%m%d-%H%M%S')}.mp4"
        self.encoder = detect_encoder(exe) if self._grabber is None else "libx264"   # testte hızlı yol
        args = ffmpeg_args(exe, w, h, fps, out, self.audio_device, out_height=self.out_height, encoder=self.encoder)
        try:
            self._proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                          stderr=subprocess.PIPE)
        except OSError as err:
            raise RecorderError(f"ffmpeg başlatılamadı: {err}") from err
        self.last_rect, self.last_path, self.fps = rect, out, fps
        self.frames_written, self.frames_grabbed, self.error = 0, 0, None
        self._stop.clear()
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._loop, args=(grab_rect, first, w, h, fps), daemon=True)
        self._thread.start()

    def stop(self) -> Path | None:
        if not self.is_recording:
            return self.last_path
        self._stop.set()
        self.last_duration = time.monotonic() - (self.started_at or time.monotonic())
        if self._thread is not None:
            self._thread.join(timeout=10)
        proc = self._proc
        self._proc, self._thread, self.started_at = None, None, None
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
                    proc.stdin = None        # communicate() kapalı boruyu flush etmesin (Py3.12/macOS ValueError)
                _, err = proc.communicate(timeout=30)
                if proc.returncode not in (0, None) and err:
                    self.error = err.decode("utf-8", "replace").strip()[-400:]
            except subprocess.TimeoutExpired:
                proc.kill()
                self.error = "ffmpeg zamanında kapanmadı"
        return self.last_path

    @property
    def is_recording(self) -> bool:
        return self.started_at is not None

    @property
    def elapsed_seconds(self) -> int:
        return 0 if self.started_at is None else int(time.monotonic() - self.started_at)

    # --- iç ----------------------------------------------------------------------
    def _grab(self, rect: RecordRect, sct=None) -> np.ndarray:
        return self._grabber(rect) if self._grabber else grab_screen(rect, sct)

    def _grab_loop(self, rect: RecordRect, w: int, h: int) -> None:
        """Yakalama iş parçacığı: elinden geldiğince hızlı kare alır, en yenisini bırakır."""
        sct = None
        if self._grabber is None:
            sct = _new_mss()                     # mss nesnesi kendi iş parçacığında oluşturulmalı
        try:
            while not self._stop.is_set():
                try:
                    frame = self._grab(rect, sct)
                except Exception:  # noqa: BLE001 - tek kare kaçarsa son kare tekrar yazılır
                    time.sleep(0.005)
                    continue
                data = np.ascontiguousarray(frame[:h, :w]).tobytes()
                with self._latest_lock:
                    self._latest = data
                self.frames_grabbed += 1
        finally:
            if sct is not None:
                sct.close()

    def _loop(self, rect: RecordRect, first: np.ndarray, w: int, h: int, fps: int) -> None:
        """Yazıcı iş parçacığı: sabit tempoda (fps) en yeni kareyi ffmpeg'e yazar.
        Yakalama yavaşsa aynı kare tekrar yazılır; süre duvar saatiyle aynı kalır."""
        period = 1.0 / fps
        self._latest = np.ascontiguousarray(first[:h, :w]).tobytes()
        grabber = threading.Thread(target=self._grab_loop, args=(rect, w, h), daemon=True)
        grabber.start()
        t0 = time.monotonic()
        try:
            while not self._stop.is_set():
                with self._latest_lock:
                    data = self._latest
                due = int((time.monotonic() - t0) * fps) - self.frames_written
                for _ in range(max(1, due)):
                    try:
                        self._proc.stdin.write(data)      # type: ignore[union-attr]
                    except (BrokenPipeError, OSError, AttributeError):
                        self.error = "ffmpeg borusu kapandı"
                        return
                    self.frames_written += 1
                delay = (t0 + self.frames_written * period) - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        finally:
            self._stop.set()
            grabber.join(timeout=5)

    @property
    def capture_fps(self) -> float:
        """Son kayıtta gerçekten yakalanan kare/sn (yazılan değil)."""
        return self.frames_grabbed / self.last_duration if self.last_duration else 0.0
