"""Pencere ve ayar sağlamlaştırmasının kullanıcı davranışı regresyonları."""
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from matematigin_mantigi.core.recorder import RecorderState
from matematigin_mantigi.ui import error_notice
from matematigin_mantigi.ui.settings_dialog import SettingsDialog


@pytest.fixture(autouse=True)
def safe_cleanup(window, monkeypatch):
    # Başarısız test bile offscreen modal ya da çalışan kamera işçisi bırakmaz.
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "exec", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    monkeypatch.setattr(error_notice, "post", lambda *a, **k: None)
    yield
    if window.recorder.state is RecorderState.RECORDING:
        window.recorder.stop()
    window.webcam_panel.shutdown()


@pytest.mark.parametrize("navigation", ["next_question", "prev_question", "select"])
def test_question_transition_saves_open_text_before_clearing(window, navigation):
    canvas = window.canvas
    canvas.begin_text(QPointF(100, 100))
    canvas.text_edit.setText("Kaybolmayan yazı")
    # Beklenen PNG, Enter ile işlenen gerçek mürekkebin görüntüsüyle aynı olmalı.
    expected = canvas.snapshot_image()
    getattr(window.flow, navigation)(1) if navigation == "select" else getattr(window.flow, navigation)()
    saved = QImage(str(window.session_store.session_dir / "S1_01.png"))
    fmt = QImage.Format.Format_ARGB32
    assert saved.convertToFormat(fmt) == expected.convertToFormat(fmt)
    assert window.flow.index != 0
    assert canvas.is_empty() and not canvas.text_edit.isVisible()
    assert not canvas.can_undo()


def test_failed_transition_preserves_open_text_and_retry_saves_it(window, monkeypatch):
    canvas = window.canvas
    canvas.begin_text(QPointF(100, 100))
    canvas.text_edit.setText("Yeniden denenecek yazı")
    expected = canvas.snapshot_image()
    save = window.session_store.save_snapshot

    def fail(*args):
        raise OSError("disk")

    monkeypatch.setattr(window.session_store, "save_snapshot", fail)
    window.flow.next_question()
    assert window.flow.index == 0
    assert canvas.text_edit.isVisible()
    assert canvas.text_edit.text() == "Yeniden denenecek yazı"
    assert canvas.snapshot_image() == expected
    monkeypatch.setattr(window.session_store, "save_snapshot", save)
    window.flow.next_question()
    assert window.flow.index == 1
    assert window.session_store.count("S1") == 1
    assert not canvas.text_edit.isVisible()


def test_settings_return_applies_from_non_text_control(window, qtbot):
    dialog = SettingsDialog(window.settings, window.fam, window)
    qtbot.addWidget(dialog)
    applied = []
    dialog.applied.connect(applied.append)
    dialog.setModal(True)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.activateWindow()
    dialog.reading_slider.setFocus()
    qtbot.keyClick(dialog.reading_slider, Qt.Key.Key_Return)
    assert len(applied) == 1
    assert not dialog.isVisible()


@pytest.mark.parametrize("control", ["presenter_edit", "audio_combo", "fps_combo"])
def test_settings_return_in_input_does_not_apply_or_close(window, qtbot, control):
    dialog = SettingsDialog(window.settings, window.fam, window)
    qtbot.addWidget(dialog)
    applied = []
    dialog.applied.connect(applied.append)
    dialog.setModal(True)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.activateWindow()
    widget = getattr(dialog, control)
    dialog.scroll.ensureWidgetVisible(widget)
    widget.setFocus()
    if control == "audio_combo":
        widget = widget.lineEdit()
        widget.setText("Mikrofon adı")
    qtbot.keyClick(widget, Qt.Key.Key_Return)
    assert dialog.isVisible()
    assert applied == []


def test_settings_return_selects_popup_item_without_applying(window, qtbot):
    dialog = SettingsDialog(window.settings, window.fam, window)
    qtbot.addWidget(dialog)
    applied = []
    dialog.applied.connect(applied.append)
    dialog.setModal(True)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.activateWindow()
    combo = dialog.fps_combo
    dialog.scroll.ensureWidgetVisible(combo)
    combo.setFocus()
    combo.showPopup()
    qtbot.keyClick(combo.view(), Qt.Key.Key_Return)
    assert dialog.isVisible()
    assert applied == []


