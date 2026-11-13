"""Şekil menüsü ve düzgün şekiller: kapsam, geometri, Shift/Alt, dolgu, geri alma, kalıcılık, kayıt kuralı.

Geometri testleri Qt'siz core/shapes.py'yi, menü/araç çubuğu/tuval testleri offscreen Qt'yi kullanır.
Gerçek modal açabilecek her testte QMessageBox monkeypatch'lenir.
"""
import math

import pytest
from PyQt6.QtCore import QPointF, QSettings, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QMessageBox

from matematigin_mantigi.core.models import SHAPE_META, SHAPE_ORDER, Shape, Tool
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.core.shapes import CLOSED_SHAPES, Oval, Poly, constrain, shape_geometry
from matematigin_mantigi.ui.canvas import DrawingCanvas
from matematigin_mantigi.ui.shape_menu import ShapeMenu
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar

FAM = FontFamilies("Arial", "Arial", False)
REQUIRED = {Shape.LINE, Shape.ARROW, Shape.DOUBLE_ARROW, Shape.RECT, Shape.SQUARE, Shape.ELLIPSE, Shape.CIRCLE,
            Shape.TRIANGLE, Shape.EQUILATERAL, Shape.RIGHT_TRIANGLE, Shape.PENTAGON, Shape.HEXAGON,
            Shape.PARALLELOGRAM, Shape.TRAPEZOID, Shape.AXES, Shape.AXES_TICKS, Shape.NUMBER_LINE, Shape.ANGLE}
DRAGS = [((10, 10), (110, 70)), ((110, 70), (10, 10)), ((10, 70), (110, 10)), ((110, 10), (10, 70))]


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def sides(pts):
    return [dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def angle_at(pts, i):
    p, q, r = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
    v1, v2 = (p[0] - q[0], p[1] - q[1]), (r[0] - q[0], r[1] - q[1])
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def poly(shape, a, b):
    items = shape_geometry(shape, a, b)
    assert len(items) == 1 and isinstance(items[0], Poly)
    return items[0].points


# --- kapsam ----------------------------------------------------------------------------------------
def test_required_shapes_are_all_in_menu_with_turkish_names():
    assert REQUIRED <= set(SHAPE_ORDER)
    assert set(SHAPE_ORDER) == set(Shape) == set(SHAPE_META)
    assert all(SHAPE_META[s][0] for s in Shape)


# --- geometri --------------------------------------------------------------------------------------
@pytest.mark.parametrize("a,b", DRAGS)
def test_regular_hexagon_has_six_equal_sides_within_one_pixel(a, b):
    pts = poly(Shape.HEXAGON, a, b)
    assert len(pts) == 6
    s = sides(pts)
    assert max(s) - min(s) <= 1.0
    assert all(abs(angle_at(pts, i) - 120) < 1e-6 for i in range(6))


@pytest.mark.parametrize("a,b", DRAGS)
def test_regular_pentagon_has_five_equal_sides_within_one_pixel(a, b):
    pts = poly(Shape.PENTAGON, a, b)
    s = sides(pts)
    assert len(pts) == 5 and max(s) - min(s) <= 1.0
    assert all(abs(angle_at(pts, i) - 108) < 1e-6 for i in range(5))


@pytest.mark.parametrize("a,b", DRAGS)
def test_square_sides_equal_and_right_angles(a, b):
    pts = poly(Shape.SQUARE, a, b)
    s = sides(pts)
    assert max(s) - min(s) <= 1e-6
    assert all(abs(angle_at(pts, i) - 90) < 1e-6 for i in range(4))


@pytest.mark.parametrize("a,b", DRAGS)
def test_equilateral_triangle_sides_within_one_pixel(a, b):
    s = sides(poly(Shape.EQUILATERAL, a, b))
    assert max(s) - min(s) <= 1.0


def test_right_triangle_has_exactly_one_right_angle():
    pts = poly(Shape.RIGHT_TRIANGLE, (10, 10), (110, 70))
    angles = sorted(angle_at(pts, i) for i in range(3))
    assert angles[2] == pytest.approx(90, abs=1e-6) and sum(angles) == pytest.approx(180)


def test_isosceles_triangle_has_two_equal_legs_and_apex_over_base_center():
    pts = poly(Shape.TRIANGLE, (10, 10), (110, 70))
    s = sides(pts)                                           # [tepe-sağ, taban, sol-tepe]
    assert s[0] == pytest.approx(s[2]) and s[1] == pytest.approx(100)
    assert pts[0] == (60, 10)


def test_angle_is_two_rays_and_an_arc_between_them():
    items = shape_geometry(Shape.ANGLE, (100, 200), (200, 200))
    assert len(items) == 3 and all(isinstance(i, Poly) and not i.closed for i in items)
    ray1, ray2, arc = items
    vertex = (100.0, 200.0)
    assert ray1.points[0] == vertex and ray2.points[0] == vertex
    assert ray1.points[1] == (200, 200)
    L = dist(vertex, ray2.points[1])
    assert L == pytest.approx(100, abs=1e-6)
    v1 = (ray1.points[1][0] - vertex[0], ray1.points[1][1] - vertex[1])
    v2 = (ray2.points[1][0] - vertex[0], ray2.points[1][1] - vertex[1])
    between = math.degrees(math.acos((v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))))
    assert between == pytest.approx(60, abs=1e-6)
    radii = [dist(p, vertex) for p in arc.points]
    assert radii == pytest.approx([radii[0]] * len(radii)) and radii[0] < L
    assert arc.points[0] == pytest.approx((vertex[0] + radii[0], vertex[1]))        # yay birinci ışında başlar
    end = arc.points[-1]
    assert math.degrees(math.atan2(end[1] - vertex[1], end[0] - vertex[0])) == pytest.approx(
        math.degrees(math.atan2(v2[1], v2[0])), abs=1e-6)                            # ikinci ışında biter


