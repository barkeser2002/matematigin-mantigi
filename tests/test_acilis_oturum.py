"""Bilgisayar açılınca başlatma + oturum geri yükleme.

Gerçek kayıt defterine, ~/Library/LaunchAgents'a ve ~/.config/autostart'a YAZILMAZ: platform, winreg, ev ve
yapılandırma klasörü her testte enjekte edilir (tmp_path). Pencere testleri ayar olarak tmp .ini kullanır.
Hiçbir testte gerçek kayıt başlamaz."""
import argparse
import plistlib
from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF, QRect, QSettings
from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication, QMessageBox

from matematigin_mantigi import app as app_mod
from matematigin_mantigi import paths
from matematigin_mantigi.core import autostart as autostart_mod
from matematigin_mantigi.core.autostart import Autostart, AutostartError
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question
from matematigin_mantigi.core.question_loader import write_questions
from matematigin_mantigi.core.recorder import NullRecorder, RecorderState
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings, SessionState
from matematigin_mantigi.ui import main_window as mw
from matematigin_mantigi.ui.main_window import MainWindow, ink_from_snapshot
from matematigin_mantigi.ui.settings_dialog import SettingsDialog, SettingsValues
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


# --- sahte Windows kayıt defteri ---------------------------------------------------------------------------------

class FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_QUERY_VALUE, KEY_SET_VALUE, REG_SZ = 1, 2, 1

    def __init__(self):
        self.store: dict[tuple[str, str], tuple[str, int]] = {}
        self.keys: set[str] = set()
        self.calls: list[tuple] = []

    class _Key:
        def __init__(self, path): self.path = path
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def OpenKey(self, root, path, reserved, access):
        if path not in self.keys:
            raise FileNotFoundError(path)
        return self._Key(path)

    def CreateKeyEx(self, root, path, reserved, access):
        self.keys.add(path)
        return self._Key(path)

    def QueryValueEx(self, key, name):
        try:
            return self.store[(key.path, name)]
        except KeyError:
            raise FileNotFoundError(name) from None

    def SetValueEx(self, key, name, reserved, kind, value):
        self.calls.append(("set", key.path, name, kind, value))
        self.store[(key.path, name)] = (value, kind)

    def DeleteValue(self, key, name):
        self.calls.append(("delete", key.path, name))
        try:
            del self.store[(key.path, name)]
        except KeyError:
            raise FileNotFoundError(name) from None


RUN = autostart_mod.RUN_KEY
EXE = r"C:\Program Files\Matematigin Mantigi\MatematiginMantigi.exe"


def win_autostart(reg=None, exe=EXE, frozen=True):
    return Autostart(platform="win32", frozen=frozen, executable=exe, winreg=reg or FakeWinreg())


# --- Windows -----------------------------------------------------------------------------------------------------

def test_windows_enable_writes_quoted_exe_with_baslangic_and_disable_removes():
    reg = FakeWinreg()
    a = win_autostart(reg)
    assert not a.is_enabled()
    a.set_enabled(True)
    value, kind = reg.store[(RUN, "MatematiginMantigi")]
    assert value == f'"{EXE}" --baslangic' and kind == reg.REG_SZ
    assert a.is_enabled()
    a.set_enabled(False)
    assert not a.is_enabled() and (RUN, "MatematiginMantigi") not in reg.store
    a.set_enabled(False)                                     # zaten yok: hata vermez


def test_windows_state_comes_from_the_real_registry_not_a_cached_flag():
    reg = FakeWinreg()
    a = win_autostart(reg)
    a.set_enabled(True)
    del reg.store[(RUN, "MatematiginMantigi")]               # kullanıcı Görev Yöneticisi/regedit'ten elle sildi
    assert a.is_enabled() is False
    reg.keys.discard(RUN)                                    # anahtarın kendisi de yok
    assert a.is_enabled() is False


def test_windows_source_run_is_unsupported_with_reason_and_writes_nothing():
    reg = FakeWinreg()
    a = win_autostart(reg, frozen=False)
    assert not a.supported and "kaynak" in a.unsupported_reason
    assert a.is_enabled() is False
    with pytest.raises(AutostartError):
        a.set_enabled(True)
    assert reg.calls == [] and reg.keys == set()


