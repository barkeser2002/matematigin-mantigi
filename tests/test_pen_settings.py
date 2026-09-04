from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from matematigin_mantigi.core.models import Nib, PenSettings
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


def test_dialog_reflects_current_and_returns_edits(qtbot):
    d = PenSettingsDialog(PenSettings(), QColor("#c8322b"), 4, FAM)
    qtbot.addWidget(d)
    assert d.curve_slider.value() == 50 and d.smoothing_slider.value() == 35
    assert d.min_slider.value() == 1 and d.max_slider.value() == 12
    assert d.nib_buttons[Nib.ROUND].isChecked()
    assert d.toggles["math_recognition"].isChecked() and not d.toggles["template_matching"].isChecked()
    d.smoothing_slider.setValue(60); d.max_slider.setValue(20)
    d.nib_buttons[Nib.CHALK].click()
    d.toggles["autosave"].setChecked(False)
    v = d.value()
    assert v == PenSettings(smoothing=60, max_width=20, nib=Nib.CHALK, autosave=False)


def test_apply_emits_and_accepts(qtbot):
    d = PenSettingsDialog(PenSettings(), QColor("#000"), 4, FAM)
    qtbot.addWidget(d)
    d.min_slider.setValue(3)
    with qtbot.waitSignal(d.applied) as sig:
        qtbot.mouseClick(d.apply_button, Qt.MouseButton.LeftButton)
    assert sig.args[0].min_width == 3 and d.result() == d.DialogCode.Accepted.value


def test_min_never_exceeds_max(qtbot):
    d = PenSettingsDialog(PenSettings(min_width=1, max_width=4), QColor("#000"), 4, FAM)
    qtbot.addWidget(d)
    d.min_slider.setValue(10)
    assert d.value().min_width <= d.value().max_width
