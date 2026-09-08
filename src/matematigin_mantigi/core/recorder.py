"""Kayıt: RecordRect + Recorder protokolü, NullRecorder (test/taslak) ve MssFfmpegRecorder (gerçek kayıt).

MssFfmpegRecorder: ekranın tahta bölgesini mss ile yakalar (yakalama iş parçacığı), sabit tempolu yazıcı iş
parçacığı en yeni kareyi boru ile ffmpeg'e verir (yakalama yavaşsa kare çoğaltılır; süre duvar saatiyle aynı kalır).
Ses ffmpeg'e DEĞİL, uygulama içinde PortAudio ile WAV'a alınır (core/audio_capture.py); durdurunca ffmpeg videoyu
kopyalayıp sesi ölçülen zaman farkıyla hizalayarak tek MP4'e birleştirir.
"""
from __future__ import annotations

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

from matematigin_mantigi.core.audio_capture import AudioCapture, AudioResult


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
    stop_is_quick = True

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
        return np.frombuffer(shot.bgra, np.uint8).reshape(shot.height, shot.width, 4)
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


def ffmpeg_args(exe: str, width: int, height: int, fps: int, out: Path,
                platform: str | None = None, out_height: int = 0, encoder: str = "libx264") -> list[str]:
    """Video ffmpeg komutu: ham BGRA kareler stdin'den, H.264 MP4 (ses yok; ses ayrı alınıp sonda birleştirilir).
    Giriş kuyruğu bilerek küçük (8 kare): Retina'da kare ~20 MB; büyük kuyruk belleği şişirir. Kodlayıcı geride
    kalırsa geri basınç Python yazıcısına ulaşır, o da kareyi çoğaltarak süreyi korur."""
    args = [exe, "-y", "-hide_banner", "-loglevel", "warning", "-nostats", "-thread_queue_size", "8",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
    if out_height and out_height != height:
        args += ["-filter_threads", "4", "-vf", f"scale=-2:{out_height}:flags=bilinear"]
    args += [*ENCODER_ARGS.get(encoder, ENCODER_ARGS["libx264"]), "-pix_fmt", "yuv420p",
             "-r", str(fps), "-fps_mode", "cfr", "-movflags", "+faststart", str(out)]
    return args


def mux_args(exe: str, video: Path, audio: Path, out: Path, offset_s: float,
             asetrate: int | None = None, out_rate: int = 48000) -> list[str]:
    """Video (kopya) + WAV -> MP4 (AAC). offset_s > 0: ses videodan önce başladı, başı atılır (-ss);
    offset_s < 0: ses geç başladı, geciktirilir (-itsoffset). asetrate: ölçülen gerçek örnekleme hızı
    (mikrofon saati kaymasını düzeltir; ppm düzeyi, duyulmaz)."""
    args = [exe, "-y", "-hide_banner", "-loglevel", "warning", "-nostats", "-i", str(video)]
    if offset_s >= 0:
        args += ["-ss", f"{offset_s:.3f}", "-i", str(audio)]
    else:
        args += ["-itsoffset", f"{-offset_s:.3f}", "-i", str(audio)]
    args += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy"]
    if asetrate:
        args += ["-af", f"asetrate={asetrate},aresample={out_rate}"]
    args += ["-ar", str(out_rate), "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
    return args


def audio_rate_correction(result: AudioResult, min_duration: float = 600.0, min_ppm: float = 100.0) -> int | None:
    """Uzun kayıtta mikrofon saati ile bilgisayar saati arasındaki farkı ölç: örnek sayısı / duvar süresi.
    Kısa kayıtta ölçüm gürültüsü (±30 ms) gerçek kaymadan büyük olduğu için uygulanmaz."""
    wall = result.wall_duration
    if wall < min_duration or result.samples <= 0:
        return None
    actual = result.samples / wall
    ppm = abs(actual / result.samplerate - 1.0) * 1e6
    if ppm < min_ppm or ppm > 10_000:            # %1'den büyük fark ölçüm hatasıdır, dokunma
        return None
    return int(round(actual))


class MssFfmpegRecorder:
    """Gerçek kaydedici. grabber(rect) -> BGRA kare; varsayılan ekran yakalama (mss).
    audio_device verilirse ses PortAudio ile alınır (audio_factory testte sahte yakalayıcı verir)."""

    def __init__(self, output_dir: Callable[[], Path], fps: int = 60, audio_device: str | None = None,
                 ffmpeg_exe: str | None = None, grabber: Callable[[RecordRect], np.ndarray] | None = None,
                 clock: Callable[[], datetime] = datetime.now, out_height: int = 1440,
                 audio_factory: Callable[[str | None], AudioCapture] | None = None):
        self._output_dir = output_dir
        self.fps = fps
        self.out_height = out_height
        self.audio_device = audio_device or None
        self._audio_factory = audio_factory or (lambda dev: AudioCapture(dev))
        self._ffmpeg_exe = ffmpeg_exe
        self._grabber = grabber
        self._clock = clock
        self._proc: subprocess.Popen | None = None
        self._log_file = None
        self._log_path: Path | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._latest: bytes = b""
        self._latest_lock = threading.Lock()
        self._audio: AudioCapture | None = None
        self._video_path: Path | None = None
        self.audio_result: AudioResult | None = None
        self.audio_error: str | None = None
        self.video_t0: float | None = None
        self.last_duration = 0.0
        self.started_at: float | None = None
        self.last_path: Path | None = None
        self.frames_written = 0
        self.frames_grabbed = 0
        self.error: str | None = None
        self.failed = False
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
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        out = out_dir / f"kayit_{stamp}.mp4"
        self._video_path = out_dir / f"kayit_{stamp}.video.mp4" if self.audio_device else out
        self._log_path = out_dir / f"kayit_{stamp}.log"
        self.encoder = detect_encoder(exe) if self._grabber is None else "libx264"   # testte hızlı yol
        self.audio_result, self.audio_error, self._audio = None, None, None
        if self.audio_device:
            # Ses önce başlar: ilk örneğin zamanı ölçülür, video t0 ile fark durdurunca telafi edilir.
            try:
                self._audio = self._audio_factory(self.audio_device)
                self._audio.start(out_dir / f"kayit_{stamp}.wav")
            except Exception as err:  # noqa: BLE001 - mikrofon açılmazsa kayıt sessiz devam eder
                self._audio, self.audio_error = None, f"Mikrofon açılamadı: {err}"
        args = ffmpeg_args(exe, w, h, fps, self._video_path, out_height=self.out_height, encoder=self.encoder)
        try:
            self._log_file = open(self._log_path, "wb")     # stderr borusu dolarsa ffmpeg donar; dosyaya yaz
            self._proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                          stderr=self._log_file)
        except OSError as err:
            self._close_log()
            self._abort_audio()
            raise RecorderError(f"ffmpeg başlatılamadı: {err}") from err
        self.last_rect, self.last_path, self.fps = rect, out, fps
        self.frames_written, self.frames_grabbed, self.error, self.failed = 0, 0, None, False
        self.video_t0 = None
        self._stop.clear()
        self.started_at = time.monotonic()
        self._thread = threading.Thread(target=self._loop, args=(grab_rect, first, w, h, fps), daemon=True)
        self._thread.start()

    def stop(self) -> Path | None:
        """Kaydı kapatır ve sesi videoyla birleştirir. Uzun sürebilir (birkaç sn); arayüz bunu ayrı iş
        parçacığında çağırmalı."""
        if not self.is_recording:
            return self.last_path
        self._stop.set()
        self.last_duration = time.monotonic() - (self.started_at or time.monotonic())
        if self._thread is not None:
            self._thread.join(timeout=10)
        audio = self._stop_audio()
        proc = self._proc
        self._proc, self._thread, self.started_at = None, None, None
        if proc is not None:
            try:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except (OSError, ValueError):
                        pass
                    proc.stdin = None        # communicate() kapalı boruyu flush etmesin (Py3.12/macOS ValueError)
                proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                self.error = "ffmpeg zamanında kapanmadı"
        self._close_log()
        if proc is not None and proc.returncode not in (0, None) and not self.error:
            self.error = f"ffmpeg hata kodu {proc.returncode}: {self._log_tail()}"
        if audio is not None and self.last_path is not None and self._video_path is not None:
            self._mux(audio)
        elif self._video_path is not None and self.last_path is not None and self._video_path != self.last_path:
            if self._video_path.exists():
                self._video_path.replace(self.last_path)      # mikrofon açılamadı: yalnız video
        return self.last_path

    @property
    def is_recording(self) -> bool:
        return self.started_at is not None

    @property
    def elapsed_seconds(self) -> int:
        return 0 if self.started_at is None else int(time.monotonic() - self.started_at)

    @property
    def capture_fps(self) -> float:
        """Son kayıtta gerçekten yakalanan kare/sn (yazılan değil)."""
        return self.frames_grabbed / self.last_duration if self.last_duration else 0.0

    @property
    def av_offset_ms(self) -> float | None:
        """Ölçülen ses-video başlangıç farkı (ms, + = ses önce başladı). Son kayıt için."""
        r = self.audio_result
        if r is None or r.first_sample_monotonic is None or self.video_t0 is None:
            return None
        return (self.video_t0 - r.first_sample_monotonic) * 1000.0

    # --- iç ----------------------------------------------------------------------
    def _grab(self, rect: RecordRect, sct=None) -> np.ndarray:
        return self._grabber(rect) if self._grabber else grab_screen(rect, sct)

    def _close_log(self) -> None:
        if self._log_file is not None:
            try:
                self._log_file.close()
            except OSError:
                pass
            self._log_file = None

    def _log_tail(self, n: int = 400) -> str:
        try:
            return self._log_path.read_text(encoding="utf-8", errors="replace").strip()[-n:] if self._log_path else ""
        except OSError:
            return ""

    def _abort_audio(self) -> None:
        if self._audio is not None:
            try:
                self._audio.stop()
            except Exception:  # noqa: BLE001
                pass
            self._audio = None

    def _stop_audio(self) -> AudioResult | None:
        if self._audio is None:
            return None
        try:
            self.audio_result = self._audio.stop()
        except Exception as err:  # noqa: BLE001
            self.audio_error = f"Mikrofon kapatılamadı: {err}"
            self.audio_result = None
        self._audio = None
        return self.audio_result

    def _mux(self, audio: AudioResult) -> None:
        """Video (kopya) + WAV -> son MP4. Başarısızsa yalnız video dosyası sonuç olur."""
        exe = self._ffmpeg_exe or find_ffmpeg()
        video, out = self._video_path, self.last_path
        assert video is not None and out is not None
        if not exe or audio.samples <= 0 or not audio.path.exists():
            self.audio_error = self.audio_error or "Ses kaydedilemedi (örnek yok)"
            video.replace(out)
            return
        t0 = self.video_t0 if self.video_t0 is not None else (audio.first_sample_monotonic or 0.0)
        offset = t0 - (audio.first_sample_monotonic if audio.first_sample_monotonic is not None else t0)
        args = mux_args(exe, video, audio.path, out, offset, asetrate=audio_rate_correction(audio))
        try:
            res = subprocess.run(args, capture_output=True, timeout=max(120, int(self.last_duration * 2)))
        except (OSError, subprocess.SubprocessError) as err:
            self.audio_error = f"Ses birleştirilemedi: {err}"
            video.replace(out)
            return
        if res.returncode != 0 or not out.exists():
            self.audio_error = "Ses birleştirilemedi: " + res.stderr.decode("utf-8", "replace").strip()[-300:]
            video.replace(out)
            return
        for p in (video, audio.path):
            try:
                p.unlink()
            except OSError:
                pass

    def _grab_loop(self, rect: RecordRect, w: int, h: int, fps: int) -> None:
        """Yakalama iş parçacığı: en fazla fps hızında kare alır, en yenisini bırakır."""
        sct = None
        if self._grabber is None:
            sct = _new_mss()                     # mss nesnesi kendi iş parçacığında oluşturulmalı
        period = 1.0 / fps
        try:
            while not self._stop.is_set():
                t = time.monotonic()
                try:
                    frame = self._grab(rect, sct)
                except Exception:  # noqa: BLE001 - tek kare kaçarsa son kare tekrar yazılır
                    time.sleep(0.005)
                    continue
                data = np.ascontiguousarray(frame[:h, :w]).tobytes()
                with self._latest_lock:
                    self._latest = data
                self.frames_grabbed += 1
                rest = period - (time.monotonic() - t)      # fps'ten hızlı yakalamak boşa CPU
                if rest > 0:
                    time.sleep(rest)
        finally:
            if sct is not None:
                sct.close()

    def _loop(self, rect: RecordRect, first: np.ndarray, w: int, h: int, fps: int) -> None:
        """Yazıcı iş parçacığı: sabit tempoda (fps) en yeni kareyi ffmpeg'e yazar.
        Yakalama yavaşsa aynı kare tekrar yazılır; süre duvar saatiyle aynı kalır."""
        period = 1.0 / fps
        self._latest = np.ascontiguousarray(first[:h, :w]).tobytes()
        grabber = threading.Thread(target=self._grab_loop, args=(rect, w, h, fps), daemon=True)
        grabber.start()
        t0 = time.monotonic()
        self.video_t0 = t0
        try:
            while not self._stop.is_set():
                with self._latest_lock:
                    data = self._latest
                due = int((time.monotonic() - t0) * fps) - self.frames_written
                for _ in range(max(1, due)):
                    try:
                        self._proc.stdin.write(data)      # type: ignore[union-attr]
                    except (BrokenPipeError, OSError, ValueError, AttributeError):
                        self.error = "ffmpeg borusu kapandı: " + (self._log_tail(200) or "ayrıntı yok")
                        self.failed = True
                        return
                    self.frames_written += 1
                delay = (t0 + self.frames_written * period) - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        finally:
            self._stop.set()
            grabber.join(timeout=5)
