"""Şekil geometrisi (Qt'siz): düzgün çokgenler gerçekten düzgün, kareler kare, dik üçgen dik olmalı."""
import math

import pytest

from matematigin_mantigi.core.models import SHAPE_META, SHAPE_ORDER, Shape, next_shape
from matematigin_mantigi.core.shapes import Oval, Poly, shape_geometry


def poly(shape, a, b):
    items = shape_geometry(shape, a, b)
    assert len(items) == 1 and isinstance(items[0], Poly)
    return items[0]


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def sides(pl):
    pts = pl.points
    return [dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def angle_at(pts, i):
    p, q, r = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
    v1, v2 = (p[0] - q[0], p[1] - q[1]), (r[0] - q[0], r[1] - q[1])
    return math.degrees(math.acos((v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))))


def test_every_shape_has_meta_and_is_in_menu_order():
    assert set(SHAPE_ORDER) == set(Shape) == set(SHAPE_META)
    assert len(SHAPE_ORDER) == len(set(SHAPE_ORDER))
    assert len(Shape) >= 14


def test_next_shape_visits_all_and_wraps():
    s, seen = SHAPE_ORDER[0], []
    for _ in SHAPE_ORDER:
        seen.append(s)
        s = next_shape(s)
    assert seen == list(SHAPE_ORDER) and s == SHAPE_ORDER[0]


@pytest.mark.parametrize("shape", list(Shape))
@pytest.mark.parametrize("a,b", [((10, 10), (110, 70)), ((110, 70), (10, 10)), ((10, 70), (110, 10)),
                                 ((50, 50), (50, 50)), ((50, 50), (51, 50.5)), ((5, 5), (5, 200))])
def test_geometry_never_fails_and_is_finite(shape, a, b):
    for item in shape_geometry(shape, a, b):
        vals = ([c for pt in item.points for c in pt] if isinstance(item, Poly)
                else [item.cx, item.cy, item.rx, item.ry])
        assert all(math.isfinite(v) for v in vals)


@pytest.mark.parametrize("shape", [s for s in Shape if s != Shape.LINE])
def test_degenerate_drag_draws_nothing_visible(shape):
    """Tek tıklama (a == b) boyut sıfır: çizilecek bir şey (alan) kalmamalı."""
    for item in shape_geometry(shape, (50, 50), (50, 50)):
        if isinstance(item, Oval):
            assert item.rx == 0 and item.ry == 0
        else:
            assert all(pt == (50, 50) for pt in item.points)


def test_line_is_the_two_points():
    assert poly(Shape.LINE, (1, 2), (30, 40)).points == ((1, 2), (30, 40)) and not poly(Shape.LINE, (1, 2), (3, 4)).closed


def test_rect_matches_drag_box():
    r = poly(Shape.RECT, (110, 70), (10, 10))
    assert set(r.points) == {(10, 10), (110, 10), (110, 70), (10, 70)} and r.closed


def test_square_has_equal_sides_right_angles_and_follows_drag_direction():
    for a, b in [((10, 10), (110, 70)), ((110, 70), (10, 10)), ((10, 70), (110, 10))]:
        sq = poly(Shape.SQUARE, a, b)
        s = sides(sq)
        assert s == pytest.approx([60] * 4)
        assert all(angle_at(sq.points, i) == pytest.approx(90) for i in range(4))
        assert a in [tuple(map(float, p)) for p in sq.points]       # başlangıç köşesi sabit
        far = max(sq.points, key=lambda p: dist(p, a))
        assert (far[0] > a[0]) == (b[0] > a[0]) and (far[1] > a[1]) == (b[1] > a[1])   # sürükleme yönünde


def test_ellipse_fits_drag_box_and_circle_is_round():
    e = shape_geometry(Shape.ELLIPSE, (110, 70), (10, 10))[0]
    assert (e.cx, e.cy, e.rx, e.ry) == (60, 40, 50, 30)
    c = shape_geometry(Shape.CIRCLE, (10, 10), (110, 70))[0]
    assert isinstance(c, Oval) and c.rx == c.ry == 30 and (c.cx, c.cy) == (40, 40)
    c2 = shape_geometry(Shape.CIRCLE, (110, 70), (10, 10))[0]
    assert c2.rx == c2.ry == 30 and (c2.cx, c2.cy) == (80, 40)


def test_isosceles_triangle_apex_centered_over_base():
    t = poly(Shape.TRIANGLE, (10, 10), (110, 70))
    assert t.points[0] == (60, 10) and set(t.points[1:]) == {(110, 70), (10, 70)}
    s = sides(t)
    assert s[1] == pytest.approx(100) and s[0] == pytest.approx(s[2])


def test_equilateral_triangle_has_equal_sides_and_60_degrees():
    for a, b in [((10, 10), (110, 70)), ((110, 10), (10, 70)), ((10, 70), (110, 10))]:
        t = poly(Shape.EQUILATERAL, a, b)
        s = sides(t)
        assert s == pytest.approx([100] * 3)
        assert all(angle_at(t.points, i) == pytest.approx(60) for i in range(3))