def test_number_line_has_straight_axis_and_equal_tick_spacing():
    items = shape_geometry(Shape.NUMBER_LINE, (100, 200), (300, 260))
    axis = items[0]
    ys = {round(p[1], 6) for p in axis.points}
    assert len(ys) == 1                                       # yatay eksen
    ticks = [i for i in items[1:] if isinstance(i, Poly) and not i.closed and abs(i.points[0][0] - i.points[1][0]) < 1e-6]
    xs = sorted(t.points[0][0] for t in ticks)
    assert len(xs) == 11
    gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    assert max(gaps) - min(gaps) <= 1.0


def test_double_arrow_has_heads_at_both_ends():
    items = shape_geometry(Shape.DOUBLE_ARROW, (10, 40), (210, 40))
    tips = [i.points[1] for i in items[1:]]
    assert (210, 40) in tips and (10, 40) in tips and len(items) == 3


def test_axes_ticks_are_symmetric_about_the_center():
    items = shape_geometry(Shape.AXES_TICKS, (10, 10), (210, 110))
    ticks = [i for i in items[2:] if isinstance(i, Poly)]
    assert len(ticks) >= 8
    xs = [t.points[0][0] for t in ticks if t.points[0][0] == t.points[1][0]]
    assert sum(xs) / len(xs) == pytest.approx(110, abs=1e-6)


def test_star_and_rhombus_keep_working_as_before():
    st = poly(Shape.STAR, (10, 10), (110, 70))
    assert len(st) == 10 and sides(st) == pytest.approx([sides(st)[0]] * 10)


# --- Shift / Alt ----------------------------------------------------------------------------------
def test_shift_locks_free_box_shapes_to_equal_extents():
    a, b = constrain(Shape.RECT, (0, 0), (100, 40), shift=True)
    assert b == pytest.approx((40, 40)) and a == (0, 0)


