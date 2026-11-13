from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tool(str, Enum):
    PEN = "pen"
    ERASER = "eraser"
    TEXT = "text"
    SHAPE = "shape"
    LASER = "laser"
    CLICK = "click"      # tıklama modu: kartlar, kamera ve düğmeler tıklanır; çizim yapılmaz


TOOL_META: dict[Tool, tuple[str, str]] = {
    Tool.PEN: ("Kalem", "✎"),
    Tool.ERASER: ("Silgi", "▭"),
    Tool.TEXT: ("Yazı", "T"),
    Tool.SHAPE: ("Şekil", "△"),
    Tool.LASER: ("Lazer", "●"),
    Tool.CLICK: ("Tıkla", "↖"),
}
DRAWING_TOOLS = (Tool.PEN, Tool.ERASER, Tool.TEXT, Tool.SHAPE, Tool.LASER)


class Shape(str, Enum):
    LINE = "line"
    RECT = "rect"
    ELLIPSE = "ellipse"
    TRIANGLE = "triangle"            # ikizkenar (tepe tabanın ortasında)
    ARROW = "arrow"
    SQUARE = "square"
    CIRCLE = "circle"
    EQUILATERAL = "equilateral"
    RIGHT_TRIANGLE = "right_triangle"
    RHOMBUS = "rhombus"
    PARALLELOGRAM = "parallelogram"
    TRAPEZOID = "trapezoid"
    PENTAGON = "pentagon"
    HEXAGON = "hexagon"
    STAR = "star"
    AXES = "axes"                    # koordinat ekseni (x-y okları)
    AXES_TICKS = "axes_ticks"        # koordinat ekseni + çentikler
    DOUBLE_ARROW = "double_arrow"    # çift yönlü ok
    NUMBER_LINE = "number_line"      # çentikli sayı doğrusu (10 eşit aralık)
    ANGLE = "angle"                  # iki ışın + yay


SHAPE_META: dict[Shape, tuple[str, str]] = {
    Shape.LINE: ("Çizgi", "╱"),
    Shape.ARROW: ("Ok", "→"),
    Shape.DOUBLE_ARROW: ("Çift ok", "↔"),
    Shape.NUMBER_LINE: ("Sayı doğrusu", "⊢"),
    Shape.ANGLE: ("Açı", "∠"),
    Shape.RECT: ("Dikdörtgen", "▭"),
    Shape.SQUARE: ("Kare", "□"),
    Shape.ELLIPSE: ("Elips", "⬭"),
    Shape.CIRCLE: ("Daire", "◯"),
    Shape.TRIANGLE: ("İkizkenar üçgen", "△"),
    Shape.EQUILATERAL: ("Eşkenar üçgen", "▵"),
    Shape.RIGHT_TRIANGLE: ("Dik üçgen", "◺"),
    Shape.RHOMBUS: ("Eşkenar dörtgen", "◇"),
    Shape.PARALLELOGRAM: ("Paralelkenar", "▱"),
    Shape.TRAPEZOID: ("Yamuk", "⏢"),
    Shape.PENTAGON: ("Düzgün beşgen", "⬠"),
    Shape.HEXAGON: ("Düzgün altıgen", "⬡"),
    Shape.STAR: ("Yıldız", "☆"),
    Shape.AXES: ("Koordinat ekseni", "┼"),
    Shape.AXES_TICKS: ("Eksen çentikli", "╋"),
}
# Menü sırası (5 sütun): çizgiler, dörtgen/daire, üçgenler, çokgenler, eksenler.
SHAPE_ORDER: tuple[Shape, ...] = (
    Shape.LINE, Shape.ARROW, Shape.DOUBLE_ARROW, Shape.NUMBER_LINE, Shape.ANGLE,
    Shape.RECT, Shape.SQUARE, Shape.ELLIPSE, Shape.CIRCLE, Shape.TRIANGLE,
    Shape.EQUILATERAL, Shape.RIGHT_TRIANGLE, Shape.RHOMBUS, Shape.PARALLELOGRAM, Shape.TRAPEZOID,
    Shape.PENTAGON, Shape.HEXAGON, Shape.STAR, Shape.AXES, Shape.AXES_TICKS,
)


def next_shape(s: Shape) -> Shape:
    return SHAPE_ORDER[(SHAPE_ORDER.index(s) + 1) % len(SHAPE_ORDER)]


class QuestionStatus(str, Enum):
    WAITING = "bekliyor"
    WORKING = "işleniyor"
    DONE = "tamamlandı"


class HintMaskMode(str, Enum):
    BLUR = "blur"
    REDACT = "redact"


class Nib(str, Enum):
    ROUND = "Yuvarlak"
    FELT = "Keçeli"
    CHALK = "Tebeşir"
    HIGHLIGHTER = "Fosforlu"


class LineStyle(str, Enum):
    SOLID = "Düz"
    DASHED = "Kesikli"
    DOTTED = "Noktalı"


class FrameStyle(str, Enum):
    """Tahtanın ekran çerçevesi stili -- Ayarlar > Tahta kartından seçilir (bkz. ui/frames.py:FRAME_SPECS)."""
    CLASSIC = "classic"
    HUD = "hud"


PALETTE: tuple[str, ...] = ("#1c1b19", "#c8322b", "#2456b8", "#1f8a4c")
WIDTHS: tuple[int, ...] = (1, 2, 4, 8, 12)     # 5 kalınlık kademesi (px, basınç 0.5'te)
OPTION_LETTERS = ("A", "B", "C", "D")


@dataclass(frozen=True)
class Question:
    id: str
    konu: str
    sinif: int | None
    soru: str
    hints: tuple[str, ...]
    cevap: str
    options: tuple[str, ...] = ()      # A) B) C) D) metinleri; boşsa açık uçlu soru
    image: str | None = None           # soru görseli (dosya yolu), yoksa None


@dataclass(frozen=True)
class PenSettings:
    pressure_curve: int = 50   # 0 yumuşak .. 100 sert, 50 = "Doğrusal"
    smoothing: int = 35        # yüzde
    min_width: int = 1
    max_width: int = 12
    nib: Nib = Nib.ROUND
    hold_to_straight: bool = True
    line_style: LineStyle = LineStyle.SOLID
    math_recognition: bool = True
    shape_correction: bool = True
    autosave: bool = True
    template_matching: bool = False
    reading_ms: int = 40       # soru yazma animasyonu, ms/harf; 0 = kapalı


SAMPLE_QUESTIONS: tuple[Question, ...] = (
    Question("S1", "Denklemler", 7, "3x + 5 = 20 ise x kaçtır?",
             ("Denklemin iki tarafından 5 çıkar: 3x = 15.",
              "3x = 15 ise x = 15 ÷ 3.",
              "Cevap: x = 5. Kontrol: 3·5 + 5 = 20 ✓"), "x = 5", ("3", "4", "5", "6")),
    Question("S2", "Geometri", 6, "Kenarları 6 cm ve 8 cm olan dikdörtgenin çevresi kaç cm?",
             ("Dikdörtgende karşılıklı kenarlar eşittir.",
              "Çevre = 2 × (uzun + kısa) = 2 × (8 + 6).",
              "Cevap: 28 cm."), "28 cm", ("14", "24", "28", "48")),
    Question("S3", "Kesirler", 6, "2/3 + 1/6 işleminin sonucu nedir?",
             ("Paydaları eşitle: 6 ortak payda.",
              "2/3 = 4/6 olur; 4/6 + 1/6.",
              "Cevap: 5/6."), "5/6", ("3/9", "1/2", "5/6", "1")),
)
