import pytest
from PyQt6.QtCore import Qt

from matematigin_mantigi import paths
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
    assert tb.minimumSizeHint().height() < 300                # ~950 px dayatmıyor


def test_full_tier_survives_a_1080p_fullscreen_window_and_thresholds_match_real_fit(qtbot):
    """Nihai inceleme, madde 8: eşikler (_FULL_MIN_H=1030, _COMPACT_MIN_H=800) brief'in YANLIŞ tahmininden
    alınmıştı -- gerçek eski asgari 936'ydı. Sonuç: görev çubuğu görünen 1920x1080 tam ekran pencerede
    ToolBar'a ~1000-1010 px kalıyor ve araç çubuğu FULL ~150 px boşlukla sığacakken COMPACT'a düşüyordu.
    Kullanıcının birincil hedefi tam olarak o pencere.

    Eşiklerin ölçüldüğü değerler (FULL içeriğinin sizeHint().height()'ı 853, ToolBar ~940'a kadar
    kaydırmasız sığıyor) toolbar.py'deki yorumda duruyor; BURADA iddia edilmiyor. Sebep bu dosyanın
    kendi tuzak notu (bkz. test_glyph_button_hides_label_ink_when_show_label_false): offscreen QPA'da
    kayıtlı font olup olmamasına göre glif ölçüleri -- dolayısıyla content.sizeHint() -- çalıştırma
    sırasına göre değişiyor. Kademe eşikleri ise saf sayı karşılaştırması, sıradan bağımsız."""
    tb = make(qtbot)
    for h in (1010, 1000, 960, 950):
        tb.resize(88, h)
        assert tb.tier == "full", h                           # 1080p tam ekran + görev çubuğu: FULL kalır
    for h in (949, 900, 800, 790):
        tb.resize(88, h)
        assert tb.tier == "compact", h
    for h in (789, 700, 400):
        tb.resize(88, h)
        assert tb.tier == "mini", h


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

    Review düzeltmesi (1. tur): önceki sürüm yalnız sabit y=24 satırını örnekliyordu -- paintEvent'in
    kendi etiket dikdörtgeni ifadesiyle o satır gerçek mürekkep bandının DIŞINDA bir ölü bölgeydi;
    show_label'ı tamamen yok sayan bir mutasyonla bile test yeşil kalıyordu.

    Review düzeltmesi (2. tur): bandı tara + boşluk (" ") glifi kullan yaklaşımı da yeterli değildi.
    Sebep beklediğimden farklıydı: bu PyQt6 kurulumunda offscreen QPA platformu SIFIR font ailesiyle
    başlıyor (`QFontDatabase.families() == []`) TA Kİ bir test gerçek bir font kaydedene dek -- fontsuz
    durumda Qt HERHANGİ bir glif için (boşluk dahil!) bir ".notdef" yer tutucu KUTUSU çiziyor. Böylece
    test, hangi TEST DOSYASI önce çalıştığına göre iki yönde de kırılabiliyordu: `test_theme.py`
    zaten çalışmışsa (gerçek font kayıtlı) boşluk gerçekten mürekkepsizdi ve test geçiyordu; yalnız
    `test_toolbar.py` çalıştırılınca (hiç font kayıtlı değil) boşluğun KENDİSİ 44 pikselli bir
    dikdörtgen iz bırakıyor ve DOĞRU koda karşı bile kırmızı çıkıyordu (ölçülen: satır 6-17,
    sütun 20-31 -- tam paket 331 passed, yalnız bu dosya 1 failed/15 passed, iki çalıştırmada da
    aynı 44 piksel).

    Kalıcı düzeltme: testin KENDİSİ `theme.load_fonts` ile gerçek fontu kaydediyor (uygulamanın
    zaten kullandığı yardımcı, idempotent -- iki kez çağrılması zararsız), böylece hangi sırada
    çalıştığından bağımsız hâle geliyor (bundled font hiç yoksa `test_load_bundled_fonts` ile aynı
    gerekçeyle atlanıyor). Ayrıca test artık İKİ YÖNÜ de aynı bantta doğruluyor: show_label=False
    bantta SIFIR mürekkep, show_label=True AYNI bantta SIFIRDAN FAZLA mürekkep -- yalnız "yok"u
    iddia eden bir test yanlış nedenle geçebilir (ör. ölçüm hep sıfır dönüyorsa); "var"ı da
    doğrulamak ölçüm aparatının gerçekten çalıştığını (doğru bant, doğru font, doğru piksel
    karşılaştırması) kanıtlıyor."""
    if not list(paths.FONTS_DIR.glob("*.ttf")):
        pytest.skip("bundled fonts not downloaded")
    theme.load_fonts(paths.FONTS_DIR)          # QFontDatabase'i doldurur -- testi sıradan bağımsız kılar

    btn = GlyphButton(" ", "Kalem")             # boşluk: kayıtlı gerçek fontta mürekkepsiz
    qtbot.addWidget(btn)
    btn.show()
    qtbot.waitExposed(btn)
    h = 28
    bg = theme.TOOLBAR_BTN

    label_y0 = h * (28 / 48)                    # GlyphButton.paintEvent ile BİREBİR aynı ifade
    label_h = h / 3
    y0, y1 = int(label_y0), int(label_y0 + label_h) + 1
    assert y1 > y0

    def band_ink_count(show_label: bool) -> int:
        btn.set_metrics(h, 16, show_label)
        img = btn.grab().toImage()
        assert img.height() == h
        return sum(1 for y in range(y0, y1) for x in range(8, 49)      # x: köşe yuvarlaması dışı
                   if img.pixelColor(x, y).name() != bg)

    assert band_ink_count(False) == 0           # etiket kapalı: bantta hiç mürekkep yok
    assert band_ink_count(True) > 0             # etiket açık: AYNI bantta mürekkep var -- ölçüm çalışıyor
