"""Büyük önizleme kayıt kamerasının iş yükünü ve bekleyen kareleri büyütmez."""
import time
from threading import Event

import numpy as np
import pytest
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.camera_worker import CameraWorker
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.webcam_panel import WebcamPanel, CameraView


class Camera:
    def __init__(self):
        self.frame = np.full((720, 1280, 3), 120, np.uint8)
        self.reads = 0
        self.opens = 0

    def open(self):
        self.opens += 1
        return True

    def read(self):
        self.reads += 1
        return self.frame

    def release(self):
        pass


def test_large_preview_keeps_keying_work_bounded_in_worker(qtbot, monkeypatch):
    from matematigin_mantigi.ui import camera_worker as module
    sizes = []
    original = module.apply_chroma_key_bgra

    def key(frame, params):
        sizes.append(frame.shape[1])
        return original(frame, params)

    monkeypatch.setattr(module, 'apply_chroma_key_bgra', key)
    worker = CameraWorker(Camera(), ChromaParams(), out_width=1920, auto_key=False)
    worker._deliver(np.zeros((720, 1280, 3), np.uint8))
    assert max(sizes) <= 640, 'Önizleme yeşil perdeyi 720p/1080p boyutuna çıkarmamalı'


@pytest.mark.parametrize('chroma', [True, False])
def test_worker_prepares_premultiplied_frames_before_gui_paint(qtbot, chroma):
    worker = CameraWorker(Camera(), ChromaParams(), chroma_enabled=chroma, out_width=160)
    images = []
    worker.frameReady.connect(images.append)
    worker._deliver(np.zeros((90, 160, 3), np.uint8))
    assert images[0].format() == QImage.Format.Format_ARGB32_Premultiplied


def test_keyed_preview_does_not_increase_recorded_camera_work(qtbot):
    camera = Camera()
    panel = WebcamPanel(FontFamilies('Arial', 'Arial', False), lambda: camera,
                        ChromaParams(), chroma_enabled=True)
    qtbot.addWidget(panel)
    panel.resize(320, 240)
    panel.show()
    preview = CameraView()
    qtbot.addWidget(preview)
    preview.resize(1920, 1080)
    panel.frameReady.connect(preview.set_frame)
    preview.show()
    try:
        panel.start()
        qtbot.waitUntil(lambda: preview._frame is not None)
        qtbot.waitUntil(lambda: panel.worker._out_width == panel._output_width())
        assert panel.worker._out_width <= round(panel.width() * panel.devicePixelRatioF())
        panel.set_chroma_enabled(False)
        assert panel.worker._out_width >= round(preview.width() * preview.devicePixelRatioF())
        panel.set_chroma_enabled(True)
        assert panel.worker._out_width <= round(panel.width() * panel.devicePixelRatioF())
    finally:
        panel.shutdown()
        assert panel.worker.wait(2000)


def test_external_preview_coalesces_repaints_but_keeps_latest_frame(qtbot, monkeypatch):
    from matematigin_mantigi.ui.main_window import _Preview
    preview = _Preview()
    qtbot.addWidget(preview)
    updates = []
    monkeypatch.setattr(preview, 'update', lambda: updates.append(preview._frame))
    for value in range(20):
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.fill(value)
        preview.set_frame(image)
    assert not updates, 'Tam ekran önizleme her kamera karesinde pahalı yeniden çizim istememeli'
    qtbot.waitUntil(lambda: len(updates) == 1)
    assert updates[0] is image
    preview.set_placeholder('Kamera bekleniyor…')
    assert preview._frame is None
    assert updates[-1] is None, 'Kopma durumu çizim sınırını beklememeli'


def test_external_preview_uses_fast_scaling_without_changing_board(qtbot):
    from PyQt6.QtGui import QColor
    from matematigin_mantigi.ui.main_window import _Preview

    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(QColor('blue'))
    image.setPixelColor(0, 0, QColor('red'))
    image.setPixelColor(0, 1, QColor('red'))
    views = [CameraView(), _Preview()]
    reds = []
    for view in views:
        qtbot.addWidget(view)
        view.resize(200, 200)
        view.set_frame(image)
        view.show()
        # Yakın komşu ölçekleme renkleri karıştırmaz; tahta yumuşak yolu korur.
        rendered = view.grab().toImage()
        dpr = rendered.devicePixelRatio()
        reds.append(rendered.pixelColor(round(99 * dpr), round(180 * dpr)).red())
    assert 0 < reds[0] < 255
    assert reds[1] == 255, 'Büyük harici önizleme GUI üzerinde bilinear ölçeklenmemeli'


