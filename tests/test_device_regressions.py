import pytest

from matematigin_mantigi.core import audio_capture as ac, cameras
from matematigin_mantigi.ui.settings_dialog import SettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies


def test_missing_microphone_never_falls_back(monkeypatch):
    monkeypatch.setattr(ac, 'resolve_input_device', lambda name: None)
    class SD:
        def query_devices(self, *args, **kwargs):
            return {'default_samplerate': 48000}
    with pytest.raises(RuntimeError, match='mikrofon'):
        ac.AudioCapture('removed')._pick_device(SD())


def test_missing_selections_are_preserved(qtbot, ini_settings, monkeypatch):
    ini_settings.audio_device = 'missing mic'
    ini_settings.camera_index = 3
    monkeypatch.setattr(ac, 'list_input_devices', lambda: ['other mic'])
    monkeypatch.setattr(cameras, 'list_cameras', lambda *args, **kwargs: [cameras.CameraInfo(0, 640, 480)])
    dialog = SettingsDialog(ini_settings, FontFamilies('Arial', 'Arial', False))
    qtbot.addWidget(dialog)
    dialog._list_audio()
    dialog._scan_cameras()
    assert dialog.value().audio_device == 'missing mic'
    assert dialog.value().camera_index == 3
    assert 'bulunamadı' in dialog.audio_combo.currentText()
    assert 'bulunamadı' in dialog.camera_combo.currentText()


def test_camera_never_opens_another_index(monkeypatch):
    from matematigin_mantigi.ui.camera_worker import OpenCvSource
    import cv2
    opened = []
    class Capture:
        def __init__(self, index, backend): opened.append(index)
        def isOpened(self): return False
        def release(self): pass
    monkeypatch.setattr(cv2, 'VideoCapture', Capture)
    assert not OpenCvSource(5).open()
    # Windows'ta aynı indeks iki backend ile denenir (DSHOW, MSMF); önemli olan yalnız 5 indeksinin denenmesi.
    assert opened and set(opened) == {5}


def test_removed_microphone_does_not_match_substring(monkeypatch):
    class SD:
        @staticmethod
        def query_hostapis(): return [{'name': 'Core Audio'}]
        @staticmethod
        def query_devices(): return [{'name': 'USB microphone newer', 'hostapi': 0, 'max_input_channels': 1}]
    monkeypatch.setattr(ac, '_sd', lambda: SD)
    assert ac.resolve_input_device('USB microphone') is None


def test_manually_typed_microphone_is_preserved(qtbot, ini_settings):
    dialog = SettingsDialog(ini_settings, FontFamilies('Arial', 'Arial', False))
    qtbot.addWidget(dialog)
    dialog.audio_combo.setEditText('Manual mic')
    assert dialog.value().audio_device == 'Manual mic'
