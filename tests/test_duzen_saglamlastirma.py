"""Düzen/geometri sağlamlaştırmasının regresyon testleri (#23, #24, #25, #39)."""

import sys

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import FrameStyle
from matematigin_mantigi.ui import theme
from test_work_area import make


SIZES = ((1920, 1080), (1366, 768), (900, 1200))


@pytest.mark.parametrize("size", SIZES)
def test_relayout_reuses_eye_buttons_without_hidden_children(qtbot, size):
    wa, _ = make(qtbot)
    wa.resize(*size)
    wa.set_edit_mode(True)
    original = dict(wa._eye_buttons)
    before = len(wa.findChildren(QPushButton))
    assert len(original) == 8

    for _ in range(25):
        wa.relayout()

    assert len(wa.findChildren(QPushButton)) == before
    assert wa._eye_buttons == original
    assert all(button.isVisible() for button in original.values())


def move_with_modifiers(wa, pos, modifiers):
    event = QMouseEvent(QEvent.Type.MouseMove, QPointF(pos), QPointF(wa.mapToGlobal(pos)),
                        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, modifiers)
    QApplication.sendEvent(wa, event)


SNAP_MODIFIERS = (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.MetaModifier)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("modifiers", SNAP_MODIFIERS)
def test_both_control_modifiers_highlight_snap_grid_while_dragging(qtbot, size, modifiers):
    wa, zones = make(qtbot)
    wa.resize(*size)
    wa.set_edit_mode(True)
    start = zones["webcam"].geometry().center()
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    move_with_modifiers(wa, start + QPoint(-37, -5), modifiers)
    assert wa._snap_active
    move_with_modifiers(wa, start + QPoint(-37, -5), Qt.KeyboardModifier.NoModifier)
    assert not wa._snap_active
    qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-37, -5))


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("modifiers", SNAP_MODIFIERS)
def test_both_control_modifiers_snap_the_released_zone(qtbot, size, modifiers):
    wa, zones = make(qtbot)
    wa.resize(*size)
    wa.set_edit_mode(True)
    start = zones["webcam"].geometry().center()
    end = start + QPoint(-37, -5)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, end)
    inner, geo = wa.inner_rect(), zones["webcam"].geometry()
    args = (geo.x() - inner.x(), geo.y() - inner.y(), geo.width(), geo.height(),
            inner.width(), inner.height(), theme.GRID_GAP)
    expected = lm.snap_rect(*args)
    assert lm.free_rect(*args) != expected, "Girdi serbest/yapışık sonucu ayırt etmeli"
    with qtbot.waitSignal(wa.layoutChanged) as signal:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end, modifier=modifiers)
    assert signal.args[0]["webcam"] == expected
    assert not wa._snap_active


def test_macos_edit_hint_mentions_command_and_control(qtbot, monkeypatch):
    with monkeypatch.context() as patcher:
        patcher.setattr(sys, "platform", "darwin")
        wa, _ = make(qtbot)
    hints = [label.text() for label in wa.edit_bar.findChildren(QLabel)]
    assert any("⌘/Ctrl: ızgaraya yapıştır" in text for text in hints)


def isolated_zone(qtbot, size):
    wa, zones = make(qtbot)
    wa.resize(*size)
    wa.set_layout(dict(wa.layout(), soru=lm.PanelGeom(3, 3, 4, 4)))
    for key in ("hint_zone", "webcam", *lm.ITEM_KEYS):
        wa.set_item_visible(key, False)
    wa.set_edit_mode(True)
    return wa, zones["soru"]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("edge", ("n", "s", "e", "w", "nw", "ne", "sw", "se"))
