"""Araca ve renge göre özel imleçler: kalem = renkli nokta, silgi = kesikli kare, lazer = kırmızı halka."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QCursor, QPainter, QPen, QPixmap

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.core.stroke import eraser_diameter, pen_cursor_diameter
from matematigin_mantigi.ui import theme

CURSOR_MARGIN = 1
ERASER_DASH_PX = 2
LASER_DOT = 14
LASER_HALO = 4


def _blank(size_px: int, dpr: float) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(int(size_px * dpr), int(size_px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p


def pen_cursor(color: QColor, base_width: int, dpr: float = 1.0) -> QCursor:
    d = pen_cursor_diameter(base_width)
    size = d + 2 * CURSOR_MARGIN
    pm, p = _blank(size, dpr)
    c = size / 2
    p.setPen(QPen(QColor("#ffffff"), 2))
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(QPointF(c, c), d / 2 - 1, d / 2 - 1)
    p.end()
    return QCursor(pm, size // 2, size // 2)


def eraser_cursor(base_width: int, dpr: float = 1.0) -> QCursor:
    d = eraser_diameter(base_width)
    size = d + 2 * CURSOR_MARGIN
    pm, p = _blank(size, dpr)
    p.setPen(QPen(QColor(theme.INK), ERASER_DASH_PX, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), 3, 3)
    p.end()
    return QCursor(pm, size // 2, size // 2)


def laser_cursor(dpr: float = 1.0) -> QCursor:
    size = LASER_DOT + 2 * LASER_HALO + 2 * CURSOR_MARGIN
    pm, p = _blank(size, dpr)
    c = size / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 59, 48, 77)); p.drawEllipse(QPointF(c, c), size / 2 - 1, size / 2 - 1)
    p.setBrush(QColor(theme.LASER));     p.drawEllipse(QPointF(c, c), LASER_DOT / 2, LASER_DOT / 2)
    p.end()
    return QCursor(pm, size // 2, size // 2)


def text_cursor() -> QCursor:
    return QCursor(Qt.CursorShape.IBeamCursor)


def shape_cursor() -> QCursor:
    return QCursor(Qt.CursorShape.CrossCursor)


def cursor_for(tool: Tool, color: QColor, base_width: int, dpr: float = 1.0) -> QCursor:
    if tool == Tool.PEN:
        return pen_cursor(color, base_width, dpr)
    if tool == Tool.ERASER:
        return eraser_cursor(base_width, dpr)
    if tool == Tool.LASER:
        return laser_cursor(dpr)
    if tool == Tool.TEXT:
        return text_cursor()
    return shape_cursor()
