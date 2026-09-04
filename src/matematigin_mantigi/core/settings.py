"""QSettings üzerinde tipli ayarlar."""
from __future__ import annotations

from dataclasses import fields

from PyQt6.QtCore import QSettings

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.core.models import HintMaskMode, Nib, PenSettings, Tool


class AppSettings:
    def __init__(self, backend: QSettings | None = None):
        self._q = backend or QSettings("MatematiginMantigi", "Ogretim")

    # --- helpers ---------------------------------------------------------------
    def _int(self, key: str, default: int) -> int:
        try:
            return int(self._q.value(key, default))
        except (TypeError, ValueError):
            return default

    def _float(self, key: str, default: float) -> float:
        try:
            return float(self._q.value(key, default))
        except (TypeError, ValueError):
            return default

    def _bool(self, key: str, default: bool) -> bool:
        v = self._q.value(key, default)
        if isinstance(v, bool):
            return v
        return str(v).lower() in ("1", "true", "yes")

    def _str(self, key: str, default: str) -> str:
        v = self._q.value(key, default)
        return default if v is None else str(v)

    def _enum(self, key: str, enum, default):
        try:
            return enum(self._str(key, default.value))
        except ValueError:
            return default

    # --- properties --------------------------------------------------------------
    @property
    def tool(self) -> Tool: return self._enum("tool", Tool, Tool.PEN)
    @tool.setter
    def tool(self, t: Tool) -> None: self._q.setValue("tool", t.value)

    @property
    def color(self) -> str: return self._str("color", "#1c1b19")
    @color.setter
    def color(self, hx: str) -> None: self._q.setValue("color", hx)

    @property
    def width(self) -> int: return self._int("width", 4)
    @width.setter
    def width(self, w: int) -> None: self._q.setValue("width", int(w))

    @property
    def hint_mask(self) -> HintMaskMode: return self._enum("hint_mask", HintMaskMode, HintMaskMode.BLUR)
    @hint_mask.setter
    def hint_mask(self, m: HintMaskMode) -> None: self._q.setValue("hint_mask", m.value)

    @property
    def camera_index(self) -> int: return self._int("camera/index", 0)
    @camera_index.setter
    def camera_index(self, i: int) -> None: self._q.setValue("camera/index", int(i))

    @property
    def chroma_enabled(self) -> bool: return self._bool("chroma/enabled", True)
    @chroma_enabled.setter
    def chroma_enabled(self, on: bool) -> None: self._q.setValue("chroma/enabled", bool(on))

    @property
    def chroma(self) -> ChromaParams:
        d = ChromaParams()
        return ChromaParams(tolerance=self._int("chroma/tolerance", d.tolerance),
                            feather_px=self._int("chroma/feather", d.feather_px),
                            spill=self._float("chroma/spill", d.spill))
    @chroma.setter
    def chroma(self, p: ChromaParams) -> None:
        self._q.setValue("chroma/tolerance", p.tolerance)
        self._q.setValue("chroma/feather", p.feather_px)
        self._q.setValue("chroma/spill", p.spill)

    def pen(self) -> PenSettings:
        d = PenSettings()
        return PenSettings(
            pressure_curve=self._int("pen/pressure_curve", d.pressure_curve),
            smoothing=self._int("pen/smoothing", d.smoothing),
            min_width=self._int("pen/min_width", d.min_width),
            max_width=self._int("pen/max_width", d.max_width),
            nib=self._enum("pen/nib", Nib, d.nib),
            math_recognition=self._bool("pen/math_recognition", d.math_recognition),
            shape_correction=self._bool("pen/shape_correction", d.shape_correction),
            autosave=self._bool("pen/autosave", d.autosave),
            template_matching=self._bool("pen/template_matching", d.template_matching),
        )

    def set_pen(self, p: PenSettings) -> None:
        for f in fields(PenSettings):
            v = getattr(p, f.name)
            self._q.setValue(f"pen/{f.name}", v.value if isinstance(v, Nib) else v)

    def sync(self) -> None:
        self._q.sync()
