"""QSettings üzerinde tipli ayarlar."""
from __future__ import annotations

from dataclasses import dataclass, fields
import json
import re

from PyQt6.QtCore import QSettings

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.core.models import FrameStyle, HintMaskMode, LineStyle, Nib, PenSettings, Tool
from matematigin_mantigi.core.stroke import eraser_diameter

ERASER_MIN, ERASER_MAX = 10, 120
ERASER_SIZES = (20, 34, 50, 80, 120)

# Tahtadaki gizlenebilir yazısal öğeler: (anahtar, etiket)
VISIBILITY_KEYS: tuple[tuple[str, str], ...] = (
    ("hint_controls", "İpucu kontrolleri (1/3 ◀ ▶ Blur Redakte)"),
    ("hint_heading", "\"AKILLI İPUÇLARI\" başlığı"),
    ("status", "Durum satırı (Araç · Kalınlık · Basınç)"),
    ("cam_label", "Kamera etiketi (yeşil perde: …)"),
    ("brand", "Marka plakası (Matematiğin Mantığı)"),
    ("hide_link", "Sorudaki \"gizle\" bağlantısı"),
    ("question_number", "Soru numarası"),
    ("frame", "Ekran çerçevesi"),
    ("frame_titles", "Çerçeve sunucu/marka bantları"),
    ("presenter", "Sunucu adı (webcam üstünde)"),
    ("logo", "Logo (sol üst)"),
    ("badge", "Tahtadaki kayıt rozeti (KAYIT · 00:00; kayda girer)"),
    ("question_zone", "Soru paneli"),
    ("hint_zone", "Akıllı ipuçları paneli"),
    ("webcam", "Webcam paneli"),
)
VISIBILITY_DEFAULTS = {"badge": False}


@dataclass(frozen=True)
class SessionState:
    """Kapanışta hatırlanan oturum: uygulama yeniden açılınca kaldığı yerden devam eder. Her alan ayrı ayrı
    doğrulanır; bozuk/eksik alan varsayılana düşer, uygulamayı çökertmez."""
    questions_file: str = ""            # varsayılandan farklı soru dosyası (örn. --sorular); "" = varsayılan dosya
    question_id: str = ""
    question_index: int = 0
    fullscreen: bool = False
    geometry: tuple[int, int, int, int] | None = None      # tam ekran değilken pencere (x, y, genişlik, yükseklik)
    board_image: str = ""               # o sorunun son tahta PNG'si (oturum klasöründe)
    board_question_id: str = ""         # board_image hangi soruya ait (başka soruya yüklenmez)

    @classmethod
    def from_json(cls, text: object) -> "SessionState":
        try:
            raw = json.loads(text) if isinstance(text, (str, bytes)) else {}
        except ValueError:
            raw = {}
        if not isinstance(raw, dict):
            return cls()

        def text_of(key: str) -> str:
            v = raw.get(key)
            return v if isinstance(v, str) else ""

        index = raw.get("question_index")
        geometry = raw.get("geometry")
        if not (isinstance(geometry, list) and len(geometry) == 4
                and all(isinstance(v, int) and not isinstance(v, bool) for v in geometry)
                and geometry[2] >= 200 and geometry[3] >= 150):
            geometry = None
        return cls(questions_file=text_of("questions_file"), question_id=text_of("question_id"),
                   question_index=index if isinstance(index, int) and not isinstance(index, bool) and index >= 0 else 0,
                   fullscreen=raw.get("fullscreen") is True,
                   geometry=tuple(geometry) if geometry else None,
                   board_image=text_of("board_image"), board_question_id=text_of("board_question_id"))

    def to_json(self) -> str:
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        data["geometry"] = list(self.geometry) if self.geometry else None
        return json.dumps(data, ensure_ascii=False)


