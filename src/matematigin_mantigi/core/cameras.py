"""Kamera keşfi: OpenCV ile indeksleri dener; doğrulanamayan adları eşleştirmez."""
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
        return f"{base} ({self.width}×{self.height})" if self.width > 0 and self.height > 0 else base


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


def _avfoundation_names() -> list[str]:
    """OpenCV cap_avfoundation_mac.mm sırası; ffmpeg'in aygıt sırası kullanılmaz."""
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeMuxed, AVMediaTypeVideo

        # https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm
        # OpenCV video ve ses+video (muxed) cihazlarını birlikte uniqueID'ye göre sıralar.
        devices = (list(AVCaptureDevice.devicesWithMediaType_(AVMediaTypeVideo))
                   + list(AVCaptureDevice.devicesWithMediaType_(AVMediaTypeMuxed)))
        return [str(device.localizedName()) for device in sorted(devices, key=lambda d: str(d.uniqueID()))]
    except Exception:  # noqa: BLE001 - PyObjC yoksa/izin sorgusu başarısızsa yalnız indeks gösterilir
        return []


def list_cameras(max_index: int = 6, names: list[str] | None = None, skip: set[int] | frozenset[int] = frozenset()) -> list[CameraInfo]:
    """0..max_index-1 indekslerini dener; açılıp kare verenleri döndürür (her biri ~0,1-0,5 sn).
    names geriye uyumluluk için kabul edilir ama kullanılmaz; macOS adları yalnız AVFoundation sırasından alınır."""
    log = cv2.utils.logging
    prev = log.getLogLevel()
    log.setLogLevel(log.LOG_LEVEL_SILENT)
    found: list[CameraInfo] = []
    verified_names = _avfoundation_names() if sys.platform == "darwin" else []
    try:
        for index in range(max_index):
            if index in skip:
                continue
            for backend in _backends():
                cap = cv2.VideoCapture(index, backend)
                ok = cap.isOpened()
                frame = None
                if ok:
                    ok, frame = cap.read()
                cap.release()
                if ok and frame is not None:
                    name = (verified_names[index] if backend == cv2.CAP_AVFOUNDATION
                            and index < len(verified_names) else "")
                    found.append(CameraInfo(index, int(frame.shape[1]), int(frame.shape[0]), name))
                    break
    finally:
        log.setLogLevel(prev)
    return found
