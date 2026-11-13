"""Şekil düzeltme: ML'siz geometri tanıyıcı, kalem akışı, geri al ve tahta kaydı/geri yükleme.

Tanıyıcı yalnız numpy kullanır. Kalem akışı testleri gerçek DrawingCanvas'ı begin/extend/end ile sürer.
"""
import math

import numpy as np
import pytest
from PyQt6.QtCore import QPointF, QSettings, Qt
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication

from matematigin_mantigi.core import shape_recognition as sr
from matematigin_mantigi.core.models import Nib, PenSettings
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.canvas import DrawingCanvas


# --- sentetik çizimler -------------------------------------------------------------------------------

def _resample(vertices, per_edge, closed=True, rng=None, noise=0.0):
    v = np.asarray(vertices, float)
    ring = np.vstack([v, v[:1]]) if closed else v
    parts = [a + np.linspace(0, 1, per_edge, endpoint=False)[:, None] * (b - a)
             for a, b in zip(ring[:-1], ring[1:])]
    parts.append(ring[-1:])
    p = np.vstack(parts)
    if rng is not None and noise:
        p = p + rng.normal(0, noise, p.shape)
    return p


def circle(cx=200, cy=150, r=90, n=200, noise=0.0, seed=1):
    rng = np.random.default_rng(seed)
    a = np.linspace(0, 2 * np.pi, n)
    p = np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)])
    return p + rng.normal(0, noise, p.shape) if noise else p


def line(x0=60, y0=80, x1=300, y1=120, n=60):
    return np.column_stack([np.linspace(x0, x1, n), np.linspace(y0, y1, n)])


def rectangle(l=120, t=90, r=300, b=210, per_edge=50, noise=0.0, seed=2):
    return _resample([(l, t), (r, t), (r, b), (l, b)], per_edge, rng=np.random.default_rng(seed), noise=noise)


def triangle(noise=0.0, seed=3):
    return _resample([(150, 230), (330, 230), (240, 80)], 60, rng=np.random.default_rng(seed), noise=noise)


def ellipse(cx=220, cy=160, rx=130, ry=60, n=220):
    a = np.linspace(0, 2 * np.pi, n)
    return np.column_stack([cx + rx * np.cos(a), cy + ry * np.sin(a)])


def pentagon(cx=220, cy=160, r=110):
    ang = np.radians(-90 + 72 * np.arange(5))
    return _resample(np.column_stack([cx + r * np.cos(ang), cy + r * np.sin(ang)]), 45)


def freehand(seed=4, n=300):
    rng = np.random.default_rng(seed)
    p = np.cumsum(rng.normal(0, 6, (n, 2)), axis=0)
    return p + np.array([60.0, 60.0])


# --- tanıyıcı sözleşmesi ----------------------------------------------------------------------------

def test_line_is_recognized_with_endpoints_near_the_ends():
    out = sr.recognize(line())
    assert out["type"] == "line"
    assert len(out["vertices"]) == 2
    assert np.allclose(sorted(out["vertices"]), sorted([[60, 80], [300, 120]]), atol=6)


def test_circle_is_recognized_with_center_and_radius():
    out = sr.recognize(circle(noise=1.0))
    assert out["type"] == "circle"
    assert np.allclose(out["params"]["center"], [200, 150], atol=4)
    assert abs(out["params"]["radii"][0] - 90) < 4


def test_ellipse_is_recognized_as_ellipse():
    assert sr.recognize(ellipse())["type"] == "ellipse"


@pytest.mark.parametrize("make,kind,corners", [
    (triangle, "triangle", 3),
    (rectangle, "rectangle", 4),
    (pentagon, "polygon", 5),
])
def test_polygons_keep_their_corner_count(make, kind, corners):
    out = sr.recognize(make())
    assert out["type"] == kind
    assert len(out["vertices"]) == corners


def test_freehand_scribble_is_unknown():
    assert sr.recognize(freehand())["type"] == "unknown"


