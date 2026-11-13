"""core.shapes geometrisini QPainter'a boyar (tuval, önizleme ve menü simgeleri aynı yolu kullanır)."""
from __future__ import annotations

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainter, QPolygonF

from matematigin_mantigi.core.models import Shape
from matematigin_mantigi.core.shapes import Oval, shape_geometry


def paint_shape(p: QPainter, shape: Shape, a: QPointF, b: QPointF) -> None:
    for item in shape_geometry(shape, (a.x(), a.y()), (b.x(), b.y())):
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
    if shape in (Shape.LINE, Shape.ARROW):
        a, b = QPointF(cx - half, cy + half), QPointF(cx + half, cy - half)
    elif shape == Shape.EQUILATERAL:                       # taban altta, tepe yukarıda; yükseklik tabandan türer
        base_y = cy + size * .866 / 2
        a, b = QPointF(cx - half, base_y), QPointF(cx + half, base_y - 1)
    elif shape in (Shape.CIRCLE, Shape.SQUARE, Shape.PENTAGON, Shape.HEXAGON, Shape.STAR):
        a, b = QPointF(cx - half, cy - half), QPointF(cx + half, cy + half)
    else:
        a, b = QPointF(cx - half, cy - half * .75), QPointF(cx + half, cy + half * .75)
    paint_shape(p, shape, a, b)
