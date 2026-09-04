from PyQt6.QtCore import Qt

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, HintMaskMode, QuestionStatus
from matematigin_mantigi.ui.hint_panel import HintPanel
from matematigin_mantigi.ui.question_panel import QuestionPanel
from matematigin_mantigi.ui.theme import INK, FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


def qpanel(qtbot):
    p = QuestionPanel(FAM); qtbot.addWidget(p); p.resize(900, 300); p.show()
    p.set_questions(SAMPLE_QUESTIONS)
    return p


def test_question_chips_and_text(qtbot):
    p = qpanel(qtbot)
    assert [b.text() for b in p.chip_buttons] == ["S1 · bekliyor", "S2 · bekliyor", "S3 · bekliyor"]
    assert p.chip_buttons[0].isChecked()
    p.set_current(1)
    assert p.chip_buttons[1].isChecked() and p.text_label.text() == SAMPLE_QUESTIONS[1].soru
    p.set_status(1, QuestionStatus.WORKING)
    assert p.chip_buttons[1].text() == "S2 · işleniyor"
    with qtbot.waitSignal(p.questionSelected) as sig:
        qtbot.mouseClick(p.chip_buttons[2], Qt.MouseButton.LeftButton)
    assert sig.args == [2]


def test_question_hide_and_show(qtbot):
    p = qpanel(qtbot)
    assert p.shown and p.text_label.graphicsEffect() is None and p.show_button.isHidden()
    with qtbot.waitSignal(p.hideRequested):
        qtbot.mouseClick(p.hide_link, Qt.MouseButton.LeftButton)
    p.set_shown(False)
    assert p.text_label.graphicsEffect() is not None and not p.show_button.isHidden()
    with qtbot.waitSignal(p.showRequested):
        qtbot.mouseClick(p.show_button, Qt.MouseButton.LeftButton)
    p.set_shown(True)
    assert p.text_label.graphicsEffect() is None and p.show_button.isHidden()


def hpanel(qtbot):
    h = HintPanel(FAM); qtbot.addWidget(h); h.resize(700, 500); h.show()
    h.set_hints("S1", SAMPLE_QUESTIONS[0].hints)
    return h


def test_hints_start_hidden_and_blurred(qtbot):
    h = hpanel(qtbot)
    assert h.title_label2.text() == "S1 ipuçları" and h.counter_label.text() == "1 / 3"
    assert len(h.rows) == 3
    assert all(not r.revealed and r.text_label.graphicsEffect() is not None for r in h.rows)
    assert [r.state_label.text() for r in h.rows] == ["gizli"] * 3
    assert h.reveal_button.text() == "Aç"


def test_reveal_only_clicked_row(qtbot):
    h = hpanel(qtbot)
    with qtbot.waitSignal(h.revealToggled) as sig:
        qtbot.mouseClick(h.rows[1].text_label, Qt.MouseButton.LeftButton)
    assert sig.args == [1]
    h.set_revealed(1, True)
    assert h.rows[1].revealed and h.rows[1].text_label.graphicsEffect() is None
    assert not h.rows[0].revealed and h.rows[0].text_label.graphicsEffect() is not None
    h.set_focus(1)
    assert h.counter_label.text() == "2 / 3" and h.reveal_button.text() == "Gizle"


def test_redact_mode_paints_ink(qtbot):
    h = hpanel(qtbot)
    with qtbot.waitSignal(h.maskModeChanged) as sig:
        qtbot.mouseClick(h.redact_button, Qt.MouseButton.LeftButton)
    assert sig.args == [HintMaskMode.REDACT] and h.mask_mode == HintMaskMode.REDACT
    assert h.rows[0].text_label.graphicsEffect() is None
    assert INK in h.rows[0].text_label.styleSheet()
    h.set_revealed(0, True)
    assert INK not in h.rows[0].text_label.styleSheet()


def test_nav_buttons_and_footer(qtbot):
    h = hpanel(qtbot)
    with qtbot.waitSignal(h.nextRequested):
        qtbot.mouseClick(h.next_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(h.prevRequested):
        qtbot.mouseClick(h.prev_button, Qt.MouseButton.LeftButton)
    h.set_recognized("x = 5")
    assert h.footer_label.text() == "Keras · yazı tanıma etkin · son tanınan: x = 5"
