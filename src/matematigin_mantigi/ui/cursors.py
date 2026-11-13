"""Araca göre imleç ikonları: kalem (renkli kurşun kalem, ucunda çizgi kalınlığı), silgi (gerçek silgi bloğu,
silme alanı kadar), lazer (kırmızı nokta + hale), yazı (I çubuğu), şekil (artı)."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QCursor, QPainter, QPen, QPixmap, QPolygonF

from math import ceil

from matematigin_mantigi.core.models import Nib, Tool
from matematigin_mantigi.core.stroke import MOUSE_PRESSURE, eraser_diameter, pressure_width
from matematigin_mantigi.ui import theme

CURSOR_MARGIN = 1
ERASER_DASH_PX = 2
LASER_DOT = 14
LASER_HALO = 4
PEN_SIZE = 36
PEN_HOTSPOT = (8, 28)          # kalem ucu (mürekkebin düştüğü nokta)


def _blank(size_px: int, dpr: float) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(int(size_px * dpr), int(size_px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p


def pen_cursor(color: QColor, base_width: int, dpr: float = 1.0, *,
               diameter: float | None = None, nib: Nib = Nib.ROUND) -> QCursor:
    """Sağ üste uzanan kurşun kalem; ucu hotspot'ta, uçta gerçek çizgi kalınlığında bir nokta."""
    d = max(2.0, pressure_width(base_width, MOUSE_PRESSURE)) if diameter is None else max(.1, diameter)
    hx, hy = PEN_HOTSPOT
    size = PEN_SIZE
    if diameter is not None:
        radius = ceil(d / 2 + 2)
        hx, hy = max(hx, radius), max(hy, radius)
        size = max(PEN_SIZE, hx + radius, hy + radius, hx + 27)
    pm, p = _blank(size, dpr)
    p.save()
    p.translate(hx, hy)
    p.rotate(-45)                                     # yerel x ekseni: uçtan gövdeye, sağ-yukarı
    outline = QPen(QColor(theme.INK), 1.2)
    p.setPen(outline)
    p.setBrush(QColor("#f3d9a4"))                     # ahşap uç
    p.drawPolygon(QPolygonF([QPointF(0, 0), QPointF(8, -3.6), QPointF(8, 3.6)]))
    p.setBrush(QBrush(QColor(color)))                 # gövde seçili renkte
    p.drawRect(QRectF(8, -3.6, 20, 7.2))
    p.setBrush(QColor("#e9a0b0"))                     # arkadaki silgi
    p.drawRect(QRectF(28, -3.6, 4, 7.2))
    p.restore()
    p.setPen(QPen(QColor("#ffffff"), 1.5))
    p.setBrush(QBrush(QColor(color)))
    if nib == Nib.FELT:
        p.drawRect(QRectF(hx - d / 2, hy - d / 2, d, d))
    else:
        p.drawEllipse(QPointF(hx, hy), d / 2, d / 2)  # gerçek çizgi genişliği
    p.end()
    return QCursor(pm, hx, hy)


def eraser_cursor(base_width: int, dpr: float = 1.0, *, diameter: int | None = None) -> QCursor:
    """Gerçek silme çapında daire; çap verilmezse eski kalınlık API'sini korur."""
    d = eraser_diameter(base_width) if diameter is None else diameter
    size = d + 2 * CURSOR_MARGIN
    pm, p = _blank(size, dpr)
    body = QRectF(1, 1, size - 2, size - 2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 190))
    p.drawEllipse(body)
    p.setPen(QPen(QColor(theme.INK), ERASER_DASH_PX, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(body)
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


def cursor_for(tool: Tool, color: QColor, base_width: int, dpr: float = 1.0, *,
               eraser_size: int | None = None, pen_diameter: float | None = None,
               nib: Nib = Nib.ROUND) -> QCursor:
    if tool == Tool.PEN:
        return pen_cursor(color, base_width, dpr, diameter=pen_diameter, nib=nib)
    if tool == Tool.ERASER:
        return eraser_cursor(base_width, dpr, diameter=eraser_size)
    if tool == Tool.LASER:
        return laser_cursor(dpr)
    if tool == Tool.TEXT:
        return text_cursor()
    if tool == Tool.CLICK:
        return QCursor(Qt.CursorShape.ArrowCursor)
    return shape_cursor()
