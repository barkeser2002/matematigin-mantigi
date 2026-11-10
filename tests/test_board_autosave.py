from dataclasses import replace

import pytest
from PyQt6.QtCore import QPointF


@pytest.fixture(autouse=True)
def stop_camera(window):
    yield
    window.webcam_panel.shutdown()


def draw(window):
    c = window.canvas
    c.begin_stroke(QPointF(50, 50), .6)
    c.end_stroke()


@pytest.mark.parametrize("damage", ["missing", "moved", "corrupt", "replaced", "unreadable"])
def test_changed_snapshot_is_saved_again_before_leaving(window, damage, monkeypatch):
    from pathlib import Path
    from PyQt6.QtGui import QImage, QColor
    draw(window)
    assert window._save_board(0)
    original = window.session_store.session_dir / "S1_01.png"
    if damage == "missing":
        original.unlink()
    elif damage == "moved":
        original.rename(original.with_suffix(".moved"))
    elif damage == "corrupt":
        original.write_bytes(b"broken")
    elif damage == "replaced":
        replacement = QImage(10, 10, QImage.Format.Format_RGB32)
        replacement.fill(QColor("red"))
        assert replacement.save(str(original), "PNG")
    else:
        read_bytes = Path.read_bytes
        def deny_original(path):
            if path == original:
                raise PermissionError("unreadable")
            return read_bytes(path)
        monkeypatch.setattr(Path, "read_bytes", deny_original)
    assert window._on_question_leaving(0)
    restored = window.session_store.session_dir / "S1_02.png"
    assert not QImage(str(restored)).isNull()
    if damage == "corrupt":
        assert original.read_bytes() == b"broken"
    if damage == "moved":
        assert original.with_suffix(".moved").exists()


def test_missing_snapshot_and_failed_retry_cancel_close(window, monkeypatch, qtbot):
    from matematigin_mantigi.ui import error_notice
    notice = error_notice.ErrorNotice()
    monkeypatch.setattr(error_notice, "_instance", notice)
    notice.set_anchor(window)
    draw(window)
    assert window._save_board(0)
    (window.session_store.session_dir / "S1_01.png").unlink()
    monkeypatch.setattr(window.session_store, "save_snapshot", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    window.close()
    assert window.isVisible()
    assert not window.canvas.is_empty()
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible())
    notice.release()


def test_missing_snapshot_failed_navigation_preserves_board_then_retry(window, monkeypatch, qtbot):
    from matematigin_mantigi.ui import error_notice
    notice = error_notice.ErrorNotice()
    monkeypatch.setattr(error_notice, "_instance", notice)
    notice.set_anchor(window)
    draw(window)
    assert window._save_board(0)
    (window.session_store.session_dir / "S1_01.png").unlink()
    save = window.session_store.save_snapshot
    monkeypatch.setattr(window.session_store, "save_snapshot", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    index = window.flow.index
    window.flow.next_question()
    assert window.flow.index == index
    assert not window.canvas.is_empty()
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible())
    notice.box.accept()
    monkeypatch.setattr(window.session_store, "save_snapshot", save)
    window.flow.next_question()
    assert window.flow.index != index
    assert window.canvas.is_empty()
    notice.release()


def test_autosave_timer_deduplicates_and_respects_setting(window):
    draw(window)
    assert window._autosave_timer.interval() == 30000
    window._autosave_timer.timeout.emit()
    window._autosave_timer.timeout.emit()
    assert window.session_store.count('S1') == 1
    window._apply_pen_settings(replace(window.settings.pen(), autosave=False))
    draw(window)
    window._autosave_timer.timeout.emit()
    assert window.session_store.count('S1') == 1
    window._apply_pen_settings(replace(window.settings.pen(), autosave=True))
    window._autosave_timer.timeout.emit()
    assert window.session_store.count('S1') == 2


