"""Kamera keşfi: OpenCV ile indeksleri dener, kare veren cihazları listeler. Ad bilgisi OpenCV'de yoktur."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
import cv2  # noqa: E402


@dataclass(frozen=True)
class CameraInfo:
    index: int
    width: int
    height: int

    @property
    def label(self) -> str:
        return f"Kamera {self.index} ({self.width}×{self.height})"


def _backends() -> list[int]:
    if sys.platform == "win32":
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF]
    if sys.platform == "darwin":
        return [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    return [cv2.CAP_ANY]


def list_cameras(max_index: int = 6) -> list[CameraInfo]:
    """0..max_index-1 indekslerini dener; açılıp kare verenleri döndürür (her biri ~0,1-0,5 sn)."""
    log = cv2.utils.logging
    prev = log.getLogLevel()
    log.setLogLevel(log.LOG_LEVEL_SILENT)
    found: list[CameraInfo] = []
    try:
        for index in range(max_index):
            for backend in _backends():
                cap = cv2.VideoCapture(index, backend)
                ok = cap.isOpened()
                frame = None
                if ok:
                    ok, frame = cap.read()
                cap.release()
                if ok and frame is not None:
                    found.append(CameraInfo(index, int(frame.shape[1]), int(frame.shape[0])))
                    break
    finally:
        log.setLogLevel(prev)
    return found
