from PyQt6.QtCore import Qt

from matematigin_mantigi.core.models import PALETTE, Tool
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.widgets import GlyphButton, RecordButton, SwatchButton

FAM = FontFamilies("Arial", "Arial", False)


def make(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    return tb


def test_toolbar_is_88_wide_and_pen_selected(qtbot):
    tb = make(qtbot)
    assert tb.width() == 88
    assert tb.tool_buttons[Tool.PEN].isChecked()
    assert sum(b.isChecked() for b in tb.tool_buttons.values()) == 1


def test_clicking_eraser_emits_and_is_exclusive(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.toolSelected, timeout=1000) as sig:
        qtbot.mouseClick(tb.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert sig.args == [Tool.ERASER]
    assert tb.tool_buttons[Tool.ERASER].isChecked() and not tb.tool_buttons[Tool.PEN].isChecked()


def test_swatch_and_width_signals(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.colorSelected) as sig:
        qtbot.mouseClick(tb.swatches[PALETTE[1]], Qt.MouseButton.LeftButton)
    assert sig.args == ["#c8322b"]
    with qtbot.waitSignal(tb.widthSelected) as sig:
        qtbot.mouseClick(tb.width_buttons[8], Qt.MouseButton.LeftButton)
    assert sig.args == [8]


def test_record_button_toggles(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.recordToggled) as sig:
        qtbot.mouseClick(tb.record_button, Qt.MouseButton.LeftButton)
    assert sig.args == [True]
    tb.set_recording(True)
    assert tb.record_label.text() == "DURDUR"
    tb.set_recording(False)
    assert tb.record_label.text() == "KAYIT"


def test_silent_setters_do_not_emit(qtbot):
    tb = make(qtbot)
    fired = []
    tb.toolSelected.connect(lambda t: fired.append(t))
    tb.set_tool(Tool.LASER)
    assert tb.tool_buttons[Tool.LASER].isChecked() and fired == []


def test_layout_edit_button(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.layoutEditToggled) as sig:
        qtbot.mouseClick(tb.layout_button, Qt.MouseButton.LeftButton)
    assert sig.args == [True]


def test_shape_glyph_and_reclick_emits(qtbot):
    tb = make(qtbot)
    fired = []
    tb.toolSelected.connect(lambda t: fired.append(t))
    qtbot.mouseClick(tb.tool_buttons[Tool.SHAPE], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(tb.tool_buttons[Tool.SHAPE], Qt.MouseButton.LeftButton)
    assert fired == [Tool.SHAPE, Tool.SHAPE]                   # seçiliyken de yayar (şekil döngüsü)
    tb.set_shape_glyph("○")
    assert tb.tool_buttons[Tool.SHAPE].glyph == "○"


def test_settings_button(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.settingsRequested):
        qtbot.mouseClick(tb.settings_button, Qt.MouseButton.LeftButton)


def test_prev_and_next_buttons(qtbot):
    tb = make(qtbot)
    assert tb.prev_button.text() == "← Önceki soru" and tb.next_button.text() == "Sıradaki soru →"
    with qtbot.waitSignal(tb.prevRequested):
        qtbot.mouseClick(tb.prev_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(tb.nextRequested):
        qtbot.mouseClick(tb.next_button, Qt.MouseButton.LeftButton)


# --- Görev 9: pencere kısaldıkça üç kademede küçülen araç çubuğu -----------------

def _row_widgets(row):
    """Bir DotButton satırının addStretch spacer'ları hariç gerçek widget'ları."""
    return [row.itemAt(i).widget() for i in range(row.count()) if row.itemAt(i).widget() is not None]


def test_three_height_tiers_scale_glyph_swatch_and_dot_buttons(qtbot):
    tb = make(qtbot)

    tb.resize(88, 1100)
    assert tb.tier == "full"
    assert tb.tool_buttons[Tool.PEN].height() == 48
    assert tb.swatches[PALETTE[0]].width() == 28
    assert tb.width_buttons[4].SIZE == 22
    assert tb.record_button.width() == 56
    assert [len(_row_widgets(r)) for r in tb.dot_rows] == [3, 2]

    tb.resize(88, 900)
    assert tb.tier == "compact"
    assert tb.tool_buttons[Tool.PEN].height() == 38
    assert tb.swatches[PALETTE[0]].width() == 24
    assert tb.width_buttons[4].SIZE == 18
    assert tb.record_button.width() == 44
    assert [len(_row_widgets(r)) for r in tb.dot_rows] == [3, 2]

    tb.resize(88, 700)
    assert tb.tier == "mini"
    assert tb.tool_buttons[Tool.PEN].height() == 28
    assert len(tb.dot_rows) == 1                              # 5 DotButton tek satırda
    assert len(_row_widgets(tb.dot_rows[0])) == 5


def test_mini_tier_hides_labels_and_captions_but_keeps_logical_identity(qtbot):
    tb = make(qtbot)
    original_labels = {t: b.label for t, b in tb.tool_buttons.items()}
    original_glyphs = {t: b.glyph for t, b in tb.tool_buttons.items()}

    tb.resize(88, 700)
    assert tb.tier == "mini"
    for t, b in tb.tool_buttons.items():
        assert b.show_label is False
        assert b.label == original_labels[t]                  # mantıksal kimlik değişmedi
        assert b.glyph == original_glyphs[t]
    assert all(not cap.isVisible() for cap in tb.section_captions)
    assert all(not sep.isVisible() for sep in tb.separators)
    assert tb.progress_label.isVisible()                      # başlık değil, dinamik metin -- gizlenmez
    assert tb.record_label.isVisible()

    tb.resize(88, 1100)
    assert tb.tier == "full"
    assert all(b.show_label for b in tb.tool_buttons.values())
    assert all(cap.isVisible() for cap in tb.section_captions)
    assert all(sep.isVisible() for sep in tb.separators)


def test_short_height_does_not_crash_and_keeps_minimum_small(qtbot):
    tb = make(qtbot)
    tb.resize(88, 400)                                        # eski davranışta hiç mümkün değildi
    assert tb.tier == "mini"
    assert tb.minimumSizeHint().height() < 300                # ~1030 px dayatmıyor


def test_record_button_always_visible_and_outside_scroll_area(qtbot):
    tb = make(qtbot)
    for h in (1100, 900, 700, 400):
        tb.resize(88, h)
        assert tb.record_button.isVisible()
        assert tb.record_label.isVisible()
        assert tb.record_button.parent() is tb                # dış layout'ta, kaydırmanın dışında
    assert tb.tool_buttons[Tool.PEN].parent() is not tb        # içerik kaydırma alanında (content/viewport)


def test_record_button_paint_adapts_to_smaller_diameter(qtbot):
    """Kilit nokta (bkz. brief): setFixedSize tek başına yeterli değil. RecordButton eskiden
    (28,28) merkez + 26/11 mutlak yarıçapları kodluyordu. 24px'e küçültünce eski merkeze en
    yakın köşe (sağ-alt) artık dairenin DIŞINDA kalmalı; eski mutlak koordinatlar hâlâ
    kullanılıyor olsaydı o köşe dolu kalırdı."""
    btn = RecordButton()
    qtbot.addWidget(btn)
    btn.show()
    qtbot.waitExposed(btn)
    btn.set_diameter(24)
    img = btn.grab().toImage()
    assert img.width() == 24 and img.height() == 24
    far_corner = img.pixelColor(23, 23).name()                # eski (28,28) merkeze en yakın köşe
    assert far_corner not in (theme.TOOLBAR_BTN, theme.ACCENT)
    center = img.pixelColor(12, 12).name()
    assert center in (theme.TOOLBAR_BTN, theme.ACCENT)        # hâlâ merkeze göre bir şey çiziyor


def test_swatch_button_paint_adapts_to_smaller_diameter(qtbot):
    """Aynı kilit nokta SwatchButton için: eski (14,14)/11 mutlak değerlerle 16px'e küçültülünce
    eski merkeze en yakın köşe (sağ-alt) artık dairenin dışında kalmalı."""
    btn = SwatchButton(PALETTE[1])
    qtbot.addWidget(btn)
    btn.show()
    qtbot.waitExposed(btn)
    btn.set_diameter(16)
    img = btn.grab().toImage()
    assert img.width() == 16 and img.height() == 16
    far_corner = img.pixelColor(15, 15).name()                # eski (14,14) merkeze en yakın köşe
    assert far_corner != PALETTE[1]
    center = img.pixelColor(8, 8).name()
    assert center == PALETTE[1]


def test_glyph_button_hides_label_ink_when_show_label_false(qtbot):
    """MINI kademede etiket tamamen çizilmemeli: yalnız gizli değil, hiç boyanmamalı.

    Review düzeltmesi (1. tur): önceki sürüm yalnız sabit y=24 satırını örnekliyordu. paintEvent'in
    kendi etiket dikdörtgeni ifadesiyle (QRectF(0, h*(28/48), w, h/3)) o satır h=28'de gerçek
    mürekkep bandının DIŞINDA bir ölü bölgeydi; show_label'ı tamamen yok sayan bir mutasyonla bile
    test yeşil kalıyordu (mutasyon testiyle doğrulandı, bkz. task-9-report.md "Görev 9 review
    düzeltmesi").

    Review düzeltmesi (2. tur, ilk düzeltmenin kendi hatası): "bandı tara, üstten birkaç piksel
    sızıntı payı bırak" yaklaşımı da yeterli değildi. show_label=False dalı glifi TÜM kutuda
    ortalıyor, bu yüzden glifin kendi (meşru) mürekkebi o banda TAŞAR -- ama taşma miktarı AKTİF
    FONTA bağlı: `tests/test_toolbar.py` tek başına çalışınca bir fallback fontla ölçülen pay
    (2px) yetiyordu, ama `test_theme.py::test_load_bundled_fonts` gerçek "Work Sans"/"Caveat"
    fontlarını `QApplication`'a (süreç ömrü boyunca kalıcı) kaydettikten SONRA tam pakette
    çalışınca farklı bir font kullanılıyor, taşma farklı satırlara kayıyor ve DOĞRU uygulamaya
    karşı bile kırmızı çıkıyordu -- izole çalıştırmada yeşil, tam pakette kırmızı, klasik bir
    font/test-sırası bağımlılığı (bkz. commit mesajı).

    Kalıcı düzeltme: testi FONTTAN TAMAMEN BAĞIMSIZ kıl. Glif olarak mürekkep bırakmayan bir
    boşluk (" ") kullanılıyor -- hangi font aktif olursa olsun boşluğun görünür mürekkedi yok, bu
    yüzden show_label=False'ta glif dalı da hiçbir iz bırakmıyor. Böylece köşe yuvarlamasının
    (radius=6, x<6/x>50'de) karışmayacağı x aralığında TÜM yükseklik taranabilir: mutasyonla
    etiket zorla çizilirse "KALEM" mürekkedi -- hangi font aktifse aktif olsun -- mutlaka
    yakalanır, ama boşluk glifinin kendisi asla yanlış pozitif üretmez."""
    btn = GlyphButton(" ", "Kalem")
    qtbot.addWidget(btn)
    btn.show()
    qtbot.waitExposed(btn)
    h = 28
    btn.set_metrics(h, 16, False)
    img = btn.grab().toImage()
    assert img.height() == h

    bg = theme.TOOLBAR_BTN
    offenders = [(x, y) for y in range(h) for x in range(8, 49)         # x: köşe yuvarlaması dışı
                 if img.pixelColor(x, y).name() != bg]
    assert offenders == []                    # ne boşluk glifinden ne etiketten hiç mürekkep yok
