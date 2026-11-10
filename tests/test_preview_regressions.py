from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QPushButton


def open_preview(window, monkeypatch):
    window.resize(500, 400)
    window.move(0, 0)
    board = window.screen()
    g = board.geometry()
    class Target:
        def geometry(self): return QRect(g.right() + 1, g.top(), g.width(), g.height())
        def availableGeometry(self): return self.geometry()
        def devicePixelRatio(self): return board.devicePixelRatio()
    target = Target()
    monkeypatch.setattr(QApplication, 'screens', staticmethod(lambda: [board, target]))
    window._configure_screens(None, target)
    assert window._preview is not None
    return window._preview


def test_camera_error_clears_external_preview(window, monkeypatch):
    preview = open_preview(window, monkeypatch)
    frame = QImage(4, 4, QImage.Format.Format_RGB32)
    frame.fill(QColor('red'))
    window.webcam_panel._on_frame(frame)
    window.webcam_panel._on_error('Kamera hatası')
    assert preview._frame is None
    assert 'Kamera hatası' in preview.placeholder_text


def test_preview_has_accessible_close_button(window, monkeypatch, qtbot):
    preview = open_preview(window, monkeypatch)
    button = preview.findChild(QPushButton, 'preview_close')
    assert button is not None and button.isVisible()
    button.click()
    assert window._preview is None


def test_explicit_board_selection_is_fullscreen(window, qtbot):
    board = window.screen()
    window._configure_screens(board, None)
    qtbot.waitUntil(window.isFullScreen)
    assert window.screen() is board


def test_reselect_camera_clears_old_external_frame(window, monkeypatch, fake_camera):
    preview = open_preview(window, monkeypatch)
    frame = QImage(4, 4, QImage.Format.Format_RGB32)
    frame.fill(QColor('red'))
    window.webcam_panel._on_frame(frame)
    window.webcam_panel.set_source_factory(lambda: fake_camera)
    assert preview._frame is None
    assert preview.placeholder_text == window.webcam_panel.view.placeholder_text
