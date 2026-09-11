"""OBS benzeri düzen modeli: tahta üstündeki bölgeler 12x10 ızgara biriminde konum/boyut taşır."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

GRID_COLS = 12
GRID_ROWS = 10
MIN_SPAN = 2
MIN_FREE_W = 80   # serbest boyutlandırmada asgari genişlik (px); work_area.py'deki sürükleme kırpmasıyla aynı taban
MIN_FREE_H = 60   # serbest boyutlandırmada asgari yükseklik (px)
_MIN_POSITIVE_SPAN = 1e-6   # clamp_free'nin alansız modunda yalnız sıfır/negatif span'e karşı koruma; bir
                            # boyut tabanı DEĞİL (bkz. clamp_free docstring'i)
ZONE_KEYS = ("soru", "ipucu", "webcam")
PANEL_KEYS = ZONE_KEYS   # eski ad


@dataclass(frozen=True)
class PanelGeom:
    col: float
    row: float
    col_span: float
    row_span: float


Layout = dict[str, PanelGeom]

DEFAULT_LAYOUT: Layout = {
    "soru": PanelGeom(0, 0, 6, 4),      # sol üst
    "ipucu": PanelGeom(6, 0, 6, 4),     # sağ üst
    "webcam": PanelGeom(9, 7, 3, 3),    # sağ alt köşe
}


def clamp(g: PanelGeom) -> PanelGeom:
    cs = max(MIN_SPAN, min(GRID_COLS, g.col_span))
    rs = max(MIN_SPAN, min(GRID_ROWS, g.row_span))
    col = max(0, min(GRID_COLS - cs, g.col))
    row = max(0, min(GRID_ROWS - rs, g.row))
    return PanelGeom(col, row, cs, rs)


def clamp_free(g: PanelGeom, area_w: float | None = None, area_h: float | None = None,
                gap: float | None = None) -> PanelGeom:
    """`clamp`'in yuvarlamayan, serbest boyutlandırma için ikizi.

    area_w/area_h/gap'in HEPSİ verilirse (yalnız `free_rect`, sürüklemenin o anki GERÇEK alanıyla): asgari
    span MIN_SPAN=2 hücre (ızgaranın 1/6'sı) değil, MIN_FREE_W x MIN_FREE_H piksel tabanından, bu alana göre
    hücreye çevrilerek türetilir -- 80x60 px'lik bir bölge sürüklemenin kendisinde anlamlıdır, çünkü orada
    gerçek pencere ölçüsü bilinir.

    Herhangi biri (veya hepsi) None ise -- `from_json` ve `WorkArea.set_layout` gibi YÜKLEME yolunda, gerçek
    pencere ölçüsü bilinmez -- piksel tabanı UYGULANMAZ: yalnız ızgara sınırları (0..GRID_COLS, 0..GRID_ROWS)
    ve sıfır/negatif span'e karşı asgari bir koruma (_MIN_POSITIVE_SPAN, gerçek bir boyut tabanı değil)
    kalır. Kalıcılık kaydedileni birebir geri vermeli: kesirli bir düzen tasarım gereği çözünürlükten
    bağımsızdır, bu yüzden ayrıştırma anında (o anki pencerenin ölçüsüyle ya da rastgele bir referansla)
    piksel tabanını yeniden türetmek hem yanlış hem gereksizdir -- taban yalnız onu YARATAN tek yer olan
    sürüklemede, gerçek alan bilinirken uygulanır. (Önceki bir sürüm burada sabit bir 1920x1080 referansı
    kullanıyordu; bu, referanstan büyük ekranlarda serbestçe küçültülmüş bir bölgeyi yüklemede sessizce
    büyütüyordu -- bkz. review notları.)
    """
    if area_w is None or area_h is None or gap is None:
        cs = max(_MIN_POSITIVE_SPAN, min(GRID_COLS, g.col_span))
        rs = max(_MIN_POSITIVE_SPAN, min(GRID_ROWS, g.row_span))
    else:
        cw, ch = cell_size(area_w, area_h, gap)
        min_cs = (MIN_FREE_W + gap) / (cw + gap)
        min_rs = (MIN_FREE_H + gap) / (ch + gap)
        cs = max(min_cs, min(GRID_COLS, g.col_span))
        rs = max(min_rs, min(GRID_ROWS, g.row_span))
    col = max(0.0, min(GRID_COLS - cs, g.col))
    row = max(0.0, min(GRID_ROWS - rs, g.row))
    return PanelGeom(col, row, cs, rs)


def cell_size(area_w: int, area_h: int, gap: int) -> tuple[float, float]:
    cw = (area_w - gap * (GRID_COLS - 1)) / GRID_COLS
    ch = (area_h - gap * (GRID_ROWS - 1)) / GRID_ROWS
    return cw, ch


def pixel_rect(g: PanelGeom, area_w: int, area_h: int, gap: int) -> tuple[int, int, int, int]:
    cw, ch = cell_size(area_w, area_h, gap)
    x0 = round(g.col * (cw + gap))
    y0 = round(g.row * (ch + gap))
    x1 = round((g.col + g.col_span) * (cw + gap) - gap)
    y1 = round((g.row + g.row_span) * (ch + gap) - gap)
    return x0, y0, x1 - x0, y1 - y0


def snap_rect(x: int, y: int, w: int, h: int, area_w: int, area_h: int, gap: int) -> PanelGeom:
    cw, ch = cell_size(area_w, area_h, gap)
    col = round(x / (cw + gap))
    row = round(y / (ch + gap))
    cs = max(1, round((w + gap) / (cw + gap)))
    rs = max(1, round((h + gap) / (ch + gap)))
    return clamp(PanelGeom(col, row, cs, rs))


def free_rect(x: float, y: float, w: float, h: float, area_w: float, area_h: float, gap: float) -> PanelGeom:
    """`snap_rect`'in yuvarlamayan ikizi: bırakılan yerdeki kesirli hücre konum/boyutunu aynen taşır."""
    cw, ch = cell_size(area_w, area_h, gap)
    col = x / (cw + gap)
    row = y / (ch + gap)
    col_span = (w + gap) / (cw + gap)
    row_span = (h + gap) / (ch + gap)
    return clamp_free(PanelGeom(col, row, col_span, row_span), area_w, area_h, gap)


def to_json(layout: Layout) -> str:
    return json.dumps({k: asdict(v) for k, v in layout.items()}, indent=2, ensure_ascii=False)


def from_json(text: str) -> Layout:
    """Bilinmeyen anahtarlar (örn. eski 'cizim') yok sayılır; bozuk girdi varsayılana döner."""
    result: Layout = dict(DEFAULT_LAYOUT)
    try:
        raw = json.loads(text)
    except (TypeError, ValueError):
        return result
    if not isinstance(raw, dict):
        return result
    for key in ZONE_KEYS:
        item = raw.get(key)
        if not isinstance(item, dict):
            continue
        try:
            g = PanelGeom(float(item["col"]), float(item["row"]), float(item["col_span"]), float(item["row_span"]))
        except (KeyError, TypeError, ValueError):
            continue
        result[key] = clamp_free(g)
    return result


def load_layout(path: Path) -> Layout:
    try:
        return from_json(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return dict(DEFAULT_LAYOUT)


def save_layout(path: Path, layout: Layout) -> None:
    Path(path).write_text(to_json(layout), encoding="utf-8")
