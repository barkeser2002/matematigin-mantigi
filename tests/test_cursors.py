from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QColor

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.ui import cursors


def test_pen_cursor_size_and_hotspot(qapp):
    c = cursors.pen_cursor(QColor("#c8322b"), 4)
    assert c.pixmap().size() == QSize(20, 20) and c.hotSpot() == QPoint(10, 10)
    assert cursors.pen_cursor(QColor("#000"), 8).pixmap().size() == QSize(28, 28)


def test_pen_cursor_uses_color(qapp):
    img = cursors.pen_cursor(QColor("#2456b8"), 8).pixmap().toImage()
    px = img.pixelColor(14, 14)
    assert (px.red(), px.green(), px.blue()) == (0x24, 0x56, 0xb8)


def test_eraser_cursor_scales(qapp):
    assert cursors.eraser_cursor(4).pixmap().size() == QSize(36, 36)
    assert cursors.eraser_cursor(8).pixmap().size() == QSize(70, 70)


def test_laser_text_shape(qapp):
    assert cursors.laser_cursor().pixmap().size() == QSize(24, 24)
    assert cursors.text_cursor().shape() == Qt.CursorShape.IBeamCursor
    assert cursors.shape_cursor().shape() == Qt.CursorShape.CrossCursor


def test_retina_doubles_pixmap_keeps_hotspot(qapp):
    c = cursors.pen_cursor(QColor("#000"), 4, dpr=2.0)
    assert c.pixmap().size() == QSize(40, 40) and c.hotSpot() == QPoint(10, 10)


def test_cursor_for_dispatch(qapp):
    for tool in Tool:
        assert cursors.cursor_for(tool, QColor("#000"), 4) is not None