def test_windows_repair_fixes_a_stale_path_only_when_enabled():
    reg = FakeWinreg()
    old = win_autostart(reg, exe=r"C:\Eski\Matematigin.exe")
    old.set_enabled(True)
    new = win_autostart(reg)
    assert new.repair() is True
    assert reg.store[(RUN, "MatematiginMantigi")][0] == f'"{EXE}" --baslangic'
    reg.calls.clear()
    assert new.repair() is False and reg.calls == []         # güncelken yazmaz
    new.set_enabled(False)
    reg.calls.clear()
    assert new.repair() is False and reg.calls == []         # kapalıyken kendiliğinden AÇMAZ


def test_registry_failure_is_reported_not_raised_raw():
    class Broken(FakeWinreg):
        def CreateKeyEx(self, *a):
            raise PermissionError("erişim reddedildi")
    a = win_autostart(Broken())
    with pytest.raises(AutostartError, match="yazılamadı"):
        a.set_enabled(True)
    assert a.repair() is False


# --- macOS -------------------------------------------------------------------------------------------------------

MAC_EXE = "/Applications/Matematiğin Mantığı.app/Contents/MacOS/MatematiginMantigi"


def mac_autostart(home, frozen=True):
    return Autostart(platform="darwin", frozen=frozen, executable=MAC_EXE, home=home)


def test_macos_plist_written_and_removed(tmp_path):
    a = mac_autostart(tmp_path)
    plist = tmp_path / "Library" / "LaunchAgents" / "com.barkeser.matematiginmantigi.plist"
    assert not a.is_enabled()
    a.set_enabled(True)
    data = plistlib.loads(plist.read_bytes())
    assert data == {"Label": "com.barkeser.matematiginmantigi", "ProgramArguments": [MAC_EXE, "--baslangic"],
                    "RunAtLoad": True}
    assert a.is_enabled()
    plist.unlink()
    assert not a.is_enabled()                                # elle silindi: gerçek durum
    a.set_enabled(True)
    a.set_enabled(False)
    assert not plist.exists() and not a.is_enabled()
    a.set_enabled(False)


def test_macos_repair_and_unsupported_source_run(tmp_path):
    old = Autostart(platform="darwin", frozen=True, executable="/Eski/yol/App", home=tmp_path)
    old.set_enabled(True)
    new = mac_autostart(tmp_path)
    assert new.repair() is True
    assert plistlib.loads(new.mac_plist_path.read_bytes())["ProgramArguments"][0] == MAC_EXE
    assert new.repair() is False
    src = mac_autostart(tmp_path / "baska", frozen=False)
    assert not src.supported and src.unsupported_reason
    with pytest.raises(AutostartError):
        src.set_enabled(True)
    assert not (tmp_path / "baska").exists()


# --- Linux (geliştirme) ------------------------------------------------------------------------------------------

def test_linux_desktop_entry_quotes_paths_and_respects_config_home(tmp_path):
    exe = "/opt/Matematiğin Mantığı/bin/mm"
    a = Autostart(platform="linux", frozen=True, executable=exe, home=tmp_path / "ev", config_home=tmp_path / "cfg")
    a.set_enabled(True)
    path = tmp_path / "cfg" / "autostart" / "matematigin-mantigi.desktop"
    text = path.read_text(encoding="utf-8")
    assert 'Exec="/opt/Matematiğin Mantığı/bin/mm" --baslangic' in text and "Type=Application" in text
    assert a.is_enabled() and not (tmp_path / "ev").exists()
    a.set_enabled(False)
    assert not path.exists() and not a.is_enabled()


def test_linux_development_run_uses_python_dash_m(tmp_path):
    a = Autostart(platform="linux", frozen=False, executable="/usr/bin/python3", config_home=tmp_path)
    assert a.supported
    assert a.command_line() == ["/usr/bin/python3", "-m", "matematigin_mantigi", "--baslangic"]


