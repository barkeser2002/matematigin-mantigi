from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase

# Renkler (mockup)
INK = "#1c1b19"
PAGE = "#e9e7e2"
PANEL = "#ffffff"
PANEL_SOFT = "#f7f6f3"
MUTED = "#7a776f"
MUTED_DARK = "#8e8b84"
LINE = "#e3e0d9"
DOT = "#d9d6cf"
CHIP = "#efede8"
ROW_FOCUS = "#f3ede6"
HINT_EMPTY = "#b3afa6"
ACCENT = "#bd4334"        # oklch(55% 0.16 30)
ACCENT_HOVER = "#963426"  # oklch(45% 0.16 30)
REC_DOT = "#de3e2d"       # oklch(60% 0.2 30)
OK_DOT = "#008a39"        # oklch(55% 0.16 150)
TOOLBAR_BTN = "#2c2a27"
TOOLBAR_LINE = "#3a3834"
TOOLBAR_MUTED = "#c9c6bf"
TOOLBAR_DIM = "#5a5751"
CAM_RAW = "#00ff3c"
LASER = "#ff3b30"

# Beyaz tahta (PDF stili)
QUESTION_NUMBER = "#c8322b"
HINT_HEADING = "#a3551b"
HINT_CARD_BG = "#fff4d6"
HINT_CARD_BORDER = "#e8a23a"
HINT_CARD_BORDER_FOCUS = "#c77d12"
BULB = "#f6c343"

# Ölçüler
GRID_GAP = 14
PANEL_RADIUS = 4
PANEL_BORDER = 2
FRAME_INSET = 10
TOOLBAR_WIDTH = 88
DOT_SPACING = 28
WORK_PADDING = (0, 0, 0, 0)        # tahta kenardan kenara; top, right, bottom, left


def tr_upper(text: str) -> str:
    """Türkçe büyük harf: i -> İ, ı -> I (str.upper 'Silgi' için 'SILGI' üretir)."""
    return text.replace("i", "İ").replace("ı", "I").upper()


@dataclass(frozen=True)
class FontFamilies:
    sans: str
    hand: str
    loaded: bool


def load_fonts(fonts_dir: Path) -> FontFamilies:
    found: dict[str, str] = {}
    for ttf in sorted(Path(fonts_dir).glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        if fid == -1:
            continue
        for fam in QFontDatabase.applicationFontFamilies(fid):
            if fam.lower().startswith("work sans"):
                found.setdefault("Work Sans", fam)
            elif fam.lower().startswith("caveat"):
                found.setdefault("Caveat", fam)
    system = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    sans = found.get("Work Sans", system)
    hand = found.get("Caveat", sans)
    return FontFamilies(sans=sans, hand=hand, loaded=("Work Sans" in found and "Caveat" in found))


def load_font_file(path: str | Path) -> str | None:
    """Tek bir .ttf/.otf dosyasını yükler, aile adını döndürür; yüklenemezse None."""
    p = Path(path)
    if not p.is_file():
        return None
    fid = QFontDatabase.addApplicationFont(str(p))
    if fid == -1:
        return None
    fams = QFontDatabase.applicationFontFamilies(fid)
    return fams[0] if fams else None


def font(fam: FontFamilies, px: int, weight: int = 400, spacing_pct: int | None = None) -> QFont:
    f = QFont(fam.sans)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(weight))
    if spacing_pct is not None:
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, spacing_pct)
    return f


def hand_font(fam: FontFamilies, px: int, weight: int = 500) -> QFont:
    f = QFont(fam.hand)
    f.setPixelSize(px)
    f.setWeight(QFont.Weight(weight))
    return f


def build_stylesheet(fam: FontFamilies) -> str:
    """Uygulama stil sayfası. Yazı ailesi burada DEĞİL, QApplication.setFont ile verilir:
    stil sayfasındaki font-family, setFont ile verilen Caveat gibi özel fontları ezer."""
    return f"""
    QMainWindow, QDialog {{ background: {PAGE}; }}
    QWidget {{ color: {INK}; }}
    QToolTip {{ background: {INK}; color: {PANEL_SOFT}; border: none; padding: 4px 8px; }}
    QPushButton#pill {{ background: {CHIP}; border: 1px solid {LINE}; border-radius: 12px;
                        padding: 3px 10px; font-size: 11px; font-weight: 600; }}
    QPushButton#pill:checked {{ background: {INK}; color: {PANEL_SOFT}; border-color: {INK}; }}
    QPushButton#accent {{ background: {ACCENT}; color: white; border: none; border-radius: 6px;
                          padding: 8px 14px; font-weight: 600; }}
    QPushButton#accent:hover {{ background: {ACCENT_HOVER}; }}
    QPushButton#link {{ background: transparent; border: none; color: {MUTED}; text-decoration: underline; }}
    QSlider::groove:horizontal {{ height: 4px; background: {LINE}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ width: 14px; margin: -6px 0; background: {INK}; border-radius: 7px; }}
    """
