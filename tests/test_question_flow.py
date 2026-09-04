from matematigin_mantigi.core.models import QuestionStatus
from matematigin_mantigi.core.question_flow import QuestionFlow


def test_initial_state(sample_questions):
    f = QuestionFlow(sample_questions)
    assert f.index == 0 and f.current.id == "S1"
    assert all(f.status(i) == QuestionStatus.WAITING for i in range(3))
    assert f.done_count() == 0 and f.progress_label() == "0/3 tamamlandı · S1"
    assert f.work_label() == "Soruyu işle" and f.is_question_shown() is True
    assert f.hint_index() == 0 and f.hint_count() == 3 and not f.is_revealed()


def test_toggle_work_cycles(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.statusChanged) as sig:
        f.toggle_work()
    assert sig.args == [0, QuestionStatus.WORKING] and f.work_label() == "Soruyu tamamla ✓"
    f.toggle_work()
    assert f.status() == QuestionStatus.DONE and f.done_count() == 1
    f.toggle_work()
    assert f.status() == QuestionStatus.WORKING


def test_next_question_marks_done_and_emits_in_order(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    order = []
    f.questionLeaving.connect(lambda i: order.append(("leaving", i)))
    f.questionChanged.connect(lambda i: order.append(("changed", i)))
    f.toggle_work(); f.set_hint_index(2)
    f.next_question()
    assert order == [("leaving", 0), ("changed", 1)]
    assert f.status(0) == QuestionStatus.DONE and f.index == 1 and f.hint_index() == 0


def test_next_wraps_and_waiting_stays_waiting(sample_questions):
    f = QuestionFlow(sample_questions)
    f.next_question(); f.next_question(); f.next_question()
    assert f.index == 0 and f.status(2) == QuestionStatus.WAITING


def test_prev_wraps_and_keeps_status(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    f.toggle_work()
    with qtbot.waitSignal(f.questionChanged) as sig:
        f.prev_question()
    assert sig.args == [2] and f.index == 2
    assert f.status(0) == QuestionStatus.WORKING          # önceki durum değişmez
    f.prev_question()
    assert f.index == 1


def test_hint_navigation_clamps(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    f.hint_prev(); assert f.hint_index() == 0
    with qtbot.waitSignal(f.hintChanged) as sig:
        f.hint_next()
    assert sig.args == [1, 3]
    f.hint_next(); f.hint_next(); f.hint_next()
    assert f.hint_index() == 2


def test_reveal_is_per_hint_and_per_question(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.hintRevealChanged) as sig:
        f.toggle_reveal(1)
    assert sig.args == [0, 1, True]
    assert f.is_revealed(1) and not f.is_revealed(0)
    f.hint_next()                                   # gezinme açmaz
    assert f.is_revealed(1) and not f.is_revealed(2)
    f.select(1)
    assert not f.is_revealed(1)
    f.select(0)
    assert f.is_revealed(1)
    f.toggle_reveal(1)
    assert not f.is_revealed(1)


def test_show_hide_question(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.questionVisibilityChanged) as sig:
        f.hide_question()
    assert sig.args == [False] and not f.is_question_shown()
    f.show_question()
    assert f.is_question_shown()


def test_select_emits_progress_and_changed(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.questionChanged) as sig:
        f.select(2)
    assert sig.args == [2] and f.progress_label() == "0/3 tamamlandı · S3"


def test_empty_flow_is_safe():
    f = QuestionFlow([])
    assert f.hint_count() == 0 and f.progress_label() == "0/0 tamamlandı"
    f.next_question(); f.toggle_work(); f.toggle_reveal()
