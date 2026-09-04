from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

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
