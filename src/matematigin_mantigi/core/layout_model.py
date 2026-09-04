"""OBS benzeri düzen modeli: tahta üstündeki bölgeler 12x10 ızgara biriminde konum/boyut taşır."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

GRID_COLS = 12
GRID_ROWS = 10
MIN_SPAN = 2
ZONE_KEYS = ("soru", "ipucu", "webcam")
PANEL_KEYS = ZONE_KEYS   # eski ad


@dataclass(frozen=True)
class PanelGeom:
    col: int
    row: int
    col_span: int
    row_span: int


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
            g = PanelGeom(int(item["col"]), int(item["row"]), int(item["col_span"]), int(item["row_span"]))
        except (KeyError, TypeError, ValueError):
            continue
        result[key] = clamp(g)
    return result


def load_layout(path: Path) -> Layout:
    try:
        return from_json(Path(path).read_text(encoding="utf-8"))
    except OSError:
        return dict(DEFAULT_LAYOUT)


def save_layout(path: Path, layout: Layout) -> None:
    Path(path).write_text(to_json(layout), encoding="utf-8")
