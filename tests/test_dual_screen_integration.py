from PyQt6.QtCore import QRect
from matematigin_mantigi.ui.dual_screen import layout_supported


class Screen:
    def __init__(self, x, dpr):
        self.x, self.dpr = x, dpr
    def geometry(self):
        return QRect(self.x, 0, 800, 600)
    def devicePixelRatio(self):
        return self.dpr


def test_layout_rejects_mixed_and_overlapping_screens():
    a, b = Screen(0, 1), Screen(800, 1)
    assert layout_supported([a, b], a, b)
    assert not layout_supported([a, b, Screen(1600, 2)], a, b)
    assert not layout_supported([a, Screen(799, 1)], a, b)
    assert not layout_supported([a], a, a)


def test_preview_lifecycle_and_frames(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QImage, QColor
    window.resize(500, 400)
    window.move(0, 0)
    qtbot.waitUntil(lambda: window.width() == 500)
    board = window.screen()
    g = board.geometry()
    class Target:
        def geometry(self):
            return QRect(g.right() + 1, g.top(), g.width(), g.height())
        def availableGeometry(self):
            return self.geometry()
        def devicePixelRatio(self):
            return board.devicePixelRatio()
    target = Target()
    monkeypatch.setattr(QApplication, "screens", staticmethod(lambda: [board, target]))
    window._configure_screens(None, target)
    assert window._preview is not None
    preview = window._preview
    frame = QImage(4, 4, QImage.Format.Format_RGB32)
    frame.fill(QColor("red"))
    window.webcam_panel._on_frame(frame)
    assert preview._frame.pixelColor(0, 0) == QColor("red")
    assert window.webcam_panel.view._frame.pixelColor(0, 0) == QColor("red")
    window._screen_topology_changed()
    assert window._preview is None
    assert not preview.isVisible()


def test_one_monitor_ui_disables_preview(window):
    from matematigin_mantigi.ui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(window.settings, window.fam, window)
    assert not dlg.preview_screen_combo.isEnabled()
    assert dlg.preview_screen_combo.currentData() is None


def test_preview_close_stops_active_recording(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from matematigin_mantigi.core.recorder import RecorderState
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Ok)
    window.resize(500, 400)
    window.move(0, 0)
    board = window.screen()
    g = board.geometry()
    class Target:
        def geometry(self):
            return QRect(g.right() + 1, g.top(), g.width(), g.height())
        def availableGeometry(self):
            return self.geometry()
        def devicePixelRatio(self):
            return board.devicePixelRatio()
    target = Target()
    monkeypatch.setattr(QApplication, "screens", staticmethod(lambda: [board, target]))
    window._configure_screens(None, target)
    assert window._preview is not None
    window.toggle_recording(True)
    assert window.recorder.state is RecorderState.RECORDING
    window._preview.close()
    assert window._preview is None
    qtbot.waitUntil(lambda: window.recorder.state is RecorderState.IDLE)
