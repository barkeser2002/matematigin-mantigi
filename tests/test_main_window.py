from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtGui import QColor

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, HintMaskMode, QuestionStatus, Tool


def test_window_shell(window):
    assert window.windowTitle() == "Matematiğin Mantığı"
    assert window.toolbar.width() == 88
    x, y, w, h, _ = window.work_area.recording_rect()
    assert w == window.width() - 88 and h == window.height()
    assert window.canvas is window.work_area.board and window.canvas.geometry() == window.work_area.inner_rect()
    assert window.work_area.name_label.text() == "Koray Varol" and window.work_area.frame_visible
    assert window.question_zone.number_label.text() == "1."
    assert window.question_zone.text_label.text().startswith("3x + 5")
    assert len(window.hint_zone.cards) == 3
    assert window.work_area.status_label.text().startswith("Araç: Kalem")


def test_tool_switch_updates_cursor_and_status(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.ERASER
    assert window.canvas.cursor().pixmap().size() == QSize(36, 36)
    assert "Araç: Silgi" in window.work_area.status_label.text()
    qtbot.mouseClick(window.toolbar.width_buttons[8], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().pixmap().size() == QSize(70, 70)          # silgi alanı büyüdü
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.PEN], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().pixmap().size() == QSize(36, 36)          # kurşun kalem ikonu
    assert window.settings.width == 8 and window.settings.tool == Tool.PEN


def test_tool_cursor_also_applies_over_zones(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toolbar.width_buttons[12], Qt.MouseButton.LeftButton)
    for zone in (window.question_zone, window.hint_zone, window.webcam_panel):
        assert zone.cursor().pixmap().size() == QSize(82, 82)
    assert window.hint_zone.cards[0].cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_color_selects_pen_and_persists(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.LASER], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toolbar.swatches["#c8322b"], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.PEN and window.canvas.color.name() == "#c8322b"
    assert window.settings.color == "#c8322b" and window.toolbar.tool_buttons[Tool.PEN].isChecked()


def test_question_flow_saves_snapshot_and_clears(window, qtbot):
    c = window.canvas
    c.begin_stroke(QPointF(50, 50), 0.6); c.extend_stroke(QPointF(200, 200), 0.6); c.end_stroke()
    qtbot.mouseClick(window.toolbar.work_button, Qt.MouseButton.LeftButton)
    assert window.toolbar.work_button.text() == "Soruyu tamamla ✓"
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)
    files = sorted(p.name for p in window.session_store.session_dir.glob("*.png"))
    assert files == ["S1_01.png"]
    assert c.is_empty() and window.flow.index == 1
    assert window.flow.status(0) == QuestionStatus.DONE
    assert window.toolbar.progress_label.text() == "1/3 tamamlandı · S2"
    assert window.question_zone.number_label.text() == "2."
    assert window.question_zone.text_label.text() == SAMPLE_QUESTIONS[1].soru
    assert len(window.hint_zone.cards) == 3


def test_prev_button_goes_back(window, qtbot):
    qtbot.mouseClick(window.toolbar.prev_button, Qt.MouseButton.LeftButton)
    assert window.flow.index == 2 and window.question_zone.number_label.text() == "3."


def test_next_without_drawing_writes_nothing(window, qtbot):
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)
    assert not window.session_store.session_dir.exists()


def test_hint_reveal_and_mask_mode(window, qtbot):
    hz = window.hint_zone
    qtbot.mouseClick(hz.cards[2], Qt.MouseButton.LeftButton)
    assert hz.cards[2].revealed and not hz.cards[0].revealed
    qtbot.mouseClick(hz.next_button, Qt.MouseButton.LeftButton)
    assert hz.counter_label.text() == "2 / 3"
    qtbot.mouseClick(hz.redact_button, Qt.MouseButton.LeftButton)
    assert window.settings.hint_mask == HintMaskMode.REDACT
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)   # S2
    assert not any(c.revealed for c in hz.cards)


