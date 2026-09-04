# Matematiğin Mantığı — Görünüş Demosu (PyQt6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable look-and-feel demo of a teacher's graphics-tablet lecture app: the 4-region window (questions, hand-drawing, smart hints, webcam) plus the outer toolbar, with real pressure drawing, real webcam chroma key, and questions loaded from an Excel template. Recording, Keras recognition and pyautogui stay as UI stubs behind stable interfaces.

**Architecture:** A `src/` layout Python package `matematigin_mantigi`. `core/` holds Qt-free (or QtCore-only) logic: models, stroke math, chroma key (numpy/cv2), Excel loader, question flow state machine, recorder interface, settings, session snapshots. `ui/` holds PyQt6 widgets, one file per region, and `main_window.py` does wiring only. A `QThread` camera worker keeps the UI responsive.

**Tech Stack:** Python 3.13, PyQt6 6.11 (Qt 6.11), opencv-python 4.13, numpy 2.3, openpyxl 3.1, pytest 9 + pytest-qt 4.5 (offscreen platform). Later milestones: mss + ffmpeg (recording), pyautogui (hotkeys/cursor), Keras (math handwriting).

**Spec:** The visual mockup `Ogretim Platformu.dc.html` and the feature list `Ozellik Listesi.dc.html` in `C:\Users\bkese\Desktop\arayuz-soru-sistemi-metematigin-mantigi\` (Claude Design canvas files), plus the sketches in `uploads/`. The user's brief (Turkish) is summarised in the Context section below. At execution time, copy this plan to `docs/superpowers/plans/2026-09-04-gorunus-demosu.md` inside the repo (Task 1) so it travels with the code.

## Context

The user (a math teacher, brand "Matematiğin Mantığı") wants a desktop app to record lessons while solving questions on an XP-Pen graphics tablet on a Mac. The mockup already fixes the layout:

- **Region 1 "Soru"** (top-left): question chips S1/S2/S3 with status bekliyor / işleniyor / tamamlandı, the question text, can be blurred and re-shown with a "? Soruyu göster" button.
- **Region 2 "El çizimi"** (bottom-left, largest): dotted-grid canvas, pressure-sensitive pen, eraser, laser, status strip "Araç · Kalınlık · Basınç: XP-Pen".
- **Region 3 "Akıllı ipuçları"** (top-right): three hints per question, masked with blur or black redaction, a hint never opens unless clicked, ◀ ▶ navigation, "Aç/Gizle", Keras status footer (stub).
- **Region 4 "Webcam"** (bottom-right): live camera with in-app green-screen removal, click toggles raw/keyed.
- **Region 9** (outer left toolbar, 88 px, dark): tools, colors, thickness, question flow buttons, undo/clear, record button. Labeled "kayıtta görünmez": it is outside the recording rectangle.
- A second screen "Kalem ayarları" (pen settings: pressure curve, smoothing, min/max width, nib, Keras toggles) becomes a dialog.

Decisions made with the user on 2026-09-04: PyQt6; demo = real layout + real drawing + real webcam keying; recording engine later is mss + OpenCV/ffmpeg with pyautogui only for hotkeys/cursor (this plan ships a `Recorder` interface and a `NullRecorder`); feature set = the 10 core brief items only. The 51-item research list stays as "next plans" at the end.

Added mid-planning by the user (same day):
- Every region is an OBS-style widget: drag to move, drag the corner to resize, snapping to the 12x10 grid, layout saved to `duzen.json` and restored on start (Task 4).
- In normal use no lines are visible: no panel borders and no board frame ("tahtanın sınırları gözükmesin", "iç widgetlerin çizgileri gözükmeyecek"). Outlines, the grid and the recording frame appear only while "⧉ Düzen" edit mode is on.

Toolchain verified on the dev machine (Windows 11): Python 3.13.13, PyQt6 6.11.0, opencv-python 4.13.0, numpy 2.3.5, openpyxl 3.1.5, pytest 9.1.1, pytest-qt 4.5.0, mss 10.2.0, ffmpeg 7.1.1, uv 0.11.6. Target machine is a Mac with an XP-Pen tablet (arm64).

## Global Constraints

- Python >= 3.11 (uses `X | None`, `dataclass(frozen=True, slots=True)` is avoided for Qt-compat simplicity).
- PyQt6 >= 6.6 (`QTabletEvent.position()`, `QPointingDevice` constructor used in tests).
- All UI strings in Turkish exactly as in the mockup: "Soru", "El çizimi", "Akıllı ipuçları", "Webcam", "Kalem", "Silgi", "Yazı", "Şekil", "Lazer", "Soruyu işle", "Soruyu tamamla ✓", "Sıradaki soru →", "KAYIT", "DURDUR", "Soruyu göster", "Gizle", "Aç", "Blur", "Siyah redakte", "Matematiğin Mantığı".
- Palette (hex, from the mockup): ink `#1c1b19`, page `#e9e7e2`, panel `#ffffff`, panel-soft `#f7f6f3`, muted `#7a776f`, dot `#d9d6cf`, accent `#bd4334`, record dot `#de3e2d`, ok dot `#008a39`, pens `#1c1b19 #c8322b #2456b8 #1f8a4c`, laser `#ff3b30`, chroma green `#00ff3c`.
- Layout numbers: toolbar width 88, grid 12 columns x 10 rows, gap 14, work-area padding `30 30 60 210` (top right bottom left), panel border 2 px radius 4, inset recording frame 10 px, dot spacing 28 px, target window 1920x1080.
- Pressure width formula: `width = base * (0.6 + pressure * 1.2)`; mouse pressure = 0.5.
- Chroma defaults: tolerance 38, feather 2 px, spill 0.60, background `#f7f6f3`.
- Excel template columns, in order: `id, konu, sinif, soru, ipucu1, ipucu2, ipucu3, cevap`; file name `sorular_sablon.xlsx`.
- Tests run headless: `QT_QPA_PLATFORM=offscreen` set in `tests/conftest.py` before any PyQt6 import. No test touches a real camera or the tablet.
- Nothing in `core/` imports `PyQt6.QtWidgets`. `core/question_flow.py`, `core/settings.py`, `core/session_store.py` may import `PyQt6.QtCore` / `PyQt6.QtGui`.
- Run command: `python -m matematigin_mantigi`. Tests: `python -m pytest -q`.
- On Windows PowerShell set `$env:PYTHONUTF8 = "1"` before running so Turkish output prints correctly.
- Commit after every task. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File Structure

```
C:\Users\bkese\Desktop\arayuz-soru-sistemi-metematigin-mantigi\
  pyproject.toml                       # package metadata, deps, pytest config (qt_api = pyqt6)
  README.md                            # run + platform checklist (Task 15)
  .gitignore
  docs/superpowers/plans/2026-09-04-gorunus-demosu.md   # copy of this plan
  sorular_sablon.xlsx                  # generated on first run (Task 10), committed as sample
  duzen.json                           # saved panel layout (Task 4), git-ignored
  oturum/                              # runtime snapshots, git-ignored
  src/matematigin_mantigi/
    __init__.py
    __main__.py                        # python -m matematigin_mantigi
    app.py                             # QApplication bootstrap, CLI args, fonts, MainWindow
    paths.py                           # ASSETS_DIR, FONTS_DIR, default template + oturum paths
    assets/fonts/                      # WorkSans[wght].ttf, Caveat[wght].ttf, OFL.txt (Task 2)
    core/
      __init__.py
      models.py                        # Tool, QuestionStatus, HintMaskMode, Nib, Question, PenSettings, PALETTE, WIDTHS
      layout_model.py                  # PanelGeom, DEFAULT_LAYOUT, snap/pixel math, duzen.json load/save (OBS-style)
      stroke.py                        # pressure_width, eraser_diameter, pen_cursor_diameter
      chroma_key.py                    # ChromaParams, green_mask, suppress_spill, composite, apply_chroma_key
      question_loader.py               # REQUIRED_COLUMNS, write_template, ensure_template, load_questions
      question_flow.py                 # QuestionFlow(QObject) state machine + signals
      recorder.py                      # RecordRect, record_rect_for, Recorder Protocol, NullRecorder
      settings.py                      # AppSettings over QSettings
      session_store.py                 # SessionStore.save_snapshot
    ui/
      __init__.py
      theme.py                         # colors, sizes, FontFamilies, load_fonts, font helpers, stylesheet
      widgets.py                       # GlyphButton, SwatchButton, DotButton, RecordButton, ClickableLabel
      panel.py                         # PanelFrame (white panel, ink border, numbered header)
      toolbar.py                       # ToolBar (region 9, incl. "⧉ Düzen" edit toggle)
      work_area.py                     # WorkArea: movable/resizable panels on a 12x10 snap grid, edit mode, brand plate, badge, recording_rect
      canvas.py                        # DrawingCanvas (tablet + mouse, layers, undo)
      canvas_panel.py                  # CanvasPanel (region 2 chrome)
      cursors.py                       # pen/eraser/laser/text/shape cursors
      camera_worker.py                 # FrameSource, OpenCvSource, to_qimage_bgr, CameraWorker(QThread)
      webcam_panel.py                  # CameraView + WebcamPanel (region 4)
      question_panel.py                # QuestionPanel (region 1)
      hint_panel.py                    # HintPanel (region 3)
      record_badge.py                  # RecordBadge (KAYIT · 00:00 · 1920×1080 · 60 fps)
      pen_settings.py                  # PenSettingsDialog
      main_window.py                   # MainWindow: composition + signal wiring
  tests/
    conftest.py
    test_models.py test_theme.py test_toolbar.py test_layout_model.py test_work_area.py
    test_stroke.py test_canvas.py test_cursors.py test_chroma_key.py test_camera_worker.py
    test_webcam_panel.py test_question_loader.py test_question_flow.py test_session_store.py
    test_recorder.py test_settings.py test_panels.py test_main_window.py test_pen_settings.py
```

Task order: 1 bootstrap → 2 theme → 3 widgets/toolbar → 4 layout model + WorkArea → 5 canvas → 6 cursors → 7 chroma key → 8 camera worker → 9 webcam panel → 10 Excel loader → 11 question flow → 12 session store → 13 recorder + badge → 14 settings → 15 question/hint panels → 16 MainWindow → 17 pen settings dialog → 18 shortcuts, README, final verification. The app is runnable from Task 1 on and visually checkable from Task 4 on.

---

### Task 1: Bootstrap package, git repo, models

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/matematigin_mantigi/__init__.py`, `src/matematigin_mantigi/__main__.py`, `src/matematigin_mantigi/app.py`, `src/matematigin_mantigi/paths.py`, `src/matematigin_mantigi/core/__init__.py`, `src/matematigin_mantigi/core/models.py`, `src/matematigin_mantigi/ui/__init__.py`, `tests/conftest.py`, `tests/test_models.py`
- Copy: this plan to `docs/superpowers/plans/2026-09-04-gorunus-demosu.md`

**Interfaces:**
- Produces: `core.models.Tool`, `QuestionStatus`, `HintMaskMode`, `Nib`, `Question`, `PenSettings`, `PALETTE`, `WIDTHS`, `TOOL_META`, `SAMPLE_QUESTIONS`; `paths.ASSETS_DIR`, `paths.FONTS_DIR`, `paths.default_template_path()`, `paths.default_session_root()`; `app.main(argv) -> int`.

- [ ] **Step 1: Initialise git and write the project files**

```powershell
cd C:\Users\bkese\Desktop\arayuz-soru-sistemi-metematigin-mantigi
git init
New-Item -ItemType Directory -Force docs\superpowers\plans | Out-Null
Copy-Item C:\Users\bkese\.claude\plans\superpowers-writing-plans-1-alan-sorula-vast-alpaca.md docs\superpowers\plans\2026-09-04-gorunus-demosu.md
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
oturum/
*.egg-info/
build/
dist/
```

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "matematigin-mantigi"
version = "0.1.0"
description = "Grafik tablet ile ders anlatım ve kayıt uygulaması (görünüş demosu)"
requires-python = ">=3.11"
dependencies = [
  "PyQt6>=6.6",
  "opencv-python>=4.8",
  "numpy>=1.26",
  "openpyxl>=3.1",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-qt>=4.4"]

[project.scripts]
matematigin-mantigi = "matematigin_mantigi.app:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
matematigin_mantigi = ["assets/fonts/*.ttf", "assets/fonts/*.txt"]

[tool.pytest.ini_options]
qt_api = "pyqt6"
testpaths = ["tests"]
```

`src/matematigin_mantigi/__init__.py`:
```python
"""Matematiğin Mantığı — grafik tablet ders anlatım uygulaması."""
__version__ = "0.1.0"
```

`src/matematigin_mantigi/__main__.py`:
```python
import sys
from matematigin_mantigi.app import main

sys.exit(main(sys.argv))
```

`src/matematigin_mantigi/paths.py`:
```python
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
TEMPLATE_NAME = "sorular_sablon.xlsx"


def default_template_path() -> Path:
    return Path.cwd() / TEMPLATE_NAME


def default_session_root() -> Path:
    return Path.cwd() / "oturum"
```

`src/matematigin_mantigi/core/__init__.py` and `src/matematigin_mantigi/ui/__init__.py`: empty files.

`src/matematigin_mantigi/core/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tool(str, Enum):
    PEN = "pen"
    ERASER = "eraser"
    TEXT = "text"
    SHAPE = "shape"
    LASER = "laser"


TOOL_META: dict[Tool, tuple[str, str]] = {
    Tool.PEN: ("Kalem", "✎"),
    Tool.ERASER: ("Silgi", "▭"),
    Tool.TEXT: ("Yazı", "T"),
    Tool.SHAPE: ("Şekil", "△"),
    Tool.LASER: ("Lazer", "●"),
}


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


PALETTE: tuple[str, ...] = ("#1c1b19", "#c8322b", "#2456b8", "#1f8a4c")
WIDTHS: tuple[int, ...] = (2, 4, 8)


@dataclass(frozen=True)
class Question:
    id: str
    konu: str
    sinif: int | None
    soru: str
    hints: tuple[str, ...]
    cevap: str


@dataclass(frozen=True)
class PenSettings:
    pressure_curve: int = 50   # 0 yumuşak .. 100 sert, 50 = "Doğrusal"
    smoothing: int = 35        # yüzde
    min_width: int = 1
    max_width: int = 12
    nib: Nib = Nib.ROUND
    math_recognition: bool = True
    shape_correction: bool = True
    autosave: bool = True
    template_matching: bool = False


SAMPLE_QUESTIONS: tuple[Question, ...] = (
    Question("S1", "Denklemler", 7, "3x + 5 = 20 ise x kaçtır?",
             ("Denklemin iki tarafından 5 çıkar: 3x = 15.",
              "3x = 15 ise x = 15 ÷ 3.",
              "Cevap: x = 5. Kontrol: 3·5 + 5 = 20 ✓"), "x = 5"),
    Question("S2", "Geometri", 6, "Kenarları 6 cm ve 8 cm olan dikdörtgenin çevresi kaç cm?",
             ("Dikdörtgende karşılıklı kenarlar eşittir.",
              "Çevre = 2 × (uzun + kısa) = 2 × (8 + 6).",
              "Cevap: 28 cm."), "28 cm"),
    Question("S3", "Kesirler", 6, "2/3 + 1/6 işleminin sonucu nedir?",
             ("Paydaları eşitle: 6 ortak payda.",
              "2/3 = 4/6 olur; 4/6 + 1/6.",
              "Cevap: 5/6."), "5/6"),
)
```

`src/matematigin_mantigi/app.py` (first version; later tasks extend it):
```python
from __future__ import annotations

import argparse
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMainWindow


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="matematigin-mantigi")
    p.add_argument("--sorular", help="Soru şablonu (.xlsx) yolu")
    p.add_argument("--kamera", type=int, default=None, help="Kamera indeksi (varsayılan: ayarlardan)")
    p.add_argument("--kamera-yok", action="store_true", help="Kamerayı açma")
    return p.parse_args(argv[1:])


def build_window(args: argparse.Namespace) -> QMainWindow:
    win = QMainWindow()
    win.setWindowTitle("Matematiğin Mantığı")
    win.resize(1920, 1080)
    win.setStyleSheet("QMainWindow { background: #e9e7e2; }")
    return win


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    win = build_window(parse_args(argv))
    win.show()
    return app.exec()
```

`tests/conftest.py`:
```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS  # noqa: E402


@pytest.fixture
def sample_questions():
    return list(SAMPLE_QUESTIONS)
```

- [ ] **Step 2: Write the failing test**

`tests/test_models.py`:
```python
from matematigin_mantigi.core.models import (PALETTE, SAMPLE_QUESTIONS, TOOL_META, WIDTHS,
                                             PenSettings, Question, Tool)
from matematigin_mantigi import app


def test_palette_and_widths_match_mockup():
    assert PALETTE == ("#1c1b19", "#c8322b", "#2456b8", "#1f8a4c")
    assert WIDTHS == (2, 4, 8)


def test_every_tool_has_label_and_glyph():
    assert set(TOOL_META) == set(Tool)
    assert TOOL_META[Tool.PEN] == ("Kalem", "✎")


def test_sample_questions_have_three_hints():
    assert len(SAMPLE_QUESTIONS) == 3
    assert all(isinstance(q, Question) and len(q.hints) == 3 for q in SAMPLE_QUESTIONS)


def test_pen_settings_defaults():
    p = PenSettings()
    assert (p.pressure_curve, p.smoothing, p.min_width, p.max_width) == (50, 35, 1, 12)
    assert p.template_matching is False


def test_parse_args_defaults():
    ns = app.parse_args(["prog"])
    assert ns.sorular is None and ns.kamera is None and ns.kamera_yok is False


def test_build_window_offscreen(qtbot):
    win = app.build_window(app.parse_args(["prog"]))
    qtbot.addWidget(win)
    assert win.windowTitle() == "Matematiğin Mantığı"
```

- [ ] **Step 3: Install the package in editable mode and run the test to verify it fails / passes**

```powershell
$env:PYTHONUTF8 = "1"
python -m pip install -e ".[dev]"
python -m pytest tests/test_models.py -v
```
Expected: before writing `models.py` the import fails; after Step 1 is complete all 6 tests PASS. Also run `python -m matematigin_mantigi` once: an empty 1920x1080 window with the page background opens. Close it.

- [ ] **Step 4: Commit**

```powershell
git add -A
git commit -m "feat: bootstrap matematigin_mantigi package, models and empty window

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Theme, fonts and stylesheet

**Files:**
- Create: `src/matematigin_mantigi/ui/theme.py`, `src/matematigin_mantigi/assets/fonts/OFL.txt`, `src/matematigin_mantigi/assets/fonts/WorkSans[wght].ttf`, `src/matematigin_mantigi/assets/fonts/Caveat[wght].ttf`, `tests/test_theme.py`
- Modify: `src/matematigin_mantigi/app.py`

**Interfaces:**
- Produces: `theme.INK, PAGE, PANEL, PANEL_SOFT, MUTED, MUTED_DARK, LINE, DOT, CHIP, ROW_FOCUS, HINT_EMPTY, ACCENT, REC_DOT, OK_DOT, TOOLBAR_BTN, TOOLBAR_LINE, TOOLBAR_MUTED, TOOLBAR_DIM, CAM_RAW, LASER` (hex strings); `GRID_GAP=14, PANEL_RADIUS=4, PANEL_BORDER=2, FRAME_INSET=10, TOOLBAR_WIDTH=88, DOT_SPACING=28`; `FontFamilies(sans, hand, loaded)`; `load_fonts(fonts_dir) -> FontFamilies`; `font(fam, px, weight=400, spacing_pct=None) -> QFont`; `hand_font(fam, px, weight=500) -> QFont`; `build_stylesheet(fam) -> str`.

- [ ] **Step 1: Download the fonts (Open Font License) into the assets folder**

```powershell
$d = "src\matematigin_mantigi\assets\fonts"
New-Item -ItemType Directory -Force $d | Out-Null
curl.exe -L -o "$d\WorkSans[wght].ttf" "https://raw.githubusercontent.com/google/fonts/main/ofl/worksans/WorkSans%5Bwght%5D.ttf"
curl.exe -L -o "$d\Caveat[wght].ttf"   "https://raw.githubusercontent.com/google/fonts/main/ofl/caveat/Caveat%5Bwght%5D.ttf"
curl.exe -L -o "$d\OFL.txt"            "https://raw.githubusercontent.com/google/fonts/main/ofl/worksans/OFL.txt"
Get-Item "$d\*.ttf" | Select-Object Name, Length
```
Expected: two TTF files, each larger than 100 KB. If the download fails (no network, URL moved), leave the folder with only `OFL.txt`; the code falls back to system fonts and the "loaded" test skips.

- [ ] **Step 2: Write the failing tests**

`tests/test_theme.py`:
```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```powershell
python -m pytest tests/test_theme.py -v
```
Expected: FAIL with `ModuleNotFoundError: matematigin_mantigi.ui.theme`.

- [ ] **Step 4: Implement theme.py**

`src/matematigin_mantigi/ui/theme.py`:
```python
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

# Ölçüler
GRID_GAP = 14
PANEL_RADIUS = 4
PANEL_BORDER = 2
FRAME_INSET = 10
TOOLBAR_WIDTH = 88
DOT_SPACING = 28
WORK_PADDING = (30, 30, 60, 210)   # top, right, bottom, left


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
    return f"""
    QMainWindow, QDialog {{ background: {PAGE}; }}
    QWidget {{ font-family: "{fam.sans}"; color: {INK}; }}
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
```

`QFont.Weight` is a Python enum in PyQt6 whose members are exactly the values used here (400 Normal, 500 Medium, 600 DemiBold, 700 Bold); `QFont.Weight(600)` resolves to `DemiBold` and `f.weight()` returns the enum member, so tests compare against `QFont.Weight.DemiBold`, not the int.

- [ ] **Step 5: Use the theme in app.py**

Replace `build_window` and `main` in `src/matematigin_mantigi/app.py`:
```python
from matematigin_mantigi import paths
from matematigin_mantigi.ui import theme


def build_window(args: argparse.Namespace, fam: theme.FontFamilies | None = None) -> QMainWindow:
    fam = fam or theme.FontFamilies("sans-serif", "cursive", False)
    win = QMainWindow()
    win.setWindowTitle("Matematiğin Mantığı")
    win.resize(1920, 1080)
    return win


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    fam = theme.load_fonts(paths.FONTS_DIR)
    app.setStyleSheet(theme.build_stylesheet(fam))
    win = build_window(parse_args(argv), fam)
    win.show()
    return app.exec()
```

- [ ] **Step 6: Run tests to verify they pass**

```powershell
python -m pytest tests/test_theme.py tests/test_models.py -v
```
Expected: all PASS (the bundled-fonts test may SKIP if Step 1 failed).

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "feat: theme constants, bundled Work Sans + Caveat fonts, stylesheet

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Painted widgets, PanelFrame and the toolbar (region 9)

**Files:**
- Create: `src/matematigin_mantigi/ui/widgets.py`, `src/matematigin_mantigi/ui/panel.py`, `src/matematigin_mantigi/ui/toolbar.py`, `tests/test_toolbar.py`

**Interfaces:**
- Consumes: `core.models.Tool, TOOL_META, PALETTE, WIDTHS`; `ui.theme.*`.
- Produces:
  - `widgets.GlyphButton(glyph: str, label: str, parent=None)` checkable, 56x48.
  - `widgets.SwatchButton(color_hex: str, parent=None)` checkable, `.color_hex: str`.
  - `widgets.DotButton(value: int, parent=None)` checkable, `.value: int`, dot size 8/12/16 for 2/4/8.
  - `widgets.RecordButton(parent=None)` checkable, 56 px circle.
  - `widgets.ClickableLabel(QLabel)` with `clicked = pyqtSignal()` and `doubleClicked = pyqtSignal()`.
  - `panel.PanelFrame(number: str, title: str, fam: FontFamilies, parent=None)` with `.header: QHBoxLayout`, `.body: QVBoxLayout`, `.header_widget: QWidget`, `.set_header_visible(bool)`, `.set_border_visible(bool)` (default False: no visible lines in normal use), `.border_visible: bool`, `.key: str` (set by WorkArea), signals `headerPressed = pyqtSignal(QPoint)`, `headerDoubleClicked = pyqtSignal()`.
  - `toolbar.ToolBar(fam, parent=None)` signals: `toolSelected(Tool)`, `colorSelected(str)`, `widthSelected(int)`, `workToggled()`, `nextRequested()`, `undoRequested()`, `clearRequested()`, `recordToggled(bool)`, `penSettingsRequested()`, `layoutEditToggled(bool)`; methods `set_tool(Tool)`, `set_color(str)`, `set_width(int)`, `set_work_label(str)`, `set_progress(str)`, `set_recording(bool)`, `set_undo_enabled(bool)`, `set_layout_edit(bool)`; attributes `tool_buttons: dict[Tool, GlyphButton]`, `swatches: dict[str, SwatchButton]`, `width_buttons: dict[int, DotButton]`, `record_button: RecordButton`, `work_button: QPushButton`, `next_button: QPushButton`, `layout_button: QPushButton`.

- [ ] **Step 1: Write the failing tests**

