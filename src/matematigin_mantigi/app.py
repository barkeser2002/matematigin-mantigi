from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QGuiApplication
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QWidget

from matematigin_mantigi import paths
from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import TOOL_META
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.canvas_panel import CanvasPanel
from matematigin_mantigi.ui.cursors import cursor_for
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.work_area import WorkArea


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="matematigin-mantigi")
    p.add_argument("--sorular", help="Soru şablonu (.xlsx) yolu")
    p.add_argument("--kamera", type=int, default=None, help="Kamera indeksi (varsayılan: ayarlardan)")
    p.add_argument("--kamera-yok", action="store_true", help="Kamerayı açma")
    return p.parse_args(argv[1:])


def build_window(args: argparse.Namespace, fam: theme.FontFamilies | None = None) -> QMainWindow:
    fam = fam or theme.FontFamilies("sans-serif", "cursive", False)
    win = QMainWindow()
    win.setWindowTitle("Matematiğin Mantığı")
    central = QWidget(); row = QHBoxLayout(central); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
    toolbar = ToolBar(fam); work = WorkArea(fam)
    for key, num, title in (("soru", "1", "Soru"), ("ipucu", "3", "Akıllı ipuçları"),
                            ("webcam", "4", "Webcam")):
        work.add_panel(key, PanelFrame(num, title, fam))
    canvas_panel = CanvasPanel(fam)
    work.add_panel("cizim", canvas_panel)
    canvas = canvas_panel.canvas
    toolbar.toolSelected.connect(canvas.set_tool)
    toolbar.colorSelected.connect(lambda hx: canvas.set_color(QColor(hx)))
    toolbar.widthSelected.connect(canvas.set_base_width)
    toolbar.undoRequested.connect(canvas.undo)
    toolbar.clearRequested.connect(canvas.clear)
    canvas.historyChanged.connect(lambda can_undo, _e: toolbar.set_undo_enabled(can_undo))
    toolbar.toolSelected.connect(lambda t: canvas_panel.set_status(TOOL_META[t][0], canvas.base_width, "XP-Pen"))

    def refresh_cursor(*_):
        canvas.setCursor(cursor_for(canvas.tool, canvas.color, canvas.base_width, canvas.devicePixelRatioF()))
    toolbar.toolSelected.connect(refresh_cursor)
    toolbar.colorSelected.connect(refresh_cursor)
    toolbar.widthSelected.connect(refresh_cursor)
    refresh_cursor()
    layout_path = Path.cwd() / "duzen.json"
    work.set_layout(lm.load_layout(layout_path))
    work.layoutChanged.connect(lambda lay: lm.save_layout(layout_path, lay))
    toolbar.layoutEditToggled.connect(work.set_edit_mode)
    work.editModeChanged.connect(toolbar.set_layout_edit)
    row.addWidget(toolbar); row.addWidget(work, 1)
    win.setCentralWidget(central)
    win.resize(1920, 1080)
    return win


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    fam = theme.load_fonts(paths.FONTS_DIR)
    app.setFont(theme.font(fam, 13))            # varsayılan aile; stil sayfası font-family kullanmaz
    app.setStyleSheet(theme.build_stylesheet(fam))
    win = build_window(parse_args(argv), fam)
    win.show()
    return app.exec()
