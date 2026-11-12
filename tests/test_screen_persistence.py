from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.dual_screen import screen_key, resolve_screen_key


class Screen:
    def __init__(self, name, manufacturer, model, serial):
        self.values = name, manufacturer, model, serial
    def name(self): return self.values[0]
    def manufacturer(self): return self.values[1]
    def model(self): return self.values[2]
    def serialNumber(self): return self.values[3]


def test_identity_roundtrips_and_refuses_ambiguous_matches(tmp_path):
    a = Screen('display', 'vendor', 'model', '123')
    twin = Screen('display', 'vendor', 'model', '123')
    other = Screen('display', 'vendor', 'model', '456')
    settings = AppSettings(QSettings(str(tmp_path / 'test.ini'), QSettings.Format.IniFormat))
    settings.board_screen_key = screen_key(a)
    settings.preview_screen_key = screen_key(other)
    settings.sync()
    reopened = AppSettings(QSettings(str(tmp_path / 'test.ini'), QSettings.Format.IniFormat))
    assert resolve_screen_key([other, a], reopened.board_screen_key) is a
    assert resolve_screen_key([a, twin], reopened.board_screen_key) is None
    assert resolve_screen_key([other], reopened.board_screen_key) is None
    assert resolve_screen_key([a, other], reopened.preview_screen_key) is other


def test_restoration_does_not_open_preview_when_board_missing(window, monkeypatch):
    board = window.screen()
    window.settings.board_screen_key = ('missing', '', '', '')
    window.settings.preview_screen_key = screen_key(board)
    calls = []
    monkeypatch.setattr(window, '_configure_screens', lambda b, p, **kw: calls.append((b, p)))
    window._restore_screen_preferences()
    assert calls == [(None, None)]


def test_restoration_resolves_devices_independent_of_order(window, monkeypatch):
    board = Screen('tablet', 'vendor', 'model', '1')
    preview = Screen('monitor', 'vendor', 'model', '2')
    window.settings.board_screen_key = screen_key(board)
    window.settings.preview_screen_key = screen_key(preview)
    monkeypatch.setattr(QApplication, 'screens', staticmethod(lambda: [preview, board]))
    calls = []
    monkeypatch.setattr(window, '_configure_screens', lambda b, p, **kw: calls.append((b, p)))
    window._restore_screen_preferences()
    assert calls == [(board, preview)]


def test_closing_preview_is_persistent(window, tmp_path):
    window.settings.preview_screen_key = ('monitor', 'vendor', 'model', '2')
    window._preview_closed()
    window.settings.sync()
    assert window.settings.preview_screen_key is None
