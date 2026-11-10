from matematigin_mantigi.core import audio_capture as ac, cameras


def test_all_audio_apis_and_ambiguous_legacy_names(monkeypatch):
    class SD:
        @staticmethod
        def query_hostapis(): return [{'name': 'MME'}, {'name': 'WASAPI'}]
        @staticmethod
        def query_devices(): return [
            {'name': 'Mic', 'hostapi': 0, 'max_input_channels': 1},
            {'name': 'Mic', 'hostapi': 1, 'max_input_channels': 1},
            {'name': 'Other', 'hostapi': 0, 'max_input_channels': 1}]
    monkeypatch.setattr(ac, '_sd', lambda: SD)
    names = ac.list_input_devices()
    assert len(names) == 3 and len(set(names)) == 3
    assert all(ac.resolve_input_device(name) == i for i, name in enumerate(names))
    assert ac.resolve_input_device('Mic') is None
    assert ac.resolve_input_device('Other') == 2


def test_camera_scan_skips_busy_and_does_not_use_unverified_names(monkeypatch):
    import numpy as np
    opened = []
    class Cap:
        def __init__(self, index, backend): opened.append(index)
        def isOpened(self): return True
        def read(self): return True, np.zeros((4, 5, 3))
        def release(self): pass
    monkeypatch.setattr(cameras.cv2, 'VideoCapture', Cap)
    found = cameras.list_cameras(max_index=2, names=['Wrong', 'Also wrong'], skip={0})
    assert opened == [1]
    assert len(found) == 1 and found[0].name == ''


def test_dialog_does_not_probe_running_worker_index(qtbot, ini_settings, monkeypatch):
    from types import SimpleNamespace
    from PyQt6.QtWidgets import QWidget
    from matematigin_mantigi.ui.settings_dialog import SettingsDialog
    from matematigin_mantigi.ui.theme import FontFamilies
    parent = QWidget()
    worker = SimpleNamespace(isRunning=lambda: True, _source=SimpleNamespace(index=4))
    parent.webcam_panel = SimpleNamespace(worker=worker, _pending_workers=[])
    seen = []
    def scan(*args, **kwargs):
        seen.append(kwargs.get('skip', set()))
        return []
    monkeypatch.setattr(cameras, 'list_cameras', scan)
    ini_settings.camera_index = 4
    dialog = SettingsDialog(ini_settings, FontFamilies('Arial', 'Arial', False), parent)
    qtbot.addWidget(dialog)
    dialog._scan_cameras()
    assert seen == [{4}]
    assert dialog.value().camera_index == 4
    assert 'kullanımda' in dialog.camera_combo.currentText()