def test_question_hide_show(window, qtbot):
    qtbot.mouseClick(window.question_zone.hide_link, Qt.MouseButton.LeftButton)
    assert not window.question_zone.shown and not window.flow.is_question_shown()
    qtbot.mouseClick(window.question_zone.show_button, Qt.MouseButton.LeftButton)
    assert window.question_zone.shown


def test_pen_draws_over_hint_card_and_click_tool_reveals(window, qtbot):
    from PyQt6.QtTest import QTest
    win = window.windowHandle()
    card = window.hint_zone.cards[0]
    center = card.mapTo(window, card.rect().center())
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    QTest.mouseMove(win, center + QPointF(40, 20).toPoint())
    QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center + QPointF(40, 20).toPoint())
    assert not window.canvas.is_empty() and not card.revealed             # kalem: kartın üstüne çizdi
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.CLICK], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.CLICK and window.canvas.cursor().shape() == Qt.CursorShape.ArrowCursor
    window.canvas.clear()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    assert card.revealed and window.canvas.is_empty()                       # tıkla: kart açıldı, çizim yok


def test_shape_button_cycles_and_draws(window, qtbot):
    from matematigin_mantigi.core.models import Shape
    btn = window.toolbar.tool_buttons[Tool.SHAPE]
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.SHAPE and window.canvas.shape == Shape.RECT and btn.glyph == "▭"
    assert "Şekil (Dikdörtgen)" in window.work_area.status_label.text()
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)                  # seçiliyken tekrar: elips
    assert window.canvas.shape == Shape.ELLIPSE and btn.glyph == "○"
    c = window.canvas
    c.begin_stroke(QPointF(300, 300), 0.5); c.extend_stroke(QPointF(500, 420), 0.5); c.end_stroke()
    assert not c.is_empty()
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.PEN], Qt.MouseButton.LeftButton)
    assert window.canvas.shape == Shape.ELLIPSE                        # seçim hatırlanır


def test_text_tool_through_window(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.TEXT], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().shape() == Qt.CursorShape.IBeamCursor
    window.canvas.begin_stroke(QPointF(300, 400), 0.5)
    assert window.canvas.text_edit.isVisible()
    qtbot.keyClicks(window.canvas.text_edit, "Cevap: N ve H")      # N/H harfleri kısayol olarak çalışmamalı
    assert window.flow.index == 0 and window.flow.is_question_shown()
    qtbot.keyClick(window.canvas.text_edit, Qt.Key.Key_Return)
    assert not window.canvas.is_empty() and window.toolbar.undo_button.isEnabled()
    assert window.canvas.text_edit.isHidden()
    window.canvas.begin_stroke(QPointF(300, 500), 0.5)
    qtbot.keyClicks(window.canvas.text_edit, "iptal")
    qtbot.keyClick(window.canvas.text_edit, Qt.Key.Key_Escape)
    assert window.canvas.text_edit.isHidden() and window.canvas._stroke_count == 1


def test_ink_is_visible_on_top_of_hint_card(window, qtbot):
    card = window.hint_zone.cards[1]
    center = card.mapTo(window.work_area, card.rect().center())
    bpos = QPointF(window.work_area.board.mapFrom(window.work_area, center))
    c = window.canvas; c.set_color(QColor("#2456b8")); c.set_base_width(12)
    c.begin_stroke(bpos + QPointF(-40, 0), 1.0); c.extend_stroke(bpos + QPointF(40, 0), 1.0); c.end_stroke()
    img = window.work_area.grab().toImage()
    assert img.pixelColor(center.x(), center.y()).name() == "#2456b8"     # kartın üstünde mürekkep görünür


def test_drawing_over_question_zone_reaches_board(window, qtbot):
    z = window.question_zone
    qtbot.mousePress(z, Qt.MouseButton.LeftButton, pos=z.rect().center())
    qtbot.mouseMove(z, z.rect().center() + QPointF(60, 40).toPoint())
    qtbot.mouseRelease(z, Qt.MouseButton.LeftButton, pos=z.rect().center() + QPointF(60, 40).toPoint())
    assert not window.canvas.is_empty()


