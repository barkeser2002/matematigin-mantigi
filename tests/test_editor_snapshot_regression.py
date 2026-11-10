import pytest
from PyQt6.QtCore import QPointF

from matematigin_mantigi.core.question_loader import load_questions, write_questions
from matematigin_mantigi.ui.question_editor import QuestionEditorDialog
from matematigin_mantigi.ui import error_notice


@pytest.fixture(autouse=True)
def cleanup(window):
    yield
    window.webcam_panel.shutdown()


def test_editor_save_snapshot_failure_keeps_edits_and_retries(window, tmp_path, monkeypatch):
    path = write_questions(tmp_path / 'questions.xlsx', window.flow.questions)
    window.questions_path = path
    window.questions_from_file = True
    original = load_questions(path)[0].soru
    window.canvas.begin_text(QPointF(100, 100))
    window.canvas.text_edit.setText('Tahta yazısı')
    monkeypatch.setattr(error_notice, 'post', lambda *a, **k: None)
    save = window.session_store.save_snapshot
    monkeypatch.setattr(window.session_store, 'save_snapshot', lambda *a: (_ for _ in ()).throw(OSError('disk')))

    def run(dlg):
        dlg.show()
        dlg.soru_edit.setPlainText('Yeni soru')
        dlg.save_button.click()
        assert dlg.isVisible()
        assert dlg.soru_edit.toPlainText() == 'Yeni soru'
        assert load_questions(path)[0].soru == original
        assert window.flow.questions[0].soru == original
        assert window.canvas.text_edit.text() == 'Tahta yazısı'
        monkeypatch.setattr(window.session_store, 'save_snapshot', save)
        dlg.save_button.click()
        assert not dlg.isVisible()
        return dlg.result()

    monkeypatch.setattr(QuestionEditorDialog, 'exec', run)
    window.open_editor()
    assert load_questions(path)[0].soru == 'Yeni soru'
    assert window.flow.questions[0].soru == 'Yeni soru'
    assert window.session_store.count('S1') == 1


@pytest.mark.parametrize('error', [OSError('disk'), RuntimeError('render')])
def test_snapshot_image_exception_is_handled_by_timer(window, monkeypatch, error):
    window.canvas.begin_text(QPointF(100, 100))
    window.canvas.text_edit.setText('Korunmalı')
    notices = []
    monkeypatch.setattr(error_notice, 'post', lambda *a, **k: notices.append((a, k)))
    monkeypatch.setattr(window.canvas, 'snapshot_image', lambda: (_ for _ in ()).throw(error))
    window._autosave_timer.timeout.emit()
    assert notices
    assert window.canvas.text_edit.text() == 'Korunmalı'
    assert window._save_board(window.flow.index) is False
