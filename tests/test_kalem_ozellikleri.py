"""Kalem yeniliklerinin gerçek raster ve olay akışı regresyonları."""
from dataclasses import replace

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor

from matematigin_mantigi.core.models import Nib, PenSettings
from matematigin_mantigi.ui.canvas import DrawingCanvas


def canvas_for(qtbot, **kwargs):
    c = DrawingCanvas()
    qtbot.addWidget(c)
    c.resize(320, 200)
    c.show()
    qtbot.waitExposed(c)
    c.set_pen_settings(PenSettings(smoothing=0, min_width=4, max_width=4, **kwargs))
    return c


def line(c, a=(40, 100), b=(260, 100)):
    c.begin_stroke(QPointF(*a), .5)
    c.extend_stroke(QPointF(*b), .5)
    c.end_stroke()


def test_highlighter_transparent_wide_flat_preserves_ink_and_redo(qtbot):
    c = canvas_for(qtbot)
    c.set_color(QColor("black"))
    line(c, (150, 50), (150, 150))
    before = c.strokes_image().copy()
    c.set_pen_settings(replace(c._pen_settings, nib=Nib.HIGHLIGHTER))
    c.set_color(QColor("#ffff00"))
    c.begin_stroke(QPointF(40, 100), .5)
    for x in range(45, 261, 5):
        c.extend_stroke(QPointF(x, 100), .5)
    c.end_stroke()
    image = c.strokes_image().copy()
    assert 88 <= image.pixelColor(100, 100).alpha() <= 103
    assert image.pixelColor(100, 105).alpha() > 80
    assert image.pixelColor(35, 100).alpha() == 0
    assert image.pixelColor(150, 100) == QColor("black")
    c.undo()
    assert c.strokes_image() == before
    c.redo()
    assert c.strokes_image() == image
    c.resize(640, 400)
    assert c.strokes_image().pixelColor(200, 200).alpha() > 80
    c.undo(); c.redo()
    assert c.strokes_image().pixelColor(300, 200).value() < 10


def test_highlighter_nib_settings_and_dialog(ini_settings, qtbot):
    from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
    from matematigin_mantigi.ui.theme import FontFamilies
    pen = replace(ini_settings.pen(), nib=Nib.HIGHLIGHTER)
    ini_settings.set_pen(pen)
    assert ini_settings.pen() == pen
    dlg = PenSettingsDialog(pen, QColor("yellow"), 4, FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(dlg)
    assert dlg.nib_buttons[Nib.HIGHLIGHTER].isChecked()
    assert dlg.value().nib == Nib.HIGHLIGHTER


@pytest.mark.parametrize("end", [(250, 141), (60, 160), (200, 30), (40, 30)])
def test_shift_replaces_curve_with_fifteen_degree_line(qtbot, end):
    import math
    c = canvas_for(qtbot)
    c.begin_stroke(QPointF(100, 100), .5)
    c.extend_stroke(QPointF(130, 170), .5)
    c.extend_stroke(QPointF(*end), .5, modifiers=Qt.KeyboardModifier.ShiftModifier)
    point = QPointF(c._last)
    angle = math.degrees(math.atan2(point.y() - 100, point.x() - 100))
    assert angle / 15 == pytest.approx(round(angle / 15), abs=1e-8)
    c.end_stroke()
    assert c.strokes_image().pixelColor(130, 170).alpha() == 0
    assert c.strokes_image().pixelColor(round(point.x()), round(point.y())).alpha() > 100
    c.undo(); assert c.is_empty()
    c.redo(); assert not c.is_empty()


def test_shift_mouse_events_use_modifiers(qtbot):
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QMouseEvent
    c = canvas_for(qtbot)
    def event(kind, pos, button, buttons):
        return QMouseEvent(kind, QPointF(*pos), QPointF(*pos), button, buttons,
                           Qt.KeyboardModifier.ShiftModifier)
    c.mousePressEvent(event(QEvent.Type.MouseButtonPress, (40, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
    c.mouseMoveEvent(event(QEvent.Type.MouseMove, (260, 111), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton))
    c.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease, (260, 111), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))
    assert c.strokes_image().pixelColor(200, 100).alpha() > 100
    assert c.strokes_image().pixelColor(200, 108).alpha() == 0