def test_recording_stub_and_badge(window, qtbot):
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert window.recorder.is_recording and window.badge.active
    assert window.badge.isHidden()                                     # rozet varsayılan kapalı: kayda girmesin
    assert window.recorder.last_rect.width == window.work_area.width() and window.recorder.fps == 60
    assert window.toolbar.record_label.text() == "DURDUR · 00:00"
    window.badge.tick(); window.badge.tick()
    assert window.badge.text().startswith("KAYIT · 00:02 · ") and window.toolbar.record_label.text() == "DURDUR · 00:02"
    assert "1440" in window.badge.text()                              # 2K çıktı
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert not window.recorder.is_recording and window.badge.isHidden()
    assert window.toolbar.record_label.text() == "KAYIT"


def test_badge_can_be_shown_on_board_from_settings(window, qtbot):
    window.settings.set_visible("badge", True); window.apply_ui_settings()
    window.toggle_recording(True)
    assert not window.badge.isHidden()
    window.toggle_recording(False)


def test_recorder_error_reverts_button(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import RecorderError
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[2])))

    def boom(rect, fps=60):
        raise RecorderError("ffmpeg bulunamadı")
    monkeypatch.setattr(window.recorder, "start", boom)
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert not window.recorder.is_recording and not window.toolbar.record_button.isChecked()
    assert shown and "ffmpeg" in shown[0]


def test_real_recorder_through_window(window, qtbot, tmp_path):
    import time
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    import pytest
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    frame = __import__("numpy").full((120, 160, 4), 255, __import__("numpy").uint8)
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=10, grabber=lambda r: frame, out_height=0)
    window.toggle_recording(True)
    assert window.recorder.is_recording
    time.sleep(0.5)
    window.toggle_recording(False)
    assert not window.toolbar.record_button.isEnabled()          # kapanış ayrı iş parçacığında
    qtbot.waitUntil(lambda: window.toolbar.record_button.isEnabled(), timeout=15000)
    assert window.recorder.last_path.exists() and "Kayıt kaydedildi" in window.work_area.status_label.text()


def test_real_recorder_with_audio_muxes_and_cleans_up(window, qtbot, tmp_path):
    """Pencere üzerinden ses+video: mikrofon (sahte) alınır, mux edilir, ara dosyalar silinir, süre gerçek."""
    import time
    import numpy as np
    import pytest
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    from tests.test_recorder import FakeAudioCapture, synthetic_grabber
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    window.settings.audio_device = "Sahte Mikrofon"          # apply_ui_settings bunu kaydediciye taşır
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                        out_height=0, audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture)
    window.toggle_recording(True)
    assert window.recorder.is_recording
    time.sleep(1.2)
    window.toggle_recording(False)
    assert not window.toolbar.record_button.isEnabled()      # mux ayrı iş parçacığında, arayüz donmaz
    qtbot.waitUntil(lambda: window.toolbar.record_button.isEnabled(), timeout=20000)
    path = window.recorder.last_path
    assert path.exists() and window.recorder.error is None and window.recorder.audio_error is None
    assert window.recorder.audio_result is not None and window.recorder.audio_result.samples > 40000
    assert window.recorder.av_offset_ms is not None          # ses-video başlangıç farkı ölçüldü
    assert not list(path.parent.glob("*.wav")) and not list(path.parent.glob("*.video.mp4"))   # ara dosyalar silindi
    import cv2
    cap = cv2.VideoCapture(str(path)); frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
    assert frames > 10


def test_layout_edit_persists_to_file(window, qtbot, tmp_path):
    qtbot.mouseClick(window.toolbar.layout_button, Qt.MouseButton.LeftButton)
    assert window.work_area.edit_mode
    window.work_area.reset_layout()
    assert (tmp_path / "duzen.json").exists()
    assert lm.load_layout(tmp_path / "duzen.json") == lm.DEFAULT_LAYOUT
    window.work_area.done_button.click()
    assert not window.work_area.edit_mode and not window.toolbar.layout_button.isChecked()


