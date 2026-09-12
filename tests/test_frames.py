"""frames.py: FRAME_SPECS kaydı, Klasik boyacının taşınması ve HUD boyacısının çökmezliği için birim
testler. Bunlar WorkArea'ya ihtiyaç duymaz (saf boyacı fonksiyonlar, bkz. frames.py başlığı) -- bant
büyümesi, chrome eşitleme (brand/name_label gizleme) ve gerçek widget piksel çıktısı gibi entegrasyon
davranışları tests/test_work_area.py'ye eklendi (bkz. o dosyadaki '--- Görev 8' bölümü)."""
from dataclasses import replace

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QPainter, QPixmap

from matematigin_mantigi.core.models import FrameStyle
from matematigin_mantigi.ui import frames, theme
from matematigin_mantigi.ui.frames import FRAME_SPECS, FrameContext
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


def _ctx(rect: QRect, band: int, presenter: str = "Koray Varol", brand: str = "Matematiğin Mantığı") -> FrameContext:
    inner = rect.adjusted(band, band, -band, -band)
    return FrameContext(rect=rect, stage=rect, inner=inner, band=band, fam=FAM, presenter=presenter, brand=brand)


def _paint_on_pixmap(w: int, h: int, ctx: FrameContext, paint) -> "QPixmap":
    pm = QPixmap(w, h); pm.fill(Qt.GlobalColor.black)
    p = QPainter(pm)
    paint(p, ctx)
    p.end()
    return pm


def test_frame_specs_cover_every_style_with_turkish_labels():
    assert set(FRAME_SPECS) == set(FrameStyle)
    for style in FrameStyle:
        spec = FRAME_SPECS[style]
        assert spec.label.strip() != "" and spec.band > 0
        assert callable(spec.paint)


def test_classic_spec_matches_theme_band_and_draws_no_titles_itself():
    spec = FRAME_SPECS[FrameStyle.CLASSIC]
    assert spec.band == theme.FRAME_BAND                      # mevcut testler bu bant değerine dayanıyor
    assert spec.draws_brand is False and spec.draws_presenter is False
    assert spec.paint is frames.paint_classic
    assert "klasik" in spec.label.lower()


def test_hud_spec_is_thicker_than_classic_and_draws_its_own_titles():
    spec = FRAME_SPECS[FrameStyle.HUD]
    assert spec.band == theme.HUD_BAND > theme.FRAME_BAND
    assert spec.draws_brand is True and spec.draws_presenter is True
    assert spec.paint is frames.paint_hud
    assert "hud" in spec.label.lower()


def test_paint_classic_fills_inner_with_panel_color(qapp):
    """Ekstra bir emniyet: paint_classic doğrudan çağrıldığında da (WorkArea'sız) tahta beyaz doluyor.
    Taşımanın piksel-birebir kanıtı asıl tests/test_work_area.py'deki DOKUNULMAMIŞ çerçeve testleridir."""
    rect = QRect(0, 0, 400, 300)
    ctx = _ctx(rect, theme.FRAME_BAND)
    pm = _paint_on_pixmap(rect.width(), rect.height(), ctx, frames.paint_classic)
    img = pm.toImage()
    c = ctx.inner.center()
    assert img.pixelColor(c.x(), c.y()).name() == theme.PANEL


def test_paint_hud_leaves_board_blank_and_draws_the_rail_at_its_own_coordinate(qapp):
    """Review bulgusu (Görev 8 sonrası): önceki sürüm bütün bir satırı 'içinde HUD_INK/MID/BLUE'dan biri
    var mı' diye tarıyordu -- köşe köşebentleri de aynı satırlara denk geldiği için _hud_rail'in İKİ
    çağrısı da (üst + alt) tamamen devre dışı bırakılsa BİLE bu test geçiyordu (mutasyon testiyle
    doğrulandı, bkz. task-8-report.md "Görev 8 review düzeltmesi"). Düzeltme: probu SADECE rayın kendi
    step/notch formülünden (_hud_rail_geometry, boyacıyla PAYLAŞILAN tek kaynak) türeyen bir koordinata
    -- stage'in TAM ortasındaki x, rayın kademeli çizgisinin y'si -- bağlar; o noktada başka HİÇBİR
    yardımcı (_hud_label_band sağda, _hud_corner_bracket/_hud_corner_motif solda, _hud_right_edge sağda,
    _hud_left_ruler solda kalır) çizim yapmaz. Beklenen renk theme.HUD_MID'DEN DEĞİL sabit bir hex ile
    karşılaştırılır -- HUD_MID sabitinin kendisi mutasyona uğrasa (ör. beyaza boyansa) test kendi
    beklentisini onunla birlikte KAYDIRMASIN diye (bu da mutasyon testiyle doğrulandı)."""
    rect = QRect(0, 0, 1824, 1026)                     # test_work_area.make()'teki sahneyle aynı ölçek
    ctx = _ctx(rect, theme.HUD_BAND)
    pm = _paint_on_pixmap(rect.width(), rect.height(), ctx, frames.paint_hud)
    img = pm.toImage()
    c = ctx.inner.center()
    assert img.pixelColor(c.x(), c.y()).name() == theme.PANEL              # tahta ortası boş beyaz

    anchor = frames._hud_rail_anchor_y(rect, theme.HUD_BAND, top=True)
    _notch, y2, _by, _span = frames._hud_rail_geometry(rect, theme.HUD_BAND, anchor, +1)
    cx, cy = rect.center().x(), round(y2)                                  # ortadaki nokta+halkanın yeri
    assert img.pixelColor(cx, cy).name().lower() == "#1b3f7a"              # HUD_MID'in LİTERAL hex'i (bilerek)


def test_paint_hud_draws_blank_band_when_titles_are_empty(qapp):
    """WorkArea.paintEvent frame_titles kapalıyken FrameContext'e boş dize geçer (bkz. work_area.py) --
    paint_hud bunu çökmeden kabul etmeli, bandı yine çizmeli, yalnız içi boş kalmalı."""
    rect = QRect(0, 0, 1824, 1026)
    ctx = _ctx(rect, theme.HUD_BAND, presenter="", brand="")
    pm = _paint_on_pixmap(rect.width(), rect.height(), ctx, frames.paint_hud)
    c = ctx.inner.center()
    assert pm.toImage().pixelColor(c.x(), c.y()).name() == theme.PANEL


def test_paint_hud_survives_degenerate_and_tiny_rects(qapp):
    """paint_hud çökmemeli: bant sahneden büyükse (inner_rect negatif genişlik/yükseklik -- çok küçük
    pencerede stage_rect() tüm alana düşünce olur, bkz. work_area.py:MIN_STAGE_K), sahne sıfır boyutluysa
    ya da bant sıfırsa bile. Bu, frames.py düzeyinde DOĞRUDAN kanıt; tests/test_work_area.py'deki gerçek
    WorkArea + wa.resize(...) testi aynı gereksinimin entegrasyon karşılığıdır."""
    tiny = QRect(0, 0, 10, 10)                          # HUD_BAND(52) > 10 -> inner negatif
    ctx = _ctx(tiny, theme.HUD_BAND)
    pm = QPixmap(40, 40); pm.fill(Qt.GlobalColor.white)
    p = QPainter(pm)
    frames.paint_hud(p, ctx)                                            # çökmemeli: negatif inner

    zero = QRect(0, 0, 0, 0)
    frames.paint_hud(p, replace(ctx, rect=zero, stage=zero, inner=zero))  # çökmemeli: sıfır boyut

    frames.paint_hud(p, replace(ctx, band=0))                            # çökmemeli: bant sıfır
    p.end()
