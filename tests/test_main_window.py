from PyQt6.QtCore import QPointF, QSize, Qt

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, HintMaskMode, QuestionStatus, Tool


def test_window_shell(window):
    assert window.windowTitle() == "Matematiğin Mantığı"
    assert window.toolbar.width() == 88
    x, y, w, h, _ = window.work_area.recording_rect()
    assert w == window.width() - 88 and h == window.height()
    assert window.canvas is window.work_area.board and window.canvas.geometry() == window.work_area.rect()
    assert window.question_zone.number_label.text() == "1."
    assert window.question_zone.text_label.text().startswith("3x + 5")
    assert len(window.hint_zone.cards) == 3
    assert window.work_area.status_label.text().startswith("Araç: Kalem")


def test_tool_switch_updates_cursor_and_status(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.ERASER
    assert window.canvas.cursor().pixmap().size() == QSize(36, 36)
    assert "Araç: Silgi" in window.work_area.status_label.text()
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.PEN], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toolbar.width_buttons[8], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().pixmap().size() == QSize(28, 28)
    assert window.settings.width == 8 and window.settings.tool == Tool.PEN


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


def test_drawing_over_question_zone_reaches_board(window, qtbot):
    z = window.question_zone
    qtbot.mousePress(z, Qt.MouseButton.LeftButton, pos=z.rect().center())
    qtbot.mouseMove(z, z.rect().center() + QPointF(60, 40).toPoint())
    qtbot.mouseRelease(z, Qt.MouseButton.LeftButton, pos=z.rect().center() + QPointF(60, 40).toPoint())
    assert not window.canvas.is_empty()


def test_recording_stub_and_badge(window, qtbot):
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert window.recorder.is_recording and window.badge.active and not window.badge.isHidden()
    assert window.recorder.last_rect.width == window.work_area.width()
    assert window.toolbar.record_label.text() == "DURDUR"
    window.badge.tick(); window.badge.tick()
    assert window.badge.text().startswith("KAYIT · 00:02 · ")
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert not window.recorder.is_recording and window.badge.isHidden()
    assert window.toolbar.record_label.text() == "KAYIT"


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
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda: dead_camera, tmp_path / "d.json")
    qtbot.addWidget(win)
    assert win.canvas.tool == Tool.LASER and win.canvas.color.name() == "#1f8a4c" and win.canvas.base_width == 2
    assert win.toolbar.tool_buttons[Tool.LASER].isChecked() and win.toolbar.width_buttons[2].isChecked()
    assert win.hint_zone.mask_mode == HintMaskMode.REDACT and win.webcam_panel.chroma_enabled is False
    assert win.question_zone.reading_ms == 0 and not win.question_zone.is_animating


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
    captured = {}

    def fake_exec(self):
        captured["dialog"] = self
        self.smoothing_slider.setValue(80)
        self.reading_slider.setValue(90)
        self._apply()
        return 1
    monkeypatch.setattr(ps.PenSettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.pen_settings_button, Qt.MouseButton.LeftButton)
    assert window.settings.pen() == PenSettings(smoothing=80, reading_ms=90)
    assert window.question_zone.reading_ms == 90