def test_linux_write_failure_becomes_autostart_error(tmp_path):
    blocker = tmp_path / "dosya"
    blocker.write_text("x")
    a = Autostart(platform="linux", frozen=True, executable="/x/mm", config_home=blocker)
    with pytest.raises(AutostartError, match="yazılamadı"):
        a.set_enabled(True)


# --- ayarlar ve kalıcılık ----------------------------------------------------------------------------------------

def reopen(tmp_path) -> AppSettings:
    return AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))


def test_session_state_roundtrips(ini_settings, tmp_path):
    state = SessionState(questions_file="/x/y.xlsx", question_id="S2", question_index=1, fullscreen=True,
                         geometry=(10, 20, 900, 700), board_image="/x/S2_01.png", board_question_id="S2")
    ini_settings.session_state = state
    ini_settings.sync()
    assert reopen(tmp_path).session_state == state


@pytest.mark.parametrize("raw", ["", "{", "[]", "null", "42", '{"geometry": "x"}',
                                 '{"question_index": -3, "geometry": [1,2,3], "fullscreen": "yes"}',
                                 '{"geometry": [0, 0, 5, 5], "question_id": 7, "board_image": null}'])
def test_corrupt_session_state_falls_back_to_defaults(ini_settings, raw):
    ini_settings._q.setValue("session/state", raw)
    state = ini_settings.session_state
    assert state.question_index == 0 and state.geometry is None and state.fullscreen is False
    assert state.question_id == "" or isinstance(state.question_id, str)


def test_existing_preferences_already_persist_across_restarts(ini_settings, tmp_path):
    """Hangileri ZATEN kalıcı: araç, kalem rengi/kalınlığı, kamera indeksi, webcam görünürlüğü, ekran kimlikleri,
    kayıt klasörü, mikrofon. Eksik olan yalnız soru/pencere/tam ekran/tahta görüntüsüydü (SessionState)."""
    from matematigin_mantigi.core.models import Tool
    s = ini_settings
    s.tool, s.color, s.width, s.camera_index = Tool.CHALK if hasattr(Tool, "CHALK") else Tool.ERASER, "#ff0000", 9, 2
    s.set_visible("webcam", False)
    s.board_screen_key = ("a", "b", "c", "d")
    s.record_folder, s.audio_device = "/kayit", "Mik"
    s.sync()
    r = reopen(tmp_path)
    assert (r.tool, r.color, r.width, r.camera_index) == (s.tool, "#ff0000", 9, 2)
    assert r.visible("webcam") is False and r.board_screen_key == ("a", "b", "c", "d")
    assert (r.record_folder, r.audio_device) == ("/kayit", "Mik")


# --- Ayarlar penceresi -------------------------------------------------------------------------------------------

def test_dialog_checkbox_defaults_off_and_reads_the_real_state(qtbot, ini_settings, tmp_path):
    a = mac_autostart(tmp_path)
    d = SettingsDialog(ini_settings, FAM, autostart=a)
    qtbot.addWidget(d)
    assert d.autostart_check.isEnabled() and not d.autostart_check.isChecked()
    assert d.value().autostart is None                          # dokunulmadı: hiçbir şey yazılmaz
    d.autostart_check.setChecked(True)
    assert d.value().autostart is True
    a.set_enabled(True)
    d2 = SettingsDialog(ini_settings, FAM, autostart=a)         # gerçek kayıt açık -> kutu işaretli açılır
    qtbot.addWidget(d2)
    assert d2.autostart_check.isChecked() and d2.value().autostart is None
    d2.autostart_check.setChecked(False)
    assert d2.value().autostart is False
    a.mac_plist_path.unlink()                                   # elle silindi
    d3 = SettingsDialog(ini_settings, FAM, autostart=a)
    qtbot.addWidget(d3)
    assert not d3.autostart_check.isChecked()


def test_dialog_disables_checkbox_for_source_run_and_explains(qtbot, ini_settings, tmp_path):
    d = SettingsDialog(ini_settings, FAM, autostart=mac_autostart(tmp_path, frozen=False))
    qtbot.addWidget(d)
    assert not d.autostart_check.isEnabled()
    assert "kaynak" in d.autostart_check.toolTip() and "kaynak" in d.autostart_note.text()
    assert d.value().autostart is None


