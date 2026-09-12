"""⚙ Ayarlar: yazı tipi dosyası, soru yazma hızı, otomatik perde tonu, tahtadaki yazısal öğelerin görünürlüğü."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import FrameStyle
from matematigin_mantigi.core.recorder import RESOLUTIONS
from matematigin_mantigi.core.settings import VISIBILITY_KEYS, AppSettings
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.frames import FRAME_SPECS
from matematigin_mantigi.ui.theme import FontFamilies


@dataclass
class SettingsValues:
    font_file: str = ""
    reading_ms: int = 40
    auto_key: bool = True
    chroma_enabled: bool = True
    presenter_name: str = "Koray Varol"
    logo_file: str = ""
    logo_size: int = 48
    camera_index: int = 0
    record_fps: int = 60
    record_height: int = 1440
    audio_device: str = ""
    aspect_lock: bool = True
    frame_style: FrameStyle = FrameStyle.CLASSIC
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
        # Kartlar kaydırılabilir alanda; küçük ekranlarda (MacBook) Uygula düğmesi hep görünür kalır.
        self.content = QWidget(); col = QVBoxLayout(self.content); col.setContentsMargins(0, 0, 8, 0); col.setSpacing(14)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.content); self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.content.setStyleSheet("background: transparent;")
        root.addWidget(self.scroll, 1)

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
        col.addWidget(font_card)

        speed_card, scol = _card("Soru yazma hızı", fam)
        row = QHBoxLayout()
        self.reading_slider = QSlider(Qt.Orientation.Horizontal); self.reading_slider.setRange(0, 150)
        self.reading_slider.setValue(settings.pen().reading_ms)
        self.reading_value = QLabel()
        self.reading_slider.valueChanged.connect(self._refresh_reading)
        row.addWidget(self.reading_slider, 1); row.addWidget(self.reading_value)
        scol.addLayout(row)
        self._refresh_reading()
        col.addWidget(speed_card)

        logo_card, lcol = _card("Logo (sol üst)", fam)
        row = QHBoxLayout()
        self.logo_path_edit = QLineEdit(settings.logo_file); self.logo_path_edit.setReadOnly(True)
        self.logo_path_edit.setPlaceholderText("Seçilmezse 'MM' monogramı")
        self.choose_logo_button = QPushButton("Dosya seç…"); self.choose_logo_button.setObjectName("pill")
        self.clear_logo_button = QPushButton("Kaldır"); self.clear_logo_button.setObjectName("pill")
        self.choose_logo_button.clicked.connect(self._choose_logo)
        self.clear_logo_button.clicked.connect(lambda: self.logo_path_edit.setText(""))
        row.addWidget(self.logo_path_edit, 1); row.addWidget(self.choose_logo_button); row.addWidget(self.clear_logo_button)
        lcol.addLayout(row)
        row = QHBoxLayout()
        size_lab = QLabel("Boyut"); size_lab.setFont(theme.font(fam, 11, 500))
        self.logo_size_slider = QSlider(Qt.Orientation.Horizontal); self.logo_size_slider.setRange(24, 200)
        self.logo_size_slider.setValue(settings.logo_size)
        self.logo_size_value = QLabel(f"{settings.logo_size} px")
        self.logo_size_slider.valueChanged.connect(lambda v: self.logo_size_value.setText(f"{v} px"))
        row.addWidget(size_lab); row.addWidget(self.logo_size_slider, 1); row.addWidget(self.logo_size_value)
        lcol.addLayout(row)
        col.addWidget(logo_card)

        board_card, bcol = _card("Tahta", fam)
        self.aspect_lock_check = QCheckBox("Tahtayı 16:9 oranında tut (kenarlarda bant)")
        self.aspect_lock_check.setChecked(settings.aspect_lock)
        bcol.addWidget(self.aspect_lock_check)
        board_note = QLabel("Açıkken tahta pencerede ortalanır ve kayıt tam 16:9 olur; kapalıyken tüm pencereyi kaplar.")
        board_note.setWordWrap(True); board_note.setFont(theme.font(fam, 10, 400)); board_note.setStyleSheet(f"color: {theme.MUTED};")
        bcol.addWidget(board_note)
        row = QHBoxLayout()
        style_lab = QLabel("Çerçeve stili"); style_lab.setFont(theme.font(fam, 11, 500))
        self.frame_style_combo = QComboBox()
        for style, spec in FRAME_SPECS.items():
            self.frame_style_combo.addItem(spec.label, style)
        idx = self.frame_style_combo.findData(settings.frame_style)
        self.frame_style_combo.setCurrentIndex(idx if idx >= 0 else 0)
        row.addWidget(style_lab); row.addWidget(self.frame_style_combo, 1)
        bcol.addLayout(row)
        col.addWidget(board_card)

        rec_card, rcol = _card("Kayıt (mss + ffmpeg, MP4)", fam)
        row = QHBoxLayout()
        fps_lab = QLabel("Kare hızı"); fps_lab.setFont(theme.font(fam, 11, 500))
        self.fps_combo = QComboBox()
        for f in (30, 60):
            self.fps_combo.addItem(f"{f} fps", f)
        self.fps_combo.setCurrentIndex(self.fps_combo.findData(settings.record_fps))
        res_lab = QLabel("Çözünürlük"); res_lab.setFont(theme.font(fam, 11, 500))
        self.res_combo = QComboBox()
        for label, h in RESOLUTIONS:
            self.res_combo.addItem(label, h)
        idx = self.res_combo.findData(settings.record_height)
        self.res_combo.setCurrentIndex(idx if idx >= 0 else 2)
        row.addWidget(fps_lab); row.addWidget(self.fps_combo); row.addSpacing(12)
        row.addWidget(res_lab); row.addWidget(self.res_combo, 1)
        rcol.addLayout(row)
        row = QHBoxLayout()
        mic_lab = QLabel("Mikrofon"); mic_lab.setFont(theme.font(fam, 11, 500))
        self.audio_combo = QComboBox(); self.audio_combo.setEditable(True)
        self.audio_combo.addItem("(ses yok)", "")
        if settings.audio_device:
            self.audio_combo.addItem(settings.audio_device, settings.audio_device)
            self.audio_combo.setCurrentIndex(1)
        self.list_audio_button = QPushButton("Ses aygıtlarını listele"); self.list_audio_button.setObjectName("pill")
        self.list_audio_button.clicked.connect(self._list_audio)
        row.addWidget(mic_lab); row.addWidget(self.audio_combo, 1); row.addWidget(self.list_audio_button)
        rcol.addLayout(row)
        rec_note = QLabel("Kayıt dosyası: oturum/<tarih>/kayit_<saat>.mp4. Araç çubuğu kayda girmez.")
        rec_note.setFont(theme.font(fam, 10, 400)); rec_note.setStyleSheet(f"color: {theme.MUTED};")
        rcol.addWidget(rec_note)
        col.addWidget(rec_card)

        cam_sel_card, kcol = _card("Kamera", fam)
        row = QHBoxLayout()
        self.camera_combo = QComboBox()
        self.camera_combo.addItem(f"Kamera {settings.camera_index} (kayıtlı)", settings.camera_index)
        self.scan_button = QPushButton("Kameraları tara"); self.scan_button.setObjectName("pill")
        self.scan_button.clicked.connect(self._scan_cameras)
        row.addWidget(self.camera_combo, 1); row.addWidget(self.scan_button)
        kcol.addLayout(row)
        self.camera_note = QLabel("Tarama birkaç saniye sürer; kare veren cihazlar listelenir.")
        self.camera_note.setFont(theme.font(fam, 10, 400)); self.camera_note.setStyleSheet(f"color: {theme.MUTED};")
        kcol.addWidget(self.camera_note)
        col.addWidget(cam_sel_card)

        name_card, ncol = _card("Sunucu adı (el yazısı, webcam üstünde)", fam)
        self.presenter_edit = QLineEdit(settings.presenter_name)
        self.presenter_edit.setPlaceholderText("Boş bırakılırsa gösterilmez")
        ncol.addWidget(self.presenter_edit)
        col.addWidget(name_card)

        cam_card, ccol = _card("Yeşil perde", fam)
        self.chroma_check = QCheckBox("Yeşil perdeyi kaldır (kişi tahtanın üstüne biner)")
        self.chroma_check.setChecked(settings.chroma_enabled)
        self.auto_key_check = QCheckBox("Perde tonunu kameranın kenarlarından otomatik ölç")
        self.auto_key_check.setChecked(settings.auto_key)
        ccol.addWidget(self.chroma_check); ccol.addWidget(self.auto_key_check)
        col.addWidget(cam_card)

        vis_card, vcol = _card("Görünürlük (tahtadaki yazılar)", fam)
        self.visibility_checks: dict[str, QCheckBox] = {}
        for key, label in VISIBILITY_KEYS:
            cb = QCheckBox(label); cb.setChecked(settings.visible(key))
            vcol.addWidget(cb); self.visibility_checks[key] = cb
        col.addWidget(vis_card)

        buttons = QHBoxLayout(); buttons.addStretch(1)
        self.cancel_button = QPushButton("Vazgeç"); self.cancel_button.setObjectName("pill")
        self.apply_button = QPushButton("Uygula"); self.apply_button.setObjectName("accent")
        self.cancel_button.clicked.connect(self.reject); self.apply_button.clicked.connect(self._apply)
        buttons.addWidget(self.cancel_button); buttons.addWidget(self.apply_button)
        root.addLayout(buttons)
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        """Yükseklik: içerik kadar, ama ekranın kullanılabilir alanını aşmaz."""
        screen = self.parent().screen() if self.parent() is not None else QApplication.primaryScreen()
        avail = screen.availableGeometry().height() if screen else 900
        wanted = self.content.sizeHint().height() + 140
        self.resize(max(self.minimumWidth(), 620), min(wanted, avail - 60))

    def _choose_font(self) -> None:
        start = str(Path(self.font_path_edit.text()).parent) if self.font_path_edit.text() else ""
        path, _ = QFileDialog.getOpenFileName(self, "Yazı tipi dosyası", start, "Yazı tipi (*.ttf *.otf)")
        if path:
            self.font_path_edit.setText(path)

    def _choose_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Logo dosyası", "", "Görsel (*.png *.jpg *.jpeg)")
        if path:
            self.logo_path_edit.setText(path)

    def _list_audio(self) -> None:
        from matematigin_mantigi.core.audio_capture import list_input_devices
        current = self.audio_combo.currentText().strip()
        names = list_input_devices()
        self.audio_combo.clear()
        self.audio_combo.addItem("(ses yok)", "")
        for n in names:
            self.audio_combo.addItem(n, n)
        idx = self.audio_combo.findText(current)
        self.audio_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _scan_cameras(self) -> None:
        from matematigin_mantigi.core.cameras import list_cameras
        current = self.camera_combo.currentData()
        cams = list_cameras()
        self.camera_combo.clear()
        for cam in cams:
            self.camera_combo.addItem(cam.label, cam.index)
        if not cams:
            self.camera_combo.addItem(f"Kamera {current} (bulunamadı)", current)
        idx = self.camera_combo.findData(current)
        self.camera_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.camera_note.setText(f"{len(cams)} kamera bulundu." if cams else "Kamera bulunamadı; bağlantı ve izinleri kontrol et.")

    def _refresh_reading(self, *_) -> None:
        v = self.reading_slider.value()
        self.reading_value.setText("kapalı" if v == 0 else f"{v} ms/harf")

    def value(self) -> SettingsValues:
        return SettingsValues(font_file=self.font_path_edit.text().strip(),
                              reading_ms=self.reading_slider.value(),
                              auto_key=self.auto_key_check.isChecked(),
                              chroma_enabled=self.chroma_check.isChecked(),
                              presenter_name=self.presenter_edit.text().strip(),
                              logo_file=self.logo_path_edit.text().strip(),
                              logo_size=self.logo_size_slider.value(),
                              camera_index=int(self.camera_combo.currentData() or 0),
                              record_fps=int(self.fps_combo.currentData() or 60),
                              record_height=int(self.res_combo.currentData() or 0),
                              audio_device=("" if self.audio_combo.currentText().strip() == "(ses yok)"
                                            else self.audio_combo.currentText().strip()),
                              aspect_lock=self.aspect_lock_check.isChecked(),
                              frame_style=self.frame_style_combo.currentData(),
                              visible={k: cb.isChecked() for k, cb in self.visibility_checks.items()})

    def _apply(self) -> None:
        self.applied.emit(self.value())
        self.accept()
