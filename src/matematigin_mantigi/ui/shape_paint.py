"""core.shapes geometrisini QPainter'a boyar (tuval, önizleme ve menü simgeleri aynı yolu kullanır)."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPolygonF

from matematigin_mantigi.core.models import Shape
from matematigin_mantigi.core.shapes import Oval, shape_geometry

FILL_ALPHA = 90                        # yarı saydam dolgu: kalem rengi, ~%35 opaklık


def fill_color(pen: QColor) -> QColor:
    c = QColor(pen)
    c.setAlpha(FILL_ALPHA)
    return c


def paint_shape(p: QPainter, shape: Shape, a: QPointF, b: QPointF, fill: QColor | None = None) -> None:
    """Şekli çizer. fill verilirse yalnız kapalı öğeler (Oval, closed Poly) yarı saydam dolar; açık öğeler dolmaz.
    Sınırlar (Shift/Alt) çağıran tarafından uygulanmış olmalı: bkz. core.shapes.constrain."""
    paint_items(p, shape_geometry(shape, (a.x(), a.y()), (b.x(), b.y())), fill)


def paint_items(p: QPainter, items, fill: QColor | None = None) -> None:
    """core.shapes öğelerini (Poly/Oval) boyar; kalem ve renk çağıranın QPen'inden gelir."""
    for item in items:
        closed = isinstance(item, Oval) or item.closed
        p.setBrush(QBrush(fill) if fill is not None and closed else Qt.BrushStyle.NoBrush)
        if isinstance(item, Oval):
            p.drawEllipse(QPointF(item.cx, item.cy), item.rx, item.ry)
            continue
        poly = QPolygonF([QPointF(x, y) for x, y in item.points])
        if item.closed:
            p.drawPolygon(poly)
        else:
            p.drawPolyline(poly)


def paint_shape_icon(p: QPainter, shape: Shape, cx: float, cy: float, size: float) -> None:
    """Şekli cx, cy merkezli size×size kutuya sığacak biçimde boyar (kalem/renk çağıranda)."""
    half = size / 2
    if shape == Shape.ANGLE:                                 # iki ışın yukarı açılır, yay tepede kalır
        a, b = QPointF(cx - half * .9, cy + half * .8), QPointF(cx + half * .9, cy + half * .8)
    elif shape in (Shape.LINE, Shape.ARROW, Shape.DOUBLE_ARROW):
        a, b = QPointF(cx - half, cy + half), QPointF(cx + half, cy - half)
    elif shape == Shape.EQUILATERAL:                       # taban altta, tepe yukarıda; yükseklik tabandan türer
        base_y = cy + size * .866 / 2
        a, b = QPointF(cx - half, base_y), QPointF(cx + half, base_y - 1)
    elif shape in (Shape.CIRCLE, Shape.SQUARE, Shape.PENTAGON, Shape.HEXAGON, Shape.STAR):
        a, b = QPointF(cx - half, cy - half), QPointF(cx + half, cy + half)
    else:
        a, b = QPointF(cx - half, cy - half * .75), QPointF(cx + half, cy + half * .75)
    paint_shape(p, shape, a, b)