# --- Pencere ------------------------------------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def no_real_modals(monkeypatch):
    seen = []
    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, _n=name, **k: seen.append((_n, a)) or
                                                            QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda box: seen.append(("exec", box.text())) or 0)
    yield seen


def make_window(qtbot, tmp_path, settings, dead_camera, *, state=None, questions=None, startup=False,
                autostart=None, from_file=True, show=True):
    win = MainWindow(FAM, list(questions or SAMPLE_QUESTIONS), settings, NullRecorder(),
                     SessionStore(tmp_path / "oturum"), lambda index: dead_camera, tmp_path / "duzen.json",
                     questions_from_file=from_file, session_state=state, startup=startup,
                     autostart=autostart or mac_autostart(tmp_path / "ev"))
    qtbot.addWidget(win)
    win.resize(780, 600)
    if state is not None:
        win.restore_window_state(state)
    if show:
        win.show()
        qtbot.waitExposed(win)
    return win


def close_window(win):
    win.close()
    win.webcam_panel.shutdown()


def draw_line(win, x0=100, y0=100, x1=400, y1=300):
    c = win.canvas
    c.begin_stroke(QPointF(x0, y0), .8)
    c.extend_stroke(QPointF((x0 + x1) / 2, (y0 + y1) / 2), .8)
    c.extend_stroke(QPointF(x1, y1), .8)
    c.end_stroke()


def test_last_question_is_restored_by_id_after_restart(qtbot, tmp_path, ini_settings, dead_camera):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    win.flow.select(2)
    close_window(win)
    ini_settings.sync()
    reopened = reopen(tmp_path)
    win2 = make_window(qtbot, tmp_path, reopened, dead_camera, state=reopened.session_state)
    assert win2.flow.current.id == "S3"
    assert win2.toolbar.progress_label.text().endswith("S3") if hasattr(win2.toolbar, "progress_label") else True
    close_window(win2)
    assert reopen(tmp_path).session_state.question_id == "S3"       # yeniden açılış durumu bozmadı


def test_restore_does_not_change_question_statuses_or_start_recording(qtbot, tmp_path, ini_settings, dead_camera):
    ini_settings.session_state = SessionState(question_id="S2", question_index=1)
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=ini_settings.session_state, startup=True)
    assert win.flow.current.id == "S2" and win.flow.done_count() == 0
    assert win.recorder.state is RecorderState.IDLE and win.toolbar.record_button.isChecked() is False
    close_window(win)


def test_order_changed_file_restores_by_id_and_unknown_id_starts_first(qtbot, tmp_path, ini_settings, dead_camera):
    ini_settings.session_state = SessionState(question_id="S3", question_index=0)     # sıra değişmiş
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=ini_settings.session_state)
    assert win.flow.current.id == "S3"
    close_window(win)
    ini_settings.session_state = SessionState(question_id="YOK", question_index=1)
    win2 = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=ini_settings.session_state)
    assert win2.flow.current.id == "S1"
    close_window(win2)


def test_samples_do_not_overwrite_the_saved_question_position(qtbot, tmp_path, ini_settings, dead_camera):
    """Soru dosyası okunamadı (örnek sorular): gerçek dosyanın kayıtlı konumu örnek soru kimliğiyle ezilmez."""
    saved = SessionState(questions_file="", question_id="G4", question_index=3)
    ini_settings.session_state = saved
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, from_file=False)
    win.flow.select(1)
    close_window(win)
    after = ini_settings.session_state
    assert (after.question_id, after.question_index) == ("G4", 3)


def test_corrupt_saved_state_does_not_crash_window(qtbot, tmp_path, ini_settings, dead_camera):
    ini_settings._q.setValue("session/state", '{"question_id": "S2", "geometry": [1, 2], "fullscreen": 5')
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=ini_settings.session_state)
    assert win.flow.current.id == "S1"
    close_window(win)


