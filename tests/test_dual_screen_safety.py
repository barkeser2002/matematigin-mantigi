from PyQt6.QtCore import QRect
from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.webcam_panel import WebcamPanel, CameraView

from matematigin_mantigi.ui.dual_screen import resolve_screen, screens_are_separate


class Screen:
    def __init__(self, name, geometry, serial=""):
        self._name, self._geometry, self._serial = name, geometry, serial

    def name(self):
        return self._name

    def serialNumber(self):
        return self._serial

    def geometry(self):
        return self._geometry


def test_screen_selection_requires_unique_matching_identity():
    a = Screen("XP-Pen", QRect(0, 0, 1920, 1080), "123")
    b = Screen("Monitor", QRect(1920, 0, 1920, 1080), "456")
    assert resolve_screen([a, b], "XP-Pen", "123") is a
    assert resolve_screen([b], "XP-Pen", "123") is None
    assert resolve_screen([a], "XP-Pen", "wrong") is None
    assert resolve_screen([a, a], "XP-Pen", "123") is None


def test_only_disjoint_nonempty_screen_geometries_are_safe():
    a = Screen("A", QRect(0, 0, 1920, 1080))
    b = Screen("B", QRect(1920, 0, 1920, 1080))
    overlap = Screen("C", QRect(1919, 0, 1920, 1080))
    empty = Screen("D", QRect())
    assert screens_are_separate(a, b)
    assert not screens_are_separate(a, overlap)
    assert not screens_are_separate(a, empty)
    assert not screens_are_separate(a, a)


def test_hidden_board_and_second_view_share_worker(qtbot, fake_camera):
    panel = WebcamPanel(FontFamilies("Arial", "Arial", False), lambda: fake_camera, ChromaParams())
    second = CameraView()
    qtbot.addWidget(panel)
    qtbot.addWidget(second)
    panel.frameReady.connect(second.set_frame)
    panel.hide()
    second.show()
    try:
        with qtbot.waitSignal(panel.frameReady, timeout=2000):
            panel.start()
        qtbot.waitUntil(lambda: second._frame is not None, timeout=2000)
        assert panel.view._frame is not None
        assert panel.worker.isRunning()
    finally:
        panel.shutdown()
