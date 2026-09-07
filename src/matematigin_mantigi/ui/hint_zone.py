"""Akıllı ipuçları bölgesi: ampul başlık, krem/turuncu kartlar. Kartlar tıklanmadan açılmaz."""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QGraphicsBlurEffect, QHBoxLayout, QLabel, QPushButton,
                             QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import HintMaskMode
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.zone import Zone


class BulbIcon(QWidget):
    """Basit ampul: sarı daire + koyu kenar + küçük duy."""

    def __init__(self, size: int = 20, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _e):
        s = self.width()
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(theme.HINT_HEADING), max(1.0, s / 14)))
        p.setBrush(QColor(theme.BULB))
        p.drawEllipse(QPointF(s / 2, s * 0.42), s * 0.32, s * 0.32)
        p.setBrush(QColor(theme.HINT_HEADING)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(s * 0.36, s * 0.74, s * 0.28, s * 0.18), 2, 2)
        p.end()


class HintCard(QWidget):
    clicked = pyqtSignal()

    def __init__(self, text: str, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.revealed = False
        # Açılış animasyonu QTimer ile: QPropertyAnimation yıkım sırasında finished yayıp yarı yıkılmış
        # karta dokunabiliyor (erişim ihlali); QTimer yıkımda sinyal yaymaz.
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(16)
        self._fade_timer.timeout.connect(self._fade_step)
        self._fade_from, self._fade_ms, self._fade_elapsed = 0.0, 0, 0
        self.setObjectName("hintCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self); row.setContentsMargins(14, 10, 16, 10); row.setSpacing(12)
        self.icon = BulbIcon(20)
        self.text_label = QLabel(text); self.text_label.setWordWrap(True)
        self.text_label.setFont(theme.font(fam, 16, 500))
        row.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop); row.addWidget(self.text_label, 1)

    def apply(self, mode: HintMaskMode, revealed: bool, focused: bool, anim_ms: int = 0) -> None:
        self.revealed = revealed
        border = theme.HINT_CARD_BORDER_FOCUS if focused else theme.HINT_CARD_BORDER
        self.setStyleSheet(f"#hintCard {{ background: {theme.HINT_CARD_BG}; border: {3 if focused else 2}px solid {border};"
                           f" border-radius: 10px; }}")
        if revealed:
            self.text_label.setStyleSheet("background: transparent;")
            eff = self.text_label.graphicsEffect()
            if self._fade_timer.isActive():
                return                                    # açılma animasyonu sürüyor
            if anim_ms > 0 and isinstance(eff, QGraphicsBlurEffect):
                self._fade_from, self._fade_ms, self._fade_elapsed = eff.blurRadius(), anim_ms, 0
                self._fade_timer.start()
            else:
                self.text_label.setGraphicsEffect(None)
        elif mode == HintMaskMode.BLUR:
            self.text_label.setStyleSheet("background: transparent;")
            eff = QGraphicsBlurEffect(); eff.setBlurRadius(9)
            self.text_label.setGraphicsEffect(eff)
        else:
            self.text_label.setGraphicsEffect(None)
            self.text_label.setStyleSheet(f"background: {theme.INK}; color: {theme.INK}; border-radius: 3px;")

    def _fade_step(self) -> None:
        self._fade_elapsed += self._fade_timer.interval()
        eff = self.text_label.graphicsEffect()
        if not isinstance(eff, QGraphicsBlurEffect):
            self._fade_timer.stop()
            return
        t = min(1.0, self._fade_elapsed / max(1, self._fade_ms))
        ease = 1 - (1 - t) ** 3                          # out-cubic
        eff.setBlurRadius(self._fade_from * (1 - ease))
        if t >= 1.0:
            self._fade_timer.stop()
            self.text_label.setGraphicsEffect(None)

    def stop_animation(self) -> None:
        self._fade_timer.stop()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        e.accept()                          # kart tıklaması tahtaya çizim olarak gitmez


class HintZone(Zone):
    maskModeChanged = pyqtSignal(object)
    prevRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    revealToggled = pyqtSignal(int)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self.mask_mode = HintMaskMode.BLUR
        self.reveal_anim_ms = 300                    # kart açılırken bulanıklık bu sürede çözülür (0 = anında)
        self._focus = 0
        self.cards: list[HintCard] = []
        self.body.setContentsMargins(24, 18, 24, 14)
        self.body.setSpacing(10)

        head = QHBoxLayout(); head.setSpacing(8)
        self.heading_icon = BulbIcon(28)
        head.addWidget(self.heading_icon)
        self.title_label = QLabel("AKILLI İPUÇLARI")
        self.title_label.setFont(theme.font(fam, 20, 700, spacing_pct=104))
        self.title_label.setStyleSheet(f"color: {theme.HINT_HEADING}; background: transparent;")
        head.addWidget(self.title_label); head.addStretch(1)
        self.counter_label = QLabel("0 / 0"); self.counter_label.setFont(theme.font(fam, 10, 600))
        self.counter_label.setStyleSheet(f"color: {theme.MUTED}; background: transparent;")
        self.prev_button = QPushButton("◀"); self.next_button = QPushButton("▶")
        for b in (self.prev_button, self.next_button):
            b.setObjectName("pill"); b.setFixedWidth(30)
        self.prev_button.clicked.connect(self.prevRequested); self.next_button.clicked.connect(self.nextRequested)
        self.blur_button = QPushButton("Blur"); self.redact_button = QPushButton("Redakte")
        grp = QButtonGroup(self); grp.setExclusive(True)
        for b in (self.blur_button, self.redact_button):
            b.setObjectName("pill"); b.setCheckable(True); grp.addButton(b)
        self.blur_button.setChecked(True)
        self.blur_button.clicked.connect(lambda: self._set_mode_from_ui(HintMaskMode.BLUR))
        self.redact_button.clicked.connect(lambda: self._set_mode_from_ui(HintMaskMode.REDACT))
        for w in (self.counter_label, self.prev_button, self.next_button, self.blur_button, self.redact_button):
            head.addWidget(w)
        self.body.addLayout(head)

        self.rule = QFrame(); self.rule.setFixedHeight(2)
        self.rule.setStyleSheet(f"background: {theme.HINT_CARD_BORDER};")
        self.body.addWidget(self.rule)

        self.cards_host = QWidget(); self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 4, 0, 0); self.cards_layout.setSpacing(10)
        self.body.addWidget(self.cards_host); self.body.addStretch(1)

    # --- API -------------------------------------------------------------------
    def set_hints(self, question_id: str, hints: Sequence[str]) -> None:
        for c in self.cards:
            c.stop_animation()
            self.cards_layout.removeWidget(c); c.hide(); c.deleteLater()     # hide: silinene kadar görünmesin
        self.cards = []
        for i, text in enumerate(hints):
            card = HintCard(text, self.fam)
            card.clicked.connect(lambda k=i: self.revealToggled.emit(k))
            self.cards_layout.addWidget(card); self.cards.append(card)
        self._focus = 0
        self._apply_click_through()          # yeni kartlar da geçerli moda uysun
        self._refresh()

    def set_focus(self, i: int) -> None:
        self._focus = max(0, min(len(self.cards) - 1, i)) if self.cards else 0
        self._refresh()

    def set_revealed(self, i: int, revealed: bool) -> None:
        if 0 <= i < len(self.cards):
            self.cards[i].revealed = revealed
            self._refresh()

    def set_mask_mode(self, m: HintMaskMode) -> None:
        self.mask_mode = m
        (self.blur_button if m == HintMaskMode.BLUR else self.redact_button).setChecked(True)
        self._refresh()

    def set_controls_visible(self, on: bool) -> None:
        for w in (self.counter_label, self.prev_button, self.next_button, self.blur_button, self.redact_button):
            w.setVisible(on)

    def set_heading_visible(self, on: bool) -> None:
        self.title_label.setVisible(on)
        self.heading_icon.setVisible(on)
        self.rule.setVisible(on)

    def set_families(self, fam: FontFamilies) -> None:
        """Yazı tipini değiştirir (Ayarlar > yazı tipi dosyası)."""
        self.fam = fam
        self.title_label.setFont(theme.font(fam, 20, 700, spacing_pct=104))
        for c in self.cards:
            c.text_label.setFont(theme.font(fam, 16, 500))

    # --- internals ----------------------------------------------------------------
    def _set_mode_from_ui(self, m: HintMaskMode) -> None:
        self.mask_mode = m
        self._refresh()
        self.maskModeChanged.emit(m)

    def _refresh(self) -> None:
        n = len(self.cards)
        self.counter_label.setText(f"{self._focus + 1 if n else 0} / {n}")
        for i, c in enumerate(self.cards):
            c.apply(self.mask_mode, c.revealed, i == self._focus, self.reveal_anim_ms)
