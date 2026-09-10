from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, qInstallMessageHandler
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox

from matematigin_mantigi import paths
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS
from matematigin_mantigi.core.question_loader import QuestionTemplateError, ensure_template, load_questions
from matematigin_mantigi.core.recorder import MssFfmpegRecorder
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
    p.add_argument("--duzen", default=None, help="Düzen dosyası (varsayılan: veri klasöründe duzen.json)")
    return p.parse_args(argv[1:])


def load_questions_or_samples(template: Path):
    try:
        return load_questions(ensure_template(template))
    except QuestionTemplateError as err:
        QMessageBox.warning(None, "Soru şablonu", f"{err}\n\nÖrnek sorularla devam ediliyor.")
        return list(SAMPLE_QUESTIONS)


def build_window(args: argparse.Namespace, fam: theme.FontFamilies, settings: AppSettings | None = None) -> MainWindow:
    settings = settings or AppSettings()
    if paths.is_frozen():
        paths.ensure_user_data()            # .app: ~/Documents/Matematiğin Mantığı (şablon + görseller kopyalanır)
    template = Path(args.sorular) if args.sorular else paths.default_template_path()
    questions = load_questions_or_samples(template)
    if args.kamera is not None:
        settings.camera_index = args.kamera
    factory = None if args.kamera_yok else (lambda index: OpenCvSource(index))
    layout_path = Path(args.duzen) if args.duzen else paths.default_layout_path()
    store = SessionStore()
    recorder = MssFfmpegRecorder(lambda: store.session_dir, fps=settings.record_fps,
                                 audio_device=settings.audio_device or None, out_height=settings.record_height)
    win = MainWindow(fam, questions, settings, recorder, store, factory, layout_path, questions_path=template)
    win.resize(1920, 1080)
    return win


_HARMLESS_QT_MESSAGES = ("cached device pixel ratio value was stale",
                         "QFont::setPointSize: Point size <= 0")      # piksel boyutlu uygulama fontuyla combo kutusu


def _qt_message_filter(mode, context, message: str) -> None:
    """Bilinen zararsız Qt uyarılarını süzer; gerisini stderr'e yazar."""
    if any(s in message for s in _HARMLESS_QT_MESSAGES):
        return
    print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    qInstallMessageHandler(_qt_message_filter)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    app.setApplicationName("Matematiğin Mantığı")
    fam = theme.load_fonts(paths.FONTS_DIR)
    app.setFont(theme.font(fam, 13))            # varsayılan aile; stil sayfası font-family kullanmaz
    app.setStyleSheet(theme.build_stylesheet(fam))
    win = build_window(parse_args(argv), fam)
    win.show()
    return app.exec()
