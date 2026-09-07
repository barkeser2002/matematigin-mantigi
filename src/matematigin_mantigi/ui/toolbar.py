from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
                             QSizePolicy, QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import PALETTE, TOOL_META, WIDTHS, Tool
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.widgets import DotButton, GlyphButton, RecordButton, SwatchButton, WrapButton

_BTN_CSS = (f"QPushButton {{ background: {theme.TOOLBAR_BTN}; color: {theme.TOOLBAR_MUTED}; border: none;"
            f" border-radius: 6px; padding: 5px 3px; font-size: 10px; font-weight: 600; }}"
            f"QPushButton:checked {{ background: {theme.ACCENT}; color: white; }}"
            f"QPushButton:disabled {{ color: {theme.TOOLBAR_DIM}; }}")


class ToolBar(QWidget):
    """Bölge 9: dış araç çubuğu. Kayıtta görünmez."""

    toolSelected = pyqtSignal(object)      # Tool
    colorSelected = pyqtSignal(str)        # hex
    widthSelected = pyqtSignal(int)
    workToggled = pyqtSignal()
    prevRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    undoRequested = pyqtSignal()
    clearRequested = pyqtSignal()
    recordToggled = pyqtSignal(bool)
    penSettingsRequested = pyqtSignal()
    settingsRequested = pyqtSignal()
    layoutEditToggled = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self.setFixedWidth(theme.TOOLBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {theme.INK};")
        self.setAutoFillBackground(True)

        col = QVBoxLayout(self)
        col.setContentsMargins(10, 14, 10, 14)
        col.setSpacing(6)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        nine = QLabel("9"); nine.setFont(theme.hand_font(fam, 40, 700))
        nine.setStyleSheet(f"color: {theme.PANEL_SOFT};")
        col.addWidget(nine, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addWidget(self._caption("KAYITTA\nGÖRÜNMEZ"))

        self.pen_settings_button = QPushButton("Kalem"); self.pen_settings_button.setStyleSheet(_BTN_CSS)
        self.pen_settings_button.clicked.connect(self.penSettingsRequested)
        self.settings_button = QPushButton("⚙ Ayarlar"); self.settings_button.setStyleSheet(_BTN_CSS)
        self.settings_button.clicked.connect(self.settingsRequested)
        self.layout_button = QPushButton("⧉ Düzen"); self.layout_button.setCheckable(True)
        self.layout_button.setStyleSheet(_BTN_CSS)
        self.layout_button.toggled.connect(self.layoutEditToggled)
        col.addWidget(self.pen_settings_button); col.addWidget(self.settings_button); col.addWidget(self.layout_button)
        col.addWidget(self._rule())

        self._tool_group = QButtonGroup(self); self._tool_group.setExclusive(True)
        self.tool_buttons: dict[Tool, GlyphButton] = {}
        for tool, (label, glyph) in TOOL_META.items():
            b = GlyphButton(glyph, label)
            self._tool_group.addButton(b)
            self.tool_buttons[tool] = b
            b.clicked.connect(lambda _c=False, t=tool: self.toolSelected.emit(t))   # seçiliyken de yayar (şekil döngüsü)
            col.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        self.tool_buttons[Tool.SHAPE].setToolTip("Tekrar basınca şekil değişir: dikdörtgen, elips, üçgen, çizgi")
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
        for group in (WIDTHS[:3], WIDTHS[3:]):        # 5 kademe: 3 + 2, ortalı
            wrow = QHBoxLayout(); wrow.setSpacing(0); wrow.addStretch(1)
            for w in group:
                d = DotButton(w); self._width_group.addButton(d); self.width_buttons[w] = d
                d.clicked.connect(lambda _c=False, v=w: self.widthSelected.emit(v))
                wrow.addWidget(d)
            wrow.addStretch(1)
            col.addLayout(wrow)
        self.width_buttons[4].setChecked(True)
        col.addWidget(self._rule())

        col.addWidget(self._caption("SORU AKIŞI"))
        self.work_button = WrapButton("Soruyu işle"); self.work_button.setStyleSheet(_BTN_CSS)
        self.work_button.clicked.connect(self.workToggled)
        self.prev_button = WrapButton("← Önceki soru"); self.prev_button.setStyleSheet(_BTN_CSS)
        self.prev_button.clicked.connect(self.prevRequested)
        self.next_button = WrapButton("Sıradaki soru →"); self.next_button.setStyleSheet(_BTN_CSS)
        self.next_button.clicked.connect(self.nextRequested)
        self.progress_label = self._caption("0/0")
        self.progress_label.setWordWrap(True)         # "0/3 tamamlandı · S1" iki satıra kırılır
        col.addWidget(self.work_button); col.addWidget(self.prev_button); col.addWidget(self.next_button)
        col.addWidget(self.progress_label)
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

    def set_shape_glyph(self, glyph: str) -> None:
        b = self.tool_buttons[Tool.SHAPE]
        b.glyph = glyph
        b.update()

    def set_layout_edit(self, on: bool) -> None:
        self.layout_button.blockSignals(True); self.layout_button.setChecked(on); self.layout_button.blockSignals(False)