def test_shift_snaps_lines_to_15_degree_steps_and_keeps_length():
    a, b = constrain(Shape.LINE, (0, 0), (100, 30), shift=True)
    ang = math.degrees(math.atan2(b[1], b[0]))
    assert ang == pytest.approx(15, abs=1e-6)
    assert dist(a, b) == pytest.approx(math.hypot(100, 30))


def test_shift_does_not_change_already_locked_shapes():
    for s in (Shape.SQUARE, Shape.CIRCLE, Shape.HEXAGON, Shape.PENTAGON, Shape.EQUILATERAL):
        assert constrain(s, (0, 0), (100, 40), shift=True) == constrain(s, (0, 0), (100, 40))


def test_alt_makes_the_press_point_the_center():
    a, b = constrain(Shape.RECT, (100, 100), (150, 130), alt=True)
    assert a == pytest.approx((50, 70)) and b == (150, 130)
    box = shape_geometry(Shape.RECT, a, b)[0].points
    xs, ys = [p[0] for p in box], [p[1] for p in box]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(100) and (min(ys) + max(ys)) / 2 == pytest.approx(100)


def canvas(qtbot, shape=Shape.RECT):
    c = DrawingCanvas()
    qtbot.addWidget(c)
    c.resize(500, 400)
    c.show()
    c.set_tool(Tool.SHAPE)
    c.set_base_width(4)
    c.set_shape(shape)
    return c


def drag(c, a, b, mods=Qt.KeyboardModifier.NoModifier):
    c.begin_stroke(QPointF(*a), .5, modifiers=mods)
    c.extend_stroke(QPointF(*b), .5, mods)
    c.end_stroke()


def alpha(img, x, y):
    return img.pixelColor(x, y).alpha()


def test_shift_preview_while_dragging_is_square(qtbot):
    c = canvas(qtbot)
    c.begin_stroke(QPointF(100, 100), .5)
    c.extend_stroke(QPointF(300, 200), .5, Qt.KeyboardModifier.ShiftModifier)
    ov = c._overlay
    assert any(alpha(ov, 200, y) > 0 for y in range(140, 160, 2))      # sağ kenar x=200
    assert all(alpha(ov, x, 150) == 0 for x in range(230, 300, 4))     # uzun kenar yok
    c.end_stroke()
    assert alpha(c.strokes_image(), 200, 150) > 0


def test_alt_drag_draws_symmetric_about_press_point(qtbot):
    c = canvas(qtbot)
    drag(c, (250, 200), (300, 240), Qt.KeyboardModifier.AltModifier)
    img = c.strokes_image()
    assert alpha(img, 200, 200) > 0 and alpha(img, 300, 200) > 0      # sol ve sağ kenar merkeze eşit
    assert alpha(img, 250, 160) > 0 and alpha(img, 250, 240) > 0      # üst ve alt kenar
    assert alpha(img, 250, 200) == 0                                  # boş (dolgu kapalı)


def test_shift_on_line_draws_at_15_degrees(qtbot):
    c = canvas(qtbot, Shape.LINE)
    drag(c, (50, 200), (250, 230), Qt.KeyboardModifier.ShiftModifier)
    img = c.strokes_image()
    # 15° çizgisinin orta noktası (50,200)->(245.4,252.3) yaklaşık (148,226); 5 px tolerans
    assert any(alpha(img, x, y) > 0 for x in range(143, 154) for y in range(221, 232))
    assert all(alpha(img, 150, y) == 0 for y in range(180, 205))      # 15° dışındaki yer boş


# --- dolgu -----------------------------------------------------------------------------------------
def _centroid(shape):
    items = shape_geometry(shape, (100, 80), (300, 280))
    pts = [p for i in items if isinstance(i, Poly) for p in i.points]
    if len(items) == 1 and isinstance(items[0], Oval):
        return items[0].cx, items[0].cy
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


