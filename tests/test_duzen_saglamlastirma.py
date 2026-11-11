"""Düzen/geometri sağlamlaştırmasının regresyon testleri (#23, #24, #25, #39)."""

import pytest
from PyQt6.QtWidgets import QPushButton

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
