import pytest
from PyQt6.QtGui import QFont

from matematigin_mantigi import paths
from matematigin_mantigi.ui import theme


def test_tr_upper_handles_dotted_i():
    assert theme.tr_upper("Silgi") == "SİLGİ"
    assert theme.tr_upper("El çizimi") == "EL ÇİZİMİ"
    assert theme.tr_upper("Akıllı ipuçları") == "AKILLI İPUÇLARI"
    assert theme.tr_upper("Soru") == "SORU"


def test_palette_constants():
    assert theme.INK == "#1c1b19" and theme.PAGE == "#e9e7e2" and theme.ACCENT == "#bd4334"
    assert theme.TOOLBAR_WIDTH == 88 and theme.GRID_GAP == 14 and theme.DOT_SPACING == 28


def test_load_fonts_falls_back_without_ttfs(tmp_path, qapp):
    fam = theme.load_fonts(tmp_path)
    assert fam.loaded is False
    assert fam.sans and fam.hand


def test_load_bundled_fonts(qapp):
    if not list(paths.FONTS_DIR.glob("*.ttf")):
        pytest.skip("bundled fonts not downloaded")
    fam = theme.load_fonts(paths.FONTS_DIR)
    assert fam.loaded is True
    assert fam.sans == "Work Sans" and fam.hand == "Caveat"


def test_font_helpers(qapp):
    fam = theme.FontFamilies("Arial", "Arial", False)
    f = theme.font(fam, 14, 600, spacing_pct=114)
    assert isinstance(f, QFont) and f.pixelSize() == 14 and f.weight() == QFont.Weight.DemiBold
    assert f.letterSpacingType() == QFont.SpacingType.PercentageSpacing
    h = theme.hand_font(fam, 38, 700)
    assert h.pixelSize() == 38 and h.weight() == QFont.Weight.Bold


def test_stylesheet_mentions_page_background(qapp):
    css = theme.build_stylesheet(theme.FontFamilies("Arial", "Arial", False))
    assert theme.PAGE in css
    assert "font-family" not in css      # stil sayfası fontu setFont ile verilen Caveat'i ezer; app.setFont kullanılır


def test_stylesheet_covers_list_and_input_widgets(qapp):
    """Koyu mod karşıtı palet: liste/açılır menü/çok satırlı kutular arka plan+yazı rengi almalı,
    yoksa sistem koyu modda Qt'nin koyu QPalette.Base'i koyu yazının üstüne biner (siyah-üstü-siyah)."""
    css = theme.build_stylesheet(theme.FontFamilies("Arial", "Arial", False))
    assert "QAbstractItemView" in css
    assert "QPlainTextEdit" in css
    assert "QComboBox" in css
    assert "font-family" not in css


# --- Görev 7: düzenle modunda yazı boyutu kaydırıcısı ---------------------------------------------------

def test_font_families_positional_three_args_default_scale():
    """scale alanı FontFamilies'e EN SONA eklendi -- testlerdeki (ve app.py'deki) eski üç pozisyonel
    argümanlı FontFamilies("Arial", "Arial", False) çağrıları hâlâ çalışmalı, scale varsayılanı 1.0
    olmalı (bkz. görev 7 brief'i, 'Sona koymak şart')."""
    fam = theme.FontFamilies("Arial", "Arial", False)
    assert fam.scale == 1.0
    assert (fam.sans, fam.hand, fam.loaded) == ("Arial", "Arial", False)


def test_font_helpers_apply_scale(qapp):
    """theme.font / theme.hand_font artık piksel boyutunu fam.scale ile çarpıyor: scale=1.0 bugünkü
    değerle birebir aynı kalmalı (regresyon), scale=2.0 boyutu iki katına çıkarmalı."""
    fam = theme.FontFamilies("Arial", "Arial", False)
    assert theme.font(fam, 14, 600).pixelSize() == 14
    assert theme.hand_font(fam, 38, 700).pixelSize() == 38

    fam2 = theme.FontFamilies("Arial", "Arial", False, scale=2.0)
    assert theme.font(fam2, 14, 600).pixelSize() == 28
    assert theme.hand_font(fam2, 38, 700).pixelSize() == 76
