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


def test_reading_animation_reveals_letters_then_options(qtbot):
    z = qzone(qtbot, ms=5)
    with qtbot.waitSignal(z.readingFinished, timeout=3000):
        z.set_question(Q0, 3)
        assert z.is_animating and z.text_label.text() == "" and not z.options_widget.isVisible()
    assert z.text_label.text() == Q0.soru and z.options_widget.isVisible()
    assert z.number_label.text() == "3."


def test_letters_fade_in_one_by_one(qtbot):
    z = qzone(qtbot, ms=60)
    z.set_question(Q0, 1)
    qtbot.waitUntil(lambda: z.text_label.text() != "", timeout=2000)
    t = z.text_label.text()
    assert z.text_label.textFormat() == Qt.TextFormat.RichText
    assert 'color:#40' in t                                    # en yeni harf en saydam
    qtbot.waitUntil(lambda: z._n >= 3, timeout=2000)
    t = z.text_label.text()
    assert t.count("<span") == 3 and "#c0" in t and "#80" in t and "#40" in t
    z.skip_animation()
    assert z.text_label.text() == Q0.soru and z.text_label.textFormat() == Qt.TextFormat.PlainText


def test_font_family_and_visibility_switches(qtbot):
    z = qzone(qtbot)
    z.set_question(Q0, 1)
    z.set_families(FontFamilies("Courier New", "Arial", False))
    assert z.text_label.font().family() == "Courier New" and z.option_labels[0].font().family() == "Courier New"
    z.set_number_visible(False)
    assert z.number_label.isHidden()
    z.set_hide_link_enabled(False)
    assert z.hide_link.isHidden()
    z.set_shown(False); z.set_shown(True)
    assert z.hide_link.isHidden()                               # kapalıysa göster/gizle döngüsü açmaz


def test_animation_waits_until_zone_is_shown(qtbot):
    z = QuestionZone(FAM); qtbot.addWidget(z); z.resize(900, 420)
    z.set_reading_ms(20)
    z.set_question(Q0, 1)
    assert not z.is_animating and z.text_label.text() == ""          # gizliyken bekler
    with qtbot.waitSignal(z.readingFinished, timeout=3000):
        z.show()
        assert z.is_animating
    assert z.text_label.text() == Q0.soru


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


def hzone(qtbot, anim_ms=0):
    h = HintZone(FAM); qtbot.addWidget(h); h.resize(800, 500); h.show()
    h.reveal_anim_ms = anim_ms
    h.set_hints("S1", Q0.hints)
    return h


def test_reveal_animation_ends_without_blur(qtbot):
    h = hzone(qtbot, anim_ms=120)
    h.set_revealed(0, True)
    assert h.cards[0].text_label.graphicsEffect() is not None        # animasyon sürüyor
    qtbot.waitUntil(lambda: h.cards[0].text_label.graphicsEffect() is None, timeout=2000)
    h.set_focus(1)                                                     # yeniden uygulama açık kartı bozmaz
    assert h.cards[0].text_label.graphicsEffect() is None and h.cards[0].revealed


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


def test_click_through_sends_card_presses_past_the_card(qtbot):
    """Çizim aracı aktifken (click-through) kart tıklaması açmaz; Tıkla aracında açar."""
    from PyQt6.QtTest import QTest
    h = hzone(qtbot)
    qtbot.waitExposed(h)
    win = h.windowHandle()
    fired = []
    h.revealToggled.connect(lambda i: fired.append(i))

    def click(card):                                   # her seferinde farklı kart: aynı noktaya ikinci tık çift tık sayılır
        c = card.mapTo(h, card.rect().center())
        QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, c)
        qtbot.wait(30)

    h.set_click_through(True)
    click(h.cards[0])
    assert fired == []
    h.set_click_through(False)
    click(h.cards[1])
    assert fired == [1]
    h.set_click_through(True)
    h.set_hints("S2", Q0.hints)                                       # yeni kartlar da geçirgen
    qtbot.wait(30)
    click(h.cards[2])
    assert fired == [1]


def test_hint_controls_heading_and_font_switches(qtbot):
    h = hzone(qtbot)
    h.set_controls_visible(False)
    assert h.counter_label.isHidden() and h.blur_button.isHidden() and h.next_button.isHidden()
    h.set_heading_visible(False)
    assert h.title_label.isHidden() and h.rule.isHidden()
    h.set_families(FontFamilies("Courier New", "Arial", False))
    assert h.cards[0].text_label.font().family() == "Courier New"


# --- Görev 7: düzenle modunda yazı boyutu kaydırıcısı ---------------------------------------------------

def test_hint_counter_label_font_updates_with_set_families(qtbot):
    """Kusur düzeltmesi: counter_label ("0 / 0") eskiden yalnız kurucuda font alıyordu, set_families'te
    hiç güncellenmiyordu (bkz. hint_zone.py görev 7 brief envanteri) -- artık aile DEĞİŞİNCE (dolayısıyla
    tahta yazı ölçeği değişince) o da güncellenmeli."""
    h = hzone(qtbot)
    assert h.counter_label.font().family() == "Arial"          # FAM'ın başlangıç ailesi
    h.set_families(FontFamilies("Courier New", "Arial", False, scale=1.5))
    assert h.counter_label.font().family() == "Courier New"
    assert h.counter_label.font().pixelSize() == round(10 * 1.5)


def test_new_option_label_created_after_set_families_uses_current_family(qtbot):
    """DÜZELTME DEĞİL, DRY KORUMASI (review'da doğrulandı): option_labels yeni soruya geçilince
    _build_options ile YENİDEN KURULUR -- ama bu zaten self.fam'ı (set_families'in en başta güncellediği)
    okur, o yüzden _option_font() konsolidasyonundan ÖNCE de doğru aileyi/ölçeği alıyordu; _build_options'ı
    eski satır içi `theme.font(self.fam, 24, 400)` çağrısına geri alınca bu test hâlâ geçiyor (empirik
    olarak doğrulandı). _option_font() yalnız 24/400'ün İKİ yerde tekrarlanmasını (dolayısıyla ileride
    biri değişip diğerinin unutulma riskini) ortadan kaldırıyor -- bu test o TEK kaynağın hâlâ doğru
    değeri ürettiğini kilitliyor, geçmişte var olmayan bir kusuru değil."""
    from matematigin_mantigi.core.models import SAMPLE_QUESTIONS
    z = qzone(qtbot)
    z.set_question(Q0, 1)
    z.set_families(FontFamilies("Courier New", "Arial", False, scale=1.5))
    assert z.option_labels[0].font().family() == "Courier New"
    assert z.option_labels[0].font().pixelSize() == round(24 * 1.5)

    z.set_question(SAMPLE_QUESTIONS[1], 2)                      # option_labels burada yeniden kurulur
    assert z.option_labels[0].font().family() == "Courier New"
    assert z.option_labels[0].font().pixelSize() == round(24 * 1.5)
