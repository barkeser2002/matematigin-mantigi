import numpy as np
import pytest
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


# --- run() içindeki hatalar iş parçacığını sessizce öldürmesin (#3) ------------------------------------------
class _BrokenCamera(FakeCamera):
    """mode='read': sürücü her karede istisna fırlatır (ör. cv2.error); mode='frame': kare bozuk (tek kanallı),
    işlerken OpenCV patlar; mode='open': açılış istisna fırlatır."""

    def __init__(self, mode: str):
        super().__init__(frames=10_000)
        self.mode = mode

    def open(self) -> bool:
        if self.mode == "open":
            raise RuntimeError("yapay açılış hatası")
        return super().open()

    def read(self):
        if self.mode == "read":
            import cv2
            raise cv2.error("yapay sürücü hatası")
        frame = super().read()
        return frame[:, :, 0] if frame is not None else None    # (h, w): BGR beklenen yerde tek kanal


@pytest.mark.parametrize("mode", ["read", "frame"])
def test_persistent_frame_error_is_reported_and_thread_ends_cleanly(qtbot, mode):
    """run() korumasızdı: sürücü/OpenCV istisnası iş parçacığından kaçıyor, PyQt6 qFatal ile uygulamayı (süren
    kayıtla) düşürüyordu; kanca kuruluyken de panel son karede donup kalırdı. Artık art arda bozuk karelerden sonra
    anlaşılır cameraError ve kaynak bırakılır."""
    cam = _BrokenCamera(mode)
    w = CameraWorker(cam, ChromaParams(), out_width=160, target_fps=200)
    with qtbot.waitSignal(w.cameraError, timeout=5000) as sig:
        w.start()
    assert sig.args[0] == "Kamera görüntüsü alınamadı"
    assert w.wait(2000) and cam.released


def test_single_bad_frame_is_skipped_and_stream_continues(qtbot):
    """Tek bir bozuk kare akışı öldürmesin: atlanır, sonraki karelerle görüntü sürer."""
    class Glitch(FakeCamera):
        def __init__(self):
            super().__init__(frames=10_000); self.calls = 0

        def read(self):
            self.calls += 1
            if self.calls == 3:
                raise ValueError("tek bozuk kare")
            return super().read()
    w = CameraWorker(Glitch(), ChromaParams(), out_width=160, target_fps=200)
    frames, errors = [], []
    w.frameReady.connect(lambda _img: frames.append(1))
    w.cameraError.connect(errors.append)
    w.start()
    qtbot.waitUntil(lambda: len(frames) >= 10, timeout=3000)
    assert errors == [] and w.isRunning()
    w.stop(); assert w.wait(2000)


def test_open_exception_is_reported_and_thread_ends(qtbot):
    cam = _BrokenCamera("open")
    w = CameraWorker(cam, ChromaParams())
    with qtbot.waitSignal(w.cameraError, timeout=3000) as sig:
        w.start()
    assert sig.args[0] == "Kamera açılamadı"
    assert w.wait(2000)


@pytest.fixture
def crash_logged(tmp_path):
    """Hata kancası tmp_path'e kurulur; sys/threading kancaları (global durum) test sonunda geri gelir."""
    import sys
    import threading
    from matematigin_mantigi.core import crash_log
    prev = (sys.excepthook, threading.excepthook)
    notes = []
    log = crash_log.install(tmp_path / "hatalar.log", notify=lambda *a: notes.append(a))
    yield log, notes
    crash_log.uninstall(log)
    sys.excepthook, threading.excepthook = prev


def test_handled_camera_error_is_logged_but_never_reaches_the_excepthook(qtbot, crash_logged):
    """Kendi hatasını yakalayan yol hatayı kancaya bırakmaz (uyarı kutusu açılmaz); ayrıntı yine hatalar.log'da."""
    log, notes = crash_logged
    w = CameraWorker(_BrokenCamera("read"), ChromaParams(), target_fps=200)
    with qtbot.waitSignal(w.cameraError, timeout=5000):
        w.start()
    assert w.wait(2000)
    text = log.path.read_text(encoding="utf-8")
    assert "yakalanan hata (kamera" in text and "yapay sürücü hatası" in text
    assert text.count("Traceback (most recent call last)") == 1         # 31 bozuk kare, tek kayıt
    assert notes == []


def test_failing_key_hue_estimate_does_not_stop_the_stream(qtbot, monkeypatch):
    """Perde tonu ölçümü patlarsa yalnız ölçüm atlanır: kare yine gösterilir, akış durmaz (ölçüm her karede yeniden
    denenip 30 kare sonra kamerayı 'alınamadı' diye kapatmamalı)."""
    from matematigin_mantigi.ui import camera_worker as cw

    def boom(_frame):
        raise ValueError("yapay ölçüm hatası")
    monkeypatch.setattr(cw, "estimate_key_hue", boom)
    w = CameraWorker(FakeCamera(frames=10_000), ChromaParams(), out_width=160, target_fps=200)
    frames, errors = [], []
    w.frameReady.connect(lambda _img: frames.append(1))
    w.cameraError.connect(errors.append)
    w.start()
    qtbot.waitUntil(lambda: len(frames) >= 60, timeout=5000)
    assert errors == []
    w.stop(); assert w.wait(2000)