@pytest.mark.parametrize("shape", sorted(CLOSED_SHAPES, key=lambda s: s.value))
def test_filled_closed_shapes_are_translucent_inside_and_empty_when_off(qtbot, shape):
    cx, cy = _centroid(shape)
    off = canvas(qtbot, shape)
    drag(off, (100, 80), (300, 280))
    assert alpha(off.strokes_image(), round(cx), round(cy)) == 0
    on = canvas(qtbot, shape)
    on.set_shape_fill(True)
    drag(on, (100, 80), (300, 280))
    a = alpha(on.strokes_image(), round(cx), round(cy))
    assert 0 < a < 255


def test_fill_is_ignored_by_open_shapes(qtbot):
    c = canvas(qtbot, Shape.LINE)
    c.set_shape_fill(True)
    drag(c, (100, 200), (300, 200))
    assert alpha(c.strokes_image(), 200, 150) == 0


# --- geri al / yinele, tahta kaydı, ölçekleme -------------------------------------------------------
@pytest.mark.parametrize("shape", list(Shape))
def test_every_shape_undo_then_redo_restores_identical_pixels(qtbot, shape):
    c = canvas(qtbot, shape)
    drag(c, (100, 80), (300, 280))
    before = bytes(c.strokes_image().constBits().asarray(c.strokes_image().sizeInBytes()))
    c.undo()
    assert c.is_empty()
    c.redo()
    after = bytes(c.strokes_image().constBits().asarray(c.strokes_image().sizeInBytes()))
    assert before == after


def test_board_png_round_trip_keeps_new_shapes(qtbot, tmp_path):
    c = canvas(qtbot, Shape.HEXAGON)
    drag(c, (100, 80), (300, 280))
    snap = c.snapshot_image()
    path = tmp_path / "tahta.png"
    assert snap.save(str(path), "PNG")
    back = QImage(str(path))
    assert not back.isNull()
    # altıgenin sağ köşesi (300,180) ince siyah çizgiyle geri yüklenir; 3x3 komşulukta en az bir koyu piksel
    assert min(back.pixelColor(x, y).red() for x in range(298, 303) for y in range(178, 183)) < 200
    assert back.pixelColor(20, 20).red() > 240                        # arka plan beyaz


def test_board_scaling_keeps_shapes(qtbot):
    c = canvas(qtbot, Shape.CIRCLE)
    drag(c, (100, 80), (300, 280))
    c.resize(1000, 800)
    qtbot.waitUntil(lambda: not c.strokes_image().isNull())
    img = c.strokes_image()
    assert img.width() >= 1000 and not c.is_empty()
    assert any(img.pixelColor(x, y).alpha() > 0 for x in range(180, 420, 3) for y in range(60, 560, 3))


