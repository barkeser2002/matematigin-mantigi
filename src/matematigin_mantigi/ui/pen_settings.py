"""Kalem, silgi & imleç ayarları penceresi (mockup 'Kalem ayarları' ekranı)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QPushButton, QSlider, QVBoxLayout)

from matematigin_mantigi.core.models import Nib, PenSettings
from matematigin_mantigi.ui import cursors, theme
from matematigin_mantigi.ui.theme import FontFamilies


def _card(title: str, fam: FontFamilies) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setStyleSheet(f"QFrame {{ background: {theme.PANEL}; border-radius: 6px; }}")
    col = QVBoxLayout(f); col.setContentsMargins(18, 14, 18, 16); col.setSpacing(10)
    t = QLabel(title); t.setFont(theme.font(fam, 12, 600, spacing_pct=110)); t.setStyleSheet(f"color: {theme.MUTED};")
    col.addWidget(t)
    return f, col


class PenSettingsDialog(QDialog):
    applied = pyqtSignal(object)

    def __init__(self, current: PenSettings, color: QColor, base_width: int, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kalem, silgi & imleç")
        self.setMinimumWidth(720)
        root = QVBoxLayout(self); root.setContentsMargins(24, 20, 24, 20); root.setSpacing(14)

        head = QHBoxLayout()
        nine = QLabel("9"); nine.setFont(theme.hand_font(fam, 36, 700))
        title = QLabel("Kalem, silgi & imleç"); title.setFont(theme.font(fam, 20, 600))
        sub = QLabel("XP-Pen Deco · macOS · 8192 basınç seviyesi"); sub.setFont(theme.font(fam, 11, 500))
        sub.setStyleSheet(f"color: {theme.MUTED};")
        head.addWidget(nine); head.addWidget(title); head.addStretch(1); head.addWidget(sub)
        root.addLayout(head)

        grid = QGridLayout(); grid.setSpacing(14)

        cur_card, cur_col = _card("Özel imleçler", fam)
        note = QLabel("İmleç seçili araca ve renge göre değişir."); note.setFont(theme.font(fam, 11, 400))
        cur_col.addWidget(note)
        tiles = QHBoxLayout(); tiles.setSpacing(18)
        for label, cur in ((f"Kalem · {color.name()}", cursors.pen_cursor(color, base_width)),
                           ("Silgi", cursors.eraser_cursor(base_width)),
                           ("Lazer", cursors.laser_cursor())):
            tile = QVBoxLayout(); pic = QLabel(); pic.setPixmap(cur.pixmap()); pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cap = QLabel(label); cap.setFont(theme.font(fam, 10, 500)); cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tile.addWidget(pic); tile.addWidget(cap); tiles.addLayout(tile)
        cur_col.addLayout(tiles)
        grid.addWidget(cur_card, 0, 0)

        pen_card, pen_col = _card("Kalem", fam)
        form = QFormLayout(); form.setSpacing(8)
        self.curve_slider = self._slider(0, 100, current.pressure_curve)
        self.smoothing_slider = self._slider(0, 100, current.smoothing)
        self.min_slider = self._slider(1, 30, current.min_width)
        self.max_slider = self._slider(1, 40, current.max_width)
        self.reading_slider = self._slider(0, 800, current.reading_ms)
        self.curve_value = QLabel(); self.smoothing_value = QLabel(); self.min_value = QLabel(); self.max_value = QLabel()
        self.reading_value = QLabel()
        for name, slider, value in (("Basınç eğrisi", self.curve_slider, self.curve_value),
                                    ("Yumuşatma", self.smoothing_slider, self.smoothing_value),
                                    ("Min. kalınlık", self.min_slider, self.min_value),
                                    ("Maks. kalınlık", self.max_slider, self.max_value),
                                    ("Okuma hızı", self.reading_slider, self.reading_value)):
            row = QHBoxLayout(); row.addWidget(slider, 1); row.addWidget(value)
            lab = QLabel(name); lab.setFont(theme.font(fam, 11, 500))
            form.addRow(lab, row)
        pen_col.addLayout(form)
        nib_row = QHBoxLayout(); nib_row.setSpacing(6)
        nib_lab = QLabel("Kalem ucu"); nib_lab.setFont(theme.font(fam, 11, 500)); nib_row.addWidget(nib_lab)
        self._nib_group = QButtonGroup(self); self._nib_group.setExclusive(True)
        self.nib_buttons: dict[Nib, QPushButton] = {}
        for nib in Nib:
            b = QPushButton(nib.value); b.setObjectName("pill"); b.setCheckable(True)
            self._nib_group.addButton(b); self.nib_buttons[nib] = b; nib_row.addWidget(b)
        self.nib_buttons[current.nib].setChecked(True)
        nib_row.addStretch(1); pen_col.addLayout(nib_row)
        grid.addWidget(pen_card, 0, 1)

        fx_card, fx_col = _card("Otomatik FX (Keras)", fam)
        fx_note = QLabel("El yazısı matematiksel anlama dönüşür; çizim estetiği düzeltilir.")
        fx_note.setFont(theme.font(fam, 11, 400)); fx_col.addWidget(fx_note)
        self.toggles: dict[str, QCheckBox] = {}
        for key, name, desc, on in (
            ("math_recognition", "Matematik tanıma", "El yazısı denklemleri düzgün metne çevir", current.math_recognition),
            ("shape_correction", "Şekil düzeltme", "Titrek daire/çizgi → geometrik şekil", current.shape_correction),
            ("autosave", "Otomatik kaydet", "Her 30 sn ve soru değişiminde", current.autosave),
            ("template_matching", "Ön tanımlı soru tanıma", "Yazılan soruyu şablonla eşleştir", current.template_matching),
        ):
            cb = QCheckBox(name); cb.setChecked(on); cb.setFont(theme.font(fam, 12, 600))
            d = QLabel(desc); d.setFont(theme.font(fam, 10, 400)); d.setStyleSheet(f"color: {theme.MUTED};")
            fx_col.addWidget(cb); fx_col.addWidget(d)
            self.toggles[key] = cb
        grid.addWidget(fx_card, 1, 0, 1, 2)
        root.addLayout(grid)

        preview_card, preview_col = _card("Canlı tanıma önizlemesi", fam)
        prow = QHBoxLayout()
        for hand, typed in (("3x + 5 = 20", "3x + 5 = 20"), ("x = 15 / 3", "x = 15 ÷ 3"),
                            ("2/3 + 1/6", "²⁄₃ + ¹⁄₆ = ⁵⁄₆"), ("Ç = 2(a+b)", "Ç = 2 · (a + b)")):
            cell = QVBoxLayout()
            h = QLabel(hand); h.setFont(theme.hand_font(fam, 22, 500))
            arrow = QLabel("↓ tanındı"); arrow.setFont(theme.font(fam, 9, 600)); arrow.setStyleSheet(f"color: {theme.OK_DOT};")
            t = QLabel(typed); t.setFont(theme.font(fam, 14, 500))
            for w in (h, arrow, t):
                w.setAlignment(Qt.AlignmentFlag.AlignCenter); cell.addWidget(w)
            prow.addLayout(cell)
        preview_col.addLayout(prow)
        root.addWidget(preview_card)

        buttons = QHBoxLayout(); buttons.addStretch(1)
        self.cancel_button = QPushButton("Vazgeç"); self.cancel_button.setObjectName("pill")
        self.apply_button = QPushButton("Uygula"); self.apply_button.setObjectName("accent")
        self.cancel_button.clicked.connect(self.reject); self.apply_button.clicked.connect(self._apply)
        buttons.addWidget(self.cancel_button); buttons.addWidget(self.apply_button)
        root.addLayout(buttons)

        for s in (self.curve_slider, self.smoothing_slider, self.min_slider, self.max_slider, self.reading_slider):
            s.valueChanged.connect(self._refresh_values)
        self.min_slider.valueChanged.connect(lambda v: self.max_slider.setValue(max(v, self.max_slider.value())))
        self.max_slider.valueChanged.connect(lambda v: self.min_slider.setValue(min(v, self.min_slider.value())))
        self._refresh_values()

    def _slider(self, lo: int, hi: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal); s.setRange(lo, hi); s.setValue(value); return s

    def _refresh_values(self, *_):
        curve = self.curve_slider.value()
        self.curve_value.setText("Doğrusal" if 45 <= curve <= 55 else ("Yumuşak" if curve < 45 else "Sert"))
        self.smoothing_value.setText(f"%{self.smoothing_slider.value()}")
        self.min_value.setText(f"{self.min_slider.value()} px")
        self.max_value.setText(f"{self.max_slider.value()} px")
        r = self.reading_slider.value()
        self.reading_value.setText("kapalı" if r == 0 else f"{r} ms/kelime")

    def value(self) -> PenSettings:
        nib = next(n for n, b in self.nib_buttons.items() if b.isChecked())
        return PenSettings(pressure_curve=self.curve_slider.value(), smoothing=self.smoothing_slider.value(),
                           min_width=self.min_slider.value(), max_width=self.max_slider.value(), nib=nib,
                           math_recognition=self.toggles["math_recognition"].isChecked(),
                           shape_correction=self.toggles["shape_correction"].isChecked(),
                           autosave=self.toggles["autosave"].isChecked(),
                           template_matching=self.toggles["template_matching"].isChecked(),
                           reading_ms=self.reading_slider.value())

    def _apply(self) -> None:
        self.applied.emit(self.value())
        self.accept()
