"""Soru bölgesi: kırmızı numara, kalın soru metni, görsel, A) B) C) D).
Soru değişince metin harf harf belirir; son harfler solarak (fade) gelir."""
from __future__ import annotations

import html
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QGraphicsBlurEffect, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from matematigin_mantigi.core.models import OPTION_LETTERS, Question
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.zone import Zone

IMAGE_MAX_HEIGHT = 260
FADE_ALPHAS = ("c0", "80", "40")     # son üç harf: eskiden yeniye doğru saydamlaşır (#AARRGGBB)


class QuestionZone(Zone):
    showRequested = pyqtSignal()
    hideRequested = pyqtSignal()
    readingFinished = pyqtSignal()

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self.shown = True
        self.reading_ms = 40                   # ms/harf; 0 = animasyon yok
        self.hide_link_enabled = True
        self.question: Question | None = None
        self._text = ""
        self._n = 0
        self._pending = False                  # bölge görünene kadar animasyon bekler
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.body.setContentsMargins(28, 22, 28, 18)

        self.content = QWidget(self)
        grid = QGridLayout(self.content)
        grid.setContentsMargins(0, 0, 0, 0); grid.setHorizontalSpacing(18); grid.setVerticalSpacing(8)
        self.number_label = QLabel("")
        self.number_label.setStyleSheet(f"color: {theme.QUESTION_NUMBER}; background: transparent;")
        grid.addWidget(self.number_label, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        col = QVBoxLayout(); col.setSpacing(12)
        self.image_label = QLabel(); self.image_label.hide()
        self.image_label.setStyleSheet("background: transparent;")
        self.text_label = QLabel("")
        self.text_label.setWordWrap(True)
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
        self.set_families(fam)

    # --- API ----------------------------------------------------------------
    @property
    def is_animating(self) -> bool:
        return self._timer.isActive()

    def set_reading_ms(self, ms: int) -> None:
        self.reading_ms = max(0, int(ms))

    def set_families(self, fam: FontFamilies) -> None:
        """Yazı tipini (ve tahta yazı ölçeğini, Görev 7) değiştirir (Ayarlar > yazı tipi dosyası)."""
        self.fam = fam
        self.number_label.setFont(theme.font(fam, 34, 700))
        self.text_label.setFont(theme.font(fam, 30, 700))
        self.hide_link.setFont(theme.font(fam, 11, 500))
        for lab in self.option_labels:
            lab.setFont(self._option_font())

    def _option_font(self) -> QFont:
        """A) B) C) D) etiketlerinin fontu -- set_families VE _build_options (yeni soruya geçince seçenek
        etiketleri yeniden kurulur) AYNI tek yerden okusun diye (eskiden ikisi de 24/400'ü kendi başına
        tekrarlıyordu; biri değişip diğeri unutulursa sessizce ayrışabilirdi)."""
        return theme.font(self.fam, 24, 400)

    def set_number_visible(self, on: bool) -> None:
        self.number_label.setVisible(on)

    def set_hide_link_enabled(self, on: bool) -> None:
        self.hide_link_enabled = on
        self.hide_link.setVisible(self.shown and on)

    def set_question(self, q: Question, display_no: int, animate: bool = True) -> None:
        self._timer.stop()
        self.question = q
        self.number_label.setText(f"{display_no}.")
        self._set_image(q.image)
        self._build_options(q.options)
        self._text = " ".join(q.soru.split())
        self._n = 0
        self._pending = False
        if animate and self.reading_ms > 0 and self._text:
            self.text_label.setText("")
            self.options_widget.hide()
            if self.isVisible():
                self._timer.start(self.reading_ms)
            else:
                self._pending = True           # pencere açılınca başlar, ilk soru da harf harf gelir
        else:
            self._finish()

    def skip_animation(self) -> None:
        if self.is_animating or self._pending:
            self._finish()

    def showEvent(self, e):
        super().showEvent(e)
        if self._pending:
            self._pending = False
            self._timer.start(self.reading_ms)

    def set_shown(self, shown: bool) -> None:
        self.shown = shown
        self.content.setGraphicsEffect(None if shown else QGraphicsBlurEffect())
        if not shown:
            self.content.graphicsEffect().setBlurRadius(16)
        self.show_button.setVisible(not shown)
        self.hide_link.setVisible(shown and self.hide_link_enabled)
        self._place_button()

    # --- internals -------------------------------------------------------------
    def _tick(self) -> None:
        self._n += 1
        self._render_partial()
        if self._n >= len(self._text):
            self._finish()

    def _render_partial(self) -> None:
        n, text = self._n, self._text
        trail = min(len(FADE_ALPHAS), n)
        ink = theme.INK.lstrip("#")
        parts = [html.escape(text[:n - trail])]
        alphas = FADE_ALPHAS[len(FADE_ALPHAS) - trail:]           # en yeni harf en saydam
        for alpha, ch in zip(alphas, text[n - trail:n]):
            parts.append(f'<span style="color:#{alpha}{ink}">{html.escape(ch)}</span>')
        self.text_label.setTextFormat(Qt.TextFormat.RichText)
        self.text_label.setText("".join(parts))

    def _finish(self) -> None:
        self._timer.stop()
        self._pending = False
        self._n = len(self._text)
        self.text_label.setTextFormat(Qt.TextFormat.PlainText)
        self.text_label.setText(self._text)
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
            self.options_grid.removeWidget(lab); lab.hide(); lab.deleteLater()
        self.option_labels = []
        if not options:
            self.options_widget.hide()
            return
        cols = 4 if max(len(o) for o in options) <= 10 else 2
        for i, (letter, text) in enumerate(zip(OPTION_LETTERS, options)):
            lab = QLabel(f"{letter}) {text}")
            lab.setFont(self._option_font())
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
