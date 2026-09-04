from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QInputDevice, QPointingDevice, QTabletEvent
from PyQt6.QtWidgets import QApplication

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.ui.canvas import DrawingCanvas

STYLUS = QPointingDevice("test-stylus", 1, QInputDevice.DeviceType.Stylus,
                         QPointingDevice.PointerType.Pen,
                         QInputDevice.Capability.Position | QInputDevice.Capability.Pressure, 1, 1)


def make(qtbot):
    c = DrawingCanvas()
    qtbot.addWidget(c)
    c.resize(400, 300)
    c.show()
    qtbot.waitExposed(c)
    return c


def alpha_at(c, x, y):
    return c.strokes_image().pixelColor(x, y).alpha()


def draw_diagonal(c, pressure=0.5):
    c.begin_stroke(QPointF(50, 50), pressure)
    c.extend_stroke(QPointF(150, 150), pressure)
    c.end_stroke()


def test_starts_empty(qtbot):
    c = make(qtbot)
    assert c.is_empty() and not c.can_undo() and alpha_at(c, 100, 100) == 0


def test_pen_stroke_paints_pixels_and_enables_undo(qtbot):
    c = make(qtbot)
    with qtbot.waitSignal(c.historyChanged) as sig:
        draw_diagonal(c)
    assert alpha_at(c, 100, 100) > 0 and alpha_at(c, 300, 20) == 0
    assert sig.args == [True, False]
    assert not c.is_empty()


def test_pressure_changes_width(qtbot):
    thin, thick = make(qtbot), make(qtbot)
    thin.set_base_width(8); thick.set_base_width(8)
    thin.begin_stroke(QPointF(50, 100), 0.0); thin.extend_stroke(QPointF(350, 100), 0.0); thin.end_stroke()
    thick.begin_stroke(QPointF(50, 100), 1.0); thick.extend_stroke(QPointF(350, 100), 1.0); thick.end_stroke()
    assert alpha_at(thin, 200, 104) == 0 and alpha_at(thick, 200, 104) > 0


def test_undo_restores_previous_bitmap(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.undo()
    assert alpha_at(c, 100, 100) == 0 and c.is_empty() and not c.can_undo()


def test_undo_depth_is_30(qtbot):
    c = make(qtbot)
    for i in range(31):
        c.begin_stroke(QPointF(10 + i * 5, 10), 0.5); c.end_stroke()
    for _ in range(30):
        c.undo()
    assert not c.can_undo() and alpha_at(c, 10, 10) > 0        # first stroke survives


def test_eraser_clears(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.set_tool(Tool.ERASER)
    draw_diagonal(c)
    assert alpha_at(c, 100, 100) == 0


def test_eraser_tip_overrides_tool_for_one_stroke(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.begin_stroke(QPointF(50, 50), 0.5, eraser_tip=True); c.extend_stroke(QPointF(150, 150), 0.5); c.end_stroke()
    assert alpha_at(c, 100, 100) == 0 and c.tool == Tool.PEN


def test_laser_does_not_touch_strokes_layer(qtbot):
    c = make(qtbot)
    c.set_tool(Tool.LASER)
    draw_diagonal(c)
    assert alpha_at(c, 100, 100) == 0 and c.is_empty()


def test_clear_is_undoable(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.clear()
    assert c.is_empty()
    c.undo()
    assert alpha_at(c, 100, 100) > 0


def test_color_is_used(qtbot):
    c = make(qtbot)
    c.set_color(QColor("#c8322b")); c.set_base_width(8)
    c.begin_stroke(QPointF(100, 100), 1.0); c.end_stroke()
    px = c.strokes_image().pixelColor(100, 100)
    assert (px.red(), px.green(), px.blue()) == (0xc8, 0x32, 0x2b)


def test_mouse_events_draw(qtbot):
    c = make(qtbot)
    qtbot.mousePress(c, Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
    qtbot.mouseMove(c, QPoint(150, 150))
    qtbot.mouseRelease(c, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    assert alpha_at(c, 100, 100) > 0


def tablet(widget, etype, x, y, pressure):
    pressed = etype != QEvent.Type.TabletRelease
    button = Qt.MouseButton.LeftButton if etype != QEvent.Type.TabletMove else Qt.MouseButton.NoButton
    buttons = Qt.MouseButton.LeftButton if pressed else Qt.MouseButton.NoButton
    ev = QTabletEvent(etype, STYLUS, QPointF(x, y), QPointF(widget.mapToGlobal(QPoint(x, y))),
                      pressure, 0.0, 0.0, 0.0, 0.0, 0.0, Qt.KeyboardModifier.NoModifier, button, buttons)
    QApplication.sendEvent(widget, ev)
    return ev.isAccepted()


def test_tablet_events_draw_and_are_accepted(qtbot):
    c = make(qtbot)
    assert tablet(c, QEvent.Type.TabletPress, 50, 50, 0.9)
    assert tablet(c, QEvent.Type.TabletMove, 150, 150, 0.9)
    assert tablet(c, QEvent.Type.TabletRelease, 150, 150, 0.0)
    assert alpha_at(c, 100, 100) > 0


def test_mouse_press_ignored_while_stylus_down(qtbot):
    c = make(qtbot)
    tablet(c, QEvent.Type.TabletPress, 50, 50, 0.9)
    qtbot.mousePress(c, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    tablet(c, QEvent.Type.TabletRelease, 50, 50, 0.0)
    assert len(c._undo) == 1        # only one stroke was started


def test_snapshot_has_white_background(qtbot):
    c = make(qtbot)
    img = c.snapshot_image()
    assert img.pixelColor(5, 5) == QColor("#ffffff")