class AppSettings:
    def __init__(self, backend: QSettings | None = None):
        self._q = backend or QSettings("MatematiginMantigi", "Ogretim")
        # Eski kalınlık ölçeğini yalnız ilk açılışta taşı; sonra kalemden bağımsız.
        if not self._q.contains("eraser/size"):
            self.eraser_size = eraser_diameter(self.width)

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

    def _screen_key(self, key):
        try:
            value = json.loads(self._str(key, "null"))
            if (isinstance(value, list) and len(value) == 4
                    and all(isinstance(v, str) for v in value) and value[0]):
                return tuple(value)
        except (ValueError, TypeError):
            pass
        return None

    @property
    def board_screen_key(self): return self._screen_key("screens/board")
    @board_screen_key.setter
    def board_screen_key(self, value): self._q.setValue("screens/board", json.dumps(value))

    @property
    def preview_screen_key(self): return self._screen_key("screens/preview")
    @preview_screen_key.setter
    def preview_screen_key(self, value): self._q.setValue("screens/preview", json.dumps(value))

    @property
    def has_session_state(self) -> bool:
        """İlk açılışı, pencere modunda kaydedilmiş bir oturumdan ayırır."""
        return self._q.contains("session/state")

    @property
    def session_state(self) -> SessionState:
        return SessionState.from_json(self._q.value("session/state", ""))
    @session_state.setter
    def session_state(self, state: SessionState) -> None: self._q.setValue("session/state", state.to_json())

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
    def custom_colors(self) -> list[str]:
        try:
            raw = json.loads(self._str("pen/custom_colors", "[]"))
        except ValueError:
            return []
        if not isinstance(raw, list):
            return []
        colors = []
        for value in raw:
            if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                value = value.lower()
                if value not in colors:
                    colors.append(value)
        return colors[:4]

    def remember_custom_color(self, hx: str) -> None:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", hx):
            return
        hx = hx.lower()
        colors = [hx] + [c for c in self.custom_colors if c != hx]
        self._q.setValue("pen/custom_colors", json.dumps(colors[:4]))

    @property
    def width(self) -> int: return self._int("width", 4)
    @width.setter
    def width(self, w: int) -> None: self._q.setValue("width", int(w))

    @property
    def eraser_size(self) -> int:
        return max(ERASER_MIN, min(ERASER_MAX, self._int("eraser/size", eraser_diameter(self.width))))
    @eraser_size.setter
    def eraser_size(self, size: int) -> None:
        self._q.setValue("eraser/size", max(ERASER_MIN, min(ERASER_MAX, int(size))))

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
    def auto_key(self) -> bool: return self._bool("chroma/auto_key", True)
    @auto_key.setter
    def auto_key(self, on: bool) -> None: self._q.setValue("chroma/auto_key", bool(on))

    @property
    def font_file(self) -> str: return self._str("ui/font_file", "")
    @font_file.setter
    def font_file(self, path: str) -> None: self._q.setValue("ui/font_file", path or "")

    @property
    def font_scale(self) -> float: return max(0.7, min(1.6, self._float("ui/font_scale", 1.0)))
    @font_scale.setter
    def font_scale(self, v: float) -> None: self._q.setValue("ui/font_scale", float(v))

    @property
    def logo_file(self) -> str: return self._str("ui/logo_file", "")
    @logo_file.setter
    def logo_file(self, path: str) -> None: self._q.setValue("ui/logo_file", path or "")

    @property
    def presenter_name(self) -> str: return self._str("ui/presenter_name", "Koray Varol")
    @presenter_name.setter
    def presenter_name(self, text: str) -> None: self._q.setValue("ui/presenter_name", text)

    def visible(self, key: str) -> bool:
        """Tahtadaki yazısal öğe görünürlüğü; anahtarlar VISIBILITY_KEYS içinde."""
        return self._bool(f"ui/show_{key}", VISIBILITY_DEFAULTS.get(key, True))

    @property
    def logo_size(self) -> int: return max(24, min(200, self._int("ui/logo_size", 48)))
    @logo_size.setter
    def logo_size(self, px: int) -> None: self._q.setValue("ui/logo_size", int(px))

    @property
    def aspect_lock(self) -> bool: return self._bool("ui/aspect_lock", True)
    @aspect_lock.setter
    def aspect_lock(self, on: bool) -> None: self._q.setValue("ui/aspect_lock", bool(on))

    @property
    def frame_style(self) -> FrameStyle: return self._enum("frame_style", FrameStyle, FrameStyle.CLASSIC)
    @frame_style.setter
    def frame_style(self, s: FrameStyle) -> None: self._q.setValue("frame_style", s.value)

    @property
    def record_fps(self) -> int: return 30 if self._int("record/fps", 60) == 30 else 60
    @record_fps.setter
    def record_fps(self, fps: int) -> None: self._q.setValue("record/fps", int(fps))

    @property
    def record_height(self) -> int: return self._int("record/height", 1440)      # 0 = doğal
    @record_height.setter
    def record_height(self, h: int) -> None: self._q.setValue("record/height", int(h))

    @property
    def audio_device(self) -> str: return self._str("record/audio_device", "")
    @audio_device.setter
    def audio_device(self, name: str) -> None: self._q.setValue("record/audio_device", name or "")

    @property
    def record_folder(self) -> str: return self._str("record/folder", "")
    @record_folder.setter
    def record_folder(self, path: str) -> None: self._q.setValue("record/folder", path)

    def set_visible(self, key: str, on: bool) -> None:
        self._q.setValue(f"ui/show_{key}", bool(on))

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

    MAX_READING_MS = 150      # ms/harf üst sınırı; daha büyük kayıtlar eski ms/kelime ölçeğinden kalmadır

    def pen(self) -> PenSettings:
        d = PenSettings()
        reading = self._int("pen/reading_ms", d.reading_ms)
        if reading > self.MAX_READING_MS:
            reading = d.reading_ms                      # eski ölçek: varsayılana dön
        return PenSettings(
            pressure_curve=self._int("pen/pressure_curve", d.pressure_curve),
            smoothing=self._int("pen/smoothing", d.smoothing),
            min_width=self._int("pen/min_width", d.min_width),
            max_width=self._int("pen/max_width", d.max_width),
            nib=self._enum("pen/nib", Nib, d.nib),
            line_style=self._enum("pen/line_style", LineStyle, d.line_style),
            hold_to_straight=self._bool("pen/hold_to_straight", d.hold_to_straight),
            math_recognition=self._bool("pen/math_recognition", d.math_recognition),
            shape_correction=self._bool("pen/shape_correction", d.shape_correction),
            autosave=self._bool("pen/autosave", d.autosave),
            template_matching=self._bool("pen/template_matching", d.template_matching),
            reading_ms=reading,
        )

    def set_pen(self, p: PenSettings) -> None:
        for f in fields(PenSettings):
            v = getattr(p, f.name)
            self._q.setValue(f"pen/{f.name}", v.value if isinstance(v, (Nib, LineStyle)) else v)

    def sync(self) -> None:
        self._q.sync()
