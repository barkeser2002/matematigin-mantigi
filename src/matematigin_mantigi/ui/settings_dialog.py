"""⚙ Ayarlar: yazı tipi dosyası, soru yazma hızı, otomatik perde tonu, tahtadaki yazısal öğelerin görünürlüğü."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QSlider, QVBoxLayout)

from matematigin_mantigi.core.settings import VISIBILITY_KEYS, AppSettings
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies


@dataclass
class SettingsValues:
    font_file: str = ""
    reading_ms: int = 40
    auto_key: bool = True
    chroma_enabled: bool = True
    presenter_name: str = "Koray Varol"
    visible: dict[str, bool] = field(default_factory=dict)


def _card(title: str, fam: FontFamilies) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setStyleSheet(f"QFrame {{ background: {theme.PANEL}; border-radius: 6px; }}")
    col = QVBoxLayout(f); col.setContentsMargins(18, 14, 18, 16); col.setSpacing(8)
    t = QLabel(title); t.setFont(theme.font(fam, 12, 600, spacing_pct=110)); t.setStyleSheet(f"color: {theme.MUTED};")
    col.addWidget(t)
    return f, col


class SettingsDialog(QDialog):
    applied = pyqtSignal(object)      # SettingsValues

    def __init__(self, settings: AppSettings, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(560)
        root = QVBoxLayout(self); root.setContentsMargins(24, 20, 24, 20); root.setSpacing(14)

        title = QLabel("⚙ Ayarlar"); title.setFont(theme.font(fam, 20, 600)); root.addWidget(title)

        font_card, fcol = _card("Yazı tipi (soru ve ipuçları)", fam)
        row = QHBoxLayout()
        self.font_path_edit = QLineEdit(settings.font_file); self.font_path_edit.setReadOnly(True)
        self.font_path_edit.setPlaceholderText("Varsayılan: Work Sans")
        self.choose_font_button = QPushButton("Dosya seç…"); self.choose_font_button.setObjectName("pill")
        self.default_font_button = QPushButton("Varsayılan"); self.default_font_button.setObjectName("pill")
        self.choose_font_button.clicked.connect(self._choose_font)
        self.default_font_button.clicked.connect(lambda: self.font_path_edit.setText(""))
        row.addWidget(self.font_path_edit, 1); row.addWidget(self.choose_font_button); row.addWidget(self.default_font_button)
        fcol.addLayout(row)
        note = QLabel(".ttf veya .otf dosyası. Değişiklik uygulanınca soru metni, seçenekler ve ipucu kartları bu yazı tipine geçer.")
        note.setWordWrap(True); note.setFont(theme.font(fam, 10, 400)); note.setStyleSheet(f"color: {theme.MUTED};")
        fcol.addWidget(note)
        root.addWidget(font_card)

        speed_card, scol = _card("Soru yazma hızı", fam)
        row = QHBoxLayout()
        self.reading_slider = QSlider(Qt.Orientation.Horizontal); self.reading_slider.setRange(0, 150)
        self.reading_slider.setValue(settings.pen().reading_ms)
        self.reading_value = QLabel()
        self.reading_slider.valueChanged.connect(self._refresh_reading)
        row.addWidget(self.reading_slider, 1); row.addWidget(self.reading_value)
        scol.addLayout(row)
        self._refresh_reading()
        root.addWidget(speed_card)

        name_card, ncol = _card("Sunucu adı (el yazısı, webcam üstünde)", fam)
        self.presenter_edit = QLineEdit(settings.presenter_name)
        self.presenter_edit.setPlaceholderText("Boş bırakılırsa gösterilmez")
        ncol.addWidget(self.presenter_edit)
        root.addWidget(name_card)

        cam_card, ccol = _card("Yeşil perde", fam)
        self.chroma_check = QCheckBox("Yeşil perdeyi kaldır (kişi tahtanın üstüne biner)")
        self.chroma_check.setChecked(settings.chroma_enabled)
        self.auto_key_check = QCheckBox("Perde tonunu kameranın kenarlarından otomatik ölç")
        self.auto_key_check.setChecked(settings.auto_key)
        ccol.addWidget(self.chroma_check); ccol.addWidget(self.auto_key_check)
        root.addWidget(cam_card)

        vis_card, vcol = _card("Görünürlük (tahtadaki yazılar)", fam)
        self.visibility_checks: dict[str, QCheckBox] = {}
        for key, label in VISIBILITY_KEYS:
            cb = QCheckBox(label); cb.setChecked(settings.visible(key))
            vcol.addWidget(cb); self.visibility_checks[key] = cb
        root.addWidget(vis_card)

        buttons = QHBoxLayout(); buttons.addStretch(1)
        self.cancel_button = QPushButton("Vazgeç"); self.cancel_button.setObjectName("pill")
        self.apply_button = QPushButton("Uygula"); self.apply_button.setObjectName("accent")
        self.cancel_button.clicked.connect(self.reject); self.apply_button.clicked.connect(self._apply)
        buttons.addWidget(self.cancel_button); buttons.addWidget(self.apply_button)
        root.addLayout(buttons)

    def _choose_font(self) -> None:
        start = str(Path(self.font_path_edit.text()).parent) if self.font_path_edit.text() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Yazı tipi dosyası", start, "Yazı tipi (*.ttf *.otf)")
        if path:
            self.font_path_edit.setText(path)

    def _refresh_reading(self, *_) -> None:
        v = self.reading_slider.value()
        self.reading_value.setText("kapalı" if v == 0 else f"{v} ms/harf")

    def value(self) -> SettingsValues:
        return SettingsValues(font_file=self.font_path_edit.text().strip(),
                              reading_ms=self.reading_slider.value(),
                              auto_key=self.auto_key_check.isChecked(),
                              chroma_enabled=self.chroma_check.isChecked(),
                              presenter_name=self.presenter_edit.text().strip(),
                              visible={k: cb.isChecked() for k, cb in self.visibility_checks.items()})

    def _apply(self) -> None:
        self.applied.emit(self.value())
        self.accept()
