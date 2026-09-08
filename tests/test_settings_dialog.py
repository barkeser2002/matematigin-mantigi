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
    assert d.chroma_check.isChecked()
    d.chroma_check.setChecked(False)
    d.reading_slider.setValue(0); d.auto_key_check.setChecked(False)
    d.visibility_checks["cam_label"].setChecked(False)
    v = d.value()
    assert v.reading_ms == 0 and d.reading_value.text() == "kapalı" and v.auto_key is False
    assert v.chroma_enabled is False
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


def test_logo_choose_and_clear(qtbot, ini_settings, tmp_path, monkeypatch):
    logo = tmp_path / "logo.png"; logo.write_bytes(b"\0")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(logo), "")))
    d = SettingsDialog(ini_settings, FAM)
    qtbot.addWidget(d)
    qtbot.mouseClick(d.choose_logo_button, Qt.MouseButton.LeftButton)
    assert d.value().logo_file == str(logo)
    qtbot.mouseClick(d.clear_logo_button, Qt.MouseButton.LeftButton)
    assert d.value().logo_file == ""


def test_camera_scan_fills_combo(qtbot, ini_settings, monkeypatch):
    from matematigin_mantigi.core import cameras
    ini_settings.camera_index = 1
    monkeypatch.setattr(cameras, "list_cameras", lambda max_index=6: [cameras.CameraInfo(0, 640, 480),
                                                                        cameras.CameraInfo(1, 1280, 720)])
    d = SettingsDialog(ini_settings, FAM)
    qtbot.addWidget(d)
    assert d.value().camera_index == 1                             # taramadan önce kayıtlı indeks
    qtbot.mouseClick(d.scan_button, Qt.MouseButton.LeftButton)
    assert d.camera_combo.count() == 2 and d.value().camera_index == 1
    assert d.camera_combo.currentText() == "Kamera 1 (1280×720)"
    d.camera_combo.setCurrentIndex(0)
    assert d.value().camera_index == 0


def test_record_and_logo_size_fields(qtbot, ini_settings, monkeypatch):
    from matematigin_mantigi.core import audio_capture as ac
    monkeypatch.setattr(ac, "list_input_devices", lambda *a, **k: ["Mikrofon (USB)", "Steam Mic"])
    d = SettingsDialog(ini_settings, FAM)
    qtbot.addWidget(d)
    v = d.value()
    assert (v.record_fps, v.record_height, v.audio_device, v.logo_size) == (60, 1440, "", 48)
    d.fps_combo.setCurrentIndex(d.fps_combo.findData(30)); d.res_combo.setCurrentIndex(d.res_combo.findData(0))
    d.logo_size_slider.setValue(96)
    qtbot.mouseClick(d.list_audio_button, Qt.MouseButton.LeftButton)
    assert d.audio_combo.count() == 3
    d.audio_combo.setCurrentIndex(1)
    v = d.value()
    assert (v.record_fps, v.record_height, v.audio_device, v.logo_size) == (30, 0, "Mikrofon (USB)", 96)
    assert d.logo_size_value.text() == "96 px"


def test_apply_emits_values(qtbot, ini_settings):
    d = SettingsDialog(ini_settings, FAM)
    qtbot.addWidget(d)
    d.reading_slider.setValue(70)
    with qtbot.waitSignal(d.applied) as sig:
        qtbot.mouseClick(d.apply_button, Qt.MouseButton.LeftButton)
    assert sig.args[0].reading_ms == 70 and d.result() == d.DialogCode.Accepted.value


def test_dialog_scrolls_and_keeps_apply_visible_on_small_screen(qtbot, ini_settings):
    d = SettingsDialog(ini_settings, FAM); qtbot.addWidget(d)
    d.setMaximumHeight(420); d.resize(620, 420); d.show(); qtbot.waitExposed(d)
    assert d.scroll.widget() is d.content and d.content.sizeHint().height() > 420
    assert d.apply_button.isVisible() and d.apply_button.geometry().bottom() <= d.height()
    assert d.scroll.verticalScrollBar().maximum() > 0