def test_preview_limits_bursts_to_30_hz_and_stops_without_new_frames(qtbot, monkeypatch):
    from matematigin_mantigi.ui import main_window as module

    clock = [100.0]
    monkeypatch.setattr(module, 'monotonic', lambda: clock[0])
    preview = module._Preview()
    qtbot.addWidget(preview)
    updates = []
    monkeypatch.setattr(preview, 'update', lambda: updates.append(preview._frame))
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(0)
    preview.set_frame(image)
    qtbot.waitUntil(lambda: len(updates) == 1)
    assert not preview._paint_timer.isActive(), 'Yeni kare olmadan periyodik çizim yapılmamalı'
    clock[0] += .010
    preview.set_frame(image)
    assert 23 <= preview._paint_timer.interval() <= 24, \
        'Her kareye sabit gecikme değil 30 Hz bütçesinden kalan süre uygulanmalı'
    latest = image.copy()
    preview.set_frame(latest)
    qtbot.waitUntil(lambda: len(updates) == 2)
    assert updates[-1] is latest
    assert not preview._paint_timer.isActive()
    preview.set_frame(image)
    preview.set_placeholder('Kamera bekleniyor…')
    assert not preview._paint_timer.isActive()
    assert updates[-1] is None


def test_worker_prepares_small_panel_image_without_losing_hd_preview(qtbot):
    worker = CameraWorker(Camera(), ChromaParams(), chroma_enabled=False, out_width=1280,
                          render_width=160)
    worker._deliver(np.full((720, 1280, 3), (50, 100, 200), np.uint8))
    panel_image, preview_image = worker.take_latest_frame()
    assert (panel_image.width(), panel_image.height()) == (160, 90)
    assert preview_image.width() == 1280
    assert panel_image.pixelColor(0, 0) == preview_image.pixelColor(0, 0)
    assert worker.take_latest_frame() is None


def test_panel_render_size_tracks_inner_view_resize(qtbot):
    panel = WebcamPanel(FontFamilies('Arial', 'Arial', False), Camera, ChromaParams(),
                        chroma_enabled=False)
    qtbot.addWidget(panel)
    panel.resize(400, 300)
    panel.show()
    panel.view.resize(200, 100)
    assert panel.worker._render_width == round(panel.view.width() * panel.view.devicePixelRatioF())


def test_mailbox_replaces_old_frames_and_rearms_after_consumption(qtbot):
    worker = CameraWorker(Camera(), ChromaParams(), chroma_enabled=False, out_width=160)
    notifications = []
    worker.frameAvailable.connect(lambda: notifications.append(None))
    for value in range(7):
        worker._deliver(np.full((90, 160, 3), value, np.uint8))
    assert len(notifications) == 1
    packet = worker.take_latest_frame()
    assert packet is not None
    assert packet[1].pixelColor(0, 0).red() == 6
    worker._deliver(np.full((90, 160, 3), 7, np.uint8))
    assert len(notifications) == 2
    packet = worker.take_latest_frame()
    assert packet is not None
    assert packet[1].pixelColor(0, 0).red() == 7


def test_slow_gui_receives_only_latest_camera_frame(qtbot):
    camera = Camera()
    panel = WebcamPanel(FontFamilies('Arial', 'Arial', False), lambda: camera,
                        ChromaParams(), chroma_enabled=False)
    qtbot.addWidget(panel)
    frames = []
    panel.frameReady.connect(frames.append)
    try:
        panel.start()
        qtbot.waitUntil(lambda: len(frames) >= 1)
        frames.clear()
        # Olay döngüsü kasıtlı durur: işçi beş kare işlerken GUI eski kareleri biriktirmemeli.
        first = camera.reads
        deadline = time.monotonic() + 3
        while camera.reads < first + 5 and time.monotonic() < deadline:
            time.sleep(.01)
        assert camera.reads >= first + 5
        panel.worker.stop()
        assert panel.worker.wait(2000)
        QCoreApplication.processEvents()
        assert len(frames) == 1, 'GUI bloke iken gelen eski kareler sırayla oynatılmamalı'
    finally:
        panel.shutdown()
        assert panel.worker.wait(2000)


