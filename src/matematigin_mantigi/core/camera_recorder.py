"""Ham kamera için bağımsız, tek karelik posta kutulu ffmpeg yazıcısı.

Ekran kaydedicisine geri basınç uygulamaz. Kamera işçisi yalnız bir kopya bırakır;
keşif, boru yazımı ve WAV birleştirmesi burada arka planda yapılır.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess
import threading
import time

import numpy as np

from matematigin_mantigi.core import crash_log
from matematigin_mantigi.core.recorder import (audio_rate_correction, detect_encoder, ffmpeg_args,
                                               find_ffmpeg, media_duration, mux_args, no_window)


class CameraRecorder:
    STALL_SECONDS = 10.0

    def __init__(self, screen_path: Path, screen_started: float):
        self.path = Path(screen_path).with_suffix(".kamera.mp4")
        self.raw_path = self.path.with_suffix(".video.mp4")
        self.metadata_path = self.path.with_suffix(".json")
        self.log_path = self.path.with_suffix(".log")
        self.screen_started = screen_started
        self.first_at: float | None = None
        self.stopped_at: float | None = None
        self.fps = 30.0
        self.resolution: tuple[int, int] | None = None
        self.frames_written = 0
        self.frames_dropped = 0
        self.warning: str | None = None
        self.audio_muxed = False
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._latest = None
        self._proc = None
        self._reserved = False
        self._progress_at = time.monotonic()
        self._write_started = 0.0
        self._thread = threading.Thread(target=self._run, name="kamera-dosya", daemon=True)
        self._thread.start()

    def submit(self, frame: np.ndarray, captured_at: float, fps: float) -> None:
        """Kamera işçisinden çağrılır; ffmpeg'i ve GUI'yi asla beklemez."""
        if self._stop.is_set() or self.warning:
            return
        with self._lock:
            if self._latest is not None:
                self.frames_dropped += 1
            self._latest = (frame.copy(), captured_at, fps)
        self._wake.set()

    def check_stall(self) -> None:
        """GUI zamanlayıcısından: bloke yazımı canlı yakalar (yakalama ve yazıcı ayrı izlenir)."""
        started, proc = self._write_started, self._proc
        if started and proc is not None and not self.warning and time.monotonic() - started > self.STALL_SECONDS:
            self._warn(f"Kamera kodlayıcısı ilerlemiyor; ham dosya korunuyor: {self.raw_path}")
            proc.kill()

    def request_stop(self) -> None:
        if not self._stop.is_set():
            self.stopped_at = time.monotonic()
            self._stop.set()
            self._wake.set()

    def _warn(self, text: str) -> None:
        self.warning = f"{self.warning}\n{text}" if self.warning else text
        crash_log.log_handled(RuntimeError(text), "ayrı kamera kaydı")

    def _take(self):
        with self._lock:
            item, self._latest = self._latest, None
        return item

    def _open(self, frame, fps):
        self.resolution = (int(frame.shape[1]), int(frame.shape[0]))
        self.fps = float(fps) if math.isfinite(fps) and 1 <= fps <= 240 else 30.0
        exe = find_ffmpeg()
        if not exe:
            raise RuntimeError("Kamera kaydı için ffmpeg bulunamadı")
        w, h = self.resolution
        enc = detect_encoder(exe, width=w, height=h, fps=self.fps)
        # Yalnız bu oturumun atomik ayırdığı dosyaları ffmpeg'in -y seçeneğine ver.
        # Çakışan yabancı kamera dosyası varsa ana kaydı değil yalnız bu çıktıyı reddet.
        for path in (self.path, self.raw_path, self.metadata_path, self.log_path):
            with path.open("xb"):
                pass
        self._reserved = True
        args = ffmpeg_args(exe, w, h, self.fps, self.raw_path, encoder=enc)
        args[args.index("-pix_fmt") + 1] = "bgr24"
        # Ham boruda düşen kareler zamanı sıkıştırmasın: ffmpeg aradaki CFR
        # yuvalarını doldurur. Duvar saati yalnız bu bağımsız alt süreçte kullanılır.
        args[args.index("-i"):args.index("-i")] = ["-use_wallclock_as_timestamps", "1"]
        if w % 2 or h % 2:
            args[-args[::-1].index("-pix_fmt")] = "yuv444p"
        self._log = self.log_path.open("ab")
        self._proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                      stderr=self._log, **no_window())

    def _run(self):
        try:
            frame = None
            deadline = time.monotonic()
            while True:
                if frame is None:
                    self._wake.wait(0.1)
                    self._wake.clear()
                else:
                    self._stop.wait(max(0.0, deadline - time.monotonic()))
                item = self._take()
                if item is not None:
                    frame, captured, fps = item
                if frame is None:
                    if self._stop.is_set():
                        break
                    continue
                if self._proc is None:
                    self._open(frame, fps)
                    newest = self._take()
                    if newest is not None:
                        frame, captured, _ = newest
                    self.first_at = captured
                    deadline = time.monotonic()
                if (frame.shape[1], frame.shape[0]) != self.resolution:
                    raise RuntimeError("Kamera çözünürlüğü kayıt sırasında değişti")
                self._write_started = time.monotonic()
                self._proc.stdin.write(np.ascontiguousarray(frame).tobytes())
                self._write_started = 0.0
                self.frames_written += 1
                self._progress_at = time.monotonic()
                # Son kaynak karesi tekrarlanabilir; ağır kodlayıcıda eski kaynak
                # kareleri birikmez. ffmpeg zaman damgaları gerçek aralığı korur.
                deadline = max(deadline + 1.0 / self.fps, time.monotonic())
                if self._stop.is_set():
                    break
        except Exception as err:  # noqa: BLE001 - ekran kaydı her koşulda bağımsız kalır
            self._warn(f"Kamera dosyası yazılamadı: {err}. Ham görüntü: {self.raw_path}")
        finally:
            if self._proc is not None:
                try:
                    self._proc.stdin.close()
                    # Ham videoda faststart yok: EOF sonrası yalnız moov yazılır.
                    self._proc.wait(timeout=60)
                    if self._proc.returncode:
                        self._warn(f"Kamera kodlayıcısı hata verdi ({self._proc.returncode}); günlük: {self.log_path}")
                except (OSError, subprocess.SubprocessError) as err:
                    self._warn(f"Kamera kodlayıcısı kapanamadı: {err}; ham dosya korunuyor: {self.raw_path}")
                    self._proc.kill()
                    self._proc.wait()
                finally:
                    self._log.close()

    def finish(self, audio_result=None) -> None:
        """Ana kaydedici durduktan sonra _StopWorker'da çağrılır; ham WAV silinmez."""
        self.request_stop()
        while self._thread.is_alive():
            self._thread.join(0.1)
            if (self._proc is not None and self._proc.poll() is None
                    and time.monotonic() - self._progress_at > self.STALL_SECONDS):
                self._warn(f"Kamera kodlayıcısı ilerlemiyor; ham dosya korunuyor: {self.raw_path}")
                self._proc.kill()  # bloke stdin.write kilidini başka iş parçacığından close etme
        if not self._reserved:
            return  # kamera hiç kare vermediyse dosya oluşturulmaz
        try:
            if not self.warning and self.frames_written:
                duration = media_duration(find_ffmpeg(), self.raw_path)
                if not duration:
                    raise RuntimeError("Kamera videosunun süresi doğrulanamadı")
                if (audio_result is not None and audio_result.path.exists()
                        and audio_result.first_sample_monotonic is not None):
                    offset = self.first_at - audio_result.first_sample_monotonic
                    args = mux_args(find_ffmpeg(), self.raw_path, audio_result.path, self.path, offset,
                                    asetrate=audio_rate_correction(audio_result), video_s=duration)
                    # +faststart tüm dosyayı yeniden yazar; sabit kapanış süresiyle öldürme.
                    with self.log_path.open("ab") as log:
                        result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=log, **no_window())
                    if result.returncode or not media_duration(find_ffmpeg(), self.path):
                        raise RuntimeError("Kamera sesi birleştirilemedi; ham video ve WAV korunuyor")
                    self.audio_muxed = True
                else:
                    shutil.copyfile(self.raw_path, self.path)
                    self._warn("Kamera dosyası sessiz: ham WAV veya sesin başlangıç zamanı yok.")
        except Exception as err:  # noqa: BLE001
            self._warn(f"Kamera dosyası tamamlanamadı: {err}. Ham görüntü: {self.raw_path}")
        finally:
            try:
                self.metadata_path.write_text(json.dumps({
                    "start_offset_seconds": (None if self.first_at is None or self.screen_started is None
                                             else self.first_at - self.screen_started),
                    "resolution": self.resolution, "fps": self.fps,
                    "frames_written": self.frames_written, "frames_dropped": self.frames_dropped,
                    "audio_muxed": self.audio_muxed, "warning": self.warning,
                    "duration_seconds": None if self.first_at is None else self.stopped_at - self.first_at,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError as err:
                self._warn(f"Kamera eşleme bilgisi yazılamadı: {err}")
