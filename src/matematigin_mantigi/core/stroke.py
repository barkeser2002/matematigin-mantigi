"""Saf çizim matematiği: basınç -> kalınlık, silgi ve imleç çapları."""
MOUSE_PRESSURE = 0.5
LASER_COLOR = "#ff3b30"


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def pressure_width(base: float, pressure: float) -> float:
    return base * (0.6 + _clamp(pressure, 0.0, 1.0) * 1.2)


def eraser_diameter(base: int) -> int:
    return int(_clamp(round(base * 8.5), 20, 80))


def pen_cursor_diameter(base: int) -> int:
    return int(_clamp(10 + base * 2, 12, 40))
