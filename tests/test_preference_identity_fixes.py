from PyQt6.QtCore import QSettings
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.core import audio_capture as ac
from matematigin_mantigi.ui.settings_dialog import SettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies


def test_missing_screen_preferences_survive_unrelated_apply(window, qtbot, tmp_path, monkeypatch):
    board = ('missing-board', 'vendor', 'model', '1')
    preview = ('missing-preview', 'vendor', 'model', '2')
    window.settings.board_screen_key = board
    window.settings.preview_screen_key = preview
    monkeypatch.setattr(window, '_configure_screens', lambda *args: None)
    dialog = SettingsDialog(window.settings, FontFamilies('Arial', 'Arial', False), window)
    qtbot.addWidget(dialog)
    assert 'bulunamadı' in dialog.board_screen_combo.currentText()
    assert 'bulunamadı' in dialog.preview_screen_combo.currentText()
    window.apply_settings_values(dialog.value())
    window.settings.sync()
    reopened = AppSettings(QSettings(window.settings._q.fileName(), QSettings.Format.IniFormat))
    assert reopened.board_screen_key == board
    assert reopened.preview_screen_key == preview
    dialog.board_screen_combo.setCurrentIndex(0)
    dialog.preview_screen_combo.setCurrentIndex(0)
    window.apply_settings_values(dialog.value())
    assert window.settings.board_screen_key is None
    assert window.settings.preview_screen_key is None


def test_board_preference_when_preview_closed(window, qtbot, monkeypatch):
    from matematigin_mantigi.ui.dual_screen import screen_key
    key = screen_key(window.screen())
    window.settings.board_screen_key = key
    window.settings.preview_screen_key = None
    monkeypatch.setattr(window, '_configure_screens', lambda *args: None)
    dialog = SettingsDialog(window.settings, FontFamilies('Arial', 'Arial', False), window)
    qtbot.addWidget(dialog)
    window.apply_settings_values(dialog.value())
    assert window.settings.board_screen_key == key


def test_duplicate_microphones_not_selectable(qtbot, ini_settings, monkeypatch):
    class SD:
        @staticmethod
        def query_hostapis(): return [{'name': 'Core Audio'}]
        @staticmethod
        def query_devices(): return [{'name': 'USB', 'hostapi': 0, 'max_input_channels': 1}] * 2
    monkeypatch.setattr(ac, '_sd', lambda: SD)
    dialog = SettingsDialog(ini_settings, FontFamilies('Arial', 'Arial', False))
    qtbot.addWidget(dialog)
    dialog._list_audio()
    assert dialog.audio_combo.count() == 3
    for index in (1, 2):
        assert 'belirsiz' in dialog.audio_combo.itemText(index).lower()
        assert not dialog.audio_combo.model().item(index).isEnabled()


def test_legacy_unique_name_is_not_marked_missing(qtbot, ini_settings, monkeypatch):
    class SD:
        @staticmethod
        def query_hostapis(): return [{'name': 'Core Audio'}]
        @staticmethod
        def query_devices(): return [{'name': 'USB', 'hostapi': 0, 'max_input_channels': 1}]
    monkeypatch.setattr(ac, '_sd', lambda: SD)
    ini_settings.audio_device = 'USB'
    dialog = SettingsDialog(ini_settings, FontFamilies('Arial', 'Arial', False))
    qtbot.addWidget(dialog)
    dialog._list_audio()
    assert 'bulunamadı' not in dialog.audio_combo.currentText()
    assert dialog.value().audio_device == 'USB'


def test_unresolvable_microphone_blocks_recording_before_start(window, monkeypatch):
    from matematigin_mantigi.core.recorder import RecorderState
    from PyQt6.QtWidgets import QMessageBox
    window.settings.audio_device = 'USB [Core Audio] #0'
    monkeypatch.setattr(ac, 'resolve_input_device', lambda name: None)
    questions = []
    starts = []
    monkeypatch.setattr(window.recorder, 'start', lambda *args, **kwargs: starts.append(True))
    def reject(parent, title, text, buttons, default):
        questions.append(text)
        assert default == QMessageBox.StandardButton.No
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, 'question', reject)
    window.toggle_recording(True)
    assert not starts
    assert window.recorder.state is RecorderState.IDLE
    assert questions and 'mikrofon' in questions[0].lower()


def test_camera_index_reordering_risk_is_disclosed(qtbot, ini_settings):
    dialog = SettingsDialog(ini_settings, FontFamilies('Arial', 'Arial', False))
    qtbot.addWidget(dialog)
    assert 'farklı' in dialog.camera_note.text().lower()
    assert 'sıra' in dialog.camera_note.text().lower()