def test_window_geometry_is_restored_when_screen_still_exists(qtbot, tmp_path, ini_settings, dead_camera):
    state = SessionState(geometry=(30, 40, 640, 480))
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=state, show=False)
    assert (win.x(), win.y(), win.width(), win.height()) == (30, 40, 640, 480)
    win.show(); qtbot.waitExposed(win)
    close_window(win)
    assert ini_settings.session_state.geometry is not None
    assert ini_settings.session_state.geometry[2:] == (640, 480)


class FakeScreen:
    def __init__(self, rect): self._r = rect
    def availableGeometry(self): return self._r


def test_geometry_on_a_missing_screen_is_ignored_and_oversize_is_clamped(monkeypatch):
    monkeypatch.setattr(QApplication, "screens", staticmethod(lambda: [FakeScreen(QRect(0, 0, 1920, 1080))]))
    assert MainWindow._fitting_geometry((5000, 100, 800, 600)) is None          # ekran çıkarıldı
    assert MainWindow._fitting_geometry((1800, 900, 800, 600)) is None          # çoğu dışarıda
    assert MainWindow._fitting_geometry(None) is None
    assert MainWindow._fitting_geometry((-100, -50, 3000, 2000)) == QRect(0, 0, 1920, 1080)
    assert MainWindow._fitting_geometry((100, 100, 800, 600)) == QRect(100, 100, 800, 600)
    monkeypatch.setattr(QApplication, "screens", staticmethod(lambda: [
        FakeScreen(QRect(0, 0, 1920, 1080)), FakeScreen(QRect(1920, 0, 1280, 1024))]))
    assert MainWindow._fitting_geometry((2000, 50, 800, 600)) == QRect(2000, 50, 800, 600)   # ikinci ekranda


def test_fullscreen_state_is_remembered_and_restored(qtbot, tmp_path, ini_settings, dead_camera):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    win.showFullScreen()
    qtbot.waitUntil(lambda: win.isFullScreen())
    qtbot.waitUntil(lambda: ini_settings.session_state.fullscreen)
    close_window(win)
    state = ini_settings.session_state
    assert state.fullscreen
    win2 = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=state)
    qtbot.waitUntil(lambda: win2.isFullScreen())
    win2.showNormal()
    qtbot.waitUntil(lambda: not ini_settings.session_state.fullscreen)
    close_window(win2)


def test_no_disk_writes_while_nothing_changes(qtbot, tmp_path, ini_settings, dead_camera):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    win._remember_window(); win._remember_question()            # ilk durum bir kez yazılır
    writes = []
    original = type(ini_settings).session_state.fset

    def counting(self, state):
        writes.append(state)
        original(self, state)
    monkey = pytest.MonkeyPatch()
    monkey.setattr(type(ini_settings), "session_state", type(ini_settings).session_state.setter(counting))
    try:
        for _ in range(5):
            win._autosave_board()                               # 30 sn'lik zamanlayıcının işi
            win._remember_window()
            win._remember_question()
        qtbot.wait(50)
        assert writes == []
        win.flow.select(1)
        assert len(writes) == 1                                 # değişince bir kez
    finally:
        monkey.undo()
    close_window(win)


# --- tahta görüntüsü ---------------------------------------------------------------------------------------------

def ink_pixels(win) -> int:
    img = win.canvas.strokes_image()
    return sum(1 for y in range(0, img.height(), 3) for x in range(0, img.width(), 3)
               if QColor.fromRgba(img.pixel(x, y)).alpha() > 128)


def test_board_image_roundtrip_restores_the_last_drawing(qtbot, tmp_path, ini_settings, dead_camera):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    win.flow.select(1)
    draw_line(win)
    before = ink_pixels(win)
    assert before > 0
    close_window(win)
    state = ini_settings.session_state
    assert state.board_question_id == "S2" and Path(state.board_image).is_file()
    win2 = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=state)
    qtbot.waitUntil(lambda: not win2.canvas.is_empty())
    assert win2.flow.current.id == "S2"
    assert abs(ink_pixels(win2) - before) <= before * 0.25
    pix = win2.canvas.strokes_image().pixelColor(250, 200)          # çizginin orta noktası
    assert pix.alpha() > 100 and pix.red() < 120                    # koyu mürekkep geri geldi (beyaz zemin değil)
    assert win2.canvas.snapshot_image().pixelColor(5, 5) == QColor("white")
    close_window(win2)