`tests/test_toolbar.py`:
```python
from PyQt6.QtCore import Qt

from matematigin_mantigi.core.models import PALETTE, Tool
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.panel import PanelFrame

FAM = FontFamilies("Arial", "Arial", False)


def make(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    return tb


def test_toolbar_is_88_wide_and_pen_selected(qtbot):
    tb = make(qtbot)
    assert tb.width() == 88
    assert tb.tool_buttons[Tool.PEN].isChecked()
    assert sum(b.isChecked() for b in tb.tool_buttons.values()) == 1


def test_clicking_eraser_emits_and_is_exclusive(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.toolSelected, timeout=1000) as sig:
        qtbot.mouseClick(tb.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert sig.args == [Tool.ERASER]
    assert tb.tool_buttons[Tool.ERASER].isChecked() and not tb.tool_buttons[Tool.PEN].isChecked()


def test_swatch_and_width_signals(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.colorSelected) as sig:
        qtbot.mouseClick(tb.swatches[PALETTE[1]], Qt.MouseButton.LeftButton)
    assert sig.args == ["#c8322b"]
    with qtbot.waitSignal(tb.widthSelected) as sig:
        qtbot.mouseClick(tb.width_buttons[8], Qt.MouseButton.LeftButton)
    assert sig.args == [8]


def test_record_button_toggles(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.recordToggled) as sig:
        qtbot.mouseClick(tb.record_button, Qt.MouseButton.LeftButton)
    assert sig.args == [True]
    tb.set_recording(True)
    assert tb.record_label.text() == "DURDUR"
    tb.set_recording(False)
    assert tb.record_label.text() == "KAYIT"


def test_silent_setters_do_not_emit(qtbot):
    tb = make(qtbot)
    fired = []
    tb.toolSelected.connect(lambda t: fired.append(t))
    tb.set_tool(Tool.LASER)
    assert tb.tool_buttons[Tool.LASER].isChecked() and fired == []


def test_layout_edit_button(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.layoutEditToggled) as sig:
        qtbot.mouseClick(tb.layout_button, Qt.MouseButton.LeftButton)
    assert sig.args == [True]


def test_panel_frame_header(qtbot):
    p = PanelFrame("1", "Soru", FAM)
    qtbot.addWidget(p)
    p.show()
    assert p.number_label.text() == "1" and p.title_label.text() == "SORU"
    with qtbot.waitSignal(p.headerPressed):
        qtbot.mousePress(p.header_widget, Qt.MouseButton.LeftButton)


def test_panel_frame_has_no_border_by_default(qtbot):
    p = PanelFrame("1", "Soru", FAM)
    qtbot.addWidget(p)
    p.resize(200, 120)
    p.show()
    qtbot.waitExposed(p)
    assert p.border_visible is False
    img = p.grab().toImage()
    assert img.pixelColor(1, 60).name() == "#ffffff"      # kenar çizgisi yok, beyaz dolgu
    p.set_border_visible(True)
    img = p.grab().toImage()
    assert img.pixelColor(1, 60).name() == "#1c1b19"      # düzen modunda mürekkep kenar
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
python -m pytest tests/test_toolbar.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement widgets.py**

`src/matematigin_mantigi/ui/widgets.py`:
```python
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QLabel

from matematigin_mantigi.ui import theme


class GlyphButton(QAbstractButton):
    """56x48 araç düğmesi: büyük glif + 9px etiket. Seçiliyken accent zemin."""

    def __init__(self, glyph: str, label: str, parent=None):
        super().__init__(parent)
        self.glyph, self.label = glyph, label
        self.setCheckable(True)
        self.setFixedSize(56, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT if on else theme.TOOLBAR_BTN))
        p.drawRoundedRect(QRectF(0, 0, 56, 48), 6, 6)
        p.setPen(QColor("#ffffff" if on else theme.TOOLBAR_MUTED))
        f = QFont(self.font()); f.setPixelSize(18); p.setFont(f)
        p.drawText(QRectF(0, 4, 56, 24), Qt.AlignmentFlag.AlignCenter, self.glyph)
        f.setPixelSize(9); f.setWeight(QFont.Weight(600)); p.setFont(f)
        p.drawText(QRectF(0, 28, 56, 16), Qt.AlignmentFlag.AlignCenter, self.label.upper())
        p.end()


class SwatchButton(QAbstractButton):
    """22px renk dairesi; seçiliyken 3px açık halka."""

    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setCheckable(True)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(14, 14)
        if self.isChecked():
            p.setPen(QPen(QColor(theme.PANEL_SOFT), 3))
        else:
            p.setPen(QPen(QColor(theme.TOOLBAR_LINE), 1))
        p.setBrush(QBrush(QColor(self.color_hex)))
        p.drawEllipse(c, 11, 11)
        p.end()


class DotButton(QAbstractButton):
    """Kalınlık ön ayarı: 2/4/8 px -> 8/12/16 px nokta."""

    DOT = {2: 8, 4: 12, 8: 16}

    def __init__(self, value: int, parent=None):
        super().__init__(parent)
        self.value = value
        self.setCheckable(True)
        self.setFixedSize(28, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.DOT.get(self.value, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.PANEL_SOFT if self.isChecked() else theme.TOOLBAR_DIM))
        p.drawEllipse(QPointF(14, 12), d / 2, d / 2)
        p.end()


class RecordButton(QAbstractButton):
    """56px daire, accent kenar; kayıtta 18px yuvarlatılmış kare."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(56, 56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.setBrush(QColor(theme.TOOLBAR_BTN))
        p.drawEllipse(QPointF(28, 28), 26, 26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT))
        if self.isChecked():
            p.drawRoundedRect(QRectF(19, 19, 18, 18), 4, 4)
        else:
            p.drawEllipse(QPointF(28, 28), 11, 11)
        p.end()


class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    doubleClicked = pyqtSignal()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(e)
```

- [ ] **Step 4: Implement panel.py**

`src/matematigin_mantigi/ui/panel.py`:
```python
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies


class _Header(QWidget):
    pressed = pyqtSignal(QPoint)
    doubleClicked = pyqtSignal()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit(e.position().toPoint())
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(e)


class PanelFrame(QWidget):
    """Beyaz panel, 2px mürekkep kenar, radius 4, Caveat numaralı başlık."""

    headerPressed = pyqtSignal(QPoint)
    headerDoubleClicked = pyqtSignal()

    def __init__(self, number: str, title: str, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.key = ""
        self.fam = fam
        self.border_visible = False        # normal kullanımda çizgi yok; düzen modu açar
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PANEL_BORDER, theme.PANEL_BORDER,
                                 theme.PANEL_BORDER, theme.PANEL_BORDER)
        outer.setSpacing(0)

        self.header_widget = _Header(self)
        self.header_widget.setFixedHeight(44)
        self.header_widget.pressed.connect(self.headerPressed)
        self.header_widget.doubleClicked.connect(self.headerDoubleClicked)
        self.header = QHBoxLayout(self.header_widget)
        self.header.setContentsMargins(18, 6, 18, 0)
        self.header.setSpacing(10)

        self.number_label = QLabel(number)
        self.number_label.setFont(theme.hand_font(fam, 34, 700))
        self.title_label = QLabel(title.upper())
        self.title_label.setFont(theme.font(fam, 11, 600, spacing_pct=114))
        self.title_label.setStyleSheet(f"color: {theme.MUTED};")
        self.header.addWidget(self.number_label)
        self.header.addWidget(self.title_label)
        self.header.addStretch(1)

        self.body_widget = QWidget(self)
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(24, 6, 24, 18)
        self.body.setSpacing(8)

        outer.addWidget(self.header_widget)
        outer.addWidget(self.body_widget, 1)

    def set_header_visible(self, on: bool) -> None:
        self.header_widget.setVisible(on)

    def set_border_visible(self, on: bool) -> None:
        self.border_visible = on
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(theme.PANEL))
        if self.border_visible:
            b = theme.PANEL_BORDER / 2
            p.setPen(QPen(QColor(theme.INK), theme.PANEL_BORDER))
            p.drawRoundedRect(QRectF(b, b, self.width() - 2 * b, self.height() - 2 * b),
                              theme.PANEL_RADIUS, theme.PANEL_RADIUS)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()),
                              theme.PANEL_RADIUS, theme.PANEL_RADIUS)
        p.end()
```

The border is off by default. `WorkArea.set_edit_mode` (Task 4) turns it on for every panel while editing and off again on "Bitti".

- [ ] **Step 5: Implement toolbar.py**

`src/matematigin_mantigi/ui/toolbar.py`:
```python
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
                             QSizePolicy, QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import PALETTE, TOOL_META, WIDTHS, Tool
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.widgets import DotButton, GlyphButton, RecordButton, SwatchButton

_BTN_CSS = (f"QPushButton {{ background: {theme.TOOLBAR_BTN}; color: {theme.TOOLBAR_MUTED}; border: none;"
            f" border-radius: 6px; padding: 6px 4px; font-size: 10px; font-weight: 600; }}"
            f"QPushButton:checked {{ background: {theme.ACCENT}; color: white; }}"
            f"QPushButton:disabled {{ color: {theme.TOOLBAR_DIM}; }}")


class ToolBar(QWidget):
    """Bölge 9: dış araç çubuğu. Kayıtta görünmez."""

    toolSelected = pyqtSignal(object)      # Tool
    colorSelected = pyqtSignal(str)        # hex
    widthSelected = pyqtSignal(int)
    workToggled = pyqtSignal()
    nextRequested = pyqtSignal()
    undoRequested = pyqtSignal()
    clearRequested = pyqtSignal()
    recordToggled = pyqtSignal(bool)
    penSettingsRequested = pyqtSignal()
    layoutEditToggled = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self.setFixedWidth(theme.TOOLBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {theme.INK};")
        self.setAutoFillBackground(True)

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(6)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        nine = QLabel("9"); nine.setFont(theme.hand_font(fam, 40, 700))
        nine.setStyleSheet(f"color: {theme.PANEL_SOFT};")
        col.addWidget(nine, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._caption("KAYITTA\nGÖRÜNMEZ"))

        self.pen_settings_button = QPushButton("Kalem"); self.pen_settings_button.setStyleSheet(_BTN_CSS)
        self.pen_settings_button.clicked.connect(self.penSettingsRequested)
        self.layout_button = QPushButton("⧉ Düzen"); self.layout_button.setCheckable(True)
        self.layout_button.setStyleSheet(_BTN_CSS)
        self.layout_button.toggled.connect(self.layoutEditToggled)
        col.addWidget(self.pen_settings_button); col.addWidget(self.layout_button)
        col.addWidget(self._rule())

        self._tool_group = QButtonGroup(self); self._tool_group.setExclusive(True)
        self.tool_buttons: dict[Tool, GlyphButton] = {}
        for tool, (label, glyph) in TOOL_META.items():
            b = GlyphButton(glyph, label)
            self._tool_group.addButton(b)
            self.tool_buttons[tool] = b
            b.clicked.connect(lambda _c=False, t=tool: self.toolSelected.emit(t))
            col.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        self.tool_buttons[Tool.PEN].setChecked(True)
        col.addWidget(self._rule())

        self._swatch_group = QButtonGroup(self); self._swatch_group.setExclusive(True)
        self.swatches: dict[str, SwatchButton] = {}
        row = QHBoxLayout(); row.setSpacing(0)
        for i, hx in enumerate(PALETTE):
            s = SwatchButton(hx); self._swatch_group.addButton(s); self.swatches[hx] = s
            s.clicked.connect(lambda _c=False, h=hx: self.colorSelected.emit(h))
            if i % 2 == 0 and i:
                col.addLayout(row); row = QHBoxLayout(); row.setSpacing(0)
            row.addWidget(s)
        col.addLayout(row)
        self.swatches[PALETTE[0]].setChecked(True)

        col.addWidget(self._caption("KALINLIK"))
        self._width_group = QButtonGroup(self); self._width_group.setExclusive(True)
        self.width_buttons: dict[int, DotButton] = {}
        wrow = QHBoxLayout(); wrow.setSpacing(0)
        for w in WIDTHS:
            d = DotButton(w); self._width_group.addButton(d); self.width_buttons[w] = d
            d.clicked.connect(lambda _c=False, v=w: self.widthSelected.emit(v))
            wrow.addWidget(d)
        col.addLayout(wrow)
        self.width_buttons[4].setChecked(True)
        col.addWidget(self._rule())

        col.addWidget(self._caption("SORU AKIŞI"))
        self.work_button = QPushButton("Soruyu işle"); self.work_button.setStyleSheet(_BTN_CSS)
        self.work_button.clicked.connect(self.workToggled)
        self.next_button = QPushButton("Sıradaki soru →"); self.next_button.setStyleSheet(_BTN_CSS)
        self.next_button.clicked.connect(self.nextRequested)
        self.progress_label = self._caption("0/0")
        col.addWidget(self.work_button); col.addWidget(self.next_button); col.addWidget(self.progress_label)
        col.addWidget(self._rule())

        hrow = QHBoxLayout(); hrow.setSpacing(4)
        self.undo_button = QPushButton("↶"); self.undo_button.setStyleSheet(_BTN_CSS)
        self.undo_button.clicked.connect(self.undoRequested); self.undo_button.setEnabled(False)
        self.clear_button = QPushButton("✕"); self.clear_button.setStyleSheet(_BTN_CSS)
        self.clear_button.clicked.connect(self.clearRequested)
        hrow.addWidget(self.undo_button); hrow.addWidget(self.clear_button)
        col.addLayout(hrow)

        col.addStretch(1)
        self.record_button = RecordButton()
        self.record_button.clicked.connect(lambda: self.recordToggled.emit(self.record_button.isChecked()))
        self.record_label = self._caption("KAYIT")
        col.addWidget(self.record_button, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self.record_label)

    # --- helpers -----------------------------------------------------------
    def _caption(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setFont(theme.font(self.fam, 9, 600, spacing_pct=110))
        lab.setStyleSheet(f"color: {theme.MUTED_DARK}; background: transparent;")
        lab.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return lab

    def _rule(self) -> QFrame:
        r = QFrame(); r.setFixedHeight(1); r.setStyleSheet(f"background: {theme.TOOLBAR_LINE};")
        return r

    # --- silent setters (no signals) ---------------------------------------
    def set_tool(self, t: Tool) -> None:
        b = self.tool_buttons[t]; b.blockSignals(True); b.setChecked(True); b.blockSignals(False)

    def set_color(self, hx: str) -> None:
        if hx in self.swatches:
            s = self.swatches[hx]; s.blockSignals(True); s.setChecked(True); s.blockSignals(False)

    def set_width(self, w: int) -> None:
        if w in self.width_buttons:
            d = self.width_buttons[w]; d.blockSignals(True); d.setChecked(True); d.blockSignals(False)

    def set_work_label(self, text: str) -> None:
        self.work_button.setText(text)

    def set_progress(self, text: str) -> None:
        self.progress_label.setText(text)

    def set_recording(self, on: bool) -> None:
        self.record_button.blockSignals(True); self.record_button.setChecked(on); self.record_button.blockSignals(False)
        self.record_label.setText("DURDUR" if on else "KAYIT")
        self.record_button.update()

    def set_undo_enabled(self, on: bool) -> None:
        self.undo_button.setEnabled(on)

    def set_layout_edit(self, on: bool) -> None:
        self.layout_button.blockSignals(True); self.layout_button.setChecked(on); self.layout_button.blockSignals(False)
```

- [ ] **Step 6: Run tests to verify they pass**

```powershell
python -m pytest tests/test_toolbar.py -v
```
Expected: 8 PASS.

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "feat: painted toolbar widgets, PanelFrame and ToolBar (region 9)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: OBS-style layout model and WorkArea (movable, resizable, saveable panels)

The user asked (2026-09-04, mid-planning) that every region behaves like an OBS scene item: drag to move, drag a corner to resize, and the arrangement is saved. This task replaces a fixed grid with a layout model in 12x10 grid units, an edit mode toggled from the toolbar's "⧉ Düzen" button, snapping, per-panel maximize (double-click the header), and persistence to `duzen.json` in the working directory.

The user also asked that no lines are visible in normal use: the 10 px board frame and the panel borders are drawn only in edit mode. Outside edit mode the work area is the plain page colour with borderless white panels on it. `recording_rect()` is unchanged by this (the recording boundary is the whole work area whether or not the frame is painted).

**Files:**
- Create: `src/matematigin_mantigi/core/layout_model.py`, `src/matematigin_mantigi/ui/work_area.py`, `tests/test_layout_model.py`, `tests/test_work_area.py`
- Modify: `src/matematigin_mantigi/app.py` (show the shell)

**Interfaces:**
- Consumes: `ui.panel.PanelFrame` (`headerPressed`, `headerDoubleClicked`, `.key`), `ui.theme.*`.
- Produces:
  - `layout_model.GRID_COLS = 12`, `GRID_ROWS = 10`, `MIN_SPAN = 2`.
  - `layout_model.PanelGeom(col: int, row: int, col_span: int, row_span: int)` frozen dataclass.
  - `layout_model.PANEL_KEYS = ("soru", "ipucu", "cizim", "webcam")`, `DEFAULT_LAYOUT: dict[str, PanelGeom]`.
  - `layout_model.Layout = dict[str, PanelGeom]` (type alias).
  - `layout_model.clamp(g: PanelGeom) -> PanelGeom`.
  - `layout_model.cell_size(area_w: int, area_h: int, gap: int) -> tuple[float, float]`.
  - `layout_model.pixel_rect(g, area_w, area_h, gap) -> tuple[int, int, int, int]` (x, y, w, h inside the padded area).
  - `layout_model.snap_rect(x, y, w, h, area_w, area_h, gap) -> PanelGeom`.
  - `layout_model.to_json(layout) -> str`, `from_json(text) -> Layout` (never raises; falls back to defaults per key).
  - `layout_model.load_layout(path: Path) -> Layout`, `save_layout(path: Path, layout: Layout) -> None`.
  - `work_area.WorkArea(fam, parent=None)` with `add_panel(key: str, panel: PanelFrame)`, `set_layout(layout: Layout)`, `layout() -> Layout`, `set_edit_mode(bool)`, `edit_mode: bool`, `set_maximized(key: str | None)`, `maximized: str | None`, `reset_layout()`, `recording_rect() -> tuple[int, int, int, int, float]` (global x, y, w, h, dpr; Task 13 wraps it in `RecordRect`), `badge_slot: QWidget`, signals `layoutChanged(object)` (Layout dict), `editModeChanged(bool)`.

- [ ] **Step 1: Write the failing tests for the pure model**

`tests/test_layout_model.py`:
```python
import json

from matematigin_mantigi.core import layout_model as lm


def test_default_layout_matches_mockup():
    assert lm.DEFAULT_LAYOUT["soru"] == lm.PanelGeom(0, 0, 7, 3)
    assert lm.DEFAULT_LAYOUT["ipucu"] == lm.PanelGeom(7, 0, 5, 5)
    assert lm.DEFAULT_LAYOUT["cizim"] == lm.PanelGeom(0, 3, 7, 7)
    assert lm.DEFAULT_LAYOUT["webcam"] == lm.PanelGeom(7, 5, 5, 5)


def test_clamp_keeps_inside_grid_and_min_span():
    assert lm.clamp(lm.PanelGeom(11, 9, 1, 1)) == lm.PanelGeom(10, 8, 2, 2)
    assert lm.clamp(lm.PanelGeom(-3, -1, 20, 20)) == lm.PanelGeom(0, 0, 12, 10)
    assert lm.clamp(lm.PanelGeom(8, 2, 6, 3)) == lm.PanelGeom(6, 2, 6, 3)


def test_pixel_rect_and_snap_round_trip():
    w, h, gap = 1200, 1000, 14
    for key, g in lm.DEFAULT_LAYOUT.items():
        x, y, pw, ph = lm.pixel_rect(g, w, h, gap)
        assert lm.snap_rect(x, y, pw, ph, w, h, gap) == g, key


def test_pixel_rects_tile_the_area_without_overlap():
    w, h, gap = 1200, 1000, 14
    a = lm.pixel_rect(lm.DEFAULT_LAYOUT["soru"], w, h, gap)
    b = lm.pixel_rect(lm.DEFAULT_LAYOUT["cizim"], w, h, gap)
    assert b[1] - (a[1] + a[3]) == gap          # vertical gap between soru and cizim
    c = lm.pixel_rect(lm.DEFAULT_LAYOUT["ipucu"], w, h, gap)
    assert c[0] - (a[0] + a[2]) == gap          # horizontal gap between soru and ipucu
    assert c[0] + c[2] == w                     # right edge flush


def test_snap_moves_to_nearest_cell():
    w, h, gap = 1200, 1000, 14
    cw, ch = lm.cell_size(w, h, gap)
    g = lm.snap_rect(int(cw * 0.4), int(ch * 2.6), int(cw * 3.2), int(ch * 2.4), w, h, gap)
    assert g == lm.PanelGeom(0, 3, 3, 2)


def test_json_round_trip_and_bad_input():
    text = lm.to_json(lm.DEFAULT_LAYOUT)
    assert json.loads(text)["webcam"] == {"col": 7, "row": 5, "col_span": 5, "row_span": 5}
    assert lm.from_json(text) == lm.DEFAULT_LAYOUT
    assert lm.from_json("not json") == lm.DEFAULT_LAYOUT
    partial = lm.from_json('{"soru": {"col": 2, "row": 2, "col_span": 4, "row_span": 4}, "x": 1}')
    assert partial["soru"] == lm.PanelGeom(2, 2, 4, 4) and partial["cizim"] == lm.DEFAULT_LAYOUT["cizim"]
    assert "x" not in partial


def test_load_save_layout(tmp_path):
    p = tmp_path / "duzen.json"
    assert lm.load_layout(p) == lm.DEFAULT_LAYOUT          # missing file -> defaults
    custom = dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 8, 2, 2))
    lm.save_layout(p, custom)
    assert lm.load_layout(p) == custom
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/test_layout_model.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement layout_model.py**

`src/matematigin_mantigi/core/layout_model.py`:
```python
"""OBS benzeri düzen modeli: paneller 12x10 ızgara biriminde konum/boyut taşır."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

GRID_COLS = 12
GRID_ROWS = 10
MIN_SPAN = 2
PANEL_KEYS = ("soru", "ipucu", "cizim", "webcam")


@dataclass(frozen=True)
class PanelGeom:
    col: int
    row: int
    col_span: int
    row_span: int


Layout = dict[str, PanelGeom]

DEFAULT_LAYOUT: Layout = {
    "soru": PanelGeom(0, 0, 7, 3),
    "ipucu": PanelGeom(7, 0, 5, 5),
    "cizim": PanelGeom(0, 3, 7, 7),
    "webcam": PanelGeom(7, 5, 5, 5),
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
    result: Layout = dict(DEFAULT_LAYOUT)
    try:
        raw = json.loads(text)
    except (TypeError, ValueError):
        return result
    if not isinstance(raw, dict):
        return result
    for key in PANEL_KEYS:
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
```

- [ ] **Step 4: Run the model tests**

```powershell
python -m pytest tests/test_layout_model.py -v
```
Expected: 7 PASS.

- [ ] **Step 5: Write the failing WorkArea tests**

`tests/test_work_area.py`:
```python
from PyQt6.QtCore import QPoint, Qt

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.work_area import WorkArea

FAM = FontFamilies("Arial", "Arial", False)


def make(qtbot):
    wa = WorkArea(FAM)
    qtbot.addWidget(wa)
    panels = {}
    for key, num, title in (("soru", "1", "Soru"), ("ipucu", "3", "Akıllı ipuçları"),
                            ("cizim", "2", "El çizimi"), ("webcam", "4", "Webcam")):
        p = PanelFrame(num, title, FAM)
        wa.add_panel(key, p)
        panels[key] = p
    wa.resize(1832, 1080)
    wa.show()
    return wa, panels


def test_default_layout_places_panels(qtbot):
    wa, panels = make(qtbot)
    soru, cizim, ipucu = panels["soru"].geometry(), panels["cizim"].geometry(), panels["ipucu"].geometry()
    assert soru.left() == 210 and soru.top() == 30                     # padding left/top
    assert cizim.top() - soru.bottom() - 1 == 14                       # gap
    assert ipucu.right() == wa.width() - 30 - 1                        # padding right
    assert abs(soru.width() / ipucu.width() - 7 / 5) < 0.02


def test_edit_mode_drag_moves_and_snaps(qtbot):
    wa, panels = make(qtbot)
    wa.set_edit_mode(True)
    webcam = panels["webcam"]
    start = webcam.geometry().topLeft() + QPoint(40, 20)      # inside header
    cw, ch = lm.cell_size(wa.width() - 240, wa.height() - 90, 14)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-int(cw * 2), 0))
    assert sig.args[0]["webcam"] == lm.PanelGeom(5, 5, 5, 5)


def test_edit_mode_resize_from_corner(qtbot):
    wa, panels = make(qtbot)
    wa.set_edit_mode(True)
    soru = panels["soru"]
    corner = soru.geometry().bottomRight() - QPoint(6, 6)
    cw, ch = lm.cell_size(wa.width() - 240, wa.height() - 90, 14)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=corner)
    qtbot.mouseMove(wa, corner + QPoint(0, int(ch)))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=corner + QPoint(0, int(ch)))
    assert sig.args[0]["soru"] == lm.PanelGeom(0, 0, 7, 4)


