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
