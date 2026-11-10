import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QMessageBox

from matematigin_mantigi.core.models import PenSettings
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies


@pytest.mark.parametrize("saved", [True, False])
def test_unavailable_recognition_is_locked_and_preferences_survive_apply(qtbot, monkeypatch, saved):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: pytest.fail("unexpected modal"))
    keys = ("math_recognition", "shape_correction", "template_matching")
    original = PenSettings(**{key: saved for key in keys})
    dialog = PenSettingsDialog(original, QColor("#000"), 4, FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(dialog)
    dialog.show()
    for key in keys:
        checkbox = dialog.toggles[key]
        assert not checkbox.isEnabled()
        assert "yakında" in checkbox.text().lower()
        assert not checkbox.isChecked()
        qtbot.mouseClick(checkbox, Qt.MouseButton.LeftButton)
    assert dialog.toggles["autosave"].isEnabled()
    dialog.toggles["autosave"].setChecked(not original.autosave)
    with qtbot.waitSignal(dialog.applied) as signal:
        qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)
    result = signal.args[0]
    assert all(getattr(result, key) == saved for key in keys)
    assert result.autosave != original.autosave
    labels = [label.text().lower() for label in dialog.findChildren(QLabel)]
    assert any("örnek" in text and "canlı" in text for text in labels)
    assert not any("tanındı" in text for text in labels)
