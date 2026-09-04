import pytest
from PyQt6.QtGui import QFont

from matematigin_mantigi import paths
from matematigin_mantigi.ui import theme


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
    assert theme.PAGE in css and "Arial" in css
