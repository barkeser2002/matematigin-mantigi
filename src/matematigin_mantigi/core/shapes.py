"""Şekil geometrisi (Qt'siz, saf hesap). Sürükleme (a -> b) bir şekle çevrilir.

Üç aile var:
- Serbest kutu şekilleri (dikdörtgen, elips, ikizkenar/dik üçgen, eşkenar dörtgen, paralelkenar, yamuk):
  sürükleme kutusunu doldurur. Shift kutuyu kareye çevirir.
- Kısıtlı şekiller (kare, daire, eşkenar üçgen, düzgün beşgen/altıgen, yıldız): oranı kutudan bağımsız tam
  korunur; sürüklemenin kısa kenarı belirler, başlangıç noktası sabit köşe kalır. Shift'in etkisi yoktur.
- Çizgiler (çizgi, ok, çift ok, sayı doğrusu, açı, eksenler): Shift açıyı 15° adımlarına oturtur.

Alt: başlangıç noktası merkez olur (constrain). Dönen öğeler Poly (çokgen/kırık çizgi) ya da Oval (elips/daire)
olur; çizim katmanı bunları boyar.
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
ANGLE_MARK = math.radians(60)          # açı şeklinin iki ışını arasındaki açı
ANGLE_ARC_RATIO = 0.35                 # yay yarıçapı / ışın uzunluğu
ARC_STEPS = 24
TICK_HALF = 6.0                        # sayı doğrusu / eksen çentiği yarı uzunluğu (px)
SNAP_RAD = math.radians(15)            # Shift ile çizgi açısı adımı

# Kapalı (dolgulanabilir) şekiller. Açık şekiller (çizgi, ok, eksen, açı...) dolguyu yok sayar.
CLOSED_SHAPES = frozenset({
    Shape.RECT, Shape.SQUARE, Shape.ELLIPSE, Shape.CIRCLE, Shape.TRIANGLE, Shape.EQUILATERAL,
    Shape.RIGHT_TRIANGLE, Shape.RHOMBUS, Shape.PARALLELOGRAM, Shape.TRAPEZOID,
    Shape.PENTAGON, Shape.HEXAGON, Shape.STAR,
})
FREE_BOX_SHAPES = frozenset({
    Shape.RECT, Shape.ELLIPSE, Shape.TRIANGLE, Shape.RIGHT_TRIANGLE, Shape.RHOMBUS,
    Shape.PARALLELOGRAM, Shape.TRAPEZOID,
})
ANGLE_SNAP_SHAPES = frozenset({Shape.LINE, Shape.ARROW, Shape.DOUBLE_ARROW, Shape.ANGLE})


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


def _axes(l: float, t: float, r: float, bt: float, ticks: bool) -> list[Item]:
    cx, cy = (l + r) / 2, (t + bt) / 2
    w, h = r - l, bt - t
    out: list[Item] = [Poly(((l, cy), (r, cy)), closed=False), Poly(((cx, bt), (cx, t)), closed=False)]
    head = min(14.0, w / 2, h / 2) if w and h else 0.0
    for tail, tip in (((l, cy), (r, cy)), ((cx, bt), (cx, t))):
        hd = _arrow_head(tail, tip, head) if head else None
        if hd:
            out.append(hd)
    if ticks and w and h:
        for k in (-4, -3, -2, -1, 1, 2, 3, 4):              # her yönde 5 eşit aralık, 0 merkezde
            x = cx + k * (w / 2) / 5
            y = cy + k * (h / 2) / 5
            out.append(Poly(((x, cy - TICK_HALF), (x, cy + TICK_HALF)), closed=False))
            out.append(Poly(((cx - TICK_HALF, y), (cx + TICK_HALF, y)), closed=False))
    return out


def constrain(shape: Shape, a: Point, b: Point, *, shift: bool = False, alt: bool = False) -> tuple[Point, Point]:
    """Shift/Alt kurallarını uygular ve (başlangıç, bitiş) çiftini döndürür.

    shift: çizgi türleri 15° adımına oturur (uzunluk korunur); serbest kutu şekilleri kareye (kısa kenar)
           dönüşür. Kare/daire/çokgen/üçgen zaten kilitli olduğu için değişmez.
    alt:   a merkezdir; döndürülen başlangıç 2a-b olur, böylece kutu/çember a etrafında simetrik çizilir.
    """
    a = (float(a[0]), float(a[1]))
    b = (float(b[0]), float(b[1]))
    if shift:
        dx, dy = b[0] - a[0], b[1] - a[1]
        if shape in ANGLE_SNAP_SHAPES:
            length = math.hypot(dx, dy)
            if length > 0:
                ang = round(math.atan2(dy, dx) / SNAP_RAD) * SNAP_RAD
                b = (a[0] + length * math.cos(ang), a[1] + length * math.sin(ang))
        elif shape in FREE_BOX_SHAPES:
            s = min(abs(dx), abs(dy))
            b = (a[0] + math.copysign(s, dx if dx else 1), a[1] + math.copysign(s, dy if dy else 1))
    if alt:
        a = (2 * a[0] - b[0], 2 * a[1] - b[1])
    return a, b


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
    if shape == Shape.DOUBLE_ARROW:
        out = [Poly((a, b), closed=False)]
        for tail, tip in ((b, a), (a, b)):
            head = _arrow_head(tail, tip)
            if head:
                out.append(head)
        return out
    if shape == Shape.NUMBER_LINE:
        if w < 1e-9:
            return [Poly((a, a), closed=False)]
        out = [Poly(((l, cy), (r, cy)), closed=False)]
        head = min(12.0, w / 4)
        for tail, tip in (((r, cy), (l, cy)), ((l, cy), (r, cy))):
            hd = _arrow_head(tail, tip, head)
            if hd:
                out.append(hd)
        for k in range(11):
            x = l + w * k / 10
            out.append(Poly(((x, cy - TICK_HALF), (x, cy + TICK_HALF)), closed=False))
        return out
    if shape == Shape.ANGLE:
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 1e-9:
            return [Poly((a, a), closed=False)]
        th = math.atan2(b[1] - a[1], b[0] - a[0])
        end2 = (a[0] + length * math.cos(th - ANGLE_MARK), a[1] + length * math.sin(th - ANGLE_MARK))
        rad = length * ANGLE_ARC_RATIO
        arc = tuple((a[0] + rad * math.cos(th - ANGLE_MARK * i / ARC_STEPS),
                     a[1] + rad * math.sin(th - ANGLE_MARK * i / ARC_STEPS)) for i in range(ARC_STEPS + 1))
        return [Poly((a, b), closed=False), Poly((a, end2), closed=False), Poly(arc, closed=False)]
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
    if shape in (Shape.AXES, Shape.AXES_TICKS):
        return _axes(l, t, r, bt, ticks=shape == Shape.AXES_TICKS)
    raise ValueError(shape)