def test_invalid_inputs_never_raise():
    assert sr.recognize([])["type"] == "unknown"
    assert sr.recognize([[1.0, 2.0]])["type"] == "unknown"
    assert sr.recognize([[np.nan, 0.0], [1.0, 1.0], [30.0, 30.0]])["type"] == "unknown"
    assert sr.recognize(np.zeros((50, 4)))["type"] == "unknown"


def test_tiny_stroke_is_unknown_for_recognizer_and_skipped_by_policy():
    tiny = circle(r=15, n=120)
    assert sr.correct_stroke(tiny) is None


def test_small_line_below_forty_pixels_is_not_corrected():
    assert sr.correct_stroke(line(100, 100, 130, 100, n=20)) is None


def test_correct_stroke_accepts_a_clear_circle():
    out = sr.correct_stroke(circle(noise=1.0))
    assert out is not None and out["type"] == "circle"


def test_geometry_items_for_each_kind():
    from matematigin_mantigi.core.shapes import Oval, Poly
    circle_items = sr.geometry_items(sr.correct_stroke(circle()))
    assert len(circle_items) == 1 and isinstance(circle_items[0], Oval)
    tri_items = sr.geometry_items(sr.correct_stroke(triangle()))
    assert len(tri_items) == 1 and isinstance(tri_items[0], Poly) and tri_items[0].closed
    line_items = sr.geometry_items(sr.correct_stroke(line()))
    assert isinstance(line_items[0], Poly) and not line_items[0].closed
    ell_items = sr.geometry_items(sr.correct_stroke(ellipse()))
    assert isinstance(ell_items[0], Poly) and ell_items[0].closed and len(ell_items[0].points) >= 64


# --- kalem akışı: DrawingCanvas ---------------------------------------------------------------------

def make(qtbot, settings=None, clock=None):
    c = DrawingCanvas()
    qtbot.addWidget(c)
    c.resize(400, 300)
    c.show()
    qtbot.waitExposed(c)
    c.set_pen_settings(settings or PenSettings(shape_correction=True))
    if clock is not None:
        c._clock = clock
    return c


def draw(c, points, *, modifiers=Qt.KeyboardModifier.NoModifier, pressure=0.5):
    pts = [QPointF(float(x), float(y)) for x, y in points]
    c.begin_stroke(pts[0], pressure, modifiers=modifiers)
    for p in pts[1:]:
        c.extend_stroke(p, pressure, modifiers=modifiers)
    c.end_stroke()


def image_bytes(image: QImage) -> bytes:
    return bytes(image.constBits().asstring(image.sizeInBytes()))


def alpha(c, x, y):
    return c.strokes_image().pixelColor(int(x), int(y)).alpha()


def test_shape_correction_setting_is_off_by_default_and_persists(tmp_path):
    assert PenSettings().shape_correction is False
    path = str(tmp_path / "ayar.ini")
    fresh = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert fresh.pen().shape_correction is False
    fresh.set_pen(PenSettings(shape_correction=True))
    fresh.sync()
    assert AppSettings(QSettings(path, QSettings.Format.IniFormat)).pen().shape_correction is True


def test_shape_correction_is_off_by_default(qtbot):
    assert PenSettings().shape_correction is False
    c = make(qtbot, PenSettings())
    draw(c, circle(noise=1.0))
    assert c.last_correction is None


def test_circle_stroke_is_replaced_by_geometric_circle(qtbot):
    c = make(qtbot)
    draw(c, circle(noise=1.5))
    assert c.last_correction == "circle"
    assert alpha(c, 290, 150) > 0          # sağ kenar
    assert alpha(c, 200, 60) > 0           # üst kenar
    assert alpha(c, 200, 150) == 0         # merkez boş: dolgu yok


def test_corrected_shape_uses_pen_color(qtbot):
    c = make(qtbot)
    c.set_color(QColor("#c0392b"))
    draw(c, circle(noise=1.0))
    px = c.strokes_image().pixelColor(290, 150)
    assert px.alpha() > 0 and px.red() > px.green() + 60


