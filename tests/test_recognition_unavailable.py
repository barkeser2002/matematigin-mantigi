import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QMessageBox

from matematigin_mantigi.core.models import PenSettings
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies

LOCKED = ("math_recognition", "template_matching")          # henüz hazır olmayan tanıma özellikleri
AVAILABLE = "shape_correction"                              # ML'siz geometri: açılmış, varsayılan kapalı


@pytest.mark.parametrize("saved", [True, False])
def test_only_shape_correction_is_unlocked_and_preferences_survive_apply(qtbot, monkeypatch, saved):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: pytest.fail("unexpected modal"))
    keys = ("math_recognition", "shape_correction", "template_matching")
    original = PenSettings(**{key: saved for key in keys})
    dialog = PenSettingsDialog(original, QColor("#000"), 4, FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(dialog)
    dialog.show()
    for key in LOCKED:
        checkbox = dialog.toggles[key]
        assert not checkbox.isEnabled()
        assert "yakında" in checkbox.text().lower()
        assert not checkbox.isChecked()
        qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)
    shape = dialog.toggles[AVAILABLE]
    assert shape.isEnabled()
    assert "yakında" not in shape.text().lower()
    assert shape.isChecked() is saved
    qtbot.mouseClick(shape, Qt.MouseButton.LeftButton, pos=QPoint(8, 9))     # gösterge üstüne; satırın boş kısmı tıklanmaz
    assert shape.isChecked() is (not saved)
    assert dialog.toggles["autosave"].isEnabled()
    dialog.toggles["autosave"].setChecked(not original.autosave)
    with qtbot.waitSignal(dialog.applied) as signal:
        qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
    result = signal.args[0]
    assert all(getattr(result, key) == saved for key in LOCKED)
    assert result.shape_correction is (not saved)
    assert result.autosave != original.autosave
    labels = [label.text().lower() for label in dialog.findChildren(QLabel)]
    assert any("örnek" in text and "canlı" in text for text in labels)
    assert not any("tanındı" in text for text in labels)


def test_shape_toggle_is_off_by_default_in_a_fresh_dialog(qtbot):
    dialog = PenSettingsDialog(PenSettings(), QColor("#000"), 4, FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(dialog)
    assert dialog.toggles[AVAILABLE].isEnabled()
    assert not dialog.toggles[AVAILABLE].isChecked()
