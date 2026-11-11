"""Tuval ve ipucu kartı sağlamlaştırma regresyonları."""
from PyQt6.QtCore import QPointF, QSize

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