def test_no_drag_outside_edit_mode(qtbot):
    wa, panels = make(qtbot)
    before = panels["webcam"].geometry()
    start = before.topLeft() + QPoint(40, 20)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, start + QPoint(-300, 0))
    qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-300, 0))
    assert panels["webcam"].geometry() == before


def test_maximize_and_restore(qtbot):
    wa, panels = make(qtbot)
    wa.set_maximized("cizim")
    g = panels["cizim"].geometry()
    assert g.left() == 210 and g.right() == wa.width() - 30 - 1 and not panels["soru"].isVisible()
    wa.set_maximized(None)
    assert panels["soru"].isVisible() and panels["cizim"].geometry().top() > 30


def test_reset_layout_emits_default(qtbot):
    wa, _ = make(qtbot)
    wa.set_layout(dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 8, 2, 2)))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        wa.reset_layout()
    assert sig.args[0] == lm.DEFAULT_LAYOUT


def test_recording_rect_covers_whole_work_area(qtbot):
    wa, _ = make(qtbot)
    x, y, w, h, dpr = wa.recording_rect()
    assert (w, h) == (wa.width(), wa.height()) and dpr >= 1.0


def test_no_lines_outside_edit_mode(qtbot):
    wa, panels = make(qtbot)
    qtbot.waitExposed(wa)
    img = wa.grab().toImage()
    assert img.pixelColor(3, 300).name() == "#e9e7e2"          # çerçeve çizilmedi, sayfa rengi
    assert all(not p.border_visible for p in panels.values())
    wa.set_edit_mode(True)
    img = wa.grab().toImage()
    assert img.pixelColor(3, 300).name() == "#1c1b19"          # düzen modunda 10px çerçeve
    assert all(p.border_visible for p in panels.values())
    wa.set_edit_mode(False)
    assert all(not p.border_visible for p in panels.values())
```

- [ ] **Step 6: Run to verify failure**

```powershell
python -m pytest tests/test_work_area.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 7: Implement work_area.py**

`src/matematigin_mantigi/ui/work_area.py`:
```python
"""Çalışma alanı: 10px kayıt çerçevesi, marka plakası, OBS benzeri taşınabilir paneller."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies

GRIP = 18   # sağ-alt köşede boyutlandırma tutamağı (px)


class WorkArea(QWidget):
    layoutChanged = pyqtSignal(object)     # Layout dict
    editModeChanged = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self._panels: dict[str, PanelFrame] = {}
        self._layout: lm.Layout = dict(lm.DEFAULT_LAYOUT)
        self.edit_mode = False
        self.maximized: str | None = None
        self._drag: tuple[str, str, QPoint, QRect] | None = None   # key, "move"|"resize", press pos, start geom
        self.setMouseTracking(True)

        self.brand = QLabel("Matematiğin Mantığı", self)
        self.brand.setFont(theme.hand_font(fam, 38, 700))
        self.brand.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: {theme.INK};"
                                 f" border-top-left-radius: 14px; border-top-right-radius: 14px; padding: 6px 34px 10px;")
        self.brand.adjustSize()

        self.badge_slot = QWidget(self)          # Task 13 yerleştirir: RecordBadge
        self.badge_slot.hide()

        self.edit_bar = QWidget(self)
        self.edit_bar.setStyleSheet(f"background: {theme.INK}; border-radius: 8px;")
        bar = QHBoxLayout(self.edit_bar); bar.setContentsMargins(14, 6, 10, 6); bar.setSpacing(10)
        info = QLabel("DÜZEN MODU · başlıktan sürükle, sağ-alt köşeden boyutlandır, çift tık = büyüt")
        info.setFont(theme.font(fam, 10, 600, spacing_pct=108)); info.setStyleSheet(f"color: {theme.TOOLBAR_MUTED};")
        self.reset_button = QPushButton("Sıfırla"); self.reset_button.setObjectName("pill")
        self.done_button = QPushButton("Bitti"); self.done_button.setObjectName("accent")
        self.reset_button.clicked.connect(self.reset_layout)
        self.done_button.clicked.connect(lambda: self.set_edit_mode(False))
        bar.addWidget(info); bar.addWidget(self.reset_button); bar.addWidget(self.done_button)
        self.edit_bar.hide()

    # --- panels & layout ----------------------------------------------------
    def add_panel(self, key: str, panel: PanelFrame) -> None:
        panel.key = key
        panel.setParent(self)
        panel.headerDoubleClicked.connect(lambda k=key: self._toggle_maximized(k))
        self._panels[key] = panel
        panel.show()
        self.relayout()

    def layout(self) -> lm.Layout:                      # type: ignore[override]
        return dict(self._layout)

    def set_layout(self, layout: lm.Layout) -> None:
        self._layout = {k: lm.clamp(v) for k, v in layout.items() if k in lm.PANEL_KEYS}
        for k in lm.PANEL_KEYS:
            self._layout.setdefault(k, lm.DEFAULT_LAYOUT[k])
        self.relayout()

    def reset_layout(self) -> None:
        self.set_layout(dict(lm.DEFAULT_LAYOUT))
        self.layoutChanged.emit(self.layout())

    def set_maximized(self, key: str | None) -> None:
        self.maximized = key if key in self._panels else None
        self.relayout()

    def _toggle_maximized(self, key: str) -> None:
        self.set_maximized(None if self.maximized == key else key)

    def set_edit_mode(self, on: bool) -> None:
        if on == self.edit_mode:
            return
        self.edit_mode = on
        for panel in self._panels.values():
            panel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, on)
            panel.set_border_visible(on)          # çizgiler sadece düzen modunda
        self.edit_bar.setVisible(on)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        self.editModeChanged.emit(on)

    def inner_rect(self) -> QRect:
        t, r, b, l = theme.WORK_PADDING
        return QRect(l, t, self.width() - l - r, self.height() - t - b)

    def relayout(self) -> None:
        inner = self.inner_rect()
        for key, panel in self._panels.items():
            if self.maximized is not None:
                panel.setVisible(key == self.maximized)
                if key == self.maximized:
                    panel.setGeometry(inner)
                continue
            panel.setVisible(True)
            x, y, w, h = lm.pixel_rect(self._layout[key], inner.width(), inner.height(), theme.GRID_GAP)
            panel.setGeometry(inner.x() + x, inner.y() + y, w, h)
        self.brand.move((self.width() - self.brand.width()) // 2, self.height() - self.brand.height() - theme.FRAME_INSET)
        self.edit_bar.adjustSize()
        self.edit_bar.move((self.width() - self.edit_bar.width()) // 2, theme.FRAME_INSET + 4)
        self.edit_bar.raise_()
        self.badge_slot.move((self.width() - self.badge_slot.width()) // 2, theme.FRAME_INSET + 4)
        self.badge_slot.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def recording_rect(self) -> tuple[int, int, int, int, float]:
        g = self.mapToGlobal(QPoint(0, 0))
        return g.x(), g.y(), self.width(), self.height(), float(self.devicePixelRatioF())

    # --- edit mode mouse handling (children forward via childAt) -----------
    def _hit(self, pos: QPoint) -> tuple[str, str] | None:
        for key, panel in self._panels.items():
            if not panel.isVisible():
                continue
            geo = panel.geometry()
            if not geo.contains(pos):
                continue
            grip = QRect(geo.right() - GRIP, geo.bottom() - GRIP, GRIP + 1, GRIP + 1)
            if grip.contains(pos):
                return key, "resize"
            header = QRect(geo.x(), geo.y(), geo.width(), panel.header_widget.height() + theme.PANEL_BORDER)
            if header.contains(pos):
                return key, "move"
        return None

    def mousePressEvent(self, e: QMouseEvent):
        if self.edit_mode and e.button() == Qt.MouseButton.LeftButton and self.maximized is None:
            hit = self._hit(e.position().toPoint())
            if hit:
                key, mode = hit
                self._drag = (key, mode, e.position().toPoint(), QRect(self._panels[key].geometry()))
                self._panels[key].raise_()
                self.edit_bar.raise_()
                e.accept(); return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.position().toPoint()
        if self._drag is None:
            if self.edit_mode:
                hit = self._hit(pos)
                self.setCursor(Qt.CursorShape.SizeFDiagCursor if hit and hit[1] == "resize"
                               else Qt.CursorShape.SizeAllCursor if hit else Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(e); return
        key, mode, start, geo = self._drag
        d = pos - start
        panel = self._panels[key]
        if mode == "move":
            panel.move(geo.topLeft() + d)
        else:
            panel.resize(max(80, geo.width() + d.x()), max(60, geo.height() + d.y()))
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._drag is None:
            super().mouseReleaseEvent(e); return
        key, _mode, _start, _geo = self._drag
        self._drag = None
        inner = self.inner_rect()
        g = self._panels[key].geometry()
        self._layout[key] = lm.snap_rect(g.x() - inner.x(), g.y() - inner.y(), g.width(), g.height(),
                                         inner.width(), inner.height(), theme.GRID_GAP)
        self.relayout()
        self.layoutChanged.emit(self.layout())
        e.accept()

    def _forward_child_press(self, panel: PanelFrame, local: QPoint) -> None:
        """PanelFrame.headerPressed -> düzen modunda sürüklemeyi başlat."""
        if not self.edit_mode or self.maximized is not None:
            return
        pos = panel.mapTo(self, panel.header_widget.mapTo(panel, local))
        self._drag = (panel.key, "move", pos, QRect(panel.geometry()))
        panel.raise_(); self.edit_bar.raise_()

    # --- painting -----------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.PAGE))
        if not self.edit_mode:
            p.end()
            return                                   # normal kullanımda hiçbir çizgi yok
        p.setPen(QPen(QColor(theme.INK), theme.FRAME_INSET))
        half = theme.FRAME_INSET / 2
        p.drawRect(QRectF(half, half, self.width() - theme.FRAME_INSET, self.height() - theme.FRAME_INSET))
        if self.maximized is None:
            inner = self.inner_rect()
            cw, ch = lm.cell_size(inner.width(), inner.height(), theme.GRID_GAP)
            pen = QPen(QColor(theme.ACCENT)); pen.setStyle(Qt.PenStyle.DotLine); p.setPen(pen)
            for c in range(1, lm.GRID_COLS):
                x = inner.x() + round(c * (cw + theme.GRID_GAP) - theme.GRID_GAP / 2)
                p.drawLine(x, inner.top(), x, inner.bottom())
            for r in range(1, lm.GRID_ROWS):
                y = inner.y() + round(r * (ch + theme.GRID_GAP) - theme.GRID_GAP / 2)
                p.drawLine(inner.left(), y, inner.right(), y)
            p.setPen(QPen(QColor(theme.ACCENT), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for panel in self._panels.values():
                geo = panel.geometry()
                p.drawRoundedRect(QRectF(geo).adjusted(1, 1, -1, -1), theme.PANEL_RADIUS, theme.PANEL_RADIUS)
                p.fillRect(QRect(geo.right() - GRIP, geo.bottom() - GRIP, GRIP, GRIP), QColor(theme.ACCENT))
        p.end()
```

Mouse events over a child panel are delivered to the child, not to `WorkArea`. Two paths make the drag work: `PanelFrame.headerPressed` is connected in `add_panel` to `_forward_child_press` (so a header press starts a move), and in edit mode `set_edit_mode` makes the panels transparent for mouse events so `WorkArea` receives the press/move/release itself. With that attribute on, `WorkArea.mousePressEvent` handles the press directly (`_hit`), so the `headerPressed` route is only used when the attribute is off; keep the connection anyway (it costs nothing and is the hook for a later "lock only some panels" feature). Add to `add_panel`:

```python
        panel.headerPressed.connect(lambda pt, p=panel: self._forward_child_press(p, pt))
```

The `layout()` method shadows `QWidget.layout()`; `WorkArea` never installs a Qt layout (it positions children itself), so this is safe, but keep the `type: ignore` comment.

- [ ] **Step 8: Show the shell from app.py**

Replace `build_window` in `src/matematigin_mantigi/app.py`:
```python
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.work_area import WorkArea


def build_window(args: argparse.Namespace, fam: theme.FontFamilies | None = None) -> QMainWindow:
    fam = fam or theme.FontFamilies("sans-serif", "cursive", False)
    win = QMainWindow()
    win.setWindowTitle("Matematiğin Mantığı")
    central = QWidget(); row = QHBoxLayout(central); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
    toolbar = ToolBar(fam); work = WorkArea(fam)
    for key, num, title in (("soru", "1", "Soru"), ("ipucu", "3", "Akıllı ipuçları"),
                            ("cizim", "2", "El çizimi"), ("webcam", "4", "Webcam")):
        work.add_panel(key, PanelFrame(num, title, fam))
    layout_path = Path.cwd() / "duzen.json"
    work.set_layout(lm.load_layout(layout_path))
    work.layoutChanged.connect(lambda lay: lm.save_layout(layout_path, lay))
    toolbar.layoutEditToggled.connect(work.set_edit_mode)
    work.editModeChanged.connect(toolbar.set_layout_edit)
    row.addWidget(toolbar); row.addWidget(work, 1)
    win.setCentralWidget(central)
    win.resize(1920, 1080)
    return win
```
Add `from pathlib import Path` at the top. (Task 11 replaces this function with `MainWindow`; the shell exists so the app is visually checkable now.)

- [ ] **Step 9: Run tests, then look at the window**

```powershell
python -m pytest tests/test_work_area.py tests/test_toolbar.py -v
python -m matematigin_mantigi
```
Expected: 8 PASS. The window shows the dark toolbar, the plain page (no frame, no panel borders), four numbered white panels in the mockup arrangement, and the brand plate. Click "⧉ Düzen": the 10 px frame, the dotted grid, ink panel borders, accent outlines and corner grips appear; drag the webcam panel, it snaps; "Bitti" exits and every line disappears again; `duzen.json` appears in the folder; restart keeps the layout; "Sıfırla" restores the mockup.

- [ ] **Step 10: Commit**

```powershell
git add -A
git commit -m "feat: OBS-style movable/resizable panel layout with snapping and duzen.json persistence

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Stroke math, DrawingCanvas (tablet + mouse), CanvasPanel (region 2)

**Files:**
- Create: `src/matematigin_mantigi/core/stroke.py`, `src/matematigin_mantigi/ui/canvas.py`, `src/matematigin_mantigi/ui/canvas_panel.py`, `tests/test_stroke.py`, `tests/test_canvas.py`
- Modify: `src/matematigin_mantigi/app.py` (use `CanvasPanel` for "cizim" and wire toolbar → canvas)

**Interfaces:**
- Consumes: `core.models.Tool`, `ui.panel.PanelFrame`, `ui.theme.*`.
- Produces:
  - `stroke.MOUSE_PRESSURE = 0.5`, `stroke.pressure_width(base: float, pressure: float) -> float`, `stroke.eraser_diameter(base: int) -> int`, `stroke.pen_cursor_diameter(base: int) -> int`.
  - `canvas.DrawingCanvas(parent=None)` signals `strokeStarted()`, `strokeFinished()`, `historyChanged(bool, bool)` (can_undo, is_empty), `pressureChanged(float)`, `inputSourceChanged(str)`; methods `set_tool(Tool)`, `set_color(QColor)`, `set_base_width(int)`, `begin_stroke(QPointF, float, eraser_tip=False)`, `extend_stroke(QPointF, float)`, `end_stroke()`, `undo()`, `clear()`, `can_undo() -> bool`, `is_empty() -> bool`, `strokes_image() -> QImage`, `snapshot_image() -> QImage`; attributes `tool`, `color`, `base_width`; `MAX_UNDO = 30`.
  - `canvas_panel.CanvasPanel(fam, parent=None)` with `.canvas: DrawingCanvas`, `set_question_label(str)`, `set_status(tool_label: str, width_px: int, pressure_text: str)`, `set_empty_hint_visible(bool)`.

- [ ] **Step 1: Write the failing stroke tests**

`tests/test_stroke.py`:
```python
import pytest

from matematigin_mantigi.core import stroke


@pytest.mark.parametrize("base,p,expected", [(4, 0.0, 2.4), (4, 1.0, 7.2), (4, 0.5, 4.8), (8, 0.25, 7.2)])
def test_pressure_width(base, p, expected):
    assert stroke.pressure_width(base, p) == pytest.approx(expected)


def test_pressure_is_clamped():
    assert stroke.pressure_width(4, -1.0) == pytest.approx(2.4)
    assert stroke.pressure_width(4, 3.0) == pytest.approx(7.2)


def test_eraser_and_cursor_diameters():
    assert [stroke.eraser_diameter(b) for b in (2, 4, 8)] == [20, 34, 68]
    assert [stroke.pen_cursor_diameter(b) for b in (2, 4, 8)] == [14, 18, 26]
    assert stroke.eraser_diameter(100) == 80 and stroke.pen_cursor_diameter(100) == 40
```

- [ ] **Step 2: Implement stroke.py and run**

`src/matematigin_mantigi/core/stroke.py`:
```python
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
```

```powershell
python -m pytest tests/test_stroke.py -v
```
Expected: 7 PASS.

- [ ] **Step 3: Write the failing canvas tests**

`tests/test_canvas.py`:
```python
from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QColor, QInputDevice, QPointingDevice, QTabletEvent
from PyQt6.QtWidgets import QApplication

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.ui.canvas import DrawingCanvas

STYLUS = QPointingDevice("test-stylus", 1, QInputDevice.DeviceType.Stylus,
                         QPointingDevice.PointerType.Pen,
                         QInputDevice.Capability.Position | QInputDevice.Capability.Pressure, 1, 1)


def make(qtbot):
    c = DrawingCanvas()
    qtbot.addWidget(c)
    c.resize(400, 300)
    c.show()
    qtbot.waitExposed(c)
    return c


def alpha_at(c, x, y):
    return c.strokes_image().pixelColor(x, y).alpha()


def draw_diagonal(c, pressure=0.5):
    c.begin_stroke(QPointF(50, 50), pressure)
    c.extend_stroke(QPointF(150, 150), pressure)
    c.end_stroke()


def test_starts_empty(qtbot):
    c = make(qtbot)
    assert c.is_empty() and not c.can_undo() and alpha_at(c, 100, 100) == 0


def test_pen_stroke_paints_pixels_and_enables_undo(qtbot):
    c = make(qtbot)
    with qtbot.waitSignal(c.historyChanged) as sig:
        draw_diagonal(c)
    assert alpha_at(c, 100, 100) > 0 and alpha_at(c, 300, 20) == 0
    assert sig.args == [True, False]
    assert not c.is_empty()


def test_pressure_changes_width(qtbot):
    thin, thick = make(qtbot), make(qtbot)
    thin.set_base_width(8); thick.set_base_width(8)
    thin.begin_stroke(QPointF(50, 100), 0.0); thin.extend_stroke(QPointF(350, 100), 0.0); thin.end_stroke()
    thick.begin_stroke(QPointF(50, 100), 1.0); thick.extend_stroke(QPointF(350, 100), 1.0); thick.end_stroke()
    assert alpha_at(thin, 200, 104) == 0 and alpha_at(thick, 200, 104) > 0