def test_cleared_board_is_not_resurrected(qtbot, tmp_path, ini_settings, dead_camera):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    draw_line(win)
    assert win._save_board(0)                                       # 30 sn'lik otomatik kayıt
    assert ini_settings.session_state.board_image
    win.canvas.clear()
    close_window(win)
    assert ini_settings.session_state.board_image == ""
    win2 = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=ini_settings.session_state)
    qtbot.wait(50)
    assert win2.canvas.is_empty()
    close_window(win2)


def test_board_image_for_a_different_question_is_not_loaded(qtbot, tmp_path, ini_settings, dead_camera):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    draw_line(win)
    close_window(win)
    state = SessionState(**{**ini_settings.session_state.__dict__, "question_id": "S2", "question_index": 1})
    win2 = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=state)
    qtbot.wait(50)
    assert win2.flow.current.id == "S2" and win2.canvas.is_empty()
    close_window(win2)


@pytest.mark.parametrize("damage", ["missing", "corrupt", "empty", "huge_aspect"])
def test_damaged_board_image_never_crashes_startup(qtbot, tmp_path, ini_settings, dead_camera, damage):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    draw_line(win)
    close_window(win)
    state = ini_settings.session_state
    png = Path(state.board_image)
    if damage == "missing":
        png.unlink()
    elif damage == "corrupt":
        png.write_bytes(b"bozuk png")
    elif damage == "empty":
        png.write_bytes(b"")
    else:
        wide = QImage(2000, 100, QImage.Format.Format_RGB32)
        wide.fill(QColor("white"))
        assert wide.save(str(png), "PNG")
    win2 = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=state)
    qtbot.wait(50)
    assert win2.canvas.is_empty()
    if damage == "huge_aspect":
        assert "geri yüklenmedi" in win2.toolbar.alert_label.text()
    close_window(win2)


def test_user_drawing_before_restore_is_never_overwritten(qtbot, tmp_path, ini_settings, dead_camera):
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera)
    draw_line(win)
    close_window(win)
    win2 = make_window(qtbot, tmp_path, ini_settings, dead_camera, state=ini_settings.session_state, show=False)
    draw_line(win2, 10, 10, 60, 20)
    count = win2.canvas._stroke_count
    win2.show(); qtbot.waitExposed(win2)
    qtbot.wait(50)
    assert win2.canvas._stroke_count == count
    close_window(win2)


def test_ink_from_snapshot_is_exact_for_single_layer_ink_on_white():
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QPainter, QPen
    img = QImage(60, 40, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    p.setPen(QPen(QColor(200, 30, 30), 6))
    p.drawLine(5, 20, 55, 20)
    p.end()
    ink = ink_from_snapshot(img, QSize(60, 40))
    assert ink.format() == QImage.Format.Format_ARGB32_Premultiplied
    assert ink.pixelColor(2, 2).alpha() == 0
    c = ink.pixelColor(30, 20)
    assert c.alpha() == 255 - 30                               # alfa = 255 - min(R,G,B): beyaz üstünde kayıpsız
    back = QImage(60, 40, QImage.Format.Format_RGB32)
    back.fill(QColor("white"))
    q = QPainter(back); q.drawImage(0, 0, ink); q.end()
    assert back == img


# --- --baslangic ve uçtan uca build_window ------------------------------------------------------------------------

def test_baslangic_flag_parsed():
    assert app_mod.parse_args(["prog", "--baslangic"]).baslangic is True
    assert app_mod.parse_args(["prog"]).baslangic is False


def test_startup_waits_for_the_saved_board_screen_without_blocking(qtbot, tmp_path, ini_settings, dead_camera,
                                                                    monkeypatch):
    monkeypatch.setattr(mw, "STARTUP_SCREEN_WAIT_MS", 400)
    monkeypatch.setattr(mw, "STARTUP_SCREEN_POLL_MS", 20)
    missing = ("tablet", "v", "m", "1")
    ini_settings.board_screen_key = missing
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, startup=True, show=False)
    calls = []
    monkeypatch.setattr(win, "_configure_screens", lambda b, p: calls.append((b, p)))
    win._restore_screen_preferences()
    assert calls == []                                          # hemen vazgeçilmedi, UI dönüyor
    qtbot.waitUntil(lambda: calls == [(None, None)], timeout=5000)   # süre dolunca mevcut ekranda kalır
    close_window(win)


