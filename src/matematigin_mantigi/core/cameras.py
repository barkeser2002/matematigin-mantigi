"""Kamera keşfi: OpenCV ile indeksleri dener, kare veren cihazları listeler. Adlar ffmpeg'in aygıt
listesinden alınır (macOS avfoundation, Windows dshow); OpenCV ad vermez."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
import cv2  # noqa: E402

from matematigin_mantigi.core.recorder import no_window  # noqa: E402


@dataclass(frozen=True)
class CameraInfo:
    index: int
    width: int
    height: int
    name: str = ""

    @property
    def label(self) -> str:
        base = f"{self.index}: {self.name}" if self.name else f"Kamera {self.index}"
        return f"{base} ({self.width}×{self.height})"


def _backends() -> list[int]:
    if sys.platform == "win32":
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF]
    if sys.platform == "darwin":
        return [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY]
    return [cv2.CAP_ANY]


def list_camera_names(exe: str | None = None, platform: str | None = None, runner=None) -> list[str]:
    """ffmpeg'in gördüğü video aygıt adları, indeks sırasıyla. macOS: avfoundation, Windows: dshow."""
    platform = platform or sys.platform
    if exe is None and runner is None:
        try:
            from matematigin_mantigi.core.recorder import find_ffmpeg
            exe = find_ffmpeg()
        except Exception:  # noqa: BLE001
            exe = None
        if not exe:
            return []
    if platform == "darwin":
        cmd = [exe, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""]
    elif platform == "win32":
        cmd = [exe, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
    else:
        return []
    runner = runner or (lambda c: subprocess.run(c, capture_output=True, text=True, encoding="utf-8",
                                                 errors="replace", timeout=15, **no_window()).stderr)
    try:
        text = runner(cmd)
    except (OSError, subprocess.SubprocessError):
        return []
    names: list[str] = []
    if platform == "darwin":
        in_video = False
        for line in text.splitlines():
            if "video devices" in line:
                in_video = True
                continue
            if "audio devices" in line:
                break
            m = re.search(r"\[(\d+)\]\s+(.+)$", line) if in_video else None
            if m:
                names.append(m.group(2).strip())
    else:
        for line in text.splitlines():
            m = re.search(r'"([^"]+)"\s+\((video|video, audio)\)', line)
            if m:
                names.append(m.group(1))
    return names


def list_cameras(max_index: int = 6, names: list[str] | None = None) -> list[CameraInfo]:
    """0..max_index-1 indekslerini dener; açılıp kare verenleri döndürür (her biri ~0,1-0,5 sn).
    names verilmezse ffmpeg'den alınır; indeks sırası aygıt listesiyle eşleşir."""
    if names is None:
        names = list_camera_names()
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
                    name = names[index] if index < len(names) else ""
                    found.append(CameraInfo(index, int(frame.shape[1]), int(frame.shape[0]), name))
                    break
    finally:
        log.setLogLevel(prev)
    return found