def test_restores_settings_on_start(qtbot, tmp_path, ini_settings, dead_camera):
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    ini_settings.tool = Tool.LASER; ini_settings.color = "#1f8a4c"; ini_settings.width = 2
    ini_settings.hint_mask = HintMaskMode.REDACT; ini_settings.chroma_enabled = False
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda index: dead_camera, tmp_path / "d.json")
    qtbot.addWidget(win)
    assert win.canvas.tool == Tool.LASER and win.canvas.color.name() == "#1f8a4c" and win.canvas.base_width == 2
    assert win.toolbar.tool_buttons[Tool.LASER].isChecked() and win.toolbar.width_buttons[2].isChecked()
    assert win.hint_zone.mask_mode == HintMaskMode.REDACT
    assert win.webcam_panel.chroma_enabled is False           # Ayarlar'daki perde anahtarı geri gelir
    assert win.question_zone.reading_ms == 0 and not win.question_zone.is_animating


def test_settings_camera_change_restarts_worker_and_logo(window, qtbot, tmp_path, monkeypatch):
    from PyQt6.QtGui import QImage
    from matematigin_mantigi.ui import settings_dialog as sd
    img = QImage(80, 80, QImage.Format.Format_RGB32); img.fill(Qt.GlobalColor.blue)
    logo = tmp_path / "logo.png"; img.save(str(logo))
    old_worker = window.webcam_panel.worker
    seen = []
    window.camera_source_factory = lambda index: (seen.append(index), window.camera_source_factory_dead)[1]
    window.camera_source_factory_dead = old_worker._source

    def fake_exec(self):
        self.logo_path_edit.setText(str(logo))
        self.camera_combo.addItem("Kamera 2", 2); self.camera_combo.setCurrentIndex(self.camera_combo.count() - 1)
        self._apply()
        return 1
    monkeypatch.setattr(sd.SettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.settings_button, Qt.MouseButton.LeftButton)
    assert window.settings.camera_index == 2 and seen == [2]
    assert window.webcam_panel.worker is not old_worker
    assert window.work_area.logo_is_file and window.settings.logo_file == str(logo)


def test_reload_questions_updates_flow_and_zone(window):
    from matematigin_mantigi.core.models import Question
    new = [Question("Z1", "Yeni konu", 5, "Yepyeni soru?", ("ip",), "cevap", ("a", "b", "c", "d"), None),
           Question("Z2", "Konu2", None, "İkinci?", (), "x", (), None)]
    window.reload_questions(new)
    assert [q.id for q in window.flow.questions] == ["Z1", "Z2"] and window.flow.index == 0
    assert window.question_zone.number_label.text() == "1."
    assert window.question_zone.text_label.text() == "Yepyeni soru?"
    assert len(window.hint_zone.cards) == 1


def test_reload_empty_list_does_not_crash(window):
    window.reload_questions([])
    assert window.flow.questions == () and window.flow.index == 0


def test_editor_button_disabled_and_open_is_guarded_without_path(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    calls = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: calls.append(a)))
    assert not window.toolbar.editor_button.isEnabled()          # fixture questions_path yok
    window.open_editor()
    assert calls                                                 # bilgi kutusu gösterildi, başka iş yok


def test_window_with_questions_path_enables_editor(qtbot, tmp_path, ini_settings, dead_camera):
    from matematigin_mantigi.core.models import PenSettings, Question
    from matematigin_mantigi.core.question_loader import write_questions
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    path = write_questions(tmp_path / "sorular.xlsx", list(SAMPLE_QUESTIONS))
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda index: dead_camera,
                     tmp_path / "d.json", questions_path=path)
    qtbot.addWidget(win)
    assert win.questions_path == path and win.toolbar.editor_button.isEnabled()
    win.reload_questions([Question("Z1", "K", 5, "Yeni?", ("i",), "c", ("a", "b", "c", "d"), None)])
    assert [q.id for q in win.flow.questions] == ["Z1"] and win.flow.index == 0
    assert win.question_zone.text_label.text() == "Yeni?"


def test_close_is_clean(window):
    window.close()


