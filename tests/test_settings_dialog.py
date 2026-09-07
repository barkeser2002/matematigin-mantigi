from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog

from matematigin_mantigi.core.models import PenSettings
from matematigin_mantigi.core.settings import VISIBILITY_KEYS
from matematigin_mantigi.ui.settings_dialog import SettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


def test_dialog_reflects_settings_and_returns_values(qtbot, ini_settings):
    ini_settings.set_visible("status", False)
    ini_settings.set_pen(PenSettings(reading_ms=25))
    d = SettingsDialog(ini_settings, FAM)
    qtbot.addWidget(d)
    assert d.reading_slider.value() == 25 and d.reading_value.text() == "25 ms/harf"
    assert d.auto_key_check.isChecked()
    assert set(d.visibility_checks) == {k for k, _ in VISIBILITY_KEYS}
    assert not d.visibility_checks["status"].isChecked() and d.visibility_checks["brand"].isChecked()
    d.reading_slider.setValue(0); d.auto_key_check.setChecked(False)
    d.visibility_checks["cam_label"].setChecked(False)
    v = d.value()
    assert v.reading_ms == 0 and d.reading_value.text() == "kapalı" and v.auto_key is False
    assert v.visible["cam_label"] is False and v.visible["status"] is False and v.visible["brand"] is True
    assert v.font_file == "" and v.presenter_name == "Koray Varol"
    d.presenter_edit.setText("  Ad Soyad ")
    assert d.value().presenter_name == "Ad Soyad"


def test_choose_font_file_and_default(qtbot, ini_settings, tmp_path, monkeypatch):
    fake = tmp_path / "Ozel.ttf"; fake.write_bytes(b"\0")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(fake), "")))
    d = SettingsDialog(ini_settings, FAM)
    qtbot.addWidget(d)
    qtbot.mouseClick(d.choose_font_button, Qt.MouseButton.LeftButton)
    assert d.value().font_file == str(fake)
    qtbot.mouseClick(d.default_font_button, Qt.MouseButton.LeftButton)
    assert d.value().font_file == ""


def test_apply_emits_values(qtbot, ini_settings):
    d = SettingsDialog(ini_settings, FAM)
    qtbot.addWidget(d)
    d.reading_slider.setValue(70)
    with qtbot.waitSignal(d.applied) as sig:
        qtbot.mouseClick(d.apply_button, Qt.MouseButton.LeftButton)
    assert sig.args[0].reading_ms == 70 and d.result() == d.DialogCode.Accepted.value
