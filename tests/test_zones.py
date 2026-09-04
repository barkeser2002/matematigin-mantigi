from dataclasses import replace

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, HintMaskMode
from matematigin_mantigi.ui.hint_zone import HintZone
from matematigin_mantigi.ui.question_zone import QuestionZone
from matematigin_mantigi.ui.theme import INK, FontFamilies

FAM = FontFamilies("Arial", "Arial", False)
Q0 = SAMPLE_QUESTIONS[0]


def qzone(qtbot, ms=0):
    z = QuestionZone(FAM); qtbot.addWidget(z); z.resize(900, 420); z.show()
    qtbot.waitExposed(z)
    z.set_reading_ms(ms)
    return z


def test_question_zone_without_animation(qtbot):
    z = qzone(qtbot, ms=0)
    z.set_question(Q0, 1, animate=True)
    assert z.number_label.text() == "1." and z.text_label.text() == Q0.soru
    assert [lab.text() for lab in z.option_labels] == ["A) 3", "B) 4", "C) 5", "D) 6"]
    assert z.options_widget.isVisible() and not z.is_animating
    assert z.image_label.isHidden()


def test_reading_animation_reveals_words_then_options(qtbot):
    z = qzone(qtbot, ms=20)
    with qtbot.waitSignal(z.readingFinished, timeout=3000):
        z.set_question(Q0, 3)
        assert z.is_animating and z.text_label.text() == "" and not z.options_widget.isVisible()
    assert z.text_label.text() == Q0.soru and z.options_widget.isVisible()
    assert z.number_label.text() == "3."


def test_click_skips_animation(qtbot):
    z = qzone(qtbot, ms=500)
    z.set_question(Q0, 1)
    assert z.is_animating
    qtbot.mouseClick(z, Qt.MouseButton.LeftButton, pos=QPoint(400, 300))
    assert not z.is_animating and z.text_label.text() == Q0.soru


def test_hide_and_show_blur(qtbot):
    z = qzone(qtbot)
    z.set_question(Q0, 1)
    assert z.shown and z.content.graphicsEffect() is None and z.show_button.isHidden()
    with qtbot.waitSignal(z.hideRequested):
        qtbot.mouseClick(z.hide_link, Qt.MouseButton.LeftButton)
    z.set_shown(False)
    assert z.content.graphicsEffect() is not None and not z.show_button.isHidden()
    with qtbot.waitSignal(z.showRequested):
        qtbot.mouseClick(z.show_button, Qt.MouseButton.LeftButton)
    z.set_shown(True)
    assert z.content.graphicsEffect() is None


def test_image_shown_when_file_exists(qtbot, tmp_path):
    img = QImage(300, 120, QImage.Format.Format_RGB32); img.fill(Qt.GlobalColor.green)
    path = tmp_path / "fig.png"; img.save(str(path))
    z = qzone(qtbot)
    z.set_question(replace(Q0, image=str(path)), 1)
    assert z.image_label.isVisible() and not z.image_label.pixmap().isNull()
    z.set_question(replace(Q0, image=str(tmp_path / "yok.png")), 2)
    assert z.image_label.isHidden()


def hzone(qtbot):
    h = HintZone(FAM); qtbot.addWidget(h); h.resize(800, 500); h.show()
    h.set_hints("S1", Q0.hints)
    return h


def test_hints_start_hidden(qtbot):
    h = hzone(qtbot)
    assert h.title_label.text() == "AKILLI İPUÇLARI" and h.counter_label.text() == "1 / 3"
    assert len(h.cards) == 3
    assert all(not c.revealed and c.text_label.graphicsEffect() is not None for c in h.cards)


def test_card_click_reveals_only_that_card(qtbot):
    h = hzone(qtbot)
    with qtbot.waitSignal(h.revealToggled) as sig:
        qtbot.mouseClick(h.cards[1], Qt.MouseButton.LeftButton)
    assert sig.args == [1]
    h.set_revealed(1, True)
    assert h.cards[1].revealed and h.cards[1].text_label.graphicsEffect() is None
    assert not h.cards[0].revealed and h.cards[0].text_label.graphicsEffect() is not None
    h.set_focus(1)
    assert h.counter_label.text() == "2 / 3"


def test_redact_mode_paints_ink(qtbot):
    h = hzone(qtbot)
    with qtbot.waitSignal(h.maskModeChanged) as sig:
        qtbot.mouseClick(h.redact_button, Qt.MouseButton.LeftButton)
    assert sig.args == [HintMaskMode.REDACT] and h.mask_mode == HintMaskMode.REDACT
    assert h.cards[0].text_label.graphicsEffect() is None and INK in h.cards[0].text_label.styleSheet()
    h.set_revealed(0, True)
    assert INK not in h.cards[0].text_label.styleSheet()


def test_nav_buttons(qtbot):
    h = hzone(qtbot)
    with qtbot.waitSignal(h.nextRequested):
        qtbot.mouseClick(h.next_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(h.prevRequested):
        qtbot.mouseClick(h.prev_button, Qt.MouseButton.LeftButton)