def test_reload_preserves_pending_text(window):
    c = window.canvas
    c.begin_text(QPointF(100, 100))
    c.text_edit.setText('Kaybolmasın')
    window.reload_questions(window.flow.questions)
    assert window.session_store.count('S1') == 1
    assert c.is_empty()
    assert not c.text_edit.isVisible()


def test_autosave_preserves_open_editor_and_captures_text(window):
    c = window.canvas
    c.begin_text(QPointF(100, 100))
    c.text_edit.setText('Metin')
    window._autosave_timer.timeout.emit()
    assert c.text_edit.text() == 'Metin' and c.text_edit.isVisible()
    from PyQt6.QtGui import QImage
    image = QImage(str(window.session_store.session_dir / 'S1_01.png'))
    assert not image.isNull()
    assert any(image.pixelColor(x, y).red() < 200 for x in range(100, 220) for y in range(75, 115))


def test_close_saves_board(window):
    draw(window)
    window.close()
    assert window.session_store.count('S1') == 1


def test_failed_close_snapshot_keeps_window_and_text(window, monkeypatch):
    c = window.canvas
    c.begin_text(QPointF(100, 100))
    c.text_edit.setText("Kayıp olmasın")
    monkeypatch.setattr(window.session_store, "save_snapshot", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    window.close()
    assert window.isVisible()
    assert c.text_edit.text() == "Kayıp olmasın"


def test_failed_reload_keeps_old_board_and_question(window, monkeypatch):
    draw(window)
    old = window.flow.questions
    monkeypatch.setattr(window.session_store, "save_snapshot", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    window.reload_questions([])
    assert window.flow.questions == old
    assert not window.canvas.is_empty()


def test_failed_manual_retry_warns_again_after_dismissal(window, monkeypatch, qtbot):
    from matematigin_mantigi.ui import error_notice
    notice = error_notice.ErrorNotice()
    monkeypatch.setattr(error_notice, "_instance", notice)
    notice.set_anchor(window)
    draw(window)
    monkeypatch.setattr(window.session_store, "save_snapshot", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    assert not window._on_question_leaving(0)
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible())
    notice.box.accept()
    assert not window._on_question_leaving(0)
    qtbot.waitUntil(lambda: notice.box.isVisible(), timeout=1000)
    notice.release()


def test_autosave_failure_is_coalesced_until_success(window, monkeypatch, qtbot):
    from matematigin_mantigi.ui import error_notice
    notice = error_notice.ErrorNotice()
    monkeypatch.setattr(error_notice, "_instance", notice)
    notice.set_anchor(window)
    draw(window)
    save = window.session_store.save_snapshot
    def fail(*args):
        raise OSError("disk")
    monkeypatch.setattr(window.session_store, "save_snapshot", fail)
    window._autosave_board()
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible())
    notice.box.accept()
    window._autosave_board()
    qtbot.wait(20)
    assert not notice.box.isVisible()
    monkeypatch.setattr(window.session_store, "save_snapshot", save)
    window._autosave_board()
    draw(window)
    monkeypatch.setattr(window.session_store, "save_snapshot", fail)
    window._autosave_board()
    qtbot.waitUntil(lambda: notice.box.isVisible())
    notice.release()


def test_repeated_failure_while_recording_updates_one_off_scene_notice(window, monkeypatch, qtbot):
    from matematigin_mantigi.ui import error_notice
    notice = error_notice.ErrorNotice()
    monkeypatch.setattr(error_notice, "_instance", notice)
    notice.set_anchor(window)
    alerts = []
    notice.set_recording_route(lambda: True, alerts.append)
    draw(window)
    monkeypatch.setattr(window.session_store, "save_snapshot", lambda *a: (_ for _ in ()).throw(OSError("disk")))
    assert not window._on_question_leaving(0)
    qtbot.waitUntil(lambda: bool(notice._pending))
    assert not window._on_question_leaving(0)
    qtbot.wait(20)
    assert len(notice._pending) == 1
    assert notice.box is None or not notice.box.isVisible()
    assert alerts[-1] and "Tahta" in alerts[-1]
    notice.release()
