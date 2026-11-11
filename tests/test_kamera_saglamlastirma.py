"""Kamera sağlamlaştırması: donanımsız, açıkça durdurulan iş parçacıkları."""
from threading import Event

import numpy as np
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.camera_worker import CameraWorker
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.webcam_panel import CameraView, WebcamPanel


class Camera:
    def __init__(self):
        self.opens = 0
        self.releases = 0
        self.frame = np.zeros((90, 160, 3), np.uint8)

    def open(self):
        self.opens += 1
        return True

    def read(self):
        return self.frame

    def release(self):
        self.releases += 1


def panel_for(qtbot, camera):
    panel = WebcamPanel(FontFamilies("Arial", "Arial", False), lambda: camera,
                        ChromaParams(), chroma_enabled=False)
    qtbot.addWidget(panel)
    return panel


def stop(worker):
    worker.stop()
    assert worker.wait(2000)


def test_stop_before_thread_start_is_not_lost(qtbot):
    camera = Camera()
    worker = CameraWorker(camera, ChromaParams())
    worker.stop()
    try:
        worker.start()
        qtbot.waitUntil(lambda: worker.isFinished() or camera.opens > 0)
        assert camera.opens == 0, "Başlamadan gelen stop kamera açılmasını engellemeli"
        assert worker.wait(1000)
    finally:
        stop(worker)


def test_stop_during_open_does_not_resume_frame_delivery(qtbot):
    entered, proceed = Event(), Event()

    class Opening(Camera):
        def open(self):
            entered.set()
            assert proceed.wait(2)
            return super().open()

    camera = Opening()
    worker = CameraWorker(camera, ChromaParams(), chroma_enabled=False)
    frames = []
    worker.frameReady.connect(frames.append)
    try:
        worker.start()
        qtbot.waitUntil(entered.is_set)
        worker.stop()
        proceed.set()
        assert worker.wait(1000), "Açılış sırasında stop alınmışsa döngü başlamamalı"
        qtbot.waitUntil(worker.isFinished)
        assert frames == []
        assert camera.releases == 1
    finally:
        proceed.set()
        stop(worker)


def test_panel_restarts_after_clean_shutdown(qtbot):
    panel = panel_for(qtbot, Camera())
    frames = []
    panel.frameReady.connect(frames.append)
    try:
        panel.start()
        qtbot.waitUntil(lambda: len(frames) > 0)
        panel.shutdown()
        count = len(frames)
        panel.start()
        qtbot.waitUntil(lambda: len(frames) > count, timeout=1000)
        assert panel.worker.isRunning()
    finally:
        panel.shutdown()
        stop(panel.worker)