def test_moving_preview_within_second_screen_does_not_stop_recording(window, qtbot,
                                                                    monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState
    from test_recorder import small_synthetic_grabber
    from test_preview_regressions import open_preview

    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: QMessageBox.StandardButton.Ok)
    window.settings.audio_device = None
    window.settings.record_fps = 30
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / 'kayit', fps=30,
                                      grabber=small_synthetic_grabber, out_height=0)
    camera = Camera()
    window.webcam_panel.set_source_factory(lambda: camera)
    preview = open_preview(window, monkeypatch)
    ticks = []

    def tick():
        ticks.append(None)

    window._geometry_timer.timeout.connect(tick)
    try:
        qtbot.waitUntil(lambda: preview._frame is not None)
        window.toggle_recording(True)
        assert window.recorder.state is RecorderState.RECORDING
        preview.move(preview.x() + 10, preview.y() + 10)
        qtbot.waitUntil(lambda: len(ticks) >= 3, timeout=5000)
        assert window.recorder.state is RecorderState.RECORDING
        assert not window._geometry_interrupted
        assert camera.opens == 1, 'Önizleme taşımak kamerayı yeniden açmamalı'
        assert window.recorder.frames_written > 0
    finally:
        if window.recorder.state is RecorderState.RECORDING:
            window.toggle_recording(False)
        qtbot.waitUntil(lambda: window._stop_worker is None, timeout=15000)
        window.webcam_panel.shutdown()
        assert window.webcam_panel.worker.wait(2000)


