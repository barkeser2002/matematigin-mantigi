from PyQt6.QtCore import QSettings

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.core.models import HintMaskMode, Nib, PenSettings, Tool
from matematigin_mantigi.core.settings import AppSettings


def test_defaults(ini_settings):
    s = ini_settings
    assert s.tool == Tool.PEN and s.color == "#1c1b19" and s.width == 4
    assert s.hint_mask == HintMaskMode.BLUR and s.camera_index == 0 and s.chroma_enabled is True
    assert s.chroma == ChromaParams() and s.pen() == PenSettings()


def test_round_trip_through_ini(tmp_path):
    path = str(tmp_path / "rt.ini")
    s = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    s.tool = Tool.ERASER; s.color = "#2456b8"; s.width = 8; s.hint_mask = HintMaskMode.REDACT
    s.camera_index = 2; s.chroma_enabled = False
    s.chroma = ChromaParams(tolerance=55, feather_px=4, spill=0.3)
    s.set_pen(PenSettings(pressure_curve=70, smoothing=10, min_width=2, max_width=20, nib=Nib.CHALK,
                          math_recognition=False, shape_correction=False, autosave=False, template_matching=True,
                          reading_ms=0))
    s.sync()
    t = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert t.tool == Tool.ERASER and t.color == "#2456b8" and t.width == 8
    assert t.hint_mask == HintMaskMode.REDACT and t.camera_index == 2 and t.chroma_enabled is False
    assert t.chroma == ChromaParams(tolerance=55, feather_px=4, spill=0.3)
    assert t.pen().nib == Nib.CHALK and t.pen().template_matching is True and t.pen().autosave is False
    assert t.pen().reading_ms == 0


def test_ui_settings_round_trip(tmp_path):
    path = str(tmp_path / "ui.ini")
    s = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert s.auto_key is True and s.font_file == "" and s.visible("status") is True
    s.auto_key = False; s.font_file = r"C:\fonts\Ozel.ttf"; s.set_visible("status", False)
    s.logo_file = r"C:\logo.png"; s.sync()
    t = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert t.auto_key is False and t.font_file == r"C:\fonts\Ozel.ttf" and t.logo_file == r"C:\logo.png"
    assert t.visible("status") is False and t.visible("brand") is True


def test_record_and_logo_settings(tmp_path):
    path = str(tmp_path / "r.ini")
    s = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert (s.record_fps, s.record_height, s.audio_device, s.logo_size) == (60, 1440, "", 48)
    assert s.visible("badge") is False and s.visible("logo") is True      # rozet varsayılan kapalı
    assert s.aspect_lock is True                                          # tahta varsayılan 16:9
    s.record_fps = 30; s.record_height = 0; s.audio_device = "Mikrofon (USB)"; s.logo_size = 300
    s.aspect_lock = False; s.sync()
    t = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert (t.record_fps, t.record_height, t.audio_device, t.logo_size) == (30, 0, "Mikrofon (USB)", 200)
    assert t.aspect_lock is False
    t.aspect_lock = True; t.sync()
    assert AppSettings(QSettings(path, QSettings.Format.IniFormat)).aspect_lock is True


def test_stale_per_word_reading_speed_resets_to_default(tmp_path):
    q = QSettings(str(tmp_path / "old.ini"), QSettings.Format.IniFormat)
    q.setValue("pen/reading_ms", 350); q.sync()                   # eski sürüm: ms/kelime
    assert AppSettings(q).pen().reading_ms == PenSettings().reading_ms
    q.setValue("pen/reading_ms", 90); q.sync()
    assert AppSettings(q).pen().reading_ms == 90


def test_garbage_values_fall_back(tmp_path):
    q = QSettings(str(tmp_path / "g.ini"), QSettings.Format.IniFormat)
    q.setValue("tool", "hammer"); q.setValue("width", "abc"); q.setValue("hint_mask", 7); q.sync()
    s = AppSettings(q)
    assert s.tool == Tool.PEN and s.width == 4 and s.hint_mask == HintMaskMode.BLUR
