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
    assert img.width() == 160
    assert img.pixelColor(2, 2).name() == "#ffffff"          # yeşil -> beyaz tahta zemini
    assert img.pixelColor(80, 60).name() == "#dc1414"        # kırmızı kutu korunur (BGR 20,20,220)
    w.stop(); assert w.wait(2000)
    assert fake_camera.released


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


def test_stream_end_reports_error(qtbot):
    w = CameraWorker(FakeCamera(frames=2), ChromaParams(), target_fps=200)
    with qtbot.waitSignal(w.cameraError, timeout=5000) as sig:
        w.start()
    assert "kesildi" in sig.args[0]
    assert w.wait(2000)
