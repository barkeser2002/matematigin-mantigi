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