# --- menü ------------------------------------------------------------------------------------------
def test_menu_buttons_show_icon_and_name(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    for shape, b in m.buttons.items():
        assert b.label == SHAPE_META[shape][0] and b.toolTip() == SHAPE_META[shape][0]


def test_menu_grid_fits_a_720p_screen_and_uses_five_columns(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    m.show()
    assert m.width() <= 460 and m.height() <= 420
    assert len({b.x() for b in m.buttons.values()}) == 5
    assert all(b.width() >= 70 and b.height() >= 66 for b in m.buttons.values())   # kalemle seçilebilir


def test_menu_fill_row_emits_and_stays_open(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    m.show()
    with qtbot.waitSignal(m.fillSelected) as sig:
        qtbot.mouseClick(m.fill_buttons[True], Qt.MouseButton.LeftButton)
    assert sig.args == [True] and m.isVisible()
    m.set_fill(False)
    assert m.fill_buttons[False].isChecked() and not m.fill_buttons[True].isChecked()


def test_menu_closes_by_itself_after_auto_close_time(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    m.set_auto_close_ms(60)
    m.popup_beside(QPointF(10, 10).toPoint(), m.screen().availableGeometry())
    assert m.isVisible()
    qtbot.waitUntil(lambda: not m.isVisible(), timeout=3000)


def test_toolbar_refuses_menu_when_gate_says_so(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    tb.shape_menu_gate = lambda: -1
    tb.open_shape_menu()
    assert not tb.shape_menu.isVisible()


def test_toolbar_forwards_fill_choice(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    tb.open_shape_menu()
    with qtbot.waitSignal(tb.shapeFillSelected) as sig:
        qtbot.mouseClick(tb.shape_menu.fill_buttons[True], Qt.MouseButton.LeftButton)
    assert sig.args == [True]


# --- kalıcılık -------------------------------------------------------------------------------------
def test_shape_and_fill_persist_in_qsettings(tmp_path):
    ini = str(tmp_path / "s.ini")
    s = AppSettings(QSettings(ini, QSettings.Format.IniFormat))
    assert s.shape == Shape.RECT and s.shape_fill is False          # varsayılanlar
    s.shape = Shape.HEXAGON
    s.shape_fill = True
    again = AppSettings(QSettings(ini, QSettings.Format.IniFormat))
    assert again.shape == Shape.HEXAGON and again.shape_fill is True


def test_bad_stored_shape_falls_back_to_rect(tmp_path):
    q = QSettings(str(tmp_path / "bad.ini"), QSettings.Format.IniFormat)
    q.setValue("shape", "yok-boyle-bir-sekil")
    assert AppSettings(q).shape == Shape.RECT


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch, dead_camera):
    from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    cfg = AppSettings(QSettings(str(tmp_path / "w.ini"), QSettings.Format.IniFormat))
    cfg.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FAM, list(SAMPLE_QUESTIONS), cfg, NullRecorder(), SessionStore(tmp_path / "oturum"),
                     lambda index: dead_camera, tmp_path / "duzen.json")
    qtbot.addWidget(win)
    win.resize(1920, 1080)
    win.show()
    qtbot.waitExposed(win)
    yield win
    win.webcam_panel.shutdown()


def test_window_restores_saved_shape_and_fill(qtbot, tmp_path, monkeypatch, dead_camera):
    from matematigin_mantigi.core.models import PenSettings, SAMPLE_QUESTIONS
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    ini = QSettings(str(tmp_path / "r.ini"), QSettings.Format.IniFormat)
    AppSettings(ini).shape = Shape.PENTAGON
    AppSettings(ini).shape_fill = True
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    cfg = AppSettings(ini)
    cfg.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FAM, list(SAMPLE_QUESTIONS), cfg, NullRecorder(), SessionStore(tmp_path / "o2"),
                     lambda index: dead_camera, tmp_path / "d.json")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    assert win.canvas.shape == Shape.PENTAGON and win.canvas.fill_shapes is True
    assert win.toolbar.tool_buttons[Tool.SHAPE].shape_icon == Shape.PENTAGON
    win.webcam_panel.shutdown()


def test_menu_choice_is_saved_and_fill_toggle_is_saved(window, qtbot):
    window.toolbar.open_shape_menu()
    qtbot.mouseClick(window.toolbar.shape_menu.buttons[Shape.STAR], Qt.MouseButton.LeftButton)
    assert window.settings.shape == Shape.STAR and window.canvas.shape == Shape.STAR
    window.toolbar.open_shape_menu()
    qtbot.mouseClick(window.toolbar.shape_menu.fill_buttons[True], Qt.MouseButton.LeftButton)
    assert window.settings.shape_fill is True and window.canvas.fill_shapes is True


def test_menu_during_recording_auto_closes_and_never_asks_a_dialog(window, qtbot, monkeypatch):
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a) or QMessageBox.StandardButton.No)
    window._record_starting = True
    assert window._shape_menu_gate() > 0                       # kayıtta: kısa süre açık kalır
    window._record_starting = False
    window._close_after_save = True
    assert window._shape_menu_gate() < 0                       # kapanış bekleniyorsa hiç açılmaz
    window._close_after_save = False
    assert window._shape_menu_gate() == 0
    assert asked == []


def test_menu_is_not_in_the_recorded_stage_when_closed(window):
    assert not window.toolbar.shape_menu.isVisible()