def test_startup_uses_the_screen_as_soon_as_it_appears(qtbot, tmp_path, ini_settings, dead_camera, monkeypatch):
    from matematigin_mantigi.ui.dual_screen import screen_key

    class Screen:
        def name(self): return "tablet"
        def manufacturer(self): return "v"
        def model(self): return "m"
        def serialNumber(self): return "1"
    tablet = Screen()
    monkeypatch.setattr(mw, "STARTUP_SCREEN_WAIT_MS", 5000)
    monkeypatch.setattr(mw, "STARTUP_SCREEN_POLL_MS", 20)
    ini_settings.board_screen_key = screen_key(tablet)
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, startup=True, show=False)
    calls, screens = [], []
    monkeypatch.setattr(QApplication, "screens", staticmethod(lambda: list(screens)))
    monkeypatch.setattr(win, "_configure_screens", lambda b, p: calls.append((b, p)))
    win._restore_screen_preferences()
    qtbot.wait(60)
    assert calls == []
    screens.append(tablet)                                      # sürücü geç hazır oldu
    qtbot.waitUntil(lambda: calls == [(tablet, None)], timeout=2000)
    close_window(win)


def test_normal_launch_does_not_wait_for_a_missing_screen(qtbot, tmp_path, ini_settings, dead_camera, monkeypatch):
    ini_settings.board_screen_key = ("tablet", "v", "m", "1")
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, startup=False, show=False)
    calls = []
    monkeypatch.setattr(win, "_configure_screens", lambda b, p: calls.append((b, p)))
    win._restore_screen_preferences()
    assert calls == [(None, None)]
    close_window(win)


def test_applying_settings_cancels_the_startup_wait(qtbot, tmp_path, ini_settings, dead_camera, monkeypatch):
    ini_settings.board_screen_key = ("tablet", "v", "m", "1")
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, startup=True, show=False)
    monkeypatch.setattr(win, "_configure_screens", lambda b, p: None)
    win._restore_screen_preferences()
    assert win._startup_screen_timer.isActive()
    win.apply_settings_values(SettingsValues(board_screen=None, preview_screen=None))
    assert not win._startup_screen_timer.isActive() and win._startup_screen_wait_left == 0
    close_window(win)


def test_applying_settings_toggles_autostart_with_injected_backend(qtbot, tmp_path, ini_settings, dead_camera):
    a = mac_autostart(tmp_path / "ev")
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, autostart=a, show=False)
    win.apply_settings_values(SettingsValues(board_screen=None, preview_screen=None, autostart=True))
    assert a.is_enabled()
    win.apply_settings_values(SettingsValues(board_screen=None, preview_screen=None))    # dokunulmadı: değişmez
    assert a.is_enabled()
    win.apply_settings_values(SettingsValues(board_screen=None, preview_screen=None, autostart=False))
    assert not a.is_enabled()
    close_window(win)


def test_autostart_failure_is_reported_not_raised(qtbot, tmp_path, ini_settings, dead_camera, monkeypatch):
    posted = []
    monkeypatch.setattr(mw.error_notice, "post", lambda title, text, **k: posted.append((title, text)))
    a = Autostart(platform="linux", frozen=True, executable="/x/mm", config_home=tmp_path / "dosya")
    (tmp_path / "dosya").write_text("x")
    win = make_window(qtbot, tmp_path, ini_settings, dead_camera, autostart=a, show=False)
    win.apply_settings_values(SettingsValues(board_screen=None, preview_screen=None, autostart=True))
    assert posted and "yazılamadı" in posted[0][1]
    close_window(win)