def test_first_undo_restores_raw_line_and_second_removes_it(qtbot):
    raw_canvas = make(qtbot, PenSettings())
    draw(raw_canvas, circle(noise=1.5))
    raw = raw_canvas.strokes_image().copy()

    c = make(qtbot)
    draw(c, circle(noise=1.5))
    assert c.last_correction == "circle"
    assert c.can_undo()
    c.undo()
    assert image_bytes(c.strokes_image()) == image_bytes(raw)
    assert not c.is_empty()
    assert c.can_undo()
    c.undo()
    assert c.is_empty()
    assert not c.can_undo()
    assert alpha(c, 290, 150) == 0


def test_redo_after_undo_reapplies_correction(qtbot):
    c = make(qtbot)
    draw(c, circle(noise=1.5))
    corrected = image_bytes(c.strokes_image())
    c.undo()
    c.redo()
    assert image_bytes(c.strokes_image()) == corrected


def test_rectangle_and_triangle_are_replaced(qtbot):
    clock = {"t": 0.0}
    c = make(qtbot, clock=lambda: clock["t"])
    draw(c, rectangle(noise=1.0))
    assert c.last_correction == "rectangle"
    c.clear()
    clock["t"] = 10.0
    c.last_correction = None
    draw(c, triangle(noise=1.0))
    assert c.last_correction == "triangle"


def test_short_stroke_is_left_raw(qtbot):
    c = make(qtbot)
    draw(c, circle(r=15, n=120, noise=0.5))
    assert c.last_correction is None


def test_shift_straight_line_is_not_recognized(qtbot):
    c = make(qtbot)
    draw(c, circle(noise=1.0), modifiers=Qt.KeyboardModifier.ShiftModifier)
    assert c.last_correction is None


def test_highlighter_and_eraser_strokes_are_not_recognized(qtbot):
    c = make(qtbot, PenSettings(shape_correction=True, nib=Nib.HIGHLIGHTER))
    draw(c, circle(noise=1.0))
    assert c.last_correction is None
    c = make(qtbot)
    c.begin_stroke(QPointF(*circle()[0]), 0.5, eraser_tip=True)
    for x, y in circle()[1:]:
        c.extend_stroke(QPointF(x, y), 0.5)
    c.end_stroke()
    assert c.last_correction is None


def test_writing_cluster_is_not_converted(qtbot):
    clock = {"t": 0.0}
    c = make(qtbot, clock=lambda: clock["t"])
    draw(c, circle(cx=200, cy=150, r=80, noise=1.0))
    assert c.last_correction == "circle"
    clock["t"] = 0.4                                   # hemen yanına, aynı yazı bağlamında
    draw(c, triangle(noise=1.0))
    assert c.last_correction is None
    clock["t"] = 9.0                                   # bağlam bitti: düzeltme yeniden açık
    draw(c, rectangle(l=20, t=20, r=110, b=110, noise=1.0))
    assert c.last_correction == "rectangle"


def test_snapshot_round_trip_keeps_corrected_shape(qtbot):
    from matematigin_mantigi.ui.main_window import ink_from_snapshot
    c = make(qtbot)
    draw(c, circle(noise=1.0))
    snap = c.snapshot_image()
    restored = make(qtbot, PenSettings())
    layer = restored._strokes
    restored._strokes = ink_from_snapshot(snap, layer.size(), layer.devicePixelRatio())
    restored.update()
    assert alpha(restored, 290, 150) > 150
    assert alpha(restored, 200, 150) == 0


def test_resize_scales_corrected_shape_and_undo_stack(qtbot):
    c = make(qtbot)
    draw(c, circle(noise=1.0))
    c.resize(800, 600)
    QApplication.processEvents()
    assert alpha(c, 580, 300) > 0          # 2 kat büyümüş sağ kenar
    assert c.can_undo()
    c.undo()
    assert not c.is_empty()
    c.undo()
    assert c.is_empty()
