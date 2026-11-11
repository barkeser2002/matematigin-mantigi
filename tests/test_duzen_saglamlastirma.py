"""Düzen/geometri sağlamlaştırmasının regresyon testleri (#23, #24, #25, #39)."""

import sys

import pytest
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from matematigin_mantigi.core import layout_model as lm
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