def test_keyboard_shortcuts(window, qtbot):
    qtbot.keyClick(window, Qt.Key.Key_2)
    assert window.canvas.tool == Tool.ERASER and window.toolbar.tool_buttons[Tool.ERASER].isChecked()
    qtbot.keyClick(window, Qt.Key.Key_N)
    assert window.flow.index == 1
    qtbot.keyClick(window, Qt.Key.Key_P)
    assert window.flow.index == 0
    qtbot.keyClick(window, Qt.Key.Key_Right)
    assert window.hint_zone.counter_label.text() == "2 / 3"
    qtbot.keyClick(window, Qt.Key.Key_Return)
    assert window.hint_zone.cards[1].revealed
    qtbot.keyClick(window, Qt.Key.Key_R)
    assert window.recorder.is_recording
    qtbot.keyClick(window, Qt.Key.Key_R)
    assert not window.recorder.is_recording
    qtbot.keyClick(window, Qt.Key.Key_L)
    assert window.work_area.edit_mode
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert not window.work_area.edit_mode


def test_pen_settings_round_trip_through_window(window, qtbot, monkeypatch):
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.ui import pen_settings as ps

    def fake_exec(self):
        self.smoothing_slider.setValue(80)
        self._apply()
        return 1
    monkeypatch.setattr(ps.PenSettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.pen_settings_button, Qt.MouseButton.LeftButton)
    assert window.settings.pen() == PenSettings(smoothing=80, reading_ms=0)     # hız korunur (fixture: 0)


def test_settings_dialog_applies_speed_visibility_and_auto_key(window, qtbot, monkeypatch):
    from matematigin_mantigi.ui import settings_dialog as sd

    def fake_exec(self):
        self.reading_slider.setValue(90)
        self.auto_key_check.setChecked(False)
        self.visibility_checks["status"].setChecked(False)
        self.visibility_checks["cam_label"].setChecked(False)
        self.visibility_checks["hint_controls"].setChecked(False)
        self.visibility_checks["brand"].setChecked(False)
        self.visibility_checks["question_number"].setChecked(False)
        self.visibility_checks["frame"].setChecked(False)
        self.presenter_edit.setText("Barış Keser")
        self.chroma_check.setChecked(False)
        self._apply()
        return 1
    monkeypatch.setattr(sd.SettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.settings_button, Qt.MouseButton.LeftButton)
    s = window.settings
    assert s.chroma_enabled is False and window.webcam_panel.chroma_enabled is False
    assert s.presenter_name == "Barış Keser" and window.work_area.name_label.text() == "Barış Keser"
    assert not window.work_area.frame_visible and window.canvas.geometry() == window.work_area.rect()
    assert s.pen().reading_ms == 90 and window.question_zone.reading_ms == 90
    assert s.auto_key is False and s.visible("status") is False
    assert window.work_area.status_label.isHidden() and window.webcam_panel.overlay_label.isHidden()
    assert window.hint_zone.blur_button.isHidden() and window.work_area.brand.isHidden()
    assert window.question_zone.number_label.isHidden()
    assert not window.hint_zone.title_label.isHidden()                 # dokunulmayan öğe açık kalır


def test_visibility_and_font_restored_on_start(qtbot, tmp_path, ini_settings, dead_camera):
    import pytest
    from matematigin_mantigi import paths
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    caveat = next(iter(paths.FONTS_DIR.glob("Caveat*.ttf")), None)
    if caveat is None:
        pytest.skip("bundled fonts not downloaded")
    ini_settings.set_pen(PenSettings(reading_ms=0))
    ini_settings.set_visible("brand", False); ini_settings.set_visible("hide_link", False)
    ini_settings.font_file = str(caveat)
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda index: dead_camera, tmp_path / "d.json")
    qtbot.addWidget(win); win.show()
    assert win.work_area.brand.isHidden() and win.question_zone.hide_link.isHidden()
    assert win.question_zone.text_label.font().family() == "Caveat"
    assert win.hint_zone.cards[0].text_label.font().family() == "Caveat"
