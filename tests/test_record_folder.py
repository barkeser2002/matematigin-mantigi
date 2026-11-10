from PyQt6.QtWidgets import QFileDialog

from matematigin_mantigi.ui.settings_dialog import SettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies


def test_folder_selection_apply_and_cancel(qtbot, ini_settings, tmp_path, monkeypatch):
    folder = tmp_path / 'Ders Şğ'; folder.mkdir()
    dialog = SettingsDialog(ini_settings, FontFamilies('Arial', 'Arial', False))
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **k: str(folder))
    dialog.choose_record_folder_button.click()
    assert dialog.value().record_folder == str(folder)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **k: '')
    dialog.choose_record_folder_button.click()
    assert dialog.value().record_folder == str(folder)
    dialog.default_record_folder_button.click()
    assert dialog.value().record_folder == ''


def test_selected_folder_real_recording_and_next_change(qtbot, ini_settings, tmp_path, monkeypatch):
    import numpy as np
    import cv2
    import pytest
    from matematigin_mantigi import app
    from matematigin_mantigi.core.recorder import RecordRect, find_ffmpeg
    if not find_ffmpeg():
        pytest.skip("ffmpeg yok")
    monkeypatch.chdir(tmp_path)
    first = tmp_path / "Çekim bir"; first.mkdir()
    second = tmp_path / "Çekim iki"; second.mkdir()
    win = app.build_window(app.parse_args(["prog", "--kamera-yok"]), FontFamilies("Arial", "Arial", False), ini_settings)
    qtbot.addWidget(win)
    d = SettingsDialog(ini_settings, FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(d)
    d.applied.connect(win.apply_settings_values)
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', lambda *a, **k: str(first))
    d.choose_record_folder_button.click(); d.apply_button.click()
    ini_settings.sync()
    from PyQt6.QtCore import QSettings
    from matematigin_mantigi.core.settings import AppSettings
    assert AppSettings(QSettings(str(tmp_path / 'test.ini'), QSettings.Format.IniFormat)).record_folder == str(first)
    rec = win.recorder
    rec._grabber = lambda rect: np.full((rect.height, rect.width, 4), 180, np.uint8)
    rec.out_height = 0
    rec.start(RecordRect(0, 0, 160, 120), fps=10)
    qtbot.waitUntil(lambda: rec.frames_written >= 3, timeout=5000)
    ini_settings.record_folder = str(second)
    out = rec.stop()
    assert out.parent == first and out.exists() and rec.error is None
    cap = cv2.VideoCapture(str(out)); ok, frame = cap.read(); cap.release()
    assert ok and frame.shape[:2] == (120, 160)
    rec.start(RecordRect(0, 0, 160, 120), fps=10)
    qtbot.waitUntil(lambda: rec.frames_written >= 3, timeout=5000)
    out2 = rec.stop()
    assert out2.parent == second and out2.exists() and rec.error is None
    assert out.exists()
    ini_settings.record_folder = str(tmp_path / 'silinmiş')
    with pytest.raises(Exception, match='Kayıt klasörü'):
        rec.start(RecordRect(0, 0, 160, 120), fps=10)
    assert not (tmp_path / 'silinmiş').exists()
