"""Şekil menüsü: görsel ızgara, araç çubuğu bağlantısı, her şeklin tuvale çizimi."""
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QImage

from matematigin_mantigi.core.models import SHAPE_META, SHAPE_ORDER, Shape, Tool
from matematigin_mantigi.ui.canvas import DrawingCanvas
from matematigin_mantigi.ui.shape_menu import ShapeMenu
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar

FAM = FontFamilies("Arial", "Arial", False)


def test_menu_has_one_visual_button_per_shape_in_order(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    assert list(m.buttons) == list(SHAPE_ORDER)
    for shape, b in m.buttons.items():
        assert b.toolTip() == SHAPE_META[shape][0]
        pm = b.grab().toImage()
        assert any(pm.pixelColor(x, y) != pm.pixelColor(0, 0) for x in range(0, pm.width(), 2)
                   for y in range(0, pm.height(), 2)), shape      # ikon boş değil


def test_menu_icons_are_all_distinct(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    m.show()
    images = {s: b.grab().toImage() for s, b in m.buttons.items()}
    keys = {s: bytes(i.constBits().asarray(i.sizeInBytes())) for s, i in images.items()}
    assert len(set(keys.values())) == len(keys)


def test_menu_marks_current_and_emits_choice_then_closes(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    m.set_current(Shape.HEXAGON)
    assert [s for s, b in m.buttons.items() if b.isChecked()] == [Shape.HEXAGON]
    m.show()
    with qtbot.waitSignal(m.shapeSelected) as sig:
        qtbot.mouseClick(m.buttons[Shape.STAR], Qt.MouseButton.LeftButton)
    assert sig.args == [Shape.STAR] and not m.isVisible()
    assert [s for s, b in m.buttons.items() if b.isChecked()] == [Shape.STAR]


def test_menu_is_laid_out_in_a_grid_that_fits_on_small_screens(qtbot):
    m = ShapeMenu()
    qtbot.addWidget(m)
    m.show()
    assert m.width() <= 460 and m.height() <= 420      # 5 sütun, ad satırlı düğmeler + dolgu satırı; 720p'ye sığar
    assert len({b.y() for b in m.buttons.values()}) >= 2        # tek şerit değil, ızgara


def test_toolbar_opens_menu_and_forwards_selection(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    tb.open_shape_menu()
    assert tb.shape_menu.isVisible()
    with qtbot.waitSignal(tb.shapeSelected) as sig:
        qtbot.mouseClick(tb.shape_menu.buttons[Shape.PENTAGON], Qt.MouseButton.LeftButton)
    assert sig.args == [Shape.PENTAGON]
    assert tb.tool_buttons[Tool.SHAPE].shape_icon == Shape.PENTAGON


def test_toolbar_shape_button_draws_the_chosen_shape_icon(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    shots = []
    for s in (Shape.STAR, Shape.HEXAGON):
        tb.set_shape(s)
        shots.append(tb.tool_buttons[Tool.SHAPE].grab().toImage())
    assert shots[0] != shots[1]


def test_right_click_on_shape_button_opens_menu(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    qtbot.mouseClick(tb.tool_buttons[Tool.SHAPE], Qt.MouseButton.RightButton)
    assert tb.shape_menu.isVisible()


def test_menu_stays_inside_the_screen(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    tb.open_shape_menu()
    screen = tb.screen().availableGeometry()
    assert screen.contains(tb.shape_menu.geometry())


def canvas(qtbot):
    c = DrawingCanvas()
    qtbot.addWidget(c)
    c.resize(500, 400)
    c.show()
    c.set_tool(Tool.SHAPE)
    c.set_base_width(4)
    return c


def drag(c, a, b):
    c.begin_stroke(QPointF(*a), .5); c.extend_stroke(QPointF(*b), .5); c.end_stroke()


@pytest.mark.parametrize("shape", list(Shape))
def test_every_shape_draws_ink_and_undoes(qtbot, shape):
    c = canvas(qtbot)
    c.set_shape(shape)
    drag(c, (100, 80), (300, 280))
    assert not c.is_empty()
    img = c.strokes_image()
    assert any(img.pixelColor(x, y).alpha() > 0 for x in range(90, 320, 3) for y in range(70, 300, 3))
    c.undo()
    assert c.is_empty()


def test_circle_pixels_lie_on_the_circle_and_square_on_the_square(qtbot):
    c = canvas(qtbot)
    c.set_shape(Shape.CIRCLE)
    drag(c, (100, 100), (300, 250))               # sürükleme dikdörtgen ama daire yuvarlak: çap 150
    img = c.strokes_image()
    cx, cy, r = 175, 175, 75
    assert img.pixelColor(cx + r, cy).alpha() > 0 and img.pixelColor(cx, cy - r).alpha() > 0
    assert img.pixelColor(300, 250).alpha() == 0 and img.pixelColor(cx, cy).alpha() == 0
    c2 = canvas(qtbot)
    c2.set_shape(Shape.SQUARE)
    drag(c2, (100, 100), (300, 250))
    im2 = c2.strokes_image()
    assert im2.pixelColor(250, 175).alpha() > 0 and im2.pixelColor(175, 250).alpha() > 0
    assert im2.pixelColor(300, 175).alpha() == 0


def test_preview_overlay_shows_new_shape_while_dragging(qtbot):
    c = canvas(qtbot)
    c.set_shape(Shape.HEXAGON)
    c.begin_stroke(QPointF(100, 100), .5); c.extend_stroke(QPointF(260, 260), .5)
    ov = c._overlay
    assert any(ov.pixelColor(x, y).alpha() > 0 for x in range(100, 260, 4) for y in range(100, 260, 4))
    assert c.is_empty()
    c.end_stroke()
    assert not c.is_empty()
