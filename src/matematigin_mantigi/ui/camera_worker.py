"""Kamera iş parçacığı: OpenCV yakalama -> (isteğe bağlı) yeşil perde -> QImage sinyali."""
from __future__ import annotations

import os
import sys
import time
from threading import Event
from typing import Protocol

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")   # eklenti günlükleri de (FFmpeg vb.) bu seviyeye uyar
import cv2  # noqa: E402
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from dataclasses import replace

from matematigin_mantigi.core import crash_log
from matematigin_mantigi.core.chroma_key import ChromaParams, apply_chroma_key_bgra, estimate_key_hue


class FrameSource(Protocol):
    def open(self) -> bool: ...
    def read(self) -> np.ndarray | None: ...
    def release(self) -> None: ...


class OpenCvSource:
    """OpenCV kamera kaynağı: yalnız seçilen indeksi açar."""

    def __init__(self, index: int = 0):
        self.index = index
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        # Windows'ta CAP_ANY, FFmpeg eklentisini de dolaştırır ve o kendi uyarısını basar; DSHOW + MSMF yeterli.
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF] if sys.platform == "win32" else [cv2.CAP_ANY]
        candidates = [self.index]
        log = cv2.utils.logging
        prev = log.getLogLevel()
        log.setLogLevel(log.LOG_LEVEL_SILENT)         # deneme sırasındaki sürücü uyarıları konsolu kirletmesin
        try:
            for index in candidates:
                for backend in backends:              # DSHOW hızlı açılır; olmazsa varsayılan (MSMF/AVFoundation)
                    cap = cv2.VideoCapture(index, backend)
                    if cap.isOpened():
                        # İstek niteliğinde: desteklemeyen sürücünün kendi çözünürlüğüyle devam et.
                        for prop, value in ((cv2.CAP_PROP_FRAME_WIDTH, 1280), (cv2.CAP_PROP_FRAME_HEIGHT, 720)):
                            try:
                                cap.set(prop, value)
                            except cv2.error:
                                pass
                        ok, frame = cap.read()        # açılan ama kare vermeyen sürücüleri ele
                        if ok and frame is not None:
                            self._cap = cap

                            return True
                    cap.release()
        finally:
            log.setLogLevel(prev)
        self._cap = None
        return False

    def read(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def to_qimage_bgr(frame: np.ndarray) -> QImage:
    frame = np.ascontiguousarray(frame)
    h, w = frame.shape[:2]
    img = QImage(frame.tobytes(), w, h, int(frame.strides[0]), QImage.Format.Format_BGR888)
    return img.copy()      # numpy belleğinden bağımsız, iş parçacıkları arası güvenli


def to_qimage_bgra(frame: np.ndarray) -> QImage:
    """BGRA (saydam zemin) -> QImage ARGB32; derin kopya."""
    frame = np.ascontiguousarray(frame)
    h, w = frame.shape[:2]
    img = QImage(frame.tobytes(), w, h, int(frame.strides[0]), QImage.Format.Format_ARGB32)
    return img.copy()


def resize_to_width(frame: np.ndarray, width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w == width:
        return frame
    return cv2.resize(frame, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)


class CameraWorker(QThread):
    frameReady = pyqtSignal(QImage)
    cameraError = pyqtSignal(str)
    opened = pyqtSignal(int, int)
    keyHueDetected = pyqtSignal(int)          # kenarlardan ölçülen perde tonu (OpenCV birimi)
    AUTO_KEY_EVERY = 90                       # kare; ~3 sn'de bir yeniden ölç
    FRAME_TIMEOUT_MS = 2000                   # kare gelmezse donuk görüntü yerine yeniden bağlantı
    MAX_FRAME_ERRORS = 30                     # art arda bu kadar kare alınamaz/işlenemezse akış hata verip durur

    def __init__(self, source: FrameSource, params: ChromaParams, chroma_enabled: bool = True,
                 out_width: int = 640, target_fps: int = 30, auto_key: bool = True, parent=None,
                 open_retries: int = 0, retry_ms: int = 2000, reconnect: bool = False):
        super().__init__(parent)
        self._source = source
        self._params = params
        self._chroma = chroma_enabled
        self._auto_key = auto_key
        self._out_width = out_width
        self._period = 1.0 / max(1, target_fps)
        self._open_retries, self._retry_ms, self._abort = max(0, int(open_retries)), max(100, int(retry_ms)), False
        self._running = False
        self._stopped = Event()
        self.launched = Event()
        # Sonlu FrameSource tüketicileri eski bitiş davranışını korur; canlı panel yeniden bağlanır.
        self._reconnect = reconnect
        self._frames = 0

    def set_chroma_enabled(self, on: bool) -> None:
        self._chroma = on

    def set_params(self, p: ChromaParams) -> None:
        self._params = p

    def set_auto_key(self, on: bool) -> None:
        self._auto_key = on

    def current_params(self) -> ChromaParams:
        return self._params

    def _maybe_calibrate(self, frame: np.ndarray) -> None:
        if not (self._chroma and self._auto_key) or self._frames % self.AUTO_KEY_EVERY:
            return
        hue = estimate_key_hue(frame)
        if hue is not None and hue != self._params.key_hue:
            self._params = replace(self._params, key_hue=hue)
            self.keyHueDetected.emit(hue)

    def set_out_width(self, w: int) -> None:
        self._out_width = max(64, int(w))

    def stop(self) -> None:
        self._running = False
        self._abort = True
        self._stopped.set()

    def _open_with_retries(self) -> bool:
        """İlk açılış başarısızsa (ör. macOS izin penceresi henüz onaylanmadı) belirli aralıkla yeniden dener."""
        for attempt in range(self._open_retries + 1):
            if self._abort:
                return False
            if self._source.open():
                return True
            if attempt == self._open_retries:
                break
            waited = 0
            while waited < self._retry_ms and not self._abort:
                self.msleep(100)
                waited += 100
            if self._abort:
                return False
        return False

    def _reopen(self) -> bool:
        """Aynı kaynağı bırakıp tekrar aç; stop bekleme aralığını anında keser."""
        self.cameraError.emit("Kamera bekleniyor…")
        self._release()
        while not self._stopped.wait(self._retry_ms / 1000):
            try:
                if self._source.open():
                    return not self._abort
            except Exception as err:  # noqa: BLE001
                crash_log.log_handled(err, "kamera yeniden bağlantısı")
            self._release()
        return False

    def _deliver(self, frame: np.ndarray) -> None:
        frame = resize_to_width(frame, min(self._out_width, int(frame.shape[1])))
        try:
            self._maybe_calibrate(frame)
        except Exception as err:  # noqa: BLE001 - ton ölçülemezse eski ton kalır; kare yine gösterilir
            crash_log.log_handled(err, "perde tonu ölçümü")
        self._frames += 1
        if self._chroma:
            self.frameReady.emit(to_qimage_bgra(apply_chroma_key_bgra(frame, self._params)))
        else:
            self.frameReady.emit(to_qimage_bgr(frame))

    def _release(self) -> None:
        try:
            self._source.release()
        except Exception as err:  # noqa: BLE001 - kapanıştaki sürücü hatası da iş parçacığından kaçmasın
            crash_log.log_handled(err, "kamera kapanışı")

    def run(self) -> None:
        # run()'dan kaçan istisna PyQt6'da qFatal ile uygulamayı (süren kayıtla) düşürür, kanca kuruluyken de
        # iş parçacığı sessizce ölüp panel son karede donar. Her hata burada yakalanır: tek bozuk kare atlanır,
        # kalıcı hata panele anlaşılır cameraError olarak gider; ayrıntı (traceback) hatalar.log'a.
        self.launched.set()
        if self._abort:
            return
        try:
            opened = self._open_with_retries()
        except Exception as err:  # noqa: BLE001
            crash_log.log_handled(err, "kamera açılışı")
            self.cameraError.emit("Kamera açılamadı")
            self._release()
            return
        if self._abort:
            self._release()
            return
        if not opened:
            self.cameraError.emit("Kamera bulunamadı")
            return
        self._running = True
        misses, failures, announced = 0, 0, False
        last_frame = time.monotonic()
        try:
            while self._running and not self._abort:
                t0 = time.monotonic()
                try:
                    frame = self._source.read()
                    if frame is None:
                        misses += 1
                        if self._reconnect and self._frames:
                            if (time.monotonic() - last_frame) * 1000 >= self.FRAME_TIMEOUT_MS:
                                if not self._reopen():
                                    break
                                misses, failures, announced = 0, 0, False
                                last_frame = time.monotonic()
                        elif misses > 30:
                            self.cameraError.emit("Kamera akışı kesildi")
                            break
                        self.msleep(5)
                        continue
                    if self._abort:
                        break
                    misses = 0
                    if not announced:
                        self.opened.emit(int(frame.shape[1]), int(frame.shape[0]))
                        announced = True
                    self._deliver(frame)
                    last_frame = time.monotonic()
                    failures = 0
                except Exception as err:  # noqa: BLE001 - sürücü/OpenCV hatası: kare atlanır
                    failures += 1
                    if failures == 1:                  # aynı arıza dizisi günlüğe bir kez
                        crash_log.log_handled(err, "kamera karesi")
                    if failures > self.MAX_FRAME_ERRORS:
                        if self._reconnect and self._frames:
                            if not self._reopen():
                                break
                            misses, failures, announced = 0, 0, False
                            last_frame = time.monotonic()
                        else:
                            self.cameraError.emit("Kamera görüntüsü alınamadı")
                            break
                    self.msleep(5)
                    continue
                rest = self._period - (time.monotonic() - t0)
                if rest > 0:
                    self.msleep(int(rest * 1000))
        finally:
            self._release()
