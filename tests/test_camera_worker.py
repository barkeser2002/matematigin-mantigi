import numpy as np
from PyQt6.QtGui import QImage

from conftest import FakeCamera
from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.camera_worker import CameraWorker, resize_to_width, to_qimage_bgr


def test_to_qimage_is_deep_copy():
    frame = np.zeros((10, 20, 3), np.uint8)
    img = to_qimage_bgr(frame)
    frame[:] = 255
    assert img.format() == QImage.Format.Format_BGR888
    assert img.width() == 20 and img.height() == 10
    assert img.pixelColor(0, 0).red() == 0


def test_resize_to_width_keeps_aspect():
    out = resize_to_width(np.zeros((240, 320, 3), np.uint8), 160)
    assert out.shape == (120, 160, 3)


def test_worker_emits_keyed_frames(qtbot, fake_camera):
    w = CameraWorker(fake_camera, ChromaParams(), chroma_enabled=True, out_width=160, target_fps=60)
    with qtbot.waitSignal(w.opened, timeout=2000) as opened:
        with qtbot.waitSignal(w.frameReady, timeout=2000) as sig:
            w.start()
    assert opened.args == [320, 240]
    img: QImage = sig.args[0]
    assert img.width() == 160 and img.hasAlphaChannel()
    assert img.pixelColor(2, 2).alpha() == 0                  # yeşil -> saydam; altındaki çizim görünür
    subject = img.pixelColor(80, 60)
    assert subject.alpha() == 255 and subject.name() == "#dc1414"   # kırmızı kutu korunur (BGR 20,20,220)
    w.stop(); assert w.wait(2000)
    assert fake_camera.released


def test_worker_auto_calibrates_key_hue(qtbot, fake_camera):
    w = CameraWorker(fake_camera, ChromaParams(key_hue=60), chroma_enabled=True, out_width=160, target_fps=60)
    with qtbot.waitSignal(w.keyHueDetected, timeout=2000) as sig:
        w.start()
    assert 55 <= sig.args[0] <= 62 and w.current_params().key_hue == sig.args[0]
    w.stop(); assert w.wait(2000)


def test_worker_raw_mode_keeps_green(qtbot, fake_camera):
    w = CameraWorker(fake_camera, ChromaParams(), chroma_enabled=False, out_width=160, target_fps=60)
    with qtbot.waitSignal(w.frameReady, timeout=2000) as sig:
        w.start()
    assert sig.args[0].pixelColor(2, 2).green() > 150
    w.stop(); assert w.wait(2000)


def test_dead_camera_reports_error_and_finishes(qtbot, dead_camera):
    w = CameraWorker(dead_camera, ChromaParams())
    with qtbot.waitSignal(w.cameraError, timeout=2000) as sig:
        w.start()
    assert "Kamera" in sig.args[0]
    assert w.wait(2000)


def test_opencv_source_scans_other_indices(monkeypatch):
    import cv2
    from matematigin_mantigi.ui import camera_worker as cw

    class FakeCapture:
        def __init__(self, index, backend):
            self.index = index
        def isOpened(self):
            return self.index == 1                     # sadece 1 numaralı kamera var
        def read(self):
            frame = np.zeros((4, 4, 3), np.uint8)
            return (True, frame) if self.index == 1 else (False, None)
        def release(self):
            pass

    monkeypatch.setattr(cv2, "VideoCapture", FakeCapture)
    src = cw.OpenCvSource(0)
    assert src.open() is True and src.index == 1
    src.release()
    dead = cw.OpenCvSource(5)
    monkeypatch.setattr(FakeCapture, "isOpened", lambda self: False)
    assert dead.open() is False


def test_stream_end_reports_error(qtbot):
    w = CameraWorker(FakeCamera(frames=2), ChromaParams(), target_fps=200)
    with qtbot.waitSignal(w.cameraError, timeout=5000) as sig:
        w.start()
    assert "kesildi" in sig.args[0]
    assert w.wait(2000)


def test_open_retries_until_camera_becomes_available(qtbot):
    class LateCamera(FakeCamera):
        def __init__(self):
            super().__init__(frames=1000); self.attempts = 0
        def open(self):
            self.attempts += 1
            if self.attempts < 3:
                return False
            return super().open()
    cam = LateCamera()
    w = CameraWorker(cam, ChromaParams(), open_retries=5, retry_ms=100, target_fps=60)
    with qtbot.waitSignal(w.frameReady, timeout=3000):
        w.start()
    assert cam.attempts == 3
    w.stop(); assert w.wait(2000)


def test_stop_aborts_open_retries(qtbot, dead_camera):
    w = CameraWorker(dead_camera, ChromaParams(), open_retries=100, retry_ms=1000)
    w.start(); qtbot.wait(150)
    w.stop()
    assert w.wait(2000)