def _args(tmp_path, *extra) -> argparse.Namespace:
    return app_mod.parse_args(["mm", "--kamera-yok", "--duzen", str(tmp_path / "duzen.json"), *extra])


def test_build_window_restores_missing_file_with_default_and_a_short_toolbar_notice(
        qtbot, tmp_path, monkeypatch, ini_settings):
    monkeypatch.chdir(tmp_path)
    ini_settings.session_state = SessionState(questions_file=str(tmp_path / "kayip.xlsx"), question_id="G2",
                                              question_index=1, fullscreen=False)
    a = mac_autostart(tmp_path / "ev")
    win = app_mod.build_window(_args(tmp_path), FAM, ini_settings, a)
    qtbot.addWidget(win)
    assert win.questions_path == paths.default_template_path()
    assert "Son açık soru dosyası bulunamadı" in win.toolbar.alert_label.text()
    assert win._session_notice_timer.isActive() and win._session_notice_timer.parent() is win   # pencereyle ölür
    win._clear_session_notice()
    assert win.toolbar.alert_label.text() == ""                         # birkaç saniye sonra kalkar
    assert win.flow.current.id == win.flow.questions[0].id             # eski dosyanın konumu uygulanmadı
    assert win.recorder.state is RecorderState.IDLE
    close_window(win)


def test_build_window_reopens_last_question_file_and_position(qtbot, tmp_path, monkeypatch, ini_settings):
    monkeypatch.chdir(tmp_path)
    real = [Question(f"G{i}", "gerçek", 8, f"Gerçek soru {i}", ("i1",), "c", ()) for i in range(1, 5)]
    file = tmp_path / "ozel.xlsx"
    write_questions(file, real)
    ini_settings.session_state = SessionState(questions_file=str(file), question_id="G3", question_index=2)
    win = app_mod.build_window(_args(tmp_path, "--baslangic"), FAM, ini_settings, mac_autostart(tmp_path / "ev"))
    qtbot.addWidget(win)
    assert win.questions_path == file and win.flow.current.id == "G3"
    assert win._startup_screen_wait_left > 0                            # --baslangic
    assert win.toolbar.alert_label.text() == ""
    close_window(win)
    assert ini_settings.session_state.questions_file == str(file)


def test_explicit_sorular_argument_wins_and_ignores_foreign_position(qtbot, tmp_path, monkeypatch, ini_settings):
    monkeypatch.chdir(tmp_path)
    real = [Question(f"G{i}", "gerçek", 8, f"Gerçek soru {i}", ("i1",), "c", ()) for i in range(1, 4)]
    other = tmp_path / "baska.xlsx"
    write_questions(other, real)
    ini_settings.session_state = SessionState(questions_file=str(tmp_path / "ozel.xlsx"), question_id="G3",
                                              question_index=2)
    win = app_mod.build_window(_args(tmp_path, "--sorular", str(other)), FAM, ini_settings,
                               mac_autostart(tmp_path / "ev"))
    qtbot.addWidget(win)
    assert win.questions_path == other and win.flow.current.id == "G1"
    close_window(win)


def test_build_window_repairs_an_enabled_stale_autostart_but_never_enables(qtbot, tmp_path, monkeypatch, ini_settings):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "ev"
    Autostart(platform="darwin", frozen=True, executable="/Eski/App", home=home).set_enabled(True)
    new = mac_autostart(home)
    win = app_mod.build_window(_args(tmp_path), FAM, ini_settings, new)
    qtbot.addWidget(win)
    assert plistlib.loads(new.mac_plist_path.read_bytes())["ProgramArguments"][0] == MAC_EXE
    close_window(win)
    other_home = tmp_path / "ev2"
    win2 = app_mod.build_window(_args(tmp_path), FAM, ini_settings, mac_autostart(other_home))
    qtbot.addWidget(win2)
    assert not other_home.exists()                                       # kapalıyken hiçbir şey yazılmadı
    close_window(win2)