def test_right_triangle_has_a_true_right_angle_with_legs_on_box_edges():
    t = poly(Shape.RIGHT_TRIANGLE, (10, 10), (110, 70))
    angles = sorted(angle_at(t.points, i) for i in range(3))
    assert angles[2] == pytest.approx(90)
    assert sum(angles) == pytest.approx(180)
    assert set(t.points) == {(10, 10), (10, 70), (110, 70)}


def test_rhombus_is_equilateral_quadrilateral_through_box_midpoints():
    r = poly(Shape.RHOMBUS, (10, 10), (110, 70))
    assert set(r.points) == {(60, 10), (110, 40), (60, 70), (10, 40)}
    s = sides(r)
    assert s == pytest.approx([s[0]] * 4)


def test_parallelogram_opposite_sides_parallel_and_equal():
    p = poly(Shape.PARALLELOGRAM, (10, 10), (110, 70)).points
    v = lambda i, j: (p[j][0] - p[i][0], p[j][1] - p[i][1])  # noqa: E731
    assert v(0, 1) == pytest.approx(v(3, 2)) and v(0, 1)[1] == 0
    assert v(1, 2) == pytest.approx(v(0, 3)) and v(0, 3)[0] != 0
    assert min(q[1] for q in p) == 10 and max(q[1] for q in p) == 70
    assert min(q[0] for q in p) >= 10 and max(q[0] for q in p) <= 110


def test_trapezoid_is_isosceles_with_parallel_unequal_bases():
    p = poly(Shape.TRAPEZOID, (10, 10), (110, 70)).points
    top, bottom = [q for q in p if q[1] == 10], [q for q in p if q[1] == 70]
    assert len(top) == 2 and len(bottom) == 2
    assert abs(top[0][0] - top[1][0]) < abs(bottom[0][0] - bottom[1][0])
    assert sum(q[0] for q in top) / 2 == pytest.approx(60) == pytest.approx(sum(q[0] for q in bottom) / 2)


@pytest.mark.parametrize("shape,n", [(Shape.PENTAGON, 5), (Shape.HEXAGON, 6)])
def test_regular_polygons_have_equal_sides_and_interior_angles(shape, n):
    for a, b in [((10, 10), (110, 70)), ((110, 70), (10, 10))]:
        pg = poly(shape, a, b)
        assert len(pg.points) == n
        assert sides(pg) == pytest.approx([sides(pg)[0]] * n)
        interior = (n - 2) * 180 / n
        assert all(angle_at(pg.points, i) == pytest.approx(interior) for i in range(n))
        # çevrel çember: köşeler eşit uzaklıkta, çap sürüklemenin kısa kenarı
        cx = sum(p[0] for p in pg.points) / n
        radii = [dist(p, (cx, sum(q[1] for q in pg.points) / n)) for p in pg.points]
        assert radii == pytest.approx([radii[0]] * n)
        assert radii[0] <= 30 + 1e-9


def test_star_is_regular_pentagram_with_ten_equal_edges():
    st = poly(Shape.STAR, (10, 10), (110, 70))
    assert len(st.points) == 10
    s = sides(st)
    assert s == pytest.approx([s[0]] * 10)
    cx = sum(p[0] for p in st.points) / 10
    cy = sum(p[1] for p in st.points) / 10
    outer = [dist(p, (cx, cy)) for p in st.points[0::2]]
    inner = [dist(p, (cx, cy)) for p in st.points[1::2]]
    assert outer == pytest.approx([outer[0]] * 5) and inner == pytest.approx([inner[0]] * 5)
    assert inner[0] / outer[0] == pytest.approx(0.381966, abs=1e-5)


def test_arrow_head_is_symmetric_about_the_shaft_and_tip_is_endpoint():
    items = shape_geometry(Shape.ARROW, (10, 40), (210, 40))
    shaft = items[0]
    assert shaft.points == ((10, 40), (210, 40))
    head = items[1]
    assert head.points[1] == (210, 40)
    l, r = head.points[0], head.points[2]
    assert l[0] == pytest.approx(r[0]) and l[1] - 40 == pytest.approx(40 - r[1]) and l[0] < 210
    # eğik oklarda da kanatlar şaft ekseniyle eşit açı yapar
    d = shape_geometry(Shape.ARROW, (0, 0), (100, 100))[1].points
    back = (-1, -1)
    def ang(w):
        v = (w[0] - 100, w[1] - 100)
        return math.degrees(math.acos((v[0] * back[0] + v[1] * back[1]) / (math.hypot(*v) * math.hypot(*back))))
    assert ang(d[0]) == pytest.approx(ang(d[2])) and 10 < ang(d[0]) < 60
    assert dist(d[0], d[1]) == pytest.approx(dist(d[2], d[1]))


def test_axes_cross_at_box_center_with_arrowheads():
    items = shape_geometry(Shape.AXES, (10, 10), (210, 110))
    pts = [p for it in items for p in it.points]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    assert min(xs) == pytest.approx(10) and max(xs) == pytest.approx(210)
    assert min(ys) == pytest.approx(10) and max(ys) == pytest.approx(110)
    assert ((110, 60) in [tuple(p) for p in pts]) or ((210, 60) in [tuple(p) for p in pts])
    assert len(items) >= 4          # iki eksen + iki ok ucu