def test_resize_clips_only_dragged_edges_and_preserves_opposite_edges(qtbot, size, edge):
    wa, zone = isolated_zone(qtbot, size)
    inner, before = wa.inner_rect(), zone.geometry()
    start = QPoint(before.left() + 3 if "w" in edge else before.right() - 3 if "e" in edge
                   else before.center().x(),
                   before.top() + 3 if "n" in edge else before.bottom() - 3 if "s" in edge
                   else before.center().y())
    end = start + QPoint(-inner.width() if "w" in edge else inner.width() if "e" in edge else 0,
                         -inner.height() if "n" in edge else inner.height() if "s" in edge else 0)
    expected = QRect(QPoint(inner.left() if "w" in edge else before.left(),
                            inner.top() if "n" in edge else before.top()),
                     QPoint(inner.right() if "e" in edge else before.right(),
                            inner.bottom() if "s" in edge else before.bottom()))
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    assert wa._drag[0:2] == ("soru", edge)
    move_with_modifiers(wa, end, Qt.KeyboardModifier.NoModifier)
    assert zone.geometry() == expected
    qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)
    assert zone.geometry() == expected
    assert inner.contains(zone.geometry())


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("direction", (-1, 1))
def test_move_still_translates_whole_zone_against_board_boundary(qtbot, size, direction):
    wa, zone = isolated_zone(qtbot, size)
    inner, before = wa.inner_rect(), zone.geometry()
    start = before.center()
    end = start + QPoint(direction * inner.width(), direction * inner.height())
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    assert wa._drag[0:2] == ("soru", "move")
    move_with_modifiers(wa, end, Qt.KeyboardModifier.NoModifier)
    after = zone.geometry()
    assert after.size() == before.size()
    assert inner.contains(after)
    assert (after.topLeft() == inner.topLeft() if direction < 0
            else after.bottomRight() == inner.bottomRight())
    qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)
    assert zone.geometry() == after


def hud_item_over_question(qtbot, size, key, visible=True):
    wa, zones = make(qtbot)
    wa.resize(*size)
    wa.set_layout(dict(wa.layout(), soru=lm.PanelGeom(0, 0, 12, 10)))
    for hidden in ("hint_zone", "webcam", *lm.ITEM_KEYS):
        wa.set_item_visible(hidden, False)
    wa.set_item_visible(key, visible)
    wa.set_frame_style(FrameStyle.HUD)
    wa.set_edit_mode(True)
    return wa, zones["soru"], wa._items[key]


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("key", ("brand", "presenter"))
def test_frame_owned_title_cannot_steal_question_drag(qtbot, size, key):
    wa, question, item = hud_item_over_question(qtbot, size, key)
    item.move(question.geometry().center() - QPoint(item.width() // 2, item.height() // 2))
    assert item.isHidden() and wa._visible[key]
    start = item.geometry().center()
    assert wa._hit(start) == ("soru", "move")
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    assert wa._drag[0:2] == ("soru", "move")
    qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start)


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("key", ("brand", "presenter"))
@pytest.mark.parametrize("visible", (True, False))
def test_frame_owned_title_has_neither_outline_nor_hidden_ghost(qtbot, size, key, visible):
    wa, question, item = hud_item_over_question(qtbot, size, key, visible)
    before = wa.overlay.grab().toImage()
    item.move(question.geometry().center() - QPoint(item.width() // 2, item.height() // 2))
    assert item.isHidden()
    assert wa.overlay.grab().toImage() == before


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("key", ("brand", "presenter"))
def test_frame_owned_title_keeps_reachable_functional_eye_button(qtbot, size, key):
    wa, _, _ = hud_item_over_question(qtbot, size, key)
    eye = wa._eye_buttons[key]
    assert eye.isVisible() and wa.childAt(eye.geometry().center()) is eye
    with qtbot.waitSignal(wa.visibilityToggled) as signal:
        qtbot.mouseClick(eye, Qt.MouseButton.LeftButton)
    assert signal.args == [key, False]
    assert not wa._visible[key] and not eye.isChecked()


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("key", ("brand", "presenter"))
@pytest.mark.parametrize("fallback", ("titles_off", "frame_off", "classic"))
def test_title_is_draggable_again_when_frame_stops_drawing_it(qtbot, size, key, fallback):
    wa, question, item = hud_item_over_question(qtbot, size, key)
    if fallback == "titles_off":
        wa.set_item_visible("frame_titles", False)
    elif fallback == "frame_off":
        wa.set_frame_visible(False)
    else:
        wa.set_frame_style(FrameStyle.CLASSIC)
    item.move(question.geometry().center() - QPoint(item.width() // 2, item.height() // 2))
    assert not item.isHidden()
    assert wa._hit(item.geometry().center()) == (key, "move")
