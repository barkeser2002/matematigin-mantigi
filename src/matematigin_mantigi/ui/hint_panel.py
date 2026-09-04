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
        self.setObjectName("hintRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(self); row.setContentsMargins(10, 8, 10, 8); row.setSpacing(12)
        self.name_label = ClickableLabel(f"İpucu {n}")
        self.name_label.setFont(theme.font(fam, 10, 600, spacing_pct=108))
        self.name_label.setStyleSheet(f"color: {theme.MUTED};"); self.name_label.setFixedWidth(64)
        self.text_label = ClickableLabel(text); self.text_label.setWordWrap(True)
        self.text_label.setFont(theme.font(fam, 15, 500))
        self.text_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.state_label = QLabel("gizli"); self.state_label.setFont(theme.font(fam, 10, 600))
        self.state_label.setStyleSheet(f"color: {theme.MUTED};")
        self.state_label.setFixedWidth(44)
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for lab in (self.name_label, self.text_label):
            lab.clicked.connect(self.clicked)
        row.addWidget(self.name_label); row.addWidget(self.text_label, 1); row.addWidget(self.state_label)

    def apply(self, mode: HintMaskMode, revealed: bool, focused: bool) -> None:
        self.revealed = revealed
        self.state_label.setText("açık" if revealed else "gizli")
        self.setStyleSheet(f"#hintRow {{ background: {theme.ROW_FOCUS if focused else 'transparent'};"
                           f" border-radius: 6px; }}")
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
        self.reveal_button.setMinimumWidth(72)        # "Gizle" etiketi de sığsın
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