def test_recording_external_preview_paints_at_camera_rate(window, qtbot, monkeypatch,
                                                         tmp_path):
    """Teslimi değil gerçekten çizilen farklı kareleri RECORDING aralığında ölç."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState
    from test_recorder import small_synthetic_grabber
    from test_preview_regressions import open_preview

    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: QMessageBox.StandardButton.Ok)
    window.settings.audio_device = None
    window.settings.record_fps = 30
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / 'kayit', fps=30,
                                      grabber=small_synthetic_grabber, out_height=0)
    camera = Camera()
    # Küçük kaynak zamanlayıcı regresyonunu sunucunun HSV/HD işlem hızından ayırır.
    camera.frame = np.full((90, 160, 3), (30, 200, 40), np.uint8)
    panel = window.webcam_panel
    panel.set_source_factory(lambda: camera)
    preview = open_preview(window, monkeypatch)
    area = window._preview_screen.availableGeometry()
    # Çizim boyutunu da sınırla: macOS offscreen DPR=2'de 800×800 pencere
    # 1600×1600 raster işine dönüşüp zamanlayıcı regresyonunu gölgeleyebilir.
    preview.setGeometry(area.x(), area.y(), 320, 180)
    counts = {'board': 0, 'preview': 0}
    painted = {'board': set(), 'preview': set()}
    sampling = False
    real_board = panel.view.set_frame
    real_paint = CameraView.paintEvent

    def board_frame(image):
        real_board(image)
        if sampling and window.recorder.state is RecorderState.RECORDING:
            counts['board'] += 1

    def preview_frame(image):
        assert preview._frame.cacheKey() == image.cacheKey()
        if sampling and window.recorder.state is RecorderState.RECORDING:
            counts['preview'] += 1

    def paint(view, event):
        real_paint(view, event)
        if sampling and window.recorder.state is RecorderState.RECORDING and view._frame is not None:
            name = 'preview' if view is preview else 'board' if view is panel.view else None
            if name:
                painted[name].add(view._frame.cacheKey())

    monkeypatch.setattr(panel.view, 'set_frame', board_frame)
    monkeypatch.setattr(CameraView, 'paintEvent', paint)
    # Gerçek önizleme yuvasından sonra aynı cacheKey'in teslim edildiğini doğrula.
    panel.frameReady.connect(preview_frame)
    try:
        panel.start()
        qtbot.waitUntil(lambda: preview._frame is not None, timeout=5000)
        window.toggle_recording(True)
        assert window.recorder.state is RecorderState.RECORDING
        worker = panel.worker
        # Isınma sonrası iki saniyelik, hassas zamanlayıcılı ortak ölçüm aralığı.
        qtbot.waitUntil(lambda: window.recorder.frames_written >= 5, timeout=5000)
        done = []
        timer = QTimer(window)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: done.append(True))
        start = time.monotonic()
        sampling = True
        timer.start(2200)
        qtbot.waitUntil(lambda: bool(done), timeout=10000)
        sampling = False  # finalize sırasında gelen kareleri sayma
        elapsed = time.monotonic() - start
        fps = {name: len(keys) / elapsed for name, keys in painted.items()}
        delivered_fps = {name: count / elapsed for name, count in counts.items()}
        print({'drawn_fps': fps, 'delivered_fps': delivered_fps, 'seconds': elapsed})
        assert window.recorder.state is RecorderState.RECORDING
        assert counts['preview'] == counts['board']
        assert delivered_fps['preview'] >= 20
        assert fps['board'] >= 20
        assert fps['preview'] >= max(20, fps['board'] * .70), \
            'Harici görünüm 10 Hz ile değil kamera hızına yakın çizilmeli'
        assert fps['preview'] <= 32, 'Harici çizim yaklaşık 30 Hz tavanını aşmamalı'
        assert panel.worker is worker and camera.opens == 1
        assert not window._geometry_interrupted
    finally:
        sampling = False
        if window.recorder.state is RecorderState.RECORDING:
            window.toggle_recording(False)
        qtbot.waitUntil(lambda: window._stop_worker is None, timeout=15000)
        panel.shutdown()
        assert panel.worker.wait(2000)


def test_recording_preview_preserves_live_frame_distribution(window, qtbot, monkeypatch,
                                                            tmp_path):
    """Gerçek kaydedici RECORDING iken her iki set_frame çağrısını say; süreye göre hız eşiği koyma."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState
    from matematigin_mantigi.ui import camera_worker as module
    from test_recorder import small_synthetic_grabber
    from test_preview_regressions import open_preview

    monkeypatch.setattr(QMessageBox, 'question', lambda *a: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *a: QMessageBox.StandardButton.Ok)
    window.resize(500, 400)
    window.move(0, 0)
    window.settings.audio_device = None
    window.settings.record_fps = 30
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / 'kayit', fps=30,
                                      grabber=small_synthetic_grabber, out_height=0)
    camera = Camera()
    panel = window.webcam_panel
    panel.set_source_factory(lambda: camera)
    counts = {'board': 0, 'preview': 0}
    widths = []
    real_key = module.apply_chroma_key_bgra
    real_board = panel.view.set_frame

    def key(frame, params):
        widths.append(frame.shape[1])
        return real_key(frame, params)

    def board_frame(image):
        if window.recorder.state is RecorderState.RECORDING:
            counts['board'] += 1
        real_board(image)

    monkeypatch.setattr(module, 'apply_chroma_key_bgra', key)
    monkeypatch.setattr(panel.view, 'set_frame', board_frame)

    def sample():
        counts.update(board=0, preview=0)
        widths.clear()
        done = []
        timer = QTimer(window)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: done.append(True))
        t0 = time.monotonic()
        timer.start(1200)
        qtbot.waitUntil(lambda: bool(done), timeout=10000)
        elapsed = time.monotonic() - t0
        assert window.recorder.state is RecorderState.RECORDING
        return dict(counts), list(widths), elapsed

    def stop_recording():
        if window.recorder.state is RecorderState.RECORDING:
            window.toggle_recording(False)
        qtbot.waitUntil(lambda: window._stop_worker is None, timeout=15000)

    try:
        panel.start()
        qtbot.waitUntil(lambda: panel.view._frame is not None, timeout=5000)
        worker = panel.worker
        window.toggle_recording(True)
        closed_counts, closed_widths, closed_s = sample()
        assert panel.worker is worker
        stop_recording()
        preview = open_preview(window, monkeypatch)
        preview.setGeometry(window._preview_screen.availableGeometry())
        def preview_frame(image):
            assert preview._frame is not None and preview._frame.cacheKey() == image.cacheKey()
            if window.recorder.state is RecorderState.RECORDING:
                counts['preview'] += 1

        # Gerçek yuva bağlı kalır; gözlemci ondan sonra teslim edilen kareyi sayar.
        panel.frameReady.connect(preview_frame)
        qtbot.waitUntil(lambda: preview._frame is not None, timeout=5000)
        window.toggle_recording(True)
        open_counts, open_widths, open_s = sample()
        print({'closed_board_fps': closed_counts['board'] / closed_s,
               'open_board_fps': open_counts['board'] / open_s,
               'open_preview_fps': open_counts['preview'] / open_s,
               'closed_key_widths': sorted(set(closed_widths)),
               'open_key_widths': sorted(set(open_widths))})
        assert panel.worker is worker, 'Kayıt başlatmak kamera işçisini değiştirmemeli'
        assert camera.opens == 1
        assert preview.isVisible() and not window._geometry_interrupted
        assert closed_counts['board'] > 0
        assert open_counts['board'] == open_counts['preview'] > 0
        assert max(open_widths) <= max(closed_widths), \
            'Kayıt sürerken önizleme açılması iki canlı görünümün ortak kare maliyetini büyütmemeli'
    finally:
        stop_recording()
        panel.shutdown()
        assert panel.worker.wait(2000)