def test_settings_apply_is_the_only_default_button(window, qtbot):
    from PyQt6.QtWidgets import QPushButton
    dialog = SettingsDialog(window.settings, window.fam, window)
    qtbot.addWidget(dialog)
    assert dialog.apply_button.isDefault()
    assert all(not button.autoDefault() for button in dialog.findChildren(QPushButton)
               if button is not dialog.apply_button)


@pytest.mark.parametrize("kind", ["settings", "editor"])
@pytest.mark.parametrize("recording,allow", [(True, False), (True, True), (False, False)])
def test_recorded_dialog_requires_explicit_permission(window, monkeypatch, tmp_path, kind, recording, allow):
    from types import SimpleNamespace
    from matematigin_mantigi.ui import main_window
    window.questions_path = tmp_path / "questions.xlsx"
    opened, asked = [], []

    def create(*args, **kwargs):
        opened.append("created")
        signal = SimpleNamespace(connect=lambda callback: None)
        return SimpleNamespace(applied=signal, saved=signal, exec=lambda: opened.append("executed"))

    monkeypatch.setattr(main_window, "SettingsDialog" if kind == "settings" else "QuestionEditorDialog", create)

    def answer(parent, title, text, buttons, default):
        asked.append(text)
        assert text == "Bu pencere kayda girer (editör cevapları gösterir). Yine de açılsın mı?"
        assert buttons == QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        assert default == QMessageBox.StandardButton.No
        return QMessageBox.StandardButton.Yes if allow else QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", answer)
    if recording:
        window.toggle_recording(True)
    getattr(window, "open_" + kind)()
    assert len(asked) == int(recording)
    assert bool(opened) == (not recording or allow)
    if opened:
        assert opened == ["created", "executed"]
    assert window.recorder.state is (RecorderState.RECORDING if recording else RecorderState.IDLE)


@pytest.mark.parametrize("kind", ["settings", "editor"])
def test_pending_close_refuses_dialog_without_recording_permission(window, monkeypatch, kind):
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a))
    window._close_after_save = True
    getattr(window, "open_" + kind)()
    assert asked == []
    window._close_after_save = False


def test_record_result_status_shows_filename_without_user_directory(window, tmp_path):
    path = tmp_path / "ozel_kullanici" / "ders_01.mp4"
    window.recorder.capture_fps = 29.6
    window._report_record_result(path, None)
    text = window.work_area.status_label.text()
    assert text == "Kayıt kaydedildi: ders_01.mp4 · yakalama ~30 kare/sn"
    assert str(path.parent) not in text


def test_closing_summary_keeps_full_record_path(window, monkeypatch, tmp_path):
    path = tmp_path / "ozel_kullanici" / "ders_01.mp4"
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()))
    window._show_closing_summary(path, None)
    assert len(shown) == 1 and str(path) in shown[0]


def test_record_warning_keeps_full_path_off_scene(window, monkeypatch, tmp_path):
    path = tmp_path / "ozel_kullanici" / "ders_01.mp4"
    posted = []
    window.recorder.audio_error = "Mikrofon kesildi"
    monkeypatch.setattr(error_notice, "post", lambda *a, **k: posted.append((a, k)))
    window._report_record_result(path, None)
    assert len(posted) == 1 and str(path) in posted[0][0][1]
    assert "ozel_kullanici" not in window.work_area.status_label.text()


@pytest.mark.xfail(strict=True, reason="#51: gerçek çıktı boyutu arayüze açılmıyor; recorder.py değişikliği gerekir",
                   raises=AssertionError)
def test_badge_resolution_matches_real_encoded_frame(window, monkeypatch, tmp_path, qtbot):
    """Kaydedicinin gerçek ilk karesi nominal ekran dikdörtgeniyle aynı olmayabilir."""
    import cv2
    import numpy as np
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    if not find_ffmpeg():
        pytest.skip("ffmpeg yok")
    window.settings.record_height = 0
    recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", out_height=0,
                                 grabber=lambda rect: np.zeros((122, 218, 4), dtype=np.uint8))
    window.recorder = recorder
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        window.toggle_recording(True)
        qtbot.waitUntil(lambda: recorder.frames_written >= 2)
        badge_text = window.badge.text()
        window.toggle_recording(False)
        qtbot.waitUntil(lambda: window._stop_worker is None, timeout=20000)
        video = cv2.VideoCapture(str(recorder.last_path))
        try:
            assert video.isOpened()
            width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        finally:
            video.release()
        assert f"{width}×{height}" in badge_text
    finally:
        from tests.test_main_window import _release_windows_left_open
        _release_windows_left_open()
