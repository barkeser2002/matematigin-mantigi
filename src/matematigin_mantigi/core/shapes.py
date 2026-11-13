"""Şekil geometrisi (Qt'siz, saf hesap). Sürükleme (a -> b) bir şekle çevrilir.

İki aile var:
- Serbest şekiller (dikdörtgen, elips, ikizkenar üçgen, dik üçgen, eşkenar dörtgen, paralelkenar, yamuk,
  koordinat düzlemi): sürükleme kutusunu doldurur.
- Kısıtlı şekiller (kare, daire, eşkenar üçgen, düzgün beşgen/altıgen, yıldız): oranı kutudan bağımsız tam
  korunur; sürüklemenin kısa kenarı belirler, başlangıç noktası sabit köşe kalır.
Dönen öğeler Poly (çokgen/kırık çizgi) ya da Oval (elips/daire) olur; çizim katmanı bunları boyar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from matematigin_mantigi.core.models import Shape

Point = tuple[float, float]


@dataclass(frozen=True)
class Poly:
    points: tuple[Point, ...]
    closed: bool = True


@dataclass(frozen=True)
class Oval:
    cx: float
    cy: float
    rx: float
    ry: float


Item = Poly | Oval

STAR_RATIO = math.sin(math.radians(18)) / math.sin(math.radians(54))   # düzgün beşgen yıldız iç/dış yarıçap: 0.381966
ARROW_ANGLE = math.radians(28)


def _box(a: Point, b: Point) -> tuple[float, float, float, float]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


def _square_end(a: Point, b: Point) -> Point:
    """a'dan b yönünde, kısa kenar uzunluğunda kare köşesi."""
    s = min(abs(b[0] - a[0]), abs(b[1] - a[1]))
    return a[0] + math.copysign(s, b[0] - a[0] if b[0] != a[0] else 1), \
        a[1] + math.copysign(s, b[1] - a[1] if b[1] != a[1] else 1)


def _regular(cx: float, cy: float, r: float, n: int, start_deg: float) -> tuple[Point, ...]:
    return tuple((cx + r * math.cos(math.radians(start_deg + 360 * i / n)),
                  cy + r * math.sin(math.radians(start_deg + 360 * i / n))) for i in range(n))


def _arrow_head(tail: Point, tip: Point, length: float | None = None) -> Poly | None:
    dx, dy = tip[0] - tail[0], tip[1] - tail[1]
    total = math.hypot(dx, dy)
    if total < 1e-9:
        return None
    head = length if length is not None else min(max(14.0, total * 0.18), total * 0.5)
    ux, uy = dx / total, dy / total                      # şaft yönü
    wing = []
    for sign in (1, -1):
        ang = math.atan2(-uy, -ux) + sign * ARROW_ANGLE  # tepeden geriye, şaftın iki yanına
        wing.append((tip[0] + head * math.cos(ang), tip[1] + head * math.sin(ang)))
    return Poly((wing[0], tip, wing[1]), closed=False)


def shape_geometry(shape: Shape, a: Point, b: Point) -> list[Item]:
    a = (float(a[0]), float(a[1])); b = (float(b[0]), float(b[1]))
    l, t, r, bt = _box(a, b)
    w, h = r - l, bt - t
    cx, cy = (l + r) / 2, (t + bt) / 2

    if shape == Shape.LINE:
        return [Poly((a, b), closed=False)]
    if shape == Shape.ARROW:
        out: list[Item] = [Poly((a, b), closed=False)]
        head = _arrow_head(a, b)
        if head:
            out.append(head)
        return out
    if shape == Shape.RECT:
        return [Poly(((l, t), (r, t), (r, bt), (l, bt)))]
    if shape == Shape.ELLIPSE:
        return [Oval(cx, cy, w / 2, h / 2)]
    if shape == Shape.SQUARE:
        e = _square_end(a, b)
        l2, t2, r2, b2 = _box(a, e)
        return [Poly(((l2, t2), (r2, t2), (r2, b2), (l2, b2)))]
    if shape == Shape.CIRCLE:
        e = _square_end(a, b)
        l2, t2, r2, b2 = _box(a, e)
        s = r2 - l2
        return [Oval((l2 + r2) / 2, (t2 + b2) / 2, s / 2, s / 2)]
    if shape == Shape.TRIANGLE:
        return [Poly(((cx, t), (r, bt), (l, bt)))]
    if shape == Shape.EQUILATERAL:
        # Taban a'nın yatay çizgisinde (a.x -> b.x); tepe sürüklemenin dikey yönünde, yükseklik = taban * sqrt(3)/2.
        height = abs(b[0] - a[0]) * math.sqrt(3) / 2
        sy = 1 if b[1] >= a[1] else -1
        return [Poly(((a[0], a[1]), (b[0], a[1]), (cx, a[1] + sy * height)))]
    if shape == Shape.RIGHT_TRIANGLE:
        return [Poly(((l, t), (r, bt), (l, bt)))]
    if shape == Shape.RHOMBUS:
        return [Poly(((cx, t), (r, cy), (cx, bt), (l, cy)))]
    if shape == Shape.PARALLELOGRAM:
        k = w * 0.25
        return [Poly(((l + k, t), (r, t), (r - k, bt), (l, bt)))]
    if shape == Shape.TRAPEZOID:
        k = w * 0.2
        return [Poly(((l + k, t), (r - k, t), (r, bt), (l, bt)))]
    if shape in (Shape.PENTAGON, Shape.HEXAGON, Shape.STAR):
        e = _square_end(a, b)
        l2, t2, r2, b2 = _box(a, e)
        s = r2 - l2
        ccx, ccy, rad = (l2 + r2) / 2, (t2 + b2) / 2, s / 2
        if shape == Shape.PENTAGON:
            return [Poly(_regular(ccx, ccy, rad, 5, -90))]
        if shape == Shape.HEXAGON:
            return [Poly(_regular(ccx, ccy, rad, 6, 0))]
        outer = _regular(ccx, ccy, rad, 5, -90)
        inner = _regular(ccx, ccy, rad * STAR_RATIO, 5, -90 + 36)
        pts: list[Point] = []
        for o, i in zip(outer, inner):
            pts += [o, i]
        return [Poly(tuple(pts))]
    if shape == Shape.AXES:
        out = [Poly(((l, cy), (r, cy)), closed=False), Poly(((cx, bt), (cx, t)), closed=False)]
        head = min(14.0, w / 2, h / 2) if w and h else 0.0
        for tail, tip in (((l, cy), (r, cy)), ((cx, bt), (cx, t))):
            hd = _arrow_head(tail, tip, head) if head else None
            if hd:
                out.append(hd)
        return out
    raise ValueError(shape)
