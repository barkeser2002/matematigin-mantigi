"""Pencere ve ayar sağlamlaştırmasının kullanıcı davranışı regresyonları."""
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QMessageBox

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
