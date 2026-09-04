"""Kamera iş parçacığı: OpenCV yakalama -> (isteğe bağlı) yeşil perde -> QImage sinyali."""
from __future__ import annotations

import sys
import time
from typing import Protocol

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.chroma_key import ChromaParams, apply_chroma_key


class FrameSource(Protocol):
    def open(self) -> bool: ...
    def read(self) -> np.ndarray | None: ...
    def release(self) -> None: ...


class OpenCvSource:
    def __init__(self, index: int = 0):
        self.index = index
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
        for backend in backends:                      # DSHOW hızlı açılır; olmazsa varsayılan (MSMF/AVFoundation)
            cap = cv2.VideoCapture(self.index, backend)
            if cap.isOpened():
                self._cap = cap
                return True
            cap.release()
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


def resize_to_width(frame: np.ndarray, width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w == width:
        return frame
    return cv2.resize(frame, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)


class CameraWorker(QThread):
    frameReady = pyqtSignal(QImage)
    cameraError = pyqtSignal(str)
    opened = pyqtSignal(int, int)

    def __init__(self, source: FrameSource, params: ChromaParams, chroma_enabled: bool = True,
                 out_width: int = 640, target_fps: int = 30, parent=None):
        super().__init__(parent)
        self._source = source
        self._params = params
        self._chroma = chroma_enabled
        self._out_width = out_width
        self._period = 1.0 / max(1, target_fps)
        self._running = False

    def set_chroma_enabled(self, on: bool) -> None:
        self._chroma = on

    def set_params(self, p: ChromaParams) -> None:
        self._params = p

    def set_out_width(self, w: int) -> None:
        self._out_width = max(64, int(w))

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if not self._source.open():
            self.cameraError.emit("Kamera bulunamadı")
            return
        self._running = True
        misses, announced = 0, False
        try:
            while self._running:
                t0 = time.monotonic()
                frame = self._source.read()
                if frame is None:
                    misses += 1
                    if misses > 30:
                        self.cameraError.emit("Kamera akışı kesildi")
                        break
                    self.msleep(5)
                    continue
                misses = 0
                if not announced:
                    self.opened.emit(int(frame.shape[1]), int(frame.shape[0]))
                    announced = True
                frame = resize_to_width(frame, self._out_width)
                if self._chroma:
                    frame = apply_chroma_key(frame, self._params)
                self.frameReady.emit(to_qimage_bgr(frame))
                rest = self._period - (time.monotonic() - t0)
                if rest > 0:
                    self.msleep(int(rest * 1000))
        finally:
            self._source.release()
