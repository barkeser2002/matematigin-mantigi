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

    def open(self) -> bool:
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


def test_panel_start_acknowledges_launch_without_waiting_for_driver(qtbot):
    entered, proceed = Event(), Event()

    class Opening(Camera):
        def open(self) -> bool:
            entered.set()
            assert proceed.wait(3)
            return super().open()

    panel = panel_for(qtbot, Opening())
    try:
        panel.start()
        assert entered.is_set(), "start döndüğünde işçi açılış aşamasına ulaşmalı"
        assert not proceed.is_set(), "start sürücünün açılmasını beklememeli"
    finally:
        proceed.set()
        panel.shutdown()
        stop(panel.worker)


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


def test_dropout_reconnects_same_source_and_clears_both_views(qtbot, monkeypatch):
    monkeypatch.setattr(CameraWorker, "FRAME_TIMEOUT_MS", 60, raising=False)

    class Dropping(Camera):
        def __init__(self):
            super().__init__()
            self.lost = Event()
            self.available = Event()
            self.indices = []

        def open(self):
            self.indices.append(7)
            super().open()
            return self.opens == 1 or self.available.is_set()

        def read(self):
            if self.lost.is_set() and self.opens == 1:
                return None
            return super().read()

    camera = Dropping()
    panel = panel_for(qtbot, camera)
    panel.worker._retry_ms = 100
    preview = CameraView()
    qtbot.addWidget(preview)
    panel.frameReady.connect(preview.set_frame)
    panel.placeholderChanged.connect(preview.set_placeholder)
    try:
        panel.start()
        qtbot.waitUntil(lambda: preview._frame is not None)
        camera.lost.set()
        qtbot.waitUntil(lambda: panel.view._frame is None and preview._frame is None, timeout=3000)
        assert panel.view.placeholder_text == preview.placeholder_text == "Kamera bekleniyor…"
        assert not panel.has_camera
        qtbot.waitUntil(lambda: camera.opens >= 2)
        assert camera.releases >= 1
        camera.available.set()
        qtbot.waitUntil(lambda: panel.has_camera and preview._frame is not None, timeout=1500)
        assert panel.view.placeholder_text == preview.placeholder_text == ""
        assert panel.worker.isRunning()
        assert set(camera.indices) == {7}
    finally:
        panel.shutdown()
        stop(panel.worker)


def test_blocking_driver_clears_stale_frames_before_read_returns(qtbot, monkeypatch):
    monkeypatch.setattr(CameraWorker, "FRAME_TIMEOUT_MS", 70)
    entered, proceed = Event(), Event()

    class Blocking(Camera):
        def read(self):
            if entered.is_set():
                assert proceed.wait(3)
            else:
                entered.set()
            return super().read()

    panel = panel_for(qtbot, Blocking())
    preview = CameraView()
    qtbot.addWidget(preview)
    panel.frameReady.connect(preview.set_frame)
    panel.placeholderChanged.connect(preview.set_placeholder)
    try:
        panel.start()
        qtbot.waitUntil(lambda: preview._frame is not None)
        qtbot.waitUntil(lambda: preview._frame is None, timeout=600)
        assert not proceed.is_set(), "Durum sürücünün dönmesini beklememeli"
        assert panel.view._frame is None
        assert preview.placeholder_text == "Kamera bekleniyor…"
        proceed.set()
        qtbot.waitUntil(lambda: preview._frame is not None)
        assert preview.placeholder_text == ""
    finally:
        proceed.set()
        panel.shutdown()
        stop(panel.worker)


def test_stop_interrupts_reconnect_backoff(qtbot, monkeypatch):
    monkeypatch.setattr(CameraWorker, "FRAME_TIMEOUT_MS", 40)

    class Lost(Camera):
        def read(self):
            return self.frame if self.opens == 1 and not lost.is_set() else None

    lost = Event()
    panel = panel_for(qtbot, Lost())
    panel.worker._retry_ms = 30000
    try:
        panel.start()
        qtbot.waitUntil(lambda: panel.view._frame is not None)
        lost.set()
        qtbot.waitUntil(lambda: panel.view._frame is None)
        panel.worker.stop()
        assert panel.worker.wait(300), "stop yeniden deneme aralığını beklememeli"
    finally:
        panel.shutdown()
        stop(panel.worker)
