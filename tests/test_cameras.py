import numpy as np


def test_list_cameras_reports_frame_giving_indices(monkeypatch):
    import cv2
    from matematigin_mantigi.core import cameras

    class FakeCapture:
        def __init__(self, index, backend):
            self.index = index
        def isOpened(self):
            return self.index in (1, 3)
        def read(self):
            return (True, np.zeros((480, 640, 3), np.uint8)) if self.index in (1, 3) else (False, None)
        def release(self):
            pass

    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    cams = cameras.list_cameras(names=[], max_index=5)
    assert [(c.index, c.width, c.height) for c in cams] == [(1, 640, 480), (3, 640, 480)]
    assert cams[0].label == "Kamera 1 (640×480)"


def test_list_cameras_empty(monkeypatch):
    import cv2
    from matematigin_mantigi.core import cameras

    class Dead:
        def __init__(self, *a): pass
        def isOpened(self): return False
        def read(self): return (False, None)
        def release(self): pass

    monkeypatch.setattr(cv2, "VideoCapture", Dead)
    assert cameras.list_cameras(names=[], max_index=3) == []


def test_list_camera_names_parses_mac_and_windows():
    from matematigin_mantigi.core.cameras import list_camera_names
    mac = ("[AVFoundation indev @ 0x1] AVFoundation video devices:\n[AVFoundation indev @ 0x1] [0] OBS Virtual Camera\n"
           "[AVFoundation indev @ 0x1] [1] FaceTime HD Camera\n[AVFoundation indev @ 0x1] [2] Capture screen 0\n"
           "[AVFoundation indev @ 0x1] AVFoundation audio devices:\n[AVFoundation indev @ 0x1] [0] MacBook Pro Microphone\n")
    assert list_camera_names("ffmpeg", platform="darwin", runner=lambda c: mac) == \
        ["OBS Virtual Camera", "FaceTime HD Camera", "Capture screen 0"]
    win = ('[dshow @ 0] "OBS Virtual Camera" (video)\n[dshow @ 0]   Alternative name "@device_pnp_x"\n'
           '[dshow @ 0] "Mikrofon (USB)" (audio)\n[dshow @ 0] "HD Pro Webcam C920" (video)\n')
    assert list_camera_names("ffmpeg", platform="win32", runner=lambda c: win) == ["OBS Virtual Camera", "HD Pro Webcam C920"]
    assert list_camera_names("ffmpeg", platform="linux", runner=lambda c: "") == []


def test_camera_info_label_with_name():
    from matematigin_mantigi.core.cameras import CameraInfo
    assert CameraInfo(1, 1280, 720, "FaceTime HD Camera").label == "1: FaceTime HD Camera (1280×720)"
    assert CameraInfo(0, 640, 480).label == "Kamera 0 (640×480)"


def test_list_camera_names_hides_the_ffmpeg_console_window_on_windows(monkeypatch):
    """#10: paketli Windows uygulamasında kamera adları için koşan ffmpeg konsol penceresi açmaz."""
    import subprocess
    import sys
    from matematigin_mantigi.core.cameras import list_camera_names
    seen = []

    def run(cmd, **k):
        seen.append(k)
        return subprocess.CompletedProcess(cmd, 1, "", '[dshow @ 0] "HD Pro Webcam C920" (video)\n')
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", run)
    assert list_camera_names("ffmpeg", platform="win32") == ["HD Pro Webcam C920"]
    assert len(seen) == 1 and seen[0].get("creationflags") == 0x08000000, seen
