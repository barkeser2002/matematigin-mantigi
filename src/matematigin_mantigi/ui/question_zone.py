"""Soru bölgesi: kırmızı numara, kalın soru metni, görsel, A) B) C) D). Soru değişince okuma animasyonu."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPixmap
from PyQt6.QtWidgets import QGraphicsBlurEffect, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from matematigin_mantigi.core.models import OPTION_LETTERS, Question
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.zone import Zone

IMAGE_MAX_HEIGHT = 260


class QuestionZone(Zone):
    showRequested = pyqtSignal()
    hideRequested = pyqtSignal()
    readingFinished = pyqtSignal()

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self.shown = True
        self.reading_ms = 150
        self.question: Question | None = None
        self._words: list[str] = []
        self._n = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.body.setContentsMargins(28, 22, 28, 18)

        self.content = QWidget(self)
        grid = QGridLayout(self.content)
        grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(8)
        self.number_label = QLabel("")
        self.number_label.setFont(theme.font(fam, 34, 700))
        self.number_label.setStyleSheet(f"color: {theme.QUESTION_NUMBER}; background: transparent;")
        grid.addWidget(self.number_label, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        col = QVBoxLayout(); col.setSpacing(12)
        self.image_label = QLabel(); self.image_label.hide()
        self.image_label.setStyleSheet("background: transparent;")
        self.text_label = QLabel("")
        self.text_label.setWordWrap(True)
        self.text_label.setFont(theme.font(fam, 30, 700))
        self.text_label.setStyleSheet("background: transparent;")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.options_widget = QWidget()
        self.options_grid = QGridLayout(self.options_widget)
        self.options_grid.setContentsMargins(0, 4, 0, 0); self.options_grid.setHorizontalSpacing(40)
        self.options_grid.setVerticalSpacing(6)
        self.option_labels: list[QLabel] = []
        col.addWidget(self.image_label, 0, Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.text_label)
        col.addWidget(self.options_widget, 0, Qt.AlignmentFlag.AlignLeft)
        col.addStretch(1)
        grid.addLayout(col, 0, 1)
        grid.setColumnStretch(1, 1)

        head = QHBoxLayout(); head.setContentsMargins(0, 0, 0, 0)
        self.hide_link = QPushButton("gizle"); self.hide_link.setObjectName("link")
        self.hide_link.setFont(theme.font(fam, 11, 500))
        self.hide_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hide_link.clicked.connect(self.hideRequested)
        head.addStretch(1); head.addWidget(self.hide_link)
        self.body.addLayout(head)
        self.body.addWidget(self.content, 1)

        self.show_button = QPushButton("?  Soruyu göster", self)
        self.show_button.setObjectName("accent")
        self.show_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_button.clicked.connect(self.showRequested)
        self.show_button.hide()

    # --- API ----------------------------------------------------------------
    @property
    def is_animating(self) -> bool:
        return self._timer.isActive()

    def set_reading_ms(self, ms: int) -> None:
        self.reading_ms = max(0, int(ms))

    def set_question(self, q: Question, display_no: int, animate: bool = True) -> None:
        self._timer.stop()
        self.question = q
        self.number_label.setText(f"{display_no}.")
        self._set_image(q.image)
        self._build_options(q.options)
        self._words = q.soru.split()
        self._n = 0
        if animate and self.reading_ms > 0 and self._words:
            self.text_label.setText("")
            self.options_widget.hide()
            self._timer.start(self.reading_ms)
        else:
            self._finish()

    def skip_animation(self) -> None:
        if self.is_animating:
            self._finish()

    def set_shown(self, shown: bool) -> None:
        self.shown = shown
        self.content.setGraphicsEffect(None if shown else QGraphicsBlurEffect())
        if not shown:
            self.content.graphicsEffect().setBlurRadius(16)
        self.show_button.setVisible(not shown)
        self.hide_link.setVisible(shown)
        self._place_button()

    # --- internals -------------------------------------------------------------
    def _tick(self) -> None:
        self._n += 1
        self.text_label.setText(" ".join(self._words[:self._n]))
        if self._n >= len(self._words):
            self._finish()

    def _finish(self) -> None:
        self._timer.stop()
        self._n = len(self._words)
        self.text_label.setText(" ".join(self._words))
        self.options_widget.setVisible(bool(self.option_labels))
        self.readingFinished.emit()

    def _set_image(self, path: str | None) -> None:
        pm = QPixmap(path) if path and Path(path).exists() else QPixmap()
        if pm.isNull():
            self.image_label.clear(); self.image_label.hide()
            return
        max_w = max(200, self.width() - 140)
        self.image_label.setPixmap(pm.scaled(QSize(max_w, IMAGE_MAX_HEIGHT), Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))
        self.image_label.show()

    def _build_options(self, options: tuple[str, ...]) -> None:
        for lab in self.option_labels:
            self.options_grid.removeWidget(lab); lab.deleteLater()
        self.option_labels = []
        if not options:
            self.options_widget.hide()
            return
        cols = 4 if max(len(o) for o in options) <= 10 else 2
        for i, (letter, text) in enumerate(zip(OPTION_LETTERS, options)):
            lab = QLabel(f"{letter}) {text}")
            lab.setFont(theme.font(self.fam, 24, 400))
            lab.setStyleSheet("background: transparent;")
            self.options_grid.addWidget(lab, i // cols, i % cols, Qt.AlignmentFlag.AlignLeft)
            self.option_labels.append(lab)
        self.options_widget.setVisible(True)

    def _place_button(self) -> None:
        self.show_button.adjustSize()
        self.show_button.move((self.width() - self.show_button.width()) // 2,
                              (self.height() - self.show_button.height()) // 2)
        self.show_button.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_button()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if self.is_animating and e.button() == Qt.MouseButton.LeftButton:
            self.skip_animation()          # tıklayınca metin anında tamamlanır
            e.accept()
            return
        super().mousePressEvent(e)

    def event(self, e):
        if e.type() == QEvent.Type.Show and self.question is not None and self.image_label.isVisible():
            pass
        return super().event(e)