def test_undo_restores_previous_bitmap(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.undo()
    assert alpha_at(c, 100, 100) == 0 and c.is_empty() and not c.can_undo()


def test_undo_depth_is_30(qtbot):
    c = make(qtbot)
    for i in range(31):
        c.begin_stroke(QPointF(10 + i * 5, 10), 0.5); c.end_stroke()
    for _ in range(30):
        c.undo()
    assert not c.can_undo() and alpha_at(c, 10, 10) > 0        # first stroke survives


def test_eraser_clears(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.set_tool(Tool.ERASER)
    draw_diagonal(c)
    assert alpha_at(c, 100, 100) == 0


def test_eraser_tip_overrides_tool_for_one_stroke(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.begin_stroke(QPointF(50, 50), 0.5, eraser_tip=True); c.extend_stroke(QPointF(150, 150), 0.5); c.end_stroke()
    assert alpha_at(c, 100, 100) == 0 and c.tool == Tool.PEN


def test_laser_does_not_touch_strokes_layer(qtbot):
    c = make(qtbot)
    c.set_tool(Tool.LASER)
    draw_diagonal(c)
    assert alpha_at(c, 100, 100) == 0 and c.is_empty()


def test_clear_is_undoable(qtbot):
    c = make(qtbot)
    draw_diagonal(c)
    c.clear()
    assert c.is_empty()
    c.undo()
    assert alpha_at(c, 100, 100) > 0


def test_color_is_used(qtbot):
    c = make(qtbot)
    c.set_color(QColor("#c8322b")); c.set_base_width(8)
    c.begin_stroke(QPointF(100, 100), 1.0); c.end_stroke()
    px = c.strokes_image().pixelColor(100, 100)
    assert (px.red(), px.green(), px.blue()) == (0xc8, 0x32, 0x2b)


def test_mouse_events_draw(qtbot):
    c = make(qtbot)
    qtbot.mousePress(c, Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
    qtbot.mouseMove(c, QPoint(150, 150))
    qtbot.mouseRelease(c, Qt.MouseButton.LeftButton, pos=QPoint(150, 150))
    assert alpha_at(c, 100, 100) > 0


def tablet(widget, etype, x, y, pressure):
    pressed = etype != QEvent.Type.TabletRelease
    button = Qt.MouseButton.LeftButton if etype != QEvent.Type.TabletMove else Qt.MouseButton.NoButton
    buttons = Qt.MouseButton.LeftButton if pressed else Qt.MouseButton.NoButton
    ev = QTabletEvent(etype, STYLUS, QPointF(x, y), QPointF(widget.mapToGlobal(QPoint(x, y))),
                      pressure, 0.0, 0.0, 0.0, 0.0, 0.0, Qt.KeyboardModifier.NoModifier, button, buttons)
    QApplication.sendEvent(widget, ev)
    return ev.isAccepted()


def test_tablet_events_draw_and_are_accepted(qtbot):
    c = make(qtbot)
    assert tablet(c, QEvent.Type.TabletPress, 50, 50, 0.9)
    assert tablet(c, QEvent.Type.TabletMove, 150, 150, 0.9)
    assert tablet(c, QEvent.Type.TabletRelease, 150, 150, 0.0)
    assert alpha_at(c, 100, 100) > 0


def test_mouse_press_ignored_while_stylus_down(qtbot):
    c = make(qtbot)
    tablet(c, QEvent.Type.TabletPress, 50, 50, 0.9)
    qtbot.mousePress(c, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    tablet(c, QEvent.Type.TabletRelease, 50, 50, 0.0)
    assert len(c._undo) == 1        # only one stroke was started


def test_snapshot_has_white_background(qtbot):
    c = make(qtbot)
    img = c.snapshot_image()
    assert img.pixelColor(5, 5) == QColor("#ffffff")
```

If the `QPointingDevice(...)` constructor signature differs on the installed PyQt6 (it takes `name, systemId, deviceType, pointerType, capabilities, maxPoints, buttonCount`), adjust the positional arguments in `STYLUS` to match; check with `help(QPointingDevice.__init__)`.

- [ ] **Step 4: Run to verify failure**

```powershell
python -m pytest tests/test_canvas.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 5: Implement canvas.py**

`src/matematigin_mantigi/ui/canvas.py`:
```python
"""Bölge 2 çizim yüzeyi: tablet basıncı, fare geri dönüşü, silgi, lazer, 30 adım geri al."""
from __future__ import annotations

from collections import deque

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap,
                         QPointingDevice, QResizeEvent, QTabletEvent)
from PyQt6.QtWidgets import QWidget

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.core.stroke import LASER_COLOR, MOUSE_PRESSURE, eraser_diameter, pressure_width
from matematigin_mantigi.ui import theme


def _grown(old: QImage, size: QSize, dpr: float) -> QImage:
    new = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    new.setDevicePixelRatio(dpr)
    new.fill(Qt.GlobalColor.transparent)
    if not old.isNull():
        p = QPainter(new); p.drawImage(0, 0, old); p.end()
    return new


def _dot_tile(dpr: float) -> QPixmap:
    s = theme.DOT_SPACING
    pm = QPixmap(int(s * dpr), int(s * dpr)); pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(theme.DOT))
    p.drawEllipse(QPointF(s / 2, s / 2), 1.0, 1.0); p.end()
    return pm


class DrawingCanvas(QWidget):
    strokeStarted = pyqtSignal()
    strokeFinished = pyqtSignal()
    historyChanged = pyqtSignal(bool, bool)     # can_undo, is_empty
    pressureChanged = pyqtSignal(float)
    inputSourceChanged = pyqtSignal(str)        # "tablet" | "mouse"
    MAX_UNDO = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabletTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.tool = Tool.PEN
        self.color = QColor(theme.INK)
        self.base_width = 4
        self._strokes = QImage()
        self._overlay = QImage()
        self._undo: deque[tuple[QImage, int]] = deque(maxlen=self.MAX_UNDO)
        self._stroke_count = 0
        self._tablet_down = False
        self._mouse_down = False
        self._last: QPointF | None = None
        self._last_p = MOUSE_PRESSURE
        self._active_tool = Tool.PEN
        self._tile = _dot_tile(1.0)
        self._ensure_layers(QSize(1, 1))

    # --- public state --------------------------------------------------------
    def set_tool(self, t: Tool) -> None: self.tool = t
    def set_color(self, c: QColor) -> None: self.color = QColor(c)
    def set_base_width(self, w: int) -> None: self.base_width = int(w)
    def can_undo(self) -> bool: return len(self._undo) > 0
    def is_empty(self) -> bool: return self._stroke_count == 0
    def strokes_image(self) -> QImage: return self._strokes

    def snapshot_image(self) -> QImage:
        out = QImage(self._strokes.size(), QImage.Format.Format_RGB32)
        out.setDevicePixelRatio(self._strokes.devicePixelRatio())
        out.fill(Qt.GlobalColor.white)
        p = QPainter(out); p.drawImage(0, 0, self._strokes); p.end()
        return out

    # --- stroke API (used by tablet, mouse and tests) -------------------------
    def begin_stroke(self, pos: QPointF, pressure: float, eraser_tip: bool = False) -> None:
        self._active_tool = Tool.ERASER if eraser_tip else self.tool
        if self._active_tool in (Tool.PEN, Tool.ERASER):
            self._undo.append((self._strokes.copy(), self._stroke_count))
            self._stroke_count += 1
        self._last, self._last_p = pos, pressure
        self._draw_segment(pos, pos, pressure)
        self.strokeStarted.emit()

    def extend_stroke(self, pos: QPointF, pressure: float) -> None:
        if self._last is None:
            return
        self._draw_segment(self._last, pos, (self._last_p + pressure) / 2)
        self._last, self._last_p = pos, pressure

    def end_stroke(self) -> None:
        self._last = None
        if self._active_tool == Tool.LASER:
            self._overlay.fill(Qt.GlobalColor.transparent)
            self.update()
        self.strokeFinished.emit()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def undo(self) -> None:
        if not self._undo:
            return
        self._strokes, self._stroke_count = self._undo.pop()
        self.update()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def clear(self) -> None:
        if self.is_empty():
            return
        self._undo.append((self._strokes.copy(), self._stroke_count))
        self._strokes.fill(Qt.GlobalColor.transparent)
        self._stroke_count = 0
        self.update()
        self.historyChanged.emit(self.can_undo(), True)

    # --- painting ------------------------------------------------------------
    def _draw_segment(self, a: QPointF, b: QPointF, pressure: float) -> None:
        tool = self._active_tool
        if tool in (Tool.TEXT, Tool.SHAPE):       # bu sürümde arayüz taslağı
            return
        target = self._overlay if tool == Tool.LASER else self._strokes
        p = QPainter(target)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if tool == Tool.ERASER:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            width = float(eraser_diameter(self.base_width))
            color = QColor(0, 0, 0, 255)
        else:
            width = pressure_width(self.base_width, pressure)
            color = QColor(LASER_COLOR) if tool == Tool.LASER else self.color
        p.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(a, b)
        p.end()
        m = int(width) + 2
        self.update(QRectF(a, b).normalized().toAlignedRect().adjusted(-m, -m, m, m))

    def _ensure_layers(self, logical: QSize) -> None:
        dpr = self.devicePixelRatioF()
        need = QSize(max(1, int(logical.width() * dpr)), max(1, int(logical.height() * dpr)))
        if (self._strokes.isNull() or self._strokes.width() < need.width()
                or self._strokes.height() < need.height()):
            self._strokes = _grown(self._strokes, need, dpr)
            self._overlay = _grown(self._overlay, need, dpr)
        if self._tile.devicePixelRatio() != dpr:
            self._tile = _dot_tile(dpr)

    def resizeEvent(self, e: QResizeEvent) -> None:
        self._ensure_layers(e.size())
        super().resizeEvent(e)

    def paintEvent(self, e: QPaintEvent) -> None:
        p = QPainter(self)
        p.fillRect(e.rect(), QColor(theme.PANEL))
        p.fillRect(e.rect(), QBrush(self._tile))
        p.drawImage(0, 0, self._strokes)
        p.drawImage(0, 0, self._overlay)
        p.end()

    # --- tablet path -----------------------------------------------------------
    def tabletEvent(self, e: QTabletEvent) -> None:
        t = e.type()
        eraser_tip = e.pointerType() == QPointingDevice.PointerType.Eraser
        if t == QEvent.Type.TabletPress:
            if e.button() == Qt.MouseButton.LeftButton:
                self._tablet_down = True
                self.inputSourceChanged.emit("tablet")
                self.begin_stroke(e.position(), e.pressure(), eraser_tip)
        elif t == QEvent.Type.TabletMove:
            self.pressureChanged.emit(e.pressure())
            if self._tablet_down:
                self.extend_stroke(e.position(), e.pressure())
        elif t == QEvent.Type.TabletRelease:
            if self._tablet_down:
                self._tablet_down = False
                self.end_stroke()
        else:
            e.ignore()
            return
        e.accept()      # kabul edilen tablet olayı için Qt fare olayı üretmez

    # --- mouse fallback ---------------------------------------------------------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if self._tablet_down or e.button() != Qt.MouseButton.LeftButton:
            e.ignore(); return
        self._mouse_down = True
        self.inputSourceChanged.emit("mouse")
        self.begin_stroke(e.position(), MOUSE_PRESSURE)
        e.accept()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if not self._mouse_down:
            e.ignore(); return
        self.extend_stroke(e.position(), MOUSE_PRESSURE)
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if not self._mouse_down:
            e.ignore(); return
        self._mouse_down = False
        self.end_stroke()
        e.accept()
```

- [ ] **Step 6: Implement canvas_panel.py**

`src/matematigin_mantigi/ui/canvas_panel.py`:
```python
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel

from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.canvas import DrawingCanvas
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies


class CanvasPanel(PanelFrame):
    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__("2", "El çizimi", fam, parent)
        self.question_label = QLabel("")
        self.question_label.setFont(theme.font(fam, 11, 500))
        self.question_label.setStyleSheet(f"color: {theme.MUTED};")
        self.header.insertWidget(2, self.question_label)

        self.status_label = QLabel("Araç: Kalem · Kalınlık: 4 px · Basınç: XP-Pen")
        self.status_label.setFont(theme.font(fam, 10, 500))
        self.status_label.setStyleSheet(f"color: {theme.MUTED};")
        self.header.addWidget(self.status_label)

        self.body.setContentsMargins(0, 0, 0, 0)
        self.canvas = DrawingCanvas(self)
        self.body.addWidget(self.canvas, 1)

        self.empty_hint = QLabel("Buraya çizin — kalem basıncı kalınlığı değiştirir", self.canvas)
        self.empty_hint.setFont(theme.hand_font(fam, 22, 500))
        self.empty_hint.setStyleSheet(f"color: {theme.HINT_EMPTY}; background: transparent;")
        self.empty_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.empty_hint.adjustSize()
        self.canvas.historyChanged.connect(lambda _u, empty: self.set_empty_hint_visible(empty))

    def set_question_label(self, text: str) -> None:
        self.question_label.setText(text)

    def set_status(self, tool_label: str, width_px: int, pressure_text: str) -> None:
        self.status_label.setText(f"Araç: {tool_label} · Kalınlık: {width_px} px · Basınç: {pressure_text}")

    def set_empty_hint_visible(self, on: bool) -> None:
        self.empty_hint.setVisible(on)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.empty_hint.move((self.canvas.width() - self.empty_hint.width()) // 2,
                             (self.canvas.height() - self.empty_hint.height()) // 2)
```

- [ ] **Step 7: Wire the canvas into the shell (app.py)**

In `build_window`, replace the "cizim" `PanelFrame` with a `CanvasPanel` and connect the toolbar:
```python
from matematigin_mantigi.core.models import TOOL_META
from matematigin_mantigi.ui.canvas_panel import CanvasPanel
from PyQt6.QtGui import QColor

    canvas_panel = CanvasPanel(fam)
    work.add_panel("cizim", canvas_panel)          # instead of PanelFrame("2", ...)
    canvas = canvas_panel.canvas
    toolbar.toolSelected.connect(canvas.set_tool)
    toolbar.colorSelected.connect(lambda hx: canvas.set_color(QColor(hx)))
    toolbar.widthSelected.connect(canvas.set_base_width)
    toolbar.undoRequested.connect(canvas.undo)
    toolbar.clearRequested.connect(canvas.clear)
    canvas.historyChanged.connect(lambda can_undo, _e: toolbar.set_undo_enabled(can_undo))
    toolbar.toolSelected.connect(lambda t: canvas_panel.set_status(TOOL_META[t][0], canvas.base_width, "XP-Pen"))
```

- [ ] **Step 8: Run tests and try it by hand**

```powershell
python -m pytest tests/test_canvas.py tests/test_stroke.py -v
python -m matematigin_mantigi
```
Expected: all PASS. In the app: mouse draws at constant width; with a stylus, width follows pressure; eraser erases; laser leaves no trace; undo/clear work; the hint text disappears after the first stroke.

- [ ] **Step 9: Commit**

```powershell
git add -A
git commit -m "feat: pressure-sensitive DrawingCanvas with eraser, laser, undo; CanvasPanel

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Tool cursors

**Files:**
- Create: `src/matematigin_mantigi/ui/cursors.py`, `tests/test_cursors.py`
- Modify: `src/matematigin_mantigi/app.py` (refresh cursor on tool/color/width change)

**Interfaces:**
- Consumes: `core.stroke.pen_cursor_diameter`, `eraser_diameter`; `core.models.Tool`.
- Produces: `cursors.pen_cursor(color: QColor, base_width: int, dpr: float = 1.0) -> QCursor`, `eraser_cursor(base_width, dpr=1.0)`, `laser_cursor(dpr=1.0)`, `text_cursor()`, `shape_cursor()`, `cursor_for(tool: Tool, color: QColor, base_width: int, dpr: float = 1.0) -> QCursor`; constants `CURSOR_MARGIN = 1`, `LASER_DOT = 14`, `LASER_HALO = 4`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cursors.py`:
```python
from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtGui import QColor

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.ui import cursors


def test_pen_cursor_size_and_hotspot(qapp):
    c = cursors.pen_cursor(QColor("#c8322b"), 4)
    assert c.pixmap().size() == QSize(20, 20) and c.hotSpot() == QPoint(10, 10)
    assert cursors.pen_cursor(QColor("#000"), 8).pixmap().size() == QSize(28, 28)


def test_pen_cursor_uses_color(qapp):
    img = cursors.pen_cursor(QColor("#2456b8"), 8).pixmap().toImage()
    px = img.pixelColor(14, 14)
    assert (px.red(), px.green(), px.blue()) == (0x24, 0x56, 0xb8)


def test_eraser_cursor_scales(qapp):
    assert cursors.eraser_cursor(4).pixmap().size() == QSize(36, 36)
    assert cursors.eraser_cursor(8).pixmap().size() == QSize(70, 70)


def test_laser_text_shape(qapp):
    assert cursors.laser_cursor().pixmap().size() == QSize(24, 24)
    assert cursors.text_cursor().shape() == Qt.CursorShape.IBeamCursor
    assert cursors.shape_cursor().shape() == Qt.CursorShape.CrossCursor


def test_retina_doubles_pixmap_keeps_hotspot(qapp):
    c = cursors.pen_cursor(QColor("#000"), 4, dpr=2.0)
    assert c.pixmap().size() == QSize(40, 40) and c.hotSpot() == QPoint(10, 10)


def test_cursor_for_dispatch(qapp):
    for tool in Tool:
        assert cursors.cursor_for(tool, QColor("#000"), 4) is not None
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/test_cursors.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement cursors.py**

`src/matematigin_mantigi/ui/cursors.py`:
```python
"""Araca ve renge göre özel imleçler: kalem = renkli nokta, silgi = kesikli kare, lazer = kırmızı halka."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QCursor, QPainter, QPen, QPixmap

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.core.stroke import eraser_diameter, pen_cursor_diameter
from matematigin_mantigi.ui import theme

CURSOR_MARGIN = 1
ERASER_DASH_PX = 2
LASER_DOT = 14
LASER_HALO = 4


def _blank(size_px: int, dpr: float) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(int(size_px * dpr), int(size_px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p


def pen_cursor(color: QColor, base_width: int, dpr: float = 1.0) -> QCursor:
    d = pen_cursor_diameter(base_width)
    size = d + 2 * CURSOR_MARGIN
    pm, p = _blank(size, dpr)
    c = size / 2
    p.setPen(QPen(QColor("#ffffff"), 2))
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(QPointF(c, c), d / 2 - 1, d / 2 - 1)
    p.end()
    return QCursor(pm, size // 2, size // 2)


def eraser_cursor(base_width: int, dpr: float = 1.0) -> QCursor:
    d = eraser_diameter(base_width)
    size = d + 2 * CURSOR_MARGIN
    pm, p = _blank(size, dpr)
    p.setPen(QPen(QColor(theme.INK), ERASER_DASH_PX, Qt.PenStyle.DashLine))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), 3, 3)
    p.end()
    return QCursor(pm, size // 2, size // 2)


def laser_cursor(dpr: float = 1.0) -> QCursor:
    size = LASER_DOT + 2 * LASER_HALO + 2 * CURSOR_MARGIN
    pm, p = _blank(size, dpr)
    c = size / 2
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 59, 48, 77)); p.drawEllipse(QPointF(c, c), size / 2 - 1, size / 2 - 1)
    p.setBrush(QColor(theme.LASER));     p.drawEllipse(QPointF(c, c), LASER_DOT / 2, LASER_DOT / 2)
    p.end()
    return QCursor(pm, size // 2, size // 2)


def text_cursor() -> QCursor:
    return QCursor(Qt.CursorShape.IBeamCursor)


def shape_cursor() -> QCursor:
    return QCursor(Qt.CursorShape.CrossCursor)


def cursor_for(tool: Tool, color: QColor, base_width: int, dpr: float = 1.0) -> QCursor:
    if tool == Tool.PEN:
        return pen_cursor(color, base_width, dpr)
    if tool == Tool.ERASER:
        return eraser_cursor(base_width, dpr)
    if tool == Tool.LASER:
        return laser_cursor(dpr)
    if tool == Tool.TEXT:
        return text_cursor()
    return shape_cursor()
```

- [ ] **Step 4: Refresh the cursor from app.py**

Add to `build_window` after the canvas wiring:
```python
from matematigin_mantigi.ui.cursors import cursor_for

    def refresh_cursor(*_):
        canvas.setCursor(cursor_for(canvas.tool, canvas.color, canvas.base_width, canvas.devicePixelRatioF()))
    toolbar.toolSelected.connect(refresh_cursor)
    toolbar.colorSelected.connect(refresh_cursor)
    toolbar.widthSelected.connect(refresh_cursor)
    refresh_cursor()
```

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_cursors.py -v
git add -A
git commit -m "feat: tool-specific cursors that follow color and thickness

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 6 PASS. In the app, switching to the eraser shows a dashed square that grows with the thickness preset; picking red shows a red dot cursor.

---

### Task 7: Chroma key core (numpy/cv2, no Qt)

**Files:**
- Create: `src/matematigin_mantigi/core/chroma_key.py`, `tests/test_chroma_key.py`

**Interfaces:**
- Produces: `chroma_key.ChromaParams(tolerance: int = 38, feather_px: int = 2, spill: float = 0.60, key_hue: int = 60, bg_bgr: tuple[int, int, int] = (243, 246, 247))` frozen dataclass; `green_mask(bgr: np.ndarray, p: ChromaParams) -> np.ndarray` (float32 HxW, 1 = keep); `suppress_spill(bgr, alpha, strength: float) -> np.ndarray`; `composite(bgr, alpha, bg_bgr) -> np.ndarray`; `apply_chroma_key(bgr, p) -> np.ndarray` (uint8 HxWx3, input never mutated).

- [ ] **Step 1: Write the failing tests**

`tests/test_chroma_key.py`:
```python
import numpy as np

from matematigin_mantigi.core.chroma_key import (ChromaParams, apply_chroma_key, composite,
                                                 green_mask, suppress_spill)


def scene(w=320, h=240):
    img = np.empty((h, w, 3), np.uint8)
    img[:] = (30, 200, 40)                 # yeşil perde (BGR), H≈58 S≈216 V=200
    img[60:180, 80:240] = (20, 20, 220)    # kırmızı kutu = öğretmen
    return img


def test_defaults_match_brief():
    p = ChromaParams()
    assert (p.tolerance, p.feather_px, p.spill, p.bg_bgr) == (38, 2, 0.60, (243, 246, 247))


def test_mask_is_0_on_green_and_1_on_subject():
    a = green_mask(scene(), ChromaParams(feather_px=0))
    assert a.shape == (240, 320) and a.dtype == np.float32
    assert a[10, 10] == 0.0 and a[120, 160] == 1.0


def test_green_becomes_panel_background_and_subject_survives():
    out = apply_chroma_key(scene(), ChromaParams())
    assert out.dtype == np.uint8 and out.shape == (240, 320, 3)
    assert np.allclose(out[10, 10], (243, 246, 247), atol=2)
    assert np.allclose(out[120, 160], (20, 20, 220), atol=2)


def test_feather_softens_edge():
    hard = green_mask(scene(), ChromaParams(feather_px=0))
    soft = green_mask(scene(), ChromaParams(feather_px=3))
    assert set(np.unique(hard)) <= {0.0, 1.0}
    edge = soft[54:66, 160]
    assert ((edge > 0.05) & (edge < 0.95)).any()


def test_spill_pulls_green_cast_down():
    px = np.full((4, 4, 3), (120, 180, 120), np.uint8)
    out = suppress_spill(px, np.ones((4, 4), np.float32), 0.6)
    assert tuple(out[0, 0]) == (120, 144, 120)          # 180 - 0.6 * 60


def test_composite_blends_half():
    fg = np.full((2, 2, 3), (0, 0, 0), np.uint8)
    out = composite(fg, np.full((2, 2), 0.5, np.float32), (200, 100, 0))
    assert tuple(out[0, 0]) == (100, 50, 0)


def test_tolerance_is_monotonic():
    grad = scene()
    grad[..., 1] = np.linspace(60, 255, grad.shape[1], dtype=np.uint8)[None, :]
    keyed = [(green_mask(grad, ChromaParams(tolerance=t, feather_px=0)) < 0.5).sum()
             for t in (0, 20, 38, 60, 100)]
    assert keyed == sorted(keyed)


def test_input_not_mutated():
    src = scene(); before = src.copy()
    apply_chroma_key(src, ChromaParams())
    assert (src == before).all()
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/test_chroma_key.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement chroma_key.py**

`src/matematigin_mantigi/core/chroma_key.py`:
```python
"""Program içi yeşil perde: HSV tabanlı yumuşak anahtar, kenar yumuşatma, dökülme bastırma."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ChromaParams:
    tolerance: int = 38                                  # 0..100
    feather_px: int = 2
    spill: float = 0.60                                  # 0..1
    key_hue: int = 60                                    # OpenCV hue (0..179); saf yeşil = 60
    bg_bgr: tuple[int, int, int] = (243, 246, 247)       # #f7f6f3


def green_mask(bgr: np.ndarray, p: ChromaParams) -> np.ndarray:
    """Ön plan alfası [0,1] float32. Ton uzaklığına göre yumuşak anahtar; doygunluk ve parlaklıkla kapılanır."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    t = max(0.0, min(1.0, p.tolerance / 100.0))
    hue_r = 8.0 + 30.0 * t
    dh = np.abs(h - float(p.key_hue))
    dh = np.minimum(dh, 180.0 - dh)
    hue_score = np.clip(1.0 - (dh - 0.6 * hue_r) / (0.4 * hue_r), 0.0, 1.0)
    s_min = 200.0 - 160.0 * t
    v_min = 110.0 - 80.0 * t
    bg = hue_score * np.clip((s - s_min) / 40.0, 0.0, 1.0) * np.clip((v - v_min) / 40.0, 0.0, 1.0)
    alpha = (1.0 - bg).astype(np.float32)
    if p.feather_px > 0:
        alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8))
        k = 2 * int(p.feather_px) + 1
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)
    return alpha.astype(np.float32)


def suppress_spill(bgr: np.ndarray, alpha: np.ndarray, strength: float) -> np.ndarray:
    f = bgr.astype(np.float32)
    excess = np.clip(f[..., 1] - np.maximum(f[..., 0], f[..., 2]), 0.0, None)
    f[..., 1] -= float(strength) * excess
    return np.clip(f + 0.5, 0, 255).astype(np.uint8)


def composite(bgr: np.ndarray, alpha: np.ndarray, bg_bgr: tuple[int, int, int]) -> np.ndarray:
    a = alpha[..., None].astype(np.float32)
    bg = np.empty_like(bgr, dtype=np.float32)
    bg[:] = bg_bgr
    return np.clip(bgr.astype(np.float32) * a + bg * (1.0 - a) + 0.5, 0, 255).astype(np.uint8)


def apply_chroma_key(bgr: np.ndarray, p: ChromaParams) -> np.ndarray:
    alpha = green_mask(bgr, p)
    return composite(suppress_spill(bgr, alpha, p.spill), alpha, p.bg_bgr)
```

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_chroma_key.py -v
git add -A
git commit -m "feat: HSV chroma key with feather and spill suppression

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 8 PASS.

---

### Task 8: Camera worker thread

**Files:**
- Create: `src/matematigin_mantigi/ui/camera_worker.py`, `tests/test_camera_worker.py`
- Modify: `tests/conftest.py` (fake camera fixtures)

**Interfaces:**
- Consumes: `core.chroma_key.ChromaParams`, `apply_chroma_key`.
- Produces: `camera_worker.FrameSource` Protocol (`open() -> bool`, `read() -> np.ndarray | None`, `release() -> None`); `OpenCvSource(index: int = 0)`; `to_qimage_bgr(frame) -> QImage` (deep copy, `Format_BGR888`); `resize_to_width(frame, width) -> np.ndarray`; `CameraWorker(QThread)` with signals `frameReady(QImage)`, `cameraError(str)`, `opened(int, int)`, ctor `CameraWorker(source, params, chroma_enabled=True, out_width=640, target_fps=30, parent=None)`, methods `set_chroma_enabled(bool)`, `set_params(ChromaParams)`, `stop()`.

- [ ] **Step 1: Add fake camera fixtures to conftest.py**

Append to `tests/conftest.py`:
```python
import numpy as np  # noqa: E402


class FakeCamera:
    """N adet sentetik BGR kare üretir; sonra None döndürür."""

    def __init__(self, frames: int = 5, w: int = 320, h: int = 240, green: bool = True):
        self.frames, self.w, self.h, self.green = frames, w, h, green
        self.opened = False
        self.released = False
        self._i = 0

    def open(self) -> bool:
        self.opened = True
        return True

    def read(self):
        if self._i >= self.frames:
            return None
        self._i += 1
        img = np.empty((self.h, self.w, 3), np.uint8)
        img[:] = (30, 200, 40) if self.green else (90, 90, 90)
        img[self.h // 4: 3 * self.h // 4, self.w // 4: 3 * self.w // 4] = (20, 20, 220)
        return img

    def release(self) -> None:
        self.released = True


class DeadCamera:
    def open(self) -> bool:
        return False

    def read(self):
        return None

    def release(self) -> None:
        pass


@pytest.fixture
def fake_camera():
    return FakeCamera(frames=1000)


@pytest.fixture
def dead_camera():
    return DeadCamera()
```

- [ ] **Step 2: Write the failing tests**

`tests/test_camera_worker.py`:
```python
import numpy as np
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.camera_worker import CameraWorker, resize_to_width, to_qimage_bgr


def test_to_qimage_is_deep_copy():
    frame = np.zeros((10, 20, 3), np.uint8)
    img = to_qimage_bgr(frame)
    frame[:] = 255
    assert img.format() == QImage.Format.Format_BGR888
    assert img.width() == 20 and img.height() == 10
    assert img.pixelColor(0, 0).red() == 0


def test_resize_to_width_keeps_aspect():
    out = resize_to_width(np.zeros((240, 320, 3), np.uint8), 160)
    assert out.shape == (120, 160, 3)


def test_worker_emits_keyed_frames(qtbot, fake_camera):
    w = CameraWorker(fake_camera, ChromaParams(), chroma_enabled=True, out_width=160, target_fps=60)
    with qtbot.waitSignal(w.opened, timeout=2000) as opened:
        with qtbot.waitSignal(w.frameReady, timeout=2000) as sig:
            w.start()
    assert opened.args == [320, 240]
    img: QImage = sig.args[0]
    assert img.width() == 160
    assert img.pixelColor(2, 2).name() == "#f7f6f3"          # yeşil -> panel zemini
    assert img.pixelColor(80, 60).name() == "#dc1414"        # kırmızı kutu korunur (BGR 20,20,220)
    w.stop(); assert w.wait(2000)
    assert fake_camera.released


def test_worker_raw_mode_keeps_green(qtbot, fake_camera):
    w = CameraWorker(fake_camera, ChromaParams(), chroma_enabled=False, out_width=160, target_fps=60)
    with qtbot.waitSignal(w.frameReady, timeout=2000) as sig:
        w.start()
    assert sig.args[0].pixelColor(2, 2).green() > 150
    w.stop(); assert w.wait(2000)


def test_dead_camera_reports_error_and_finishes(qtbot, dead_camera):
    w = CameraWorker(dead_camera, ChromaParams())
    with qtbot.waitSignal(w.cameraError, timeout=2000) as sig:
        w.start()
    assert "Kamera" in sig.args[0]
    assert w.wait(2000)


def test_stream_end_reports_error(qtbot):
    from conftest import FakeCamera
    w = CameraWorker(FakeCamera(frames=2), ChromaParams(), target_fps=200)
    with qtbot.waitSignal(w.cameraError, timeout=5000) as sig:
        w.start()
    assert "kesildi" in sig.args[0]
    assert w.wait(2000)
```

If `from conftest import FakeCamera` fails under the installed pytest (rootdir import mode), add an empty `tests/__init__.py` and import `from tests.conftest import FakeCamera` instead.

- [ ] **Step 3: Run to verify failure**

```powershell
python -m pytest tests/test_camera_worker.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement camera_worker.py**

`src/matematigin_mantigi/ui/camera_worker.py`:
```python
"""Kamera iş parçacığı: OpenCV yakalama -> (isteğe bağlı) yeşil perde -> QImage sinyali."""
from __future__ import annotations

import sys
import time
from typing import Protocol

import cv2
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.chroma_key import ChromaParams, apply_chroma_key


class FrameSource(Protocol):
    def open(self) -> bool: ...
    def read(self) -> np.ndarray | None: ...
    def release(self) -> None: ...


class OpenCvSource:
    def __init__(self, index: int = 0):
        self.index = index
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> bool:
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(self.index, backend)
        return bool(self._cap.isOpened())

    def read(self) -> np.ndarray | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def to_qimage_bgr(frame: np.ndarray) -> QImage:
    frame = np.ascontiguousarray(frame)
    h, w = frame.shape[:2]
    img = QImage(frame.tobytes(), w, h, int(frame.strides[0]), QImage.Format.Format_BGR888)
    return img.copy()      # numpy belleğinden bağımsız, iş parçacıkları arası güvenli


def resize_to_width(frame: np.ndarray, width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w == width:
        return frame
    return cv2.resize(frame, (width, max(1, round(h * width / w))), interpolation=cv2.INTER_AREA)


class CameraWorker(QThread):
    frameReady = pyqtSignal(QImage)
    cameraError = pyqtSignal(str)
    opened = pyqtSignal(int, int)

    def __init__(self, source: FrameSource, params: ChromaParams, chroma_enabled: bool = True,
                 out_width: int = 640, target_fps: int = 30, parent=None):
        super().__init__(parent)
        self._source = source
        self._params = params
        self._chroma = chroma_enabled
        self._out_width = out_width
        self._period = 1.0 / max(1, target_fps)
        self._running = False

    def set_chroma_enabled(self, on: bool) -> None:
        self._chroma = on

    def set_params(self, p: ChromaParams) -> None:
        self._params = p

    def set_out_width(self, w: int) -> None:
        self._out_width = max(64, int(w))

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        if not self._source.open():
            self.cameraError.emit("Kamera bulunamadı")
            return
        self._running = True
        misses, announced = 0, False
        try:
            while self._running:
                t0 = time.monotonic()
                frame = self._source.read()
                if frame is None:
                    misses += 1
                    if misses > 30:
                        self.cameraError.emit("Kamera akışı kesildi")
                        break
                    self.msleep(5)
                    continue
                misses = 0
                if not announced:
                    self.opened.emit(int(frame.shape[1]), int(frame.shape[0]))
                    announced = True
                frame = resize_to_width(frame, self._out_width)
                if self._chroma:
                    frame = apply_chroma_key(frame, self._params)
                self.frameReady.emit(to_qimage_bgr(frame))
                rest = self._period - (time.monotonic() - t0)
                if rest > 0:
                    self.msleep(int(rest * 1000))
        finally:
            self._source.release()
```

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_camera_worker.py -v
git add -A
git commit -m "feat: CameraWorker QThread with OpenCV source and chroma key

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 6 PASS, no "QThread: Destroyed while thread is still running" in the output.

---

### Task 9: Webcam panel (region 4)

**Files:**
- Create: `src/matematigin_mantigi/ui/webcam_panel.py`, `tests/test_webcam_panel.py`
- Modify: `src/matematigin_mantigi/app.py` (use `WebcamPanel` for "webcam", honour `--kamera` / `--kamera-yok`, shut down on close)

**Interfaces:**
- Consumes: `ui.camera_worker.*`, `core.chroma_key.ChromaParams`, `ui.panel.PanelFrame`.
- Produces: `webcam_panel.CameraView(QWidget)` with `clicked` signal, `set_frame(QImage)`, `set_placeholder(str)`, `set_raw_mode(bool)`; `webcam_panel.WebcamPanel(fam, source_factory: Callable[[], FrameSource], params: ChromaParams, chroma_enabled: bool = True, parent=None)` with `chromaToggled(bool)` signal, `start()`, `shutdown()`, `set_chroma_enabled(bool)`, `set_params(ChromaParams)`, attributes `chroma_enabled: bool`, `has_camera: bool`, `view: CameraView`, `overlay_label: QLabel`, `worker: CameraWorker` (constructed in `__init__`, thread started by `start()`; the factory is called once in the constructor and `OpenCvSource` opens nothing until the thread runs).

- [ ] **Step 1: Write the failing tests**

`tests/test_webcam_panel.py`:
```python
from PyQt6.QtCore import Qt

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.webcam_panel import WebcamPanel

FAM = FontFamilies("Arial", "Arial", False)


def test_shows_frames_and_toggles_on_click(qtbot, fake_camera):
    panel = WebcamPanel(FAM, lambda: fake_camera, ChromaParams())
    qtbot.addWidget(panel); panel.resize(600, 400); panel.show()
    with qtbot.waitSignal(panel.worker.frameReady, timeout=2000):
        panel.start()
    assert panel.has_camera and panel.overlay_label.text().startswith("yeşil perde: kaldırıldı")
    with qtbot.waitSignal(panel.chromaToggled) as sig:
        qtbot.mouseClick(panel.view, Qt.MouseButton.LeftButton)
    assert sig.args == [False] and panel.chroma_enabled is False
    assert panel.overlay_label.text().startswith("yeşil perde: ham görüntü")
    panel.shutdown()
    assert panel.worker.isFinished()


def test_placeholder_without_camera(qtbot, dead_camera):
    panel = WebcamPanel(FAM, lambda: dead_camera, ChromaParams())
    qtbot.addWidget(panel); panel.show()
    with qtbot.waitSignal(panel.worker.cameraError, timeout=2000):
        panel.start()
    qtbot.waitUntil(lambda: not panel.has_camera, timeout=2000)
    assert "Kamera" in panel.view.placeholder_text
    panel.shutdown()


def test_start_can_be_skipped(qtbot, dead_camera):
    panel = WebcamPanel(FAM, lambda: dead_camera, ChromaParams())
    qtbot.addWidget(panel)
    panel.shutdown()          # never started: must not raise
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/test_webcam_panel.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement webcam_panel.py**

`src/matematigin_mantigi/ui/webcam_panel.py`:
```python
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QImage, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QWidget

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.camera_worker import CameraWorker, FrameSource
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies


class CameraView(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame: QImage | None = None
        self.placeholder_text = "Kamera bekleniyor…"
        self.raw_mode = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Yeşil perdeyi aç/kapat")

    def set_frame(self, img: QImage) -> None:
        self._frame = img
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._frame = None
        self.placeholder_text = text
        self.update()

    def set_raw_mode(self, raw: bool) -> None:
        self.raw_mode = raw
        self.update()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(theme.CAM_RAW if self.raw_mode else theme.PANEL_SOFT))
        if self._frame is None:
            # siluet: gövde 230x230 üstü yuvarlak + baş 110 daire (mockup)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(theme.DOT))
            cx, base = self.width() / 2, self.height()
            p.drawEllipse(QPointF(cx, base - 190), 55, 55)
            p.drawRoundedRect(QRectF(cx - 115, base - 120, 230, 230), 115, 115)
            p.fillRect(QRectF(cx - 115, base - 5, 230, 5), QColor(theme.DOT))
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect().adjusted(0, 12, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       self.placeholder_text)
        else:
            target = self._frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = (self.width() - target.width()) // 2
            y = (self.height() - target.height()) // 2
            p.drawImage(QRect(x, y, target.width(), target.height()), self._frame)
        p.end()


class WebcamPanel(PanelFrame):
    chromaToggled = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, source_factory: Callable[[], FrameSource],
                 params: ChromaParams, chroma_enabled: bool = True, parent=None):
        super().__init__("4", "Webcam", fam, parent)
        self._params = params
        self.chroma_enabled = chroma_enabled
        self.has_camera = False
        self.worker = CameraWorker(source_factory(), params, chroma_enabled, parent=self)
        self.worker.frameReady.connect(lambda img: self.view.set_frame(img))
        self.worker.opened.connect(self._on_opened)
        self.worker.cameraError.connect(self._on_error)

        live = QLabel("CANLI"); live.setFont(theme.font(fam, 9, 700, spacing_pct=112))
        live.setStyleSheet(f"color: {theme.REC_DOT};")
        self.header.insertWidget(2, live)

        self.body.setContentsMargins(0, 0, 0, 0)
        self.view = CameraView(self)
        self.view.clicked.connect(self._toggle)
        self.body.addWidget(self.view, 1)

        self.overlay_label = QLabel(self.view)
        self.overlay_label.setFont(theme.font(fam, 10, 600))
        self.overlay_label.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: rgba(28,27,25,180);"
                                         f" border-radius: 6px; padding: 3px 8px;")
        self.overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._refresh_overlay()

    def _refresh_overlay(self) -> None:
        mode = "kaldırıldı" if self.chroma_enabled else "ham görüntü"
        self.overlay_label.setText(f"yeşil perde: {mode} · tıkla: aç/kapat")
        self.overlay_label.adjustSize()
        self.overlay_label.move(10, 10)
        self.view.set_raw_mode(not self.chroma_enabled)

    def start(self) -> None:
        if not self.worker.isRunning():
            self.worker.start()

    def shutdown(self) -> None:
        if self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)

    def set_chroma_enabled(self, on: bool) -> None:
        self.chroma_enabled = on
        self.worker.set_chroma_enabled(on)
        self._refresh_overlay()

    def set_params(self, p: ChromaParams) -> None:
        self._params = p
        self.worker.set_params(p)

    def _toggle(self) -> None:
        self.set_chroma_enabled(not self.chroma_enabled)
        self.chromaToggled.emit(self.chroma_enabled)

    def _on_opened(self, _w: int, _h: int) -> None:
        self.has_camera = True

    def _on_error(self, msg: str) -> None:
        self.has_camera = False
        self.view.set_placeholder(f"{msg} · Kamera izni / bağlantı kontrol edin")
```

- [ ] **Step 4: Wire into app.py**

In `build_window`, replace the "webcam" `PanelFrame` and add shutdown handling:
```python
from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.camera_worker import OpenCvSource
from matematigin_mantigi.ui.webcam_panel import WebcamPanel

    cam_index = 0 if args.kamera is None else args.kamera
    webcam_panel = WebcamPanel(fam, lambda: OpenCvSource(cam_index), ChromaParams())
    work.add_panel("webcam", webcam_panel)
    if not args.kamera_yok:
        webcam_panel.start()

    original_close = win.closeEvent
    def close_event(e):
        webcam_panel.shutdown()
        original_close(e)
    win.closeEvent = close_event
```
(Task 12 moves this into `MainWindow.closeEvent`.)

- [ ] **Step 5: Run tests, run the app, commit**

```powershell
python -m pytest tests/test_webcam_panel.py tests/test_camera_worker.py -v
python -m matematigin_mantigi
```
Expected: 3 + 6 PASS. In the app region 4 shows the live camera; anything green turns into the panel colour; clicking the video toggles raw mode (green background visible); without a camera the silhouette placeholder and the error text appear; closing the window prints no QThread warning.

```powershell
git add -A
git commit -m "feat: WebcamPanel with live keyed video, raw toggle and placeholder

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Questions from the Excel template

**Files:**
- Create: `src/matematigin_mantigi/core/question_loader.py`, `tests/test_question_loader.py`
- Modify: `src/matematigin_mantigi/app.py` (ensure template, load questions, `--sorular`)

**Interfaces:**
- Consumes: `core.models.Question`, `SAMPLE_QUESTIONS`; `paths.default_template_path()`.
- Produces: `question_loader.REQUIRED_COLUMNS = ("id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3", "cevap")`; `class QuestionTemplateError(ValueError)`; `write_template(path: Path, with_samples: bool = True) -> Path`; `ensure_template(path: Path) -> Path`; `load_questions(path: Path) -> list[Question]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_question_loader.py`:
```python
import openpyxl
import pytest

from matematigin_mantigi.core.question_loader import (REQUIRED_COLUMNS, QuestionTemplateError,
                                                      ensure_template, load_questions, write_template)


def test_write_then_load_round_trip(tmp_path):
    p = write_template(tmp_path / "sorular_sablon.xlsx")
    qs = load_questions(p)
    assert [q.id for q in qs] == ["S1", "S2", "S3"]
    assert qs[0].soru == "3x + 5 = 20 ise x kaçtır?" and qs[0].sinif == 7
    assert qs[2].hints == ("Paydaları eşitle: 6 ortak payda.", "2/3 = 4/6 olur; 4/6 + 1/6.", "Cevap: 5/6.")
    wb = openpyxl.load_workbook(p)
    assert [c.value for c in wb.active[1]] == list(REQUIRED_COLUMNS)
    assert wb.active["A1"].font.bold


def test_ensure_template_creates_once(tmp_path):
    p = tmp_path / "s.xlsx"
    assert not p.exists()
    ensure_template(p); mtime = p.stat().st_mtime
    ensure_template(p)
    assert p.stat().st_mtime == mtime


def test_missing_column_is_reported(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3"])   # cevap yok
    p = tmp_path / "bad.xlsx"; wb.save(p)
    with pytest.raises(QuestionTemplateError, match="cevap"):
        load_questions(p)


def test_blank_rows_skipped_and_missing_hints_dropped(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S9", "Konu", "8", "Soru metni", "ipucu a", None, "", "42"])
    ws.append([None] * 8)
    ws.append(["S10", "Konu", None, "İkinci soru", None, None, None, "x"])
    p = tmp_path / "ok.xlsx"; wb.save(p)
    qs = load_questions(p)
    assert len(qs) == 2
    assert qs[0].hints == ("ipucu a",) and qs[0].sinif == 8
    assert qs[1].hints == () and qs[1].sinif is None


def test_missing_question_text_names_the_row(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S1", "Konu", "7", None, "a", "b", "c", "d"])
    p = tmp_path / "row.xlsx"; wb.save(p)
    with pytest.raises(QuestionTemplateError, match="2"):
        load_questions(p)


def test_empty_file_raises(tmp_path):
    p = write_template(tmp_path / "empty.xlsx", with_samples=False)
    with pytest.raises(QuestionTemplateError, match="hiç soru"):
        load_questions(p)
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/test_question_loader.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement question_loader.py**

`src/matematigin_mantigi/core/question_loader.py`:
```python
"""Excel şablonu: sütun doğrulama, örnek şablon üretme, soru yükleme."""
from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question

REQUIRED_COLUMNS = ("id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3", "cevap")


class QuestionTemplateError(ValueError):
    pass


def write_template(path: Path, with_samples: bool = True) -> Path:
    path = Path(path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sorular"
    ws.append(list(REQUIRED_COLUMNS))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    if with_samples:
        for q in SAMPLE_QUESTIONS:
            hints = list(q.hints) + [""] * (3 - len(q.hints))
            ws.append([q.id, q.konu, q.sinif, q.soru, *hints[:3], q.cevap])
    for col, width in zip("ABCDEFGH", (8, 16, 8, 60, 40, 40, 40, 16)):
        ws.column_dimensions[col].width = width
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def ensure_template(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        write_template(path)
    return path


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def load_questions(path: Path) -> list[Question]:
    path = Path(path)
    if not path.exists():
        raise QuestionTemplateError(f"Şablon bulunamadı: {path}")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [_text(c).lower() for c in (next(rows, None) or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise QuestionTemplateError("Eksik sütun(lar): " + ", ".join(missing))
    idx = {c: header.index(c) for c in REQUIRED_COLUMNS}

    questions: list[Question] = []
    for row_no, row in enumerate(rows, start=2):
        cells = list(row) + [None] * (len(header) - len(row))
        if all(_text(c) == "" for c in cells):
            continue
        soru = _text(cells[idx["soru"]])
        if not soru:
            raise QuestionTemplateError(f"Satır {row_no}: 'soru' boş")
        qid = _text(cells[idx["id"]]) or f"S{len(questions) + 1}"
        sinif_raw = _text(cells[idx["sinif"]])
        try:
            sinif: int | None = int(float(sinif_raw)) if sinif_raw else None
        except ValueError:
            sinif = None
        hints = tuple(h for h in (_text(cells[idx[k]]) for k in ("ipucu1", "ipucu2", "ipucu3")) if h)
        questions.append(Question(qid, _text(cells[idx["konu"]]), sinif, soru, hints, _text(cells[idx["cevap"]])))
    wb.close()
    if not questions:
        raise QuestionTemplateError("Şablonda hiç soru yok")
    return questions
```

- [ ] **Step 4: Load questions in app.py**

Add to `build_window` (before creating panels) and keep the result on the window for Task 12:
```python
from PyQt6.QtWidgets import QMessageBox
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS
from matematigin_mantigi.core.question_loader import QuestionTemplateError, ensure_template, load_questions

    template = Path(args.sorular) if args.sorular else paths.default_template_path()
    try:
        questions = load_questions(ensure_template(template))
    except QuestionTemplateError as err:
        QMessageBox.warning(None, "Soru şablonu", f"{err}\n\nÖrnek sorularla devam ediliyor.")
        questions = list(SAMPLE_QUESTIONS)
    win.questions = questions
```

- [ ] **Step 5: Run tests, run the app once, commit**

```powershell
python -m pytest tests/test_question_loader.py -v
python -m matematigin_mantigi
```
Expected: 6 PASS; `sorular_sablon.xlsx` appears in the project folder with a bold header and the three sample questions. Open it in Excel, add a row, restart: no warning dialog.

```powershell
git add -A
git commit -m "feat: Excel question template generation and validated loader

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Question flow state machine

**Files:**
- Create: `src/matematigin_mantigi/core/question_flow.py`, `tests/test_question_flow.py`

**Interfaces:**
- Consumes: `core.models.Question`, `QuestionStatus`.
- Produces: `question_flow.QuestionFlow(QObject)` with signals `questionLeaving(int)`, `questionChanged(int)`, `statusChanged(int, object)` (index, QuestionStatus), `progressChanged(int, int)` (done, total), `questionVisibilityChanged(bool)`, `hintChanged(int, int)` (hint index, hint count), `hintRevealChanged(int, int, bool)` (question index, hint index, revealed); ctor `QuestionFlow(questions: Sequence[Question], parent=None)`; properties `index`, `current`, `questions`; methods `status(i=None) -> QuestionStatus`, `done_count() -> int`, `is_question_shown() -> bool`, `hint_index() -> int`, `hint_count() -> int`, `is_revealed(hint=None) -> bool`, `work_label() -> str`, `progress_label() -> str`, `select(i)`, `toggle_work()`, `next_question()`, `show_question()`, `hide_question()`, `hint_prev()`, `hint_next()`, `set_hint_index(i)`, `toggle_reveal(hint=None)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_question_flow.py`:
```python
from matematigin_mantigi.core.models import QuestionStatus
from matematigin_mantigi.core.question_flow import QuestionFlow


def test_initial_state(sample_questions):
    f = QuestionFlow(sample_questions)
    assert f.index == 0 and f.current.id == "S1"
    assert all(f.status(i) == QuestionStatus.WAITING for i in range(3))
    assert f.done_count() == 0 and f.progress_label() == "0/3 tamamlandı · S1"
    assert f.work_label() == "Soruyu işle" and f.is_question_shown() is True
    assert f.hint_index() == 0 and f.hint_count() == 3 and not f.is_revealed()


def test_toggle_work_cycles(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.statusChanged) as sig:
        f.toggle_work()
    assert sig.args == [0, QuestionStatus.WORKING] and f.work_label() == "Soruyu tamamla ✓"
    f.toggle_work()
    assert f.status() == QuestionStatus.DONE and f.done_count() == 1
    f.toggle_work()
    assert f.status() == QuestionStatus.WORKING


def test_next_question_marks_done_and_emits_in_order(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    order = []
    f.questionLeaving.connect(lambda i: order.append(("leaving", i)))
    f.questionChanged.connect(lambda i: order.append(("changed", i)))
    f.toggle_work(); f.set_hint_index(2)
    f.next_question()
    assert order == [("leaving", 0), ("changed", 1)]
    assert f.status(0) == QuestionStatus.DONE and f.index == 1 and f.hint_index() == 0


def test_next_wraps_and_waiting_stays_waiting(sample_questions):
    f = QuestionFlow(sample_questions)
    f.next_question(); f.next_question(); f.next_question()
    assert f.index == 0 and f.status(2) == QuestionStatus.WAITING


def test_hint_navigation_clamps(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    f.hint_prev(); assert f.hint_index() == 0
    with qtbot.waitSignal(f.hintChanged) as sig:
        f.hint_next()
    assert sig.args == [1, 3]
    f.hint_next(); f.hint_next(); f.hint_next()
    assert f.hint_index() == 2


def test_reveal_is_per_hint_and_per_question(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.hintRevealChanged) as sig:
        f.toggle_reveal(1)
    assert sig.args == [0, 1, True]
    assert f.is_revealed(1) and not f.is_revealed(0)
    f.hint_next()                                   # gezinme açmaz
    assert f.is_revealed(1) and not f.is_revealed(2)
    f.select(1)
    assert not f.is_revealed(1)
    f.select(0)
    assert f.is_revealed(1)
    f.toggle_reveal(1)
    assert not f.is_revealed(1)


def test_show_hide_question(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.questionVisibilityChanged) as sig:
        f.hide_question()
    assert sig.args == [False] and not f.is_question_shown()
    f.show_question()
    assert f.is_question_shown()


def test_select_emits_progress_and_changed(sample_questions, qtbot):
    f = QuestionFlow(sample_questions)
    with qtbot.waitSignal(f.questionChanged) as sig:
        f.select(2)
    assert sig.args == [2] and f.progress_label() == "0/3 tamamlandı · S3"


def test_empty_flow_is_safe():
    f = QuestionFlow([])
    assert f.hint_count() == 0 and f.progress_label() == "0/0 tamamlandı"
    f.next_question(); f.toggle_work(); f.toggle_reveal()
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/test_question_flow.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement question_flow.py**

`src/matematigin_mantigi/core/question_flow.py`:
```python
"""Soru akışı: sıra, durumlar, soru gizleme, ipucu gezinme ve açma durumu."""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import QObject, pyqtSignal

from matematigin_mantigi.core.models import Question, QuestionStatus


class QuestionFlow(QObject):
    questionLeaving = pyqtSignal(int)
    questionChanged = pyqtSignal(int)
    statusChanged = pyqtSignal(int, object)
    progressChanged = pyqtSignal(int, int)
    questionVisibilityChanged = pyqtSignal(bool)
    hintChanged = pyqtSignal(int, int)
    hintRevealChanged = pyqtSignal(int, int, bool)

    def __init__(self, questions: Sequence[Question], parent: QObject | None = None):
        super().__init__(parent)
        self._questions: tuple[Question, ...] = tuple(questions)
        self._index = 0
        self._status = [QuestionStatus.WAITING for _ in self._questions]
        self._shown = True
        self._hint_index = 0
        self._revealed: set[tuple[int, int]] = set()

    # --- read ------------------------------------------------------------------
    @property
    def questions(self) -> tuple[Question, ...]:
        return self._questions

    @property
    def index(self) -> int:
        return self._index

    @property
    def current(self) -> Question:
        return self._questions[self._index]

    def status(self, i: int | None = None) -> QuestionStatus:
        i = self._index if i is None else i
        return self._status[i] if 0 <= i < len(self._status) else QuestionStatus.WAITING

    def done_count(self) -> int:
        return sum(1 for s in self._status if s == QuestionStatus.DONE)

    def is_question_shown(self) -> bool:
        return self._shown

    def hint_index(self) -> int:
        return self._hint_index

    def hint_count(self) -> int:
        return len(self.current.hints) if self._questions else 0

    def is_revealed(self, hint: int | None = None) -> bool:
        hint = self._hint_index if hint is None else hint
        return (self._index, hint) in self._revealed

    def work_label(self) -> str:
        return "Soruyu tamamla ✓" if self.status() == QuestionStatus.WORKING else "Soruyu işle"

    def progress_label(self) -> str:
        total = len(self._questions)
        base = f"{self.done_count()}/{total} tamamlandı"
        return f"{base} · {self.current.id}" if total else base

    # --- mutate ----------------------------------------------------------------
    def _set_status(self, i: int, s: QuestionStatus) -> None:
        if self._status[i] != s:
            self._status[i] = s
            self.statusChanged.emit(i, s)
            self.progressChanged.emit(self.done_count(), len(self._questions))

    def select(self, i: int) -> None:
        if not self._questions or not 0 <= i < len(self._questions):
            return
        if i != self._index:
            self.questionLeaving.emit(self._index)
        self._index = i
        self._hint_index = 0
        self.questionChanged.emit(i)
        self.progressChanged.emit(self.done_count(), len(self._questions))
        self.hintChanged.emit(0, self.hint_count())

    def toggle_work(self) -> None:
        if not self._questions:
            return
        s = self.status()
        self._set_status(self._index, QuestionStatus.DONE if s == QuestionStatus.WORKING
                         else QuestionStatus.WORKING)

    def next_question(self) -> None:
        if not self._questions:
            return
        if self.status() == QuestionStatus.WORKING:
            self._set_status(self._index, QuestionStatus.DONE)
        self.select((self._index + 1) % len(self._questions))

    def show_question(self) -> None:
        if not self._shown:
            self._shown = True
            self.questionVisibilityChanged.emit(True)

    def hide_question(self) -> None:
        if self._shown:
            self._shown = False
            self.questionVisibilityChanged.emit(False)

    def set_hint_index(self, i: int) -> None:
        n = self.hint_count()
        i = max(0, min(n - 1, i)) if n else 0
        if i != self._hint_index:
            self._hint_index = i
            self.hintChanged.emit(i, n)

    def hint_prev(self) -> None:
        self.set_hint_index(self._hint_index - 1)

    def hint_next(self) -> None:
        self.set_hint_index(self._hint_index + 1)

    def toggle_reveal(self, hint: int | None = None) -> None:
        if not self.hint_count():
            return
        hint = self._hint_index if hint is None else hint
        key = (self._index, hint)
        if key in self._revealed:
            self._revealed.discard(key)
        else:
            self._revealed.add(key)
        self.hintRevealChanged.emit(self._index, hint, key in self._revealed)
```

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_question_flow.py -v
git add -A
git commit -m "feat: QuestionFlow state machine for statuses, visibility and hint reveal

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 9 PASS.

---

### Task 12: Session snapshots (oturum/ PNG per question)

**Files:**
- Create: `src/matematigin_mantigi/core/session_store.py`, `tests/test_session_store.py`

**Interfaces:**
- Produces: `session_store.SessionStore(root: Path | None = None, clock: Callable[[], datetime] = datetime.now)` with `session_dir: Path` (`root / "YYYYMMDD-HHMMSS"`, created lazily), `save_snapshot(question_id: str, image: QImage) -> Path` (`<id>_<nn>.png`, nn = 01, 02, …), `count(question_id) -> int`.

- [ ] **Step 1: Write the failing tests**

`tests/test_session_store.py`:
```python
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.session_store import SessionStore


def white(w=40, h=30):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    return img


def test_snapshots_are_numbered_per_question(tmp_path, qapp):
    store = SessionStore(tmp_path, clock=lambda: datetime(2026, 9, 4, 13, 5, 9))
    assert store.session_dir == tmp_path / "20260904-130509"
    assert not store.session_dir.exists()             # tembel oluşturma
    a = store.save_snapshot("S1", white())
    b = store.save_snapshot("S1", white())
    c = store.save_snapshot("S2", white())
    assert [p.name for p in (a, b, c)] == ["S1_01.png", "S1_02.png", "S2_01.png"]
    assert store.count("S1") == 2 and store.count("S9") == 0
    assert not QImage(str(a)).isNull() and QImage(str(a)).width() == 40


def test_unsafe_ids_are_sanitised(tmp_path, qapp):
    store = SessionStore(tmp_path)
    p = store.save_snapshot("S/1:x", white())
    assert p.name == "S_1_x_01.png" and p.exists()
```

- [ ] **Step 2: Run to verify failure, then implement**

```powershell
python -m pytest tests/test_session_store.py -v
```
Expected: FAIL with `ImportError`.

`src/matematigin_mantigi/core/session_store.py`:
```python
"""Soru başına tuval anlık görüntüsü: oturum/<zaman>/<id>_<nn>.png"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtGui import QImage

from matematigin_mantigi import paths


class SessionStore:
    def __init__(self, root: Path | None = None, clock: Callable[[], datetime] = datetime.now):
        self.root = Path(root) if root is not None else paths.default_session_root()
        self.session_dir = self.root / clock().strftime("%Y%m%d-%H%M%S")
        self._counts: dict[str, int] = {}

    @staticmethod
    def _safe(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_\-ĞğÜüŞşİıÖöÇç]", "_", name) or "soru"

    def count(self, question_id: str) -> int:
        return self._counts.get(self._safe(question_id), 0)

    def save_snapshot(self, question_id: str, image: QImage) -> Path:
        key = self._safe(question_id)
        self._counts[key] = self._counts.get(key, 0) + 1
        self.session_dir.mkdir(parents=True, exist_ok=True)
        target = self.session_dir / f"{key}_{self._counts[key]:02d}.png"
        if not image.save(str(target), "PNG"):
            raise OSError(f"PNG yazılamadı: {target}")
        return target
```

- [ ] **Step 3: Run tests and commit**

```powershell
python -m pytest tests/test_session_store.py -v
git add -A
git commit -m "feat: SessionStore writes per-question PNG snapshots

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 2 PASS.

---

### Task 13: Recorder interface, RecordRect and the recording badge

**Files:**
- Create: `src/matematigin_mantigi/core/recorder.py`, `src/matematigin_mantigi/ui/record_badge.py`, `tests/test_recorder.py`

**Interfaces:**
- Consumes: `ui.work_area.WorkArea.recording_rect()` tuple `(x, y, w, h, dpr)`.
- Produces:
  - `recorder.RecordRect(x: int, y: int, width: int, height: int, dpr: float = 1.0)` frozen; `physical() -> RecordRect` (scaled by dpr, width/height rounded down to even); `to_mss() -> dict` (`left, top, width, height`).
  - `recorder.record_rect_for(rect5: tuple[int, int, int, int, float]) -> RecordRect`.
  - `recorder.Recorder` Protocol: `start(rect: RecordRect, fps: int = 60) -> None`, `stop() -> Path | None`, `is_recording: bool`, `elapsed_seconds: int`.
  - `recorder.NullRecorder` with `last_rect: RecordRect | None`, `fps: int`, `started_at: float | None`.
  - `record_badge.RecordBadge(fam, parent=None)` with `set_format(width, height, fps)`, `start()`, `stop()`, `tick()`, `text() -> str`, `seconds: int`, `active: bool`.

- [ ] **Step 1: Write the failing tests**

`tests/test_recorder.py`:
```python
from matematigin_mantigi.core.recorder import NullRecorder, RecordRect, record_rect_for
from matematigin_mantigi.ui.record_badge import RecordBadge
from matematigin_mantigi.ui.theme import FontFamilies


def test_record_rect_physical_is_even_and_scaled():
    r = record_rect_for((88, 0, 1831, 1079, 2.0))
    assert r == RecordRect(88, 0, 1831, 1079, 2.0)
    p = r.physical()
    assert (p.x, p.y, p.width, p.height, p.dpr) == (176, 0, 3662, 2158, 1.0)
    assert RecordRect(0, 0, 1833, 1081).physical().width == 1832
    assert r.to_mss() == {"left": 88, "top": 0, "width": 1831, "height": 1079}


def test_null_recorder_lifecycle():
    rec = NullRecorder()
    assert not rec.is_recording and rec.elapsed_seconds == 0
    rec.start(RecordRect(0, 0, 100, 100), fps=60)
    assert rec.is_recording and rec.last_rect == RecordRect(0, 0, 100, 100) and rec.fps == 60
    assert rec.stop() is None and not rec.is_recording


def test_badge_text_and_ticks(qtbot):
    b = RecordBadge(FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(b)
    b.set_format(1920, 1080, 60)
    assert not b.active and b.isHidden()
    b.start()
    assert b.active and b.text() == "KAYIT · 00:00 · 1920×1080 · 60 fps"
    b.tick(); b.tick()
    assert b.text() == "KAYIT · 00:02 · 1920×1080 · 60 fps" and b.seconds == 2
    b.stop()
    assert not b.active and b.isHidden() and b.seconds == 0
```

- [ ] **Step 2: Run to verify failure, then implement**

```powershell
python -m pytest tests/test_recorder.py -v
```
Expected: FAIL with `ImportError`.

`src/matematigin_mantigi/core/recorder.py`:
```python
"""Kayıt arayüzü. Bu sürümde NullRecorder; mss+ffmpeg kaydedici sonraki planda aynı Protocol'ü uygular."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


def _even(n: int) -> int:
    return n - (n % 2)


@dataclass(frozen=True)
class RecordRect:
    x: int
    y: int
    width: int
    height: int
    dpr: float = 1.0

    def physical(self) -> "RecordRect":
        s = self.dpr
        return RecordRect(round(self.x * s), round(self.y * s),
                          _even(round(self.width * s)), _even(round(self.height * s)), 1.0)

    def to_mss(self) -> dict[str, int]:
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}


def record_rect_for(rect5: tuple[int, int, int, int, float]) -> RecordRect:
    x, y, w, h, dpr = rect5
    return RecordRect(int(x), int(y), int(w), int(h), float(dpr))


class Recorder(Protocol):
    def start(self, rect: RecordRect, fps: int = 60) -> None: ...
    def stop(self) -> Path | None: ...
    @property
    def is_recording(self) -> bool: ...
    @property
    def elapsed_seconds(self) -> int: ...


class NullRecorder:
    def __init__(self) -> None:
        self.last_rect: RecordRect | None = None
        self.fps = 60
        self.started_at: float | None = None

    def start(self, rect: RecordRect, fps: int = 60) -> None:
        self.last_rect, self.fps, self.started_at = rect, fps, time.monotonic()

    def stop(self) -> Path | None:
        self.started_at = None
        return None

    @property
    def is_recording(self) -> bool:
        return self.started_at is not None

    @property
    def elapsed_seconds(self) -> int:
        return 0 if self.started_at is None else int(time.monotonic() - self.started_at)
```

`src/matematigin_mantigi/ui/record_badge.py`:
```python
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies


class RecordBadge(QWidget):
    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.seconds = 0
        self.active = False
        self._fmt = "1920×1080"
        self._fps = 60
        self.setStyleSheet(f"background: {theme.INK}; border-radius: 12px;")
        row = QHBoxLayout(self); row.setContentsMargins(12, 4, 14, 4); row.setSpacing(8)
        self.dot = QLabel(); self.dot.setFixedSize(10, 10)
        self.dot.setStyleSheet(f"background: {theme.REC_DOT}; border-radius: 5px;")
        self.label = QLabel(); self.label.setFont(theme.font(fam, 11, 600, spacing_pct=106))
        self.label.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: transparent;")
        row.addWidget(self.dot); row.addWidget(self.label)
        self._timer = QTimer(self); self._timer.setInterval(1000); self._timer.timeout.connect(self.tick)
        self._blink = QTimer(self); self._blink.setInterval(600); self._blink.timeout.connect(self._toggle_dot)
        self.hide()

    def set_format(self, width: int, height: int, fps: int) -> None:
        self._fmt, self._fps = f"{width}×{height}", fps
        self._refresh()

    def text(self) -> str:
        return f"KAYIT · {self.seconds // 60:02d}:{self.seconds % 60:02d} · {self._fmt} · {self._fps} fps"

    def start(self) -> None:
        self.seconds, self.active = 0, True
        self._refresh(); self.show(); self._timer.start(); self._blink.start()

    def stop(self) -> None:
        self.active, self.seconds = False, 0
        self._timer.stop(); self._blink.stop(); self.dot.setVisible(True); self.hide()

    def tick(self) -> None:
        self.seconds += 1
        self._refresh()

    def _toggle_dot(self) -> None:
        self.dot.setVisible(not self.dot.isVisible())

    def _refresh(self) -> None:
        self.label.setText(self.text())
        self.adjustSize()
```

- [ ] **Step 3: Run tests and commit**

```powershell
python -m pytest tests/test_recorder.py -v
git add -A
git commit -m "feat: Recorder protocol, NullRecorder, RecordRect and RecordBadge

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 3 PASS.

---

### Task 14: Persistent settings (QSettings)

**Files:**
- Create: `src/matematigin_mantigi/core/settings.py`, `tests/test_settings.py`
- Modify: `tests/conftest.py` (`ini_settings` fixture)

**Interfaces:**
- Consumes: `core.models.Tool, HintMaskMode, Nib, PenSettings`; `core.chroma_key.ChromaParams`.
- Produces: `settings.AppSettings(backend: QSettings | None = None)` with typed properties `tool: Tool`, `color: str`, `width: int`, `hint_mask: HintMaskMode`, `camera_index: int`, `chroma_enabled: bool`, `chroma: ChromaParams`; methods `pen() -> PenSettings`, `set_pen(PenSettings)`, `sync()`. Keys: `tool`, `color`, `width`, `hint_mask`, `camera/index`, `chroma/enabled`, `chroma/tolerance`, `chroma/feather`, `chroma/spill`, `pen/<field>`.

- [ ] **Step 1: Add the fixture and write the failing tests**

Append to `tests/conftest.py`:
```python
from PyQt6.QtCore import QSettings  # noqa: E402


@pytest.fixture
def ini_settings(tmp_path):
    from matematigin_mantigi.core.settings import AppSettings
    return AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))
```

`tests/test_settings.py`:
```python
from PyQt6.QtCore import QSettings

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.core.models import HintMaskMode, Nib, PenSettings, Tool
from matematigin_mantigi.core.settings import AppSettings


def test_defaults(ini_settings):
    s = ini_settings
    assert s.tool == Tool.PEN and s.color == "#1c1b19" and s.width == 4
    assert s.hint_mask == HintMaskMode.BLUR and s.camera_index == 0 and s.chroma_enabled is True
    assert s.chroma == ChromaParams() and s.pen() == PenSettings()


def test_round_trip_through_ini(tmp_path):
    path = str(tmp_path / "rt.ini")
    s = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    s.tool = Tool.ERASER; s.color = "#2456b8"; s.width = 8; s.hint_mask = HintMaskMode.REDACT
    s.camera_index = 2; s.chroma_enabled = False
    s.chroma = ChromaParams(tolerance=55, feather_px=4, spill=0.3)
    s.set_pen(PenSettings(pressure_curve=70, smoothing=10, min_width=2, max_width=20, nib=Nib.CHALK,
                          math_recognition=False, shape_correction=False, autosave=False, template_matching=True))
    s.sync()
    t = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert t.tool == Tool.ERASER and t.color == "#2456b8" and t.width == 8
    assert t.hint_mask == HintMaskMode.REDACT and t.camera_index == 2 and t.chroma_enabled is False
    assert t.chroma == ChromaParams(tolerance=55, feather_px=4, spill=0.3)
    assert t.pen().nib == Nib.CHALK and t.pen().template_matching is True and t.pen().autosave is False


def test_garbage_values_fall_back(tmp_path):
    q = QSettings(str(tmp_path / "g.ini"), QSettings.Format.IniFormat)
    q.setValue("tool", "hammer"); q.setValue("width", "abc"); q.setValue("hint_mask", 7); q.sync()
    s = AppSettings(q)
    assert s.tool == Tool.PEN and s.width == 4 and s.hint_mask == HintMaskMode.BLUR
```

- [ ] **Step 2: Run to verify failure, then implement**

```powershell
python -m pytest tests/test_settings.py -v
```
Expected: FAIL with `ImportError`.

`src/matematigin_mantigi/core/settings.py`:
```python
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
```

- [ ] **Step 3: Run tests and commit**

```powershell
python -m pytest tests/test_settings.py -v
git add -A
git commit -m "feat: typed AppSettings over QSettings

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 3 PASS.

---

### Task 15: Question panel (region 1) and smart-hints panel (region 3)

**Files:**
- Create: `src/matematigin_mantigi/ui/question_panel.py`, `src/matematigin_mantigi/ui/hint_panel.py`, `tests/test_panels.py`

**Interfaces:**
- Consumes: `core.models.Question, QuestionStatus, HintMaskMode`; `ui.panel.PanelFrame`; `ui.widgets.ClickableLabel`.
- Produces:
  - `question_panel.QuestionPanel(fam, parent=None)` signals `questionSelected(int)`, `showRequested()`, `hideRequested()`; methods `set_questions(qs: Sequence[Question])`, `set_current(i)`, `set_status(i, QuestionStatus)`, `set_progress(text)`, `set_shown(bool)`; attributes `chip_buttons: list[QPushButton]`, `text_label: QLabel`, `show_button: QPushButton`, `hide_link: QPushButton`, `progress_label: QLabel`, `shown: bool`.
  - `hint_panel.HintPanel(fam, parent=None)` signals `maskModeChanged(object)` (HintMaskMode), `prevRequested()`, `nextRequested()`, `revealToggled(int)`; methods `set_hints(question_id: str, hints: Sequence[str])`, `set_focus(i)`, `set_revealed(i, bool)`, `set_mask_mode(HintMaskMode)`, `set_recognized(text)`; attributes `mask_mode`, `rows: list[HintRow]`, `counter_label`, `reveal_button`, `blur_button`, `redact_button`, `title_label2` ("S1 ipuçları").
  - `hint_panel.HintRow(QWidget)` with `text_label: QLabel`, `state_label: QLabel`, `revealed: bool`, `clicked = pyqtSignal()`, `apply(mode: HintMaskMode, revealed: bool, focused: bool)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_panels.py`:
```python
from PyQt6.QtCore import Qt

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, HintMaskMode, QuestionStatus
from matematigin_mantigi.ui.hint_panel import HintPanel
from matematigin_mantigi.ui.question_panel import QuestionPanel
from matematigin_mantigi.ui.theme import INK, FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


def qpanel(qtbot):
    p = QuestionPanel(FAM); qtbot.addWidget(p); p.resize(900, 300); p.show()
    p.set_questions(SAMPLE_QUESTIONS)
    return p


def test_question_chips_and_text(qtbot):
    p = qpanel(qtbot)
    assert [b.text() for b in p.chip_buttons] == ["S1 · bekliyor", "S2 · bekliyor", "S3 · bekliyor"]
    assert p.chip_buttons[0].isChecked()
    p.set_current(1)
    assert p.chip_buttons[1].isChecked() and p.text_label.text() == SAMPLE_QUESTIONS[1].soru
    p.set_status(1, QuestionStatus.WORKING)
    assert p.chip_buttons[1].text() == "S2 · işleniyor"
    with qtbot.waitSignal(p.questionSelected) as sig:
        qtbot.mouseClick(p.chip_buttons[2], Qt.MouseButton.LeftButton)
    assert sig.args == [2]


def test_question_hide_and_show(qtbot):
    p = qpanel(qtbot)
    assert p.shown and p.text_label.graphicsEffect() is None and p.show_button.isHidden()
    with qtbot.waitSignal(p.hideRequested):
        qtbot.mouseClick(p.hide_link, Qt.MouseButton.LeftButton)
    p.set_shown(False)
    assert p.text_label.graphicsEffect() is not None and not p.show_button.isHidden()
    with qtbot.waitSignal(p.showRequested):
        qtbot.mouseClick(p.show_button, Qt.MouseButton.LeftButton)
    p.set_shown(True)
    assert p.text_label.graphicsEffect() is None and p.show_button.isHidden()


def hpanel(qtbot):
    h = HintPanel(FAM); qtbot.addWidget(h); h.resize(700, 500); h.show()
    h.set_hints("S1", SAMPLE_QUESTIONS[0].hints)
    return h


def test_hints_start_hidden_and_blurred(qtbot):
    h = hpanel(qtbot)
    assert h.title_label2.text() == "S1 ipuçları" and h.counter_label.text() == "1 / 3"
    assert len(h.rows) == 3
    assert all(not r.revealed and r.text_label.graphicsEffect() is not None for r in h.rows)
    assert [r.state_label.text() for r in h.rows] == ["gizli"] * 3
    assert h.reveal_button.text() == "Aç"


def test_reveal_only_clicked_row(qtbot):
    h = hpanel(qtbot)
    with qtbot.waitSignal(h.revealToggled) as sig:
        qtbot.mouseClick(h.rows[1].text_label, Qt.MouseButton.LeftButton)
    assert sig.args == [1]
    h.set_revealed(1, True)
    assert h.rows[1].revealed and h.rows[1].text_label.graphicsEffect() is None
    assert not h.rows[0].revealed and h.rows[0].text_label.graphicsEffect() is not None
    h.set_focus(1)
    assert h.counter_label.text() == "2 / 3" and h.reveal_button.text() == "Gizle"


def test_redact_mode_paints_ink(qtbot):
    h = hpanel(qtbot)
    with qtbot.waitSignal(h.maskModeChanged) as sig:
        qtbot.mouseClick(h.redact_button, Qt.MouseButton.LeftButton)
    assert sig.args == [HintMaskMode.REDACT] and h.mask_mode == HintMaskMode.REDACT
    assert h.rows[0].text_label.graphicsEffect() is None
    assert INK in h.rows[0].text_label.styleSheet()
    h.set_revealed(0, True)
    assert INK not in h.rows[0].text_label.styleSheet().replace(f"color: {INK}", "")


def test_nav_buttons_and_footer(qtbot):
    h = hpanel(qtbot)
    with qtbot.waitSignal(h.nextRequested):
        qtbot.mouseClick(h.next_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(h.prevRequested):
        qtbot.mouseClick(h.prev_button, Qt.MouseButton.LeftButton)
    h.set_recognized("x = 5")
    assert h.footer_label.text() == "Keras · yazı tanıma etkin · son tanınan: x = 5"
```

- [ ] **Step 2: Run to verify failure**

```powershell
python -m pytest tests/test_panels.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement question_panel.py**

`src/matematigin_mantigi/ui/question_panel.py`:
```python
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QGraphicsBlurEffect, QHBoxLayout, QLabel, QPushButton, QWidget

from matematigin_mantigi.core.models import Question, QuestionStatus
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies


class QuestionPanel(PanelFrame):
    questionSelected = pyqtSignal(int)
    showRequested = pyqtSignal()
    hideRequested = pyqtSignal()

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__("1", "Soru", fam, parent)
        self.shown = True
        self._questions: list[Question] = []
        self._status: list[QuestionStatus] = []

        self.hide_link = QPushButton("Gizle"); self.hide_link.setObjectName("link")
        self.hide_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_link.clicked.connect(self.hideRequested)
        self.progress_label = QLabel("0/0 tamamlandı")
        self.progress_label.setFont(theme.font(fam, 11, 500)); self.progress_label.setStyleSheet(f"color: {theme.MUTED};")
        self.header.addWidget(self.progress_label); self.header.addWidget(self.hide_link)

        self.chip_row = QHBoxLayout(); self.chip_row.setSpacing(8); self.chip_row.addStretch(1)
        self._chip_group = QButtonGroup(self); self._chip_group.setExclusive(True)
        self.chip_buttons: list[QPushButton] = []
        self.body.addLayout(self.chip_row)

        self.text_host = QWidget(self)
        self.text_label = QLabel("", self.text_host)
        self.text_label.setWordWrap(True)
        self.text_label.setFont(theme.font(fam, 26, 500))
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.show_button = QPushButton("?  Soruyu göster", self.text_host)
        self.show_button.setObjectName("accent"); self.show_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_button.clicked.connect(self.showRequested)
        self.show_button.hide()
        self.body.addWidget(self.text_host, 1)

    # --- data ---------------------------------------------------------------
    def set_questions(self, qs: Sequence[Question]) -> None:
        for b in self.chip_buttons:
            self._chip_group.removeButton(b); b.deleteLater()
        self.chip_buttons = []
        self._questions = list(qs)
        self._status = [QuestionStatus.WAITING] * len(self._questions)
        for i, q in enumerate(self._questions):
            b = QPushButton(); b.setObjectName("pill"); b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=i: self.questionSelected.emit(k))
            self._chip_group.addButton(b)
            self.chip_row.insertWidget(i, b)
            self.chip_buttons.append(b)
        self._refresh_chips()
        if self._questions:
            self.set_current(0)

    def set_current(self, i: int) -> None:
        if not 0 <= i < len(self._questions):
            return
        self.chip_buttons[i].setChecked(True)
        self.text_label.setText(self._questions[i].soru)

    def set_status(self, i: int, s: QuestionStatus) -> None:
        if 0 <= i < len(self._status):
            self._status[i] = s
            self._refresh_chips()

    def set_progress(self, text: str) -> None:
        self.progress_label.setText(text)

    def set_shown(self, shown: bool) -> None:
        self.shown = shown
        self.text_label.setGraphicsEffect(None if shown else QGraphicsBlurEffect())
        if not shown:
            self.text_label.graphicsEffect().setBlurRadius(14)
        self.show_button.setVisible(not shown)
        self.hide_link.setVisible(shown)
        self._place_button()

    def _refresh_chips(self) -> None:
        for b, q, s in zip(self.chip_buttons, self._questions, self._status):
            b.setText(f"{q.id} · {s.value}")

    def _place_button(self) -> None:
        self.text_label.setGeometry(0, 0, self.text_host.width(), self.text_host.height())
        self.show_button.adjustSize()
        self.show_button.move((self.text_host.width() - self.show_button.width()) // 2,
                              (self.text_host.height() - self.show_button.height()) // 2)
        self.show_button.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_button()
```

- [ ] **Step 4: Implement hint_panel.py**

`src/matematigin_mantigi/ui/hint_panel.py`:
```python
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QGraphicsBlurEffect, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import HintMaskMode
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.widgets import ClickableLabel


class HintRow(QWidget):
    clicked = pyqtSignal()

    def __init__(self, n: int, text: str, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.revealed = False
        self.setAutoFillBackground(True)
        row = QHBoxLayout(self); row.setContentsMargins(10, 8, 10, 8); row.setSpacing(12)
        self.name_label = ClickableLabel(f"İpucu {n}")
        self.name_label.setFont(theme.font(fam, 10, 600, spacing_pct=108))
        self.name_label.setStyleSheet(f"color: {theme.MUTED};"); self.name_label.setFixedWidth(64)
        self.text_label = ClickableLabel(text); self.text_label.setWordWrap(True)
        self.text_label.setFont(theme.font(fam, 15, 500))
        self.text_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.state_label = QLabel("gizli"); self.state_label.setFont(theme.font(fam, 10, 600))
        self.state_label.setStyleSheet(f"color: {theme.MUTED};")
        for lab in (self.name_label, self.text_label):
            lab.clicked.connect(self.clicked)
        row.addWidget(self.name_label); row.addWidget(self.text_label, 1); row.addWidget(self.state_label)

    def apply(self, mode: HintMaskMode, revealed: bool, focused: bool) -> None:
        self.revealed = revealed
        self.state_label.setText("açık" if revealed else "gizli")
        self.setStyleSheet(f"background: {theme.ROW_FOCUS if focused else 'transparent'}; border-radius: 6px;")
        if revealed:
            self.text_label.setGraphicsEffect(None)
            self.text_label.setStyleSheet("background: transparent;")
        elif mode == HintMaskMode.BLUR:
            self.text_label.setStyleSheet("background: transparent;")
            eff = QGraphicsBlurEffect(); eff.setBlurRadius(9)
            self.text_label.setGraphicsEffect(eff)
        else:
            self.text_label.setGraphicsEffect(None)
            self.text_label.setStyleSheet(f"background: {theme.INK}; color: {theme.INK}; border-radius: 3px;")


class HintPanel(PanelFrame):
    maskModeChanged = pyqtSignal(object)
    prevRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    revealToggled = pyqtSignal(int)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__("3", "Akıllı ipuçları", fam, parent)
        self.fam = fam
        self.mask_mode = HintMaskMode.BLUR
        self._focus = 0
        self.rows: list[HintRow] = []

        self.blur_button = QPushButton("Blur"); self.redact_button = QPushButton("Siyah redakte")
        grp = QButtonGroup(self); grp.setExclusive(True)
        for b in (self.blur_button, self.redact_button):
            b.setObjectName("pill"); b.setCheckable(True); grp.addButton(b); self.header.addWidget(b)
        self.blur_button.setChecked(True)
        self.blur_button.clicked.connect(lambda: self._set_mode_from_ui(HintMaskMode.BLUR))
        self.redact_button.clicked.connect(lambda: self._set_mode_from_ui(HintMaskMode.REDACT))

        helper = QLabel("Gizli ipuçları tıklanmadan açılmaz. ◀ ▶ ile ipuçları arasında geçilir.")
        helper.setFont(theme.font(fam, 11, 400)); helper.setStyleSheet(f"color: {theme.MUTED};")
        self.body.addWidget(helper)

        nav = QHBoxLayout(); nav.setSpacing(8)
        self.title_label2 = QLabel("ipuçları"); self.title_label2.setFont(theme.font(fam, 13, 600))
        self.counter_label = QLabel("0 / 0"); self.counter_label.setFont(theme.font(fam, 11, 500))
        self.counter_label.setStyleSheet(f"color: {theme.MUTED};")
        self.prev_button = QPushButton("◀"); self.next_button = QPushButton("▶")
        self.reveal_button = QPushButton("Aç"); self.reveal_button.setObjectName("accent")
        for b in (self.prev_button, self.next_button):
            b.setObjectName("pill"); b.setFixedWidth(36)
        self.prev_button.clicked.connect(self.prevRequested); self.next_button.clicked.connect(self.nextRequested)
        self.reveal_button.clicked.connect(lambda: self.revealToggled.emit(self._focus))
        nav.addWidget(self.title_label2); nav.addWidget(self.counter_label); nav.addStretch(1)
        nav.addWidget(self.prev_button); nav.addWidget(self.next_button); nav.addWidget(self.reveal_button)
        self.body.addLayout(nav)

        self.rows_host = QWidget(); self.rows_layout = QVBoxLayout(self.rows_host)
        self.rows_layout.setContentsMargins(0, 0, 0, 0); self.rows_layout.setSpacing(4)
        self.body.addWidget(self.rows_host); self.body.addStretch(1)

        foot = QHBoxLayout(); foot.setSpacing(8)
        dot = QLabel(); dot.setFixedSize(8, 8); dot.setStyleSheet(f"background: {theme.OK_DOT}; border-radius: 4px;")
        self.footer_label = QLabel(); self.footer_label.setFont(theme.font(fam, 10, 500))
        self.footer_label.setStyleSheet(f"color: {theme.MUTED};")
        foot.addWidget(dot); foot.addWidget(self.footer_label); foot.addStretch(1)
        self.body.addLayout(foot)
        self.set_recognized("3x + 5 = 20")

    # --- API -------------------------------------------------------------------
    def set_hints(self, question_id: str, hints: Sequence[str]) -> None:
        for r in self.rows:
            self.rows_layout.removeWidget(r); r.deleteLater()
        self.rows = []
        for i, text in enumerate(hints, start=1):
            r = HintRow(i, text, self.fam)
            r.clicked.connect(lambda k=i - 1: self.revealToggled.emit(k))
            self.rows_layout.addWidget(r); self.rows.append(r)
        self.title_label2.setText(f"{question_id} ipuçları")
        self._focus = 0
        self._refresh()

    def set_focus(self, i: int) -> None:
        self._focus = max(0, min(len(self.rows) - 1, i)) if self.rows else 0
        self._refresh()

    def set_revealed(self, i: int, revealed: bool) -> None:
        if 0 <= i < len(self.rows):
            self.rows[i].revealed = revealed
            self._refresh()

    def set_mask_mode(self, m: HintMaskMode) -> None:
        self.mask_mode = m
        (self.blur_button if m == HintMaskMode.BLUR else self.redact_button).setChecked(True)
        self._refresh()

    def set_recognized(self, text: str) -> None:
        self.footer_label.setText(f"Keras · yazı tanıma etkin · son tanınan: {text}")

    # --- internals ----------------------------------------------------------------
    def _set_mode_from_ui(self, m: HintMaskMode) -> None:
        self.mask_mode = m
        self._refresh()
        self.maskModeChanged.emit(m)

    def _refresh(self) -> None:
        n = len(self.rows)
        self.counter_label.setText(f"{self._focus + 1 if n else 0} / {n}")
        for i, r in enumerate(self.rows):
            r.apply(self.mask_mode, r.revealed, i == self._focus)
        focused = self.rows[self._focus] if n else None
        self.reveal_button.setText("Gizle" if focused is not None and focused.revealed else "Aç")
        self.reveal_button.setEnabled(n > 0)
```

- [ ] **Step 5: Run tests and commit**

```powershell
python -m pytest tests/test_panels.py -v
git add -A
git commit -m "feat: QuestionPanel with chips/blur and HintPanel with blur/redact reveal

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: 6 PASS.

---

### Task 16: MainWindow composition and final app.py

**Files:**
- Create: `src/matematigin_mantigi/ui/main_window.py`, `tests/test_main_window.py`
- Modify: `src/matematigin_mantigi/app.py` (replace the throw-away `build_window` shell), `tests/conftest.py` (`window` fixture)

**Interfaces:**
- Consumes: everything from Tasks 3–15.
- Produces: `main_window.MainWindow(fam, questions, settings: AppSettings, recorder: Recorder, session_store: SessionStore, camera_source_factory: Callable[[], FrameSource] | None, layout_path: Path, parent=None)` with attributes `toolbar`, `work_area`, `question_panel`, `hint_panel`, `canvas_panel`, `canvas`, `webcam_panel`, `badge`, `flow`, `settings`, `recorder`, `session_store`; methods `refresh_cursor()`, `toggle_recording(on: bool)`, `open_pen_settings()` (stub until Task 17, shows nothing), `closeEvent`.
- `app.build_window(args, fam, settings=None) -> MainWindow`; `app.main(argv=None) -> int`.

- [ ] **Step 1: Add the window fixture to conftest.py**

Append to `tests/conftest.py`:
```python
@pytest.fixture
def window(qtbot, tmp_path, ini_settings, dead_camera):
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "oturum"), lambda: dead_camera,
                     tmp_path / "duzen.json")
    qtbot.addWidget(win)
    win.resize(1920, 1080)
    win.show()
    qtbot.waitExposed(win)
    win.activateWindow()          # Task 18 kısayolları WindowShortcut bağlamında çalışır
    return win
```

- [ ] **Step 2: Write the failing tests**

`tests/test_main_window.py`:
```python
from PyQt6.QtCore import QPointF, QSize, Qt

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import HintMaskMode, QuestionStatus, Tool


def test_window_shell(window):
    assert window.windowTitle() == "Matematiğin Mantığı"
    assert window.toolbar.width() == 88
    x, y, w, h, _ = window.work_area.recording_rect()
    assert w == window.width() - 88 and h == window.height()
    assert window.question_panel.text_label.text().startswith("3x + 5")
    assert window.hint_panel.title_label2.text() == "S1 ipuçları"
    assert window.canvas_panel.question_label.text() == "· S1 için çözüm alanı"


def test_tool_switch_updates_cursor_and_status(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.ERASER
    assert window.canvas.cursor().pixmap().size() == QSize(36, 36)
    assert "Araç: Silgi" in window.canvas_panel.status_label.text()
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.PEN], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toolbar.width_buttons[8], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().pixmap().size() == QSize(28, 28)
    assert window.settings.width == 8 and window.settings.tool == Tool.PEN


def test_color_selects_pen_and_persists(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.LASER], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toolbar.swatches["#c8322b"], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.PEN and window.canvas.color.name() == "#c8322b"
    assert window.settings.color == "#c8322b" and window.toolbar.tool_buttons[Tool.PEN].isChecked()


def test_question_flow_saves_snapshot_and_clears(window, qtbot):
    c = window.canvas
    c.begin_stroke(QPointF(50, 50), 0.6); c.extend_stroke(QPointF(200, 200), 0.6); c.end_stroke()
    qtbot.mouseClick(window.toolbar.work_button, Qt.MouseButton.LeftButton)
    assert window.toolbar.work_button.text() == "Soruyu tamamla ✓"
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)
    files = sorted(p.name for p in window.session_store.session_dir.glob("*.png"))
    assert files == ["S1_01.png"]
    assert c.is_empty() and window.flow.index == 1
    assert window.question_panel.chip_buttons[0].text() == "S1 · tamamlandı"
    assert window.toolbar.progress_label.text() == "1/3 tamamlandı · S2"
    assert window.hint_panel.title_label2.text() == "S2 ipuçları"
    assert window.canvas_panel.question_label.text() == "· S2 için çözüm alanı"


def test_next_without_drawing_writes_nothing(window, qtbot):
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)
    assert not window.session_store.session_dir.exists()


def test_hint_reveal_and_mask_mode(window, qtbot):
    hp = window.hint_panel
    qtbot.mouseClick(hp.rows[2].text_label, Qt.MouseButton.LeftButton)
    assert hp.rows[2].revealed and not hp.rows[0].revealed
    qtbot.mouseClick(hp.next_button, Qt.MouseButton.LeftButton)
    assert hp.counter_label.text() == "2 / 3"
    qtbot.mouseClick(hp.redact_button, Qt.MouseButton.LeftButton)
    assert window.settings.hint_mask == HintMaskMode.REDACT
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)   # S2
    assert not any(r.revealed for r in hp.rows)


def test_question_hide_show(window, qtbot):
    qtbot.mouseClick(window.question_panel.hide_link, Qt.MouseButton.LeftButton)
    assert not window.question_panel.shown and not window.flow.is_question_shown()
    qtbot.mouseClick(window.question_panel.show_button, Qt.MouseButton.LeftButton)
    assert window.question_panel.shown


def test_recording_stub_and_badge(window, qtbot):
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert window.recorder.is_recording and window.badge.active and not window.badge.isHidden()
    assert window.recorder.last_rect.width == window.work_area.width()
    assert window.toolbar.record_label.text() == "DURDUR"
    window.badge.tick(); window.badge.tick()
    assert window.badge.text().startswith("KAYIT · 00:02 · ")
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert not window.recorder.is_recording and window.badge.isHidden()
    assert window.toolbar.record_label.text() == "KAYIT"


def test_layout_edit_persists_to_file(window, qtbot, tmp_path):
    qtbot.mouseClick(window.toolbar.layout_button, Qt.MouseButton.LeftButton)
    assert window.work_area.edit_mode
    window.work_area.reset_layout()
    assert (tmp_path / "duzen.json").exists()
    assert lm.load_layout(tmp_path / "duzen.json") == lm.DEFAULT_LAYOUT
    window.work_area.done_button.click()
    assert not window.work_area.edit_mode and not window.toolbar.layout_button.isChecked()


def test_restores_settings_on_start(qtbot, tmp_path, ini_settings, dead_camera):
    from matematigin_mantigi.core.models import SAMPLE_QUESTIONS
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    ini_settings.tool = Tool.LASER; ini_settings.color = "#1f8a4c"; ini_settings.width = 2
    ini_settings.hint_mask = HintMaskMode.REDACT; ini_settings.chroma_enabled = False
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda: dead_camera, tmp_path / "d.json")
    qtbot.addWidget(win)
    assert win.canvas.tool == Tool.LASER and win.canvas.color.name() == "#1f8a4c" and win.canvas.base_width == 2
    assert win.toolbar.tool_buttons[Tool.LASER].isChecked() and win.toolbar.width_buttons[2].isChecked()
    assert win.hint_panel.mask_mode == HintMaskMode.REDACT and win.webcam_panel.chroma_enabled is False


def test_close_is_clean(window):
    window.close()
```

- [ ] **Step 3: Run to verify failure**

```powershell
python -m pytest tests/test_main_window.py -v
```
Expected: FAIL with `ImportError`.

- [ ] **Step 4: Implement main_window.py**

`src/matematigin_mantigi/ui/main_window.py`:
```python
"""Ana pencere: bileşenleri kurar ve sinyalleri bağlar. İş mantığı core/ içindedir."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import TOOL_META, Question, QuestionStatus, Tool
from matematigin_mantigi.core.question_flow import QuestionFlow
from matematigin_mantigi.core.recorder import Recorder, record_rect_for
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.camera_worker import FrameSource
from matematigin_mantigi.ui.canvas_panel import CanvasPanel
from matematigin_mantigi.ui.cursors import cursor_for
from matematigin_mantigi.ui.hint_panel import HintPanel
from matematigin_mantigi.ui.question_panel import QuestionPanel
from matematigin_mantigi.ui.record_badge import RecordBadge
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.webcam_panel import WebcamPanel
from matematigin_mantigi.ui.work_area import WorkArea


class MainWindow(QMainWindow):
    def __init__(self, fam: FontFamilies, questions: Sequence[Question], settings: AppSettings,
                 recorder: Recorder, session_store: SessionStore,
                 camera_source_factory: Callable[[], FrameSource] | None, layout_path: Path, parent=None):
        super().__init__(parent)
        self.fam, self.settings, self.recorder, self.session_store = fam, settings, recorder, session_store
        self.layout_path = Path(layout_path)
        self.setWindowTitle("Matematiğin Mantığı")

        central = QWidget(); row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
        self.toolbar = ToolBar(fam)
        self.work_area = WorkArea(fam)
        self.question_panel = QuestionPanel(fam)
        self.hint_panel = HintPanel(fam)
        self.canvas_panel = CanvasPanel(fam)
        self.canvas = self.canvas_panel.canvas
        self.webcam_panel = WebcamPanel(fam, camera_source_factory or (lambda: _NoCamera()),
                                        settings.chroma, settings.chroma_enabled)
        for key, panel in (("soru", self.question_panel), ("ipucu", self.hint_panel),
                           ("cizim", self.canvas_panel), ("webcam", self.webcam_panel)):
            self.work_area.add_panel(key, panel)
        self.work_area.set_layout(lm.load_layout(self.layout_path))
        self.badge = RecordBadge(fam, self.work_area)
        self.work_area.badge_slot = self.badge
        row.addWidget(self.toolbar); row.addWidget(self.work_area, 1)
        self.setCentralWidget(central)

        self.flow = QuestionFlow(questions, self)
        self._wire()
        self._restore_settings()
        self.question_panel.set_questions(questions)
        self._on_question_changed(self.flow.index if questions else 0)
        if camera_source_factory is not None:
            self.webcam_panel.start()

    # --- wiring -------------------------------------------------------------------
    def _wire(self) -> None:
        tb, c, flow = self.toolbar, self.canvas, self.flow
        tb.toolSelected.connect(self._on_tool)
        tb.colorSelected.connect(self._on_color)
        tb.widthSelected.connect(self._on_width)
        tb.undoRequested.connect(c.undo)
        tb.clearRequested.connect(c.clear)
        tb.workToggled.connect(flow.toggle_work)
        tb.nextRequested.connect(flow.next_question)
        tb.recordToggled.connect(self.toggle_recording)
        tb.penSettingsRequested.connect(self.open_pen_settings)
        tb.layoutEditToggled.connect(self.work_area.set_edit_mode)
        self.work_area.editModeChanged.connect(tb.set_layout_edit)
        self.work_area.layoutChanged.connect(lambda lay: lm.save_layout(self.layout_path, lay))

        c.historyChanged.connect(lambda can_undo, _e: tb.set_undo_enabled(can_undo))
        c.pressureChanged.connect(lambda p: self._status(f"XP-Pen · {p:.2f}"))
        c.inputSourceChanged.connect(lambda src: self._status("XP-Pen" if src == "tablet" else "fare"))

        flow.questionLeaving.connect(self._on_question_leaving)
        flow.questionChanged.connect(self._on_question_changed)
        flow.statusChanged.connect(self._on_status_changed)
        flow.progressChanged.connect(lambda _d, _t: self._refresh_progress())
        flow.questionVisibilityChanged.connect(self.question_panel.set_shown)
        flow.hintChanged.connect(lambda i, _n: self.hint_panel.set_focus(i))
        flow.hintRevealChanged.connect(lambda q, h, on: self.hint_panel.set_revealed(h, on) if q == flow.index else None)

        qp, hp = self.question_panel, self.hint_panel
        qp.questionSelected.connect(flow.select)
        qp.showRequested.connect(flow.show_question)
        qp.hideRequested.connect(flow.hide_question)
        hp.prevRequested.connect(flow.hint_prev)
        hp.nextRequested.connect(flow.hint_next)
        hp.revealToggled.connect(flow.toggle_reveal)
        hp.maskModeChanged.connect(self._on_mask_mode)
        self.webcam_panel.chromaToggled.connect(self._on_chroma_toggled)

    def _restore_settings(self) -> None:
        s = self.settings
        self.canvas.set_tool(s.tool); self.canvas.set_color(QColor(s.color)); self.canvas.set_base_width(s.width)
        self.toolbar.set_tool(s.tool); self.toolbar.set_color(s.color); self.toolbar.set_width(s.width)
        self.hint_panel.set_mask_mode(s.hint_mask)
        self.refresh_cursor()
        self._status("XP-Pen")

    # --- handlers -----------------------------------------------------------------
    def _on_tool(self, t: Tool) -> None:
        self.canvas.set_tool(t); self.settings.tool = t
        self.refresh_cursor(); self._status("XP-Pen")

    def _on_color(self, hx: str) -> None:
        self.canvas.set_color(QColor(hx)); self.settings.color = hx
        if self.canvas.tool != Tool.PEN:              # mockup: renk seçimi kalemi seçer
            self._on_tool(Tool.PEN); self.toolbar.set_tool(Tool.PEN)
        self.refresh_cursor()

    def _on_width(self, w: int) -> None:
        self.canvas.set_base_width(w); self.settings.width = w
        self.refresh_cursor(); self._status("XP-Pen")

    def refresh_cursor(self) -> None:
        self.canvas.setCursor(cursor_for(self.canvas.tool, self.canvas.color, self.canvas.base_width,
                                         self.canvas.devicePixelRatioF()))

    def _status(self, pressure_text: str) -> None:
        self.canvas_panel.set_status(TOOL_META[self.canvas.tool][0], self.canvas.base_width, pressure_text)

    def _on_question_leaving(self, i: int) -> None:
        if not self.canvas.is_empty():
            self.session_store.save_snapshot(self.flow.questions[i].id, self.canvas.snapshot_image())
        self.canvas.clear()

    def _on_question_changed(self, i: int) -> None:
        if not self.flow.questions:
            return
        q = self.flow.questions[i]
        self.question_panel.set_current(i)
        self.hint_panel.set_hints(q.id, q.hints)
        for h in range(len(q.hints)):
            self.hint_panel.set_revealed(h, self.flow.is_revealed(h))
        self.canvas_panel.set_question_label(f"· {q.id} için çözüm alanı")
        self._refresh_progress()

    def _on_status_changed(self, i: int, s: QuestionStatus) -> None:
        self.question_panel.set_status(i, s)
        self._refresh_progress()

    def _refresh_progress(self) -> None:
        text = self.flow.progress_label()
        self.toolbar.set_progress(text); self.question_panel.set_progress(text)
        self.toolbar.set_work_label(self.flow.work_label())

    def _on_mask_mode(self, m) -> None:
        self.settings.hint_mask = m

    def _on_chroma_toggled(self, on: bool) -> None:
        self.settings.chroma_enabled = on

    def toggle_recording(self, on: bool) -> None:
        if on and not self.recorder.is_recording:
            rect = record_rect_for(self.work_area.recording_rect())
            self.recorder.start(rect, fps=60)
            self.badge.set_format(rect.width, rect.height, 60)
            self.badge.start()
            self.work_area.relayout()
        elif not on and self.recorder.is_recording:
            self.recorder.stop()
            self.badge.stop()
        self.toolbar.set_recording(self.recorder.is_recording)

    def open_pen_settings(self) -> None:      # Task 17 doldurur
        pass

    def closeEvent(self, e):
        self.webcam_panel.shutdown()
        self.settings.sync()
        super().closeEvent(e)


class _NoCamera:
    def open(self) -> bool: return False
    def read(self): return None
    def release(self) -> None: pass
```

`WorkArea.relayout()` positions `badge_slot`; because `self.badge` replaces the placeholder `badge_slot` before the first relayout, the badge lands top-centre inside the frame.

- [ ] **Step 5: Replace app.py with the final bootstrap**

`src/matematigin_mantigi/app.py` (complete file):
```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox

from matematigin_mantigi import paths
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS
from matematigin_mantigi.core.question_loader import QuestionTemplateError, ensure_template, load_questions
from matematigin_mantigi.core.recorder import NullRecorder
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.camera_worker import OpenCvSource
from matematigin_mantigi.ui.main_window import MainWindow


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="matematigin-mantigi")
    p.add_argument("--sorular", help="Soru şablonu (.xlsx) yolu")
    p.add_argument("--kamera", type=int, default=None, help="Kamera indeksi (varsayılan: ayarlardan)")
    p.add_argument("--kamera-yok", action="store_true", help="Kamerayı açma")
    p.add_argument("--duzen", default=None, help="Düzen dosyası (varsayılan: ./duzen.json)")
    return p.parse_args(argv[1:])


def load_questions_or_samples(template: Path):
    try:
        return load_questions(ensure_template(template))
    except QuestionTemplateError as err:
        QMessageBox.warning(None, "Soru şablonu", f"{err}\n\nÖrnek sorularla devam ediliyor.")
        return list(SAMPLE_QUESTIONS)


def build_window(args: argparse.Namespace, fam: theme.FontFamilies, settings: AppSettings | None = None) -> MainWindow:
    settings = settings or AppSettings()
    template = Path(args.sorular) if args.sorular else paths.default_template_path()
    questions = load_questions_or_samples(template)
    cam_index = settings.camera_index if args.kamera is None else args.kamera
    if args.kamera is not None:
        settings.camera_index = args.kamera
    factory = None if args.kamera_yok else (lambda: OpenCvSource(cam_index))
    layout_path = Path(args.duzen) if args.duzen else Path.cwd() / "duzen.json"
    win = MainWindow(fam, questions, settings, NullRecorder(), SessionStore(), factory, layout_path)
    win.resize(1920, 1080)
    return win


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("Matematiğin Mantığı")
    fam = theme.load_fonts(paths.FONTS_DIR)
    app.setStyleSheet(theme.build_stylesheet(fam))
    win = build_window(parse_args(argv), fam)
    win.show()
    return app.exec()
```

Update `tests/test_models.py::test_build_window_offscreen` to the new signature:
```python
def test_build_window_offscreen(qtbot, tmp_path, ini_settings, monkeypatch):
    from matematigin_mantigi.ui.theme import FontFamilies
    monkeypatch.chdir(tmp_path)
    win = app.build_window(app.parse_args(["prog", "--kamera-yok"]), FontFamilies("Arial", "Arial", False), ini_settings)
    qtbot.addWidget(win)
    assert win.windowTitle() == "Matematiğin Mantığı"
    assert (tmp_path / "sorular_sablon.xlsx").exists()
```

- [ ] **Step 6: Run the whole suite and the app**

```powershell
python -m pytest -q
python -m matematigin_mantigi
```
Expected: all tests PASS. In the app everything from the mockup works together: chips, blurred question, hint reveal with blur/redact, drawing with per-tool cursors, webcam keyed, "Sıradaki soru" saves a PNG under `oturum/<timestamp>/`, the record button shows the badge, "⧉ Düzen" lets you rearrange panels, and restarting restores tool/colour/width/mask/layout.

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "feat: MainWindow wiring toolbar, flow, panels, webcam, recorder stub and settings

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 17: Pen settings dialog ("Kalem ayarları" screen)

**Files:**
- Create: `src/matematigin_mantigi/ui/pen_settings.py`, `tests/test_pen_settings.py`
- Modify: `src/matematigin_mantigi/ui/main_window.py` (`open_pen_settings`)

**Interfaces:**
- Consumes: `core.models.PenSettings, Nib`; `ui.cursors.*` (preview tiles); `ui.theme.*`.
- Produces: `pen_settings.PenSettingsDialog(current: PenSettings, color: QColor, base_width: int, fam, parent=None)` with `applied = pyqtSignal(object)` (PenSettings), `value() -> PenSettings`, attributes `curve_slider`, `smoothing_slider`, `min_slider`, `max_slider`, `nib_buttons: dict[Nib, QPushButton]`, `toggles: dict[str, QCheckBox]` (keys `math_recognition`, `shape_correction`, `autosave`, `template_matching`), `apply_button`, `cancel_button`.

- [ ] **Step 1: Write the failing tests**

`tests/test_pen_settings.py`:
```python
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from matematigin_mantigi.core.models import Nib, PenSettings
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


def test_dialog_reflects_current_and_returns_edits(qtbot):
    d = PenSettingsDialog(PenSettings(), QColor("#c8322b"), 4, FAM)
    qtbot.addWidget(d)
    assert d.curve_slider.value() == 50 and d.smoothing_slider.value() == 35
    assert d.min_slider.value() == 1 and d.max_slider.value() == 12
    assert d.nib_buttons[Nib.ROUND].isChecked()
    assert d.toggles["math_recognition"].isChecked() and not d.toggles["template_matching"].isChecked()
    d.smoothing_slider.setValue(60); d.max_slider.setValue(20)
    d.nib_buttons[Nib.CHALK].click()
    d.toggles["autosave"].setChecked(False)
    v = d.value()
    assert v == PenSettings(smoothing=60, max_width=20, nib=Nib.CHALK, autosave=False)


def test_apply_emits_and_accepts(qtbot):
    d = PenSettingsDialog(PenSettings(), QColor("#000"), 4, FAM)
    qtbot.addWidget(d)
    d.min_slider.setValue(3)
    with qtbot.waitSignal(d.applied) as sig:
        qtbot.mouseClick(d.apply_button, Qt.MouseButton.LeftButton)
    assert sig.args[0].min_width == 3 and d.result() == d.DialogCode.Accepted.value


def test_min_never_exceeds_max(qtbot):
    d = PenSettingsDialog(PenSettings(min_width=1, max_width=4), QColor("#000"), 4, FAM)
    qtbot.addWidget(d)
    d.min_slider.setValue(10)
    assert d.value().min_width <= d.value().max_width
```

- [ ] **Step 2: Run to verify failure, then implement**

```powershell
python -m pytest tests/test_pen_settings.py -v
```
Expected: FAIL with `ImportError`.

`src/matematigin_mantigi/ui/pen_settings.py`:
```python
"""Kalem, silgi & imleç ayarları penceresi (mockup 'Kalem ayarları' ekranı)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QPushButton, QSlider, QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import Nib, PenSettings
from matematigin_mantigi.ui import cursors, theme
from matematigin_mantigi.ui.theme import FontFamilies


def _card(title: str, fam: FontFamilies) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setStyleSheet(f"QFrame {{ background: {theme.PANEL}; border-radius: 6px; }}")
    col = QVBoxLayout(f); col.setContentsMargins(18, 14, 18, 16); col.setSpacing(10)
    t = QLabel(title); t.setFont(theme.font(fam, 12, 600, spacing_pct=110)); t.setStyleSheet(f"color: {theme.MUTED};")
    col.addWidget(t)
    return f, col


class PenSettingsDialog(QDialog):
    applied = pyqtSignal(object)

    def __init__(self, current: PenSettings, color: QColor, base_width: int, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kalem, silgi & imleç")
        self.setMinimumWidth(720)
        root = QVBoxLayout(self); root.setContentsMargins(24, 20, 24, 20); root.setSpacing(14)

        head = QHBoxLayout()
        nine = QLabel("9"); nine.setFont(theme.hand_font(fam, 36, 700))
        title = QLabel("Kalem, silgi & imleç"); title.setFont(theme.font(fam, 20, 600))
        sub = QLabel("XP-Pen Deco · macOS · 8192 basınç seviyesi"); sub.setFont(theme.font(fam, 11, 500))
        sub.setStyleSheet(f"color: {theme.MUTED};")
        head.addWidget(nine); head.addWidget(title); head.addStretch(1); head.addWidget(sub)
        root.addLayout(head)

        grid = QGridLayout(); grid.setSpacing(14)

        cur_card, cur_col = _card("Özel imleçler", fam)
        note = QLabel("İmleç seçili araca ve renge göre değişir."); note.setFont(theme.font(fam, 11, 400))
        cur_col.addWidget(note)
        tiles = QHBoxLayout(); tiles.setSpacing(18)
        for label, cur in ((f"Kalem · {color.name()}", cursors.pen_cursor(color, base_width)),
                           ("Silgi", cursors.eraser_cursor(base_width)),
                           ("Lazer", cursors.laser_cursor())):
            tile = QVBoxLayout(); pic = QLabel(); pic.setPixmap(cur.pixmap()); pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cap = QLabel(label); cap.setFont(theme.font(fam, 10, 500)); cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.addWidget(pic); tile.addWidget(cap); tiles.addLayout(tile)
        cur_col.addLayout(tiles)
        grid.addWidget(cur_card, 0, 0)

        pen_card, pen_col = _card("Kalem", fam)
        form = QFormLayout(); form.setSpacing(8)
        self.curve_slider = self._slider(0, 100, current.pressure_curve)
        self.smoothing_slider = self._slider(0, 100, current.smoothing)
        self.min_slider = self._slider(1, 30, current.min_width)
        self.max_slider = self._slider(1, 40, current.max_width)
        self.curve_value = QLabel(); self.smoothing_value = QLabel(); self.min_value = QLabel(); self.max_value = QLabel()
        for name, slider, value in (("Basınç eğrisi", self.curve_slider, self.curve_value),
                                    ("Yumuşatma", self.smoothing_slider, self.smoothing_value),
                                    ("Min. kalınlık", self.min_slider, self.min_value),
                                    ("Maks. kalınlık", self.max_slider, self.max_value)):
            row = QHBoxLayout(); row.addWidget(slider, 1); row.addWidget(value)
            lab = QLabel(name); lab.setFont(theme.font(fam, 11, 500))
            form.addRow(lab, row)
        pen_col.addLayout(form)
        nib_row = QHBoxLayout(); nib_row.setSpacing(6)
        nib_lab = QLabel("Kalem ucu"); nib_lab.setFont(theme.font(fam, 11, 500)); nib_row.addWidget(nib_lab)
        self._nib_group = QButtonGroup(self); self._nib_group.setExclusive(True)
        self.nib_buttons: dict[Nib, QPushButton] = {}
        for nib in Nib:
            b = QPushButton(nib.value); b.setObjectName("pill"); b.setCheckable(True)
            self._nib_group.addButton(b); self.nib_buttons[nib] = b; nib_row.addWidget(b)
        self.nib_buttons[current.nib].setChecked(True)
        nib_row.addStretch(1); pen_col.addLayout(nib_row)
        grid.addWidget(pen_card, 0, 1)

        fx_card, fx_col = _card("Otomatik FX (Keras)", fam)
        fx_note = QLabel("El yazısı matematiksel anlama dönüşür; çizim estetiği düzeltilir.")
        fx_note.setFont(theme.font(fam, 11, 400)); fx_col.addWidget(fx_note)
        self.toggles: dict[str, QCheckBox] = {}
        for key, name, desc, on in (
            ("math_recognition", "Matematik tanıma", "El yazısı denklemleri düzgün metne çevir", current.math_recognition),
            ("shape_correction", "Şekil düzeltme", "Titrek daire/çizgi → geometrik şekil", current.shape_correction),
            ("autosave", "Otomatik kaydet", "Her 30 sn ve soru değişiminde", current.autosave),
            ("template_matching", "Ön tanımlı soru tanıma", "Yazılan soruyu şablonla eşleştir", current.template_matching),
        ):
            cb = QCheckBox(name); cb.setChecked(on); cb.setFont(theme.font(fam, 12, 600))
            d = QLabel(desc); d.setFont(theme.font(fam, 10, 400)); d.setStyleSheet(f"color: {theme.MUTED};")
            fx_col.addWidget(cb); fx_col.addWidget(d)
            self.toggles[key] = cb
        grid.addWidget(fx_card, 1, 0, 1, 2)
        root.addLayout(grid)

        preview_card, preview_col = _card("Canlı tanıma önizlemesi", fam)
        prow = QHBoxLayout()
        for hand, typed in (("3x + 5 = 20", "3x + 5 = 20"), ("x = 15 / 3", "x = 15 ÷ 3"),
                            ("2/3 + 1/6", "²⁄₃ + ¹⁄₆ = ⁵⁄₆"), ("Ç = 2(a+b)", "Ç = 2 · (a + b)")):
            cell = QVBoxLayout()
            h = QLabel(hand); h.setFont(theme.hand_font(fam, 22, 500))
            arrow = QLabel("↓ tanındı"); arrow.setFont(theme.font(fam, 9, 600)); arrow.setStyleSheet(f"color: {theme.OK_DOT};")
            t = QLabel(typed); t.setFont(theme.font(fam, 14, 500))
            for w in (h, arrow, t):
                w.setAlignment(Qt.AlignmentFlag.AlignCenter); cell.addWidget(w)
            prow.addLayout(cell)
        preview_col.addLayout(prow)
        root.addWidget(preview_card)

        buttons = QHBoxLayout(); buttons.addStretch(1)
        self.cancel_button = QPushButton("Vazgeç"); self.cancel_button.setObjectName("pill")
        self.apply_button = QPushButton("Uygula"); self.apply_button.setObjectName("accent")
        self.cancel_button.clicked.connect(self.reject); self.apply_button.clicked.connect(self._apply)
        buttons.addWidget(self.cancel_button); buttons.addWidget(self.apply_button)
        root.addLayout(buttons)

        for s in (self.curve_slider, self.smoothing_slider, self.min_slider, self.max_slider):
            s.valueChanged.connect(self._refresh_values)
        self.min_slider.valueChanged.connect(lambda v: self.max_slider.setValue(max(v, self.max_slider.value())))
        self.max_slider.valueChanged.connect(lambda v: self.min_slider.setValue(min(v, self.min_slider.value())))
        self._refresh_values()

    def _slider(self, lo: int, hi: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi); s.setValue(value); return s

    def _refresh_values(self, *_):
        curve = self.curve_slider.value()
        self.curve_value.setText("Doğrusal" if 45 <= curve <= 55 else ("Yumuşak" if curve < 45 else "Sert"))
        self.smoothing_value.setText(f"%{self.smoothing_slider.value()}")
        self.min_value.setText(f"{self.min_slider.value()} px")
        self.max_value.setText(f"{self.max_slider.value()} px")

    def value(self) -> PenSettings:
        nib = next(n for n, b in self.nib_buttons.items() if b.isChecked())
        return PenSettings(pressure_curve=self.curve_slider.value(), smoothing=self.smoothing_slider.value(),
                           min_width=self.min_slider.value(), max_width=self.max_slider.value(), nib=nib,
                           math_recognition=self.toggles["math_recognition"].isChecked(),
                           shape_correction=self.toggles["shape_correction"].isChecked(),
                           autosave=self.toggles["autosave"].isChecked(),
                           template_matching=self.toggles["template_matching"].isChecked())

    def _apply(self) -> None:
        self.applied.emit(self.value())
        self.accept()
```

- [ ] **Step 3: Open the dialog from MainWindow**

Replace `open_pen_settings` in `src/matematigin_mantigi/ui/main_window.py`:
```python
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog

    def open_pen_settings(self) -> None:
        dlg = PenSettingsDialog(self.settings.pen(), self.canvas.color, self.canvas.base_width, self.fam, self)
        dlg.applied.connect(self.settings.set_pen)
        dlg.exec()
```

Add to `tests/test_main_window.py`:
```python
def test_pen_settings_round_trip_through_window(window, qtbot, monkeypatch):
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.ui import pen_settings as ps
    captured = {}
    def fake_exec(self):
        captured["dialog"] = self
        self.smoothing_slider.setValue(80)
        self._apply()
        return 1
    monkeypatch.setattr(ps.PenSettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.pen_settings_button, Qt.MouseButton.LeftButton)
    assert window.settings.pen() == PenSettings(smoothing=80)
```

- [ ] **Step 4: Run tests and commit**

```powershell
python -m pytest tests/test_pen_settings.py tests/test_main_window.py -v
git add -A
git commit -m "feat: pen settings dialog with cursor previews and Keras FX toggles

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Expected: all PASS. In the app, the toolbar "Kalem" button opens the dialog; "Uygula" persists (check with a restart: the sliders keep their values).

---

### Task 18: Keyboard shortcuts, README, full verification

**Files:**
- Modify: `src/matematigin_mantigi/ui/main_window.py` (shortcuts), `tests/test_main_window.py`
- Create: `README.md`

**Interfaces:**
- Produces: shortcuts on `MainWindow`: `1..5` select Kalem/Silgi/Yazı/Şekil/Lazer, `Ctrl+Z` undo, `Ctrl+Shift+X` clear, `N` next question, `Space` toggle work, `R` toggle recording, `H` hide/show question, `Left`/`Right` hint prev/next, `Return` reveal focused hint, `F11` fullscreen toggle, `L` layout edit toggle, `Escape` leaves edit mode / fullscreen.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_main_window.py`:
```python
def test_keyboard_shortcuts(window, qtbot):
    qtbot.keyClick(window, Qt.Key.Key_2)
    assert window.canvas.tool == Tool.ERASER and window.toolbar.tool_buttons[Tool.ERASER].isChecked()
    qtbot.keyClick(window, Qt.Key.Key_N)
    assert window.flow.index == 1
    qtbot.keyClick(window, Qt.Key.Key_Right)
    assert window.hint_panel.counter_label.text() == "2 / 3"
    qtbot.keyClick(window, Qt.Key.Key_Return)
    assert window.hint_panel.rows[1].revealed
    qtbot.keyClick(window, Qt.Key.Key_R)
    assert window.recorder.is_recording
    qtbot.keyClick(window, Qt.Key.Key_R)
    assert not window.recorder.is_recording
    qtbot.keyClick(window, Qt.Key.Key_L)
    assert window.work_area.edit_mode
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert not window.work_area.edit_mode
```

- [ ] **Step 2: Implement the shortcuts**

Add to `MainWindow.__init__` (after `_wire()`), and the helper method:
```python
from PyQt6.QtGui import QKeySequence, QShortcut

        self._shortcuts()

    def _shortcuts(self) -> None:
        def sc(keys: str, fn) -> None:
            QShortcut(QKeySequence(keys), self, activated=fn)
        for i, tool in enumerate(Tool, start=1):
            sc(str(i), lambda t=tool: (self._on_tool(t), self.toolbar.set_tool(t)))
        sc("Ctrl+Z", self.canvas.undo)
        sc("Ctrl+Shift+X", self.canvas.clear)
        sc("N", self.flow.next_question)
        sc("Space", self.flow.toggle_work)
        sc("R", lambda: self.toggle_recording(not self.recorder.is_recording))
        sc("H", lambda: self.flow.show_question() if not self.flow.is_question_shown() else self.flow.hide_question())
        sc("Left", self.flow.hint_prev)
        sc("Right", self.flow.hint_next)
        sc("Return", self.flow.toggle_reveal)
        sc("L", lambda: self.work_area.set_edit_mode(not self.work_area.edit_mode))
        sc("F11", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        sc("Escape", self._escape)

    def _escape(self) -> None:
        if self.work_area.edit_mode:
            self.work_area.set_edit_mode(False)
        elif self.isFullScreen():
            self.showNormal()
```

Shortcuts use `Qt.ShortcutContext.WindowShortcut` (the default), so they work while the canvas has focus; the pen settings dialog is modal and does not receive them. The `window` fixture calls `activateWindow()` because a window shortcut only fires in the active window. If `test_keyboard_shortcuts` still fails under the offscreen platform with every other test green, pass `context=Qt.ShortcutContext.ApplicationShortcut` in `sc()` and keep the rest.

- [ ] **Step 3: Write README.md**

```markdown
# Matematiğin Mantığı — grafik tablet ders uygulaması (görünüş demosu)

## Çalıştırma
    python -m pip install -e ".[dev]"
    python -m matematigin_mantigi              # kamera 0, ./sorular_sablon.xlsx, ./duzen.json
    python -m matematigin_mantigi --kamera 1
    python -m matematigin_mantigi --kamera-yok --sorular C:\yol\sorular.xlsx

Windows PowerShell'de önce `$env:PYTHONUTF8 = "1"`.

## Testler
    python -m pytest -q          # başsız (QT_QPA_PLATFORM=offscreen), kamera ve tablet gerekmez

## Bölgeler
1 Soru · 2 El çizimi · 3 Akıllı ipuçları · 4 Webcam · 9 Dış araç çubuğu (kayıtta görünmez).
"⧉ Düzen" (L) ile paneller OBS gibi taşınır/boyutlandırılır, 12x10 ızgaraya yapışır, `duzen.json`'a kaydedilir.
Normal kullanımda panel kenarları ve çerçeve çizilmez.

## Kısayollar
1-5 araçlar · Ctrl+Z geri al · Ctrl+Shift+X temizle · N sıradaki soru · Space işle/tamamla · R kayıt ·
H soruyu gizle/göster · ←/→ ipucu · Enter ipucunu aç · L düzen · F11 tam ekran · Esc çık

## Soru şablonu
`sorular_sablon.xlsx` ilk çalıştırmada üretilir. Sütunlar: id, konu, sinif, soru, ipucu1, ipucu2, ipucu3, cevap.
Boş ipucu hücreleri atlanır; `soru` boşsa satır numarasıyla hata verilir.

## macOS (hedef makine, XP-Pen)
- arm64 Python kullanın (`python3 -c "import platform; print(platform.machine())"` → arm64). PyQt6 universal2 wheel, macOS 12+.
- Kamera izni terminal uygulamasına (Terminal/iTerm/VS Code) verilir: Sistem Ayarları > Gizlilik ve Güvenlik > Kamera.
- Ekran kaydı izni (sonraki sürümdeki mss kaydedici için) aynı yerde "Ekran Kaydı".
- XP-Pen sürücüsünü kurun, Erişilebilirlik ve Giriş İzleme izinlerini verin; sürücü yoksa sadece fare olayları gelir.
- Paketlenince (py2app/PyInstaller) Info.plist'e `NSCameraUsageDescription` eklenmeli.

## Windows (geliştirme makinesi)
- XP-Pen sürücüsünde "Windows Ink" açık olmalı; Qt 6 kalem verisini WM_POINTER üzerinden alır.
- Windows Ink kapalıysa alternatif: `$env:QT_QPA_PLATFORM = "windows:nowmpointer"` (WinTab yolu).
- Ekran ölçeği %125+ ise pencere 1920x1080'den küçük başlar; paneller ızgarayla orantılı küçülür.

## Oturum çıktıları
`oturum/<tarih-saat>/<soruId>_<nn>.png` — "Sıradaki soru" veya soru seçimi sırasında tuval boş değilse kaydedilir.

## Bu sürümde taslak olan kısımlar
Kayıt düğmesi (NullRecorder + rozet), Keras tanıma durumu (sabit metin), Yazı ve Şekil araçları.
```

- [ ] **Step 4: Full verification**

```powershell
$env:PYTHONUTF8 = "1"
python -m pytest -q
python -m matematigin_mantigi
```
Expected: every test PASS with no Qt warnings on stderr. Manual checklist in the running app (Windows now, repeat on the Mac):

1. Window opens at 1920x1080 with the dark toolbar and four borderless white panels; brand plate at the bottom; no frame or lines visible.
2. Draw with the mouse: constant width. Draw with the XP-Pen: width follows pressure and the status strip reads `Basınç: XP-Pen · 0.xx`. Flip the stylus: erases.
3. Tool buttons 1–5 and their cursors: red dot (after choosing red), dashed square that grows with thickness, laser halo, I-beam, cross.
4. Webcam shows live video; green is replaced by the panel colour; clicking the video shows raw green; unplugged camera shows the silhouette placeholder.
5. Chips S1/S2/S3; "Soruyu işle" → "Soruyu tamamla ✓"; "Sıradaki soru →" clears the canvas and writes `oturum/<ts>/S1_01.png`; "Gizle" blurs the question and "? Soruyu göster" brings it back.
6. Hints start hidden (blur); switching to "Siyah redakte" turns them into black bars; a hint opens only when clicked or with Enter; ◀ ▶ moves the focus; changing question hides everything again.
7. Record button: badge `KAYIT · 00:0x · <w>×<h> · 60 fps` counts up; button label DURDUR; stop hides it.
8. "⧉ Düzen": frame, grid and outlines appear; drag panels by their header, resize from the corner, they snap; double-click a header to maximize; "Sıfırla" restores; "Bitti" hides all lines; `duzen.json` written; restart restores the layout.
9. Close and reopen: tool, colour, width, mask mode, chroma on/off and pen settings are restored; no `QThread: Destroyed while thread is still running` on the console.

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "feat: keyboard shortcuts and README with platform checklist

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Verification (end-to-end)

- Automated: `python -m pytest -q` from the project root, offscreen, on Windows now and on the Mac before the first lesson. Expected count after Task 18: about 95 tests, all green, one possible SKIP if the fonts were not downloaded.
- Manual: the nine-point checklist in Task 18 Step 4. Steps 2 (stylus pressure) and 4 (camera) need real hardware; everything else is covered by tests as well.
- Tablet on Windows: if pressure never changes, enable "Windows Ink" in the XP-Pen driver or start with `QT_QPA_PLATFORM=windows:nowmpointer`.
- Camera on macOS: grant Camera permission to the terminal app that launches Python; the placeholder text in region 4 says so when the capture fails.

## Next plans (not in this milestone)

Taken from the 51-item research list in `Ozellik Listesi.dc.html`, "A" priority first. Each is a separate plan with its own spec:

1. **Recording engine** (list items 26, 27, 4/28): `MssFfmpegRecorder` implementing `core.recorder.Recorder`: mss region grab of `RecordRect.physical()`, `sounddevice` microphone, ffmpeg mux to MP4 at 1080p60, pause/resume and chapter markers on the stylus button via pyautogui hotkeys. Separate tracks for screen/webcam/mic as an option.
2. **Chroma key controls + calibration** (33): tolerance/feather/spill sliders and an "auto calibrate from the corners" button in region 4; MediaPipe fallback when no green screen (34).
3. **Keras math recognition** (10, 11, 13): stroke capture per question → offline handwriting-to-LaTeX model → live "son tanınan" footer text, with a "dönüştür" button; step verification against `cevap`.
4. **Pen features** (1, 2, 3, 10): Shift straight-line lock, pages with thumbnails, grid/isometric/coordinate backgrounds (toggle whether the grid records), XP-Pen express-key mapping panel.
5. **Question bank** (19, 20, 24): column validation report in the UI, topic/grade/difficulty filters, "all questions blurred" mode.
6. **Presentation & ergonomics** (39, 44, 45): presentation mode that hides numbers and headers, editable shortcut map, autosave and crash recovery of the session folder.

Open questions from that list that the user still has to answer before those plans are written: resolution 1080p vs 4K; whether the grid should be visible in recordings; which XP-Pen model (express key count); whether Turkish Whisper quality is acceptable for subtitles; whether the app must work offline for LLM-generated hints.
