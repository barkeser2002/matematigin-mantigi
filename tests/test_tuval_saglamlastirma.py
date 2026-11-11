"""Tuval ve ipucu kartı sağlamlaştırma regresyonları."""
import pytest
from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtWidgets import QMessageBox


@pytest.fixture
def safe_window(window, monkeypatch):
    # Yanlışlıkla açılan modal test sürecini bekletmesin.
    monkeypatch.setattr(QMessageBox, "exec", lambda *a: QMessageBox.StandardButton.Ok)
    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.StandardButton.Ok)
    yield window
    window.webcam_panel.shutdown()

from matematigin_mantigi.ui.canvas import DrawingCanvas


def make_canvas(qtbot):
    canvas = DrawingCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(320, 240)
    canvas.show()
    qtbot.waitExposed(canvas)
    return canvas


def dot(canvas, x, y):
    canvas.begin_stroke(QPointF(x, y), 1.0)
    canvas.end_stroke()


def test_undo_after_growth_keeps_new_area_writable(qtbot):
    canvas = make_canvas(qtbot)
    dot(canvas, 40, 40)
    canvas.resize(640, 480)
    qtbot.waitUntil(lambda: canvas.strokes_image().size() == QSize(640, 480))
    canvas.undo()
    assert canvas.strokes_image().size() == QSize(640, 480)
    dot(canvas, 560, 400)
    assert canvas.strokes_image().pixelColor(560, 400).alpha() > 0


@pytest.mark.parametrize("transition", ["next", "reload", "reload_saved"])
@pytest.mark.parametrize("clear_first", [False, True])
def test_question_transition_discards_only_old_question_history(safe_window, qtbot, transition, clear_first):
    window = safe_window
    canvas = window.canvas
    dot(canvas, 100, 100)
    if clear_first:
        canvas.clear()
        assert canvas.is_empty() and canvas.can_undo()
    if transition == "next":
        window.flow.next_question()
        assert window.flow.index == 1
    else:
        if transition == "reload_saved":
            assert window._save_board(window.flow.index)
        window.reload_questions(window.flow.questions, board_saved=transition == "reload_saved")
    assert canvas.is_empty()
    assert not canvas.can_undo()
    qtbot.keyClick(window, Qt.Key.Key_Z, modifier=Qt.KeyboardModifier.ControlModifier)
    assert canvas.is_empty()
    assert canvas.strokes_image().pixelColor(100, 100).alpha() == 0
    # Araç çubuğunun temizle eylemi aynı soruda geri alınabilir kalır.
    dot(canvas, 100, 100)
    canvas.clear()
    canvas.undo()
    assert canvas.strokes_image().pixelColor(100, 100).alpha() > 0
