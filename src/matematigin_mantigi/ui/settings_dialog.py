"""⚙ Ayarlar: yazı tipi dosyası, soru yazma hızı, otomatik perde tonu, tahtadaki yazısal öğelerin görünürlüğü."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)

from matematigin_mantigi.core.autostart import Autostart
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
    hold_to_straight: bool = True
    auto_key: bool = True
    chroma_enabled: bool = True
    presenter_name: str = "Koray Varol"
    logo_file: str = ""
    logo_size: int = 48
    camera_index: int = 0
    record_fps: int = 60
    record_height: int = 1440
    audio_device: str = ""
    record_folder: str = ""
    aspect_lock: bool = True
    frame_style: FrameStyle = FrameStyle.CLASSIC
    visible: dict[str, bool] = field(default_factory=dict)
    board_screen: object = None
    preview_screen: object = None
    autostart: bool | None = None       # bilgisayar açılınca başlat: None = kullanıcı değiştirmedi


def _card(title: str, fam: FontFamilies) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setStyleSheet(f"QFrame {{ background: {theme.PANEL}; border-radius: 6px; }}")
    col = QVBoxLayout(f); col.setContentsMargins(18, 14, 18, 16); col.setSpacing(8)
    t = QLabel(title); t.setFont(theme.font(fam, 12, 600, spacing_pct=110)); t.setStyleSheet(f"color: {theme.MUTED};")
    col.addWidget(t)
    return f, col


class SettingsDialog(QDialog):
    applied = pyqtSignal(object)      # SettingsValues

    def __init__(self, settings: AppSettings, fam: FontFamilies, parent=None, *, autostart: Autostart | None = None):
        super().__init__(parent)
        self._autostart = autostart or Autostart()
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

        start_card, startcol = _card("Başlangıç", fam)
        self.autostart_check = QCheckBox("Bilgisayar açılınca başlat")
        reason = self._autostart.unsupported_reason
        # Gösterilen durum gerçek sistem kaydından okunur (kullanıcı elle sildiyse doğru görünür).
        self._autostart_initial = self._autostart.is_enabled()
        self.autostart_check.setChecked(self._autostart_initial)
        self.autostart_check.setEnabled(not reason)
        self.autostart_check.setToolTip(reason)
        startcol.addWidget(self.autostart_check)
        self.autostart_note = QLabel(reason or "Uygulama bilgisayar açılınca son soru, düzen, ekranlar, kamera ve "
                                     "ayarlarla açılır. Kayıt kendiliğinden başlamaz.")
        self.autostart_note.setWordWrap(True); self.autostart_note.setFont(theme.font(fam, 10, 400))
        self.autostart_note.setStyleSheet(f"color: {theme.MUTED};")
        startcol.addWidget(self.autostart_note)
        col.addWidget(start_card)

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
        self.hold_to_straight_check = QCheckBox("Bekle-düzelt · 0,6 sn bekleyince düz çizgi")
        self.hold_to_straight_check.setChecked(settings.pen().hold_to_straight)
        scol.addWidget(self.hold_to_straight_check)
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
        self.record_folder_edit = QLineEdit(settings.record_folder); self.record_folder_edit.setReadOnly(True)
        self.record_folder_edit.setPlaceholderText("Varsayılan: ders oturumu klasörü")
        self.choose_record_folder_button = QPushButton("Klasör seç…")
        self.default_record_folder_button = QPushButton("Varsayılan")
        self.choose_record_folder_button.clicked.connect(self._choose_record_folder)
        self.default_record_folder_button.clicked.connect(lambda: self.record_folder_edit.setText(""))
        row.addWidget(self.record_folder_edit, 1); row.addWidget(self.choose_record_folder_button); row.addWidget(self.default_record_folder_button)
        rcol.addLayout(row)
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
        rec_note = QLabel("Seçim yeni kayıtları etkiler; ders anlık görüntüleri oturum klasöründe kalır. Araç çubuğu kayda girmez.")
        rec_note.setWordWrap(True)
        rec_note.setFont(theme.font(fam, 10, 400)); rec_note.setStyleSheet(f"color: {theme.MUTED};")
        rcol.addWidget(rec_note)
        col.addWidget(rec_card)

        screen_card, screen_col = _card("Ekranlar", fam)
        self.board_screen_combo = QComboBox()
        self.preview_screen_combo = QComboBox()
        self.board_screen_combo.addItem("Mevcut tahta ekranı", None)
        self.preview_screen_combo.addItem("Kapalı", None)
        screens = QApplication.screens()
        for screen in screens:
            label = f"{screen.name()} · {screen.serialNumber() or 'seri numarası yok'} · {screen.geometry().x()},{screen.geometry().y()}"
            self.board_screen_combo.addItem(label, screen)
            self.preview_screen_combo.addItem(label, screen)
        from matematigin_mantigi.ui.dual_screen import resolve_screen_key
        for combo, key in ((self.board_screen_combo, settings.board_screen_key),
                           (self.preview_screen_combo, settings.preview_screen_key)):
            if key:
                screen = resolve_screen_key(screens, key)
                if screen is not None:
                    combo.setCurrentIndex(combo.findData(screen))
                else:
                    combo.addItem(f"{key[0]} (bulunamadı veya belirsiz)", tuple(key))
                    combo.setCurrentIndex(combo.count() - 1)
        # Eksik ekranın kullanıcı tarafından açıkça kapatılmasına da izin ver.
        self.preview_screen_combo.setEnabled(len(screens) > 1 or bool(settings.preview_screen_key))
        screen_col.addWidget(QLabel("Tahta ekranı")); screen_col.addWidget(self.board_screen_combo)
        screen_col.addWidget(QLabel("Kamera önizleme ekranı")); screen_col.addWidget(self.preview_screen_combo)
        screen_note = QLabel("Önizleme yalnız aynı ölçekli, ayrı ekranlarda açılır. Kayıt dışı olması garanti edilemez; kayıt sonucunu kontrol edin. Karma ekran ölçekleri desteklenmez.")
        screen_note.setWordWrap(True); screen_col.addWidget(screen_note)
        col.addWidget(screen_card)

        cam_sel_card, kcol = _card("Kamera", fam)
        row = QHBoxLayout()
        self.camera_combo = QComboBox()
        self.camera_combo.addItem(f"Kamera {settings.camera_index} (kayıtlı)", settings.camera_index)
        self.scan_button = QPushButton("Kameraları tara"); self.scan_button.setObjectName("pill")
        self.scan_button.clicked.connect(self._scan_cameras)
        row.addWidget(self.camera_combo, 1); row.addWidget(self.scan_button)
        kcol.addLayout(row)
        self.camera_note = QLabel("Kamera yalnız sıra numarasıyla seçilir; cihaz sırası değişirse farklı bir kamera açılabilir. Her bağlantı değişiminden sonra görüntüyü kontrol edin.")
        self.camera_note.setWordWrap(True)
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
        # Yardımcı düğmeler odak alınca Enter'ın hedefini değiştirmesin.
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
        self.apply_button.setDefault(True)
        self._fit_to_screen()

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            widget = self.focusWidget()
            while widget is not None and widget is not self:
                # Metin düzenleme / seçim onayı, pencereyi uygulayıp kapatma değildir.
                if isinstance(widget, (QLineEdit, QComboBox)):
                    event.accept()
                    return
                widget = widget.parentWidget()
        super().keyPressEvent(event)

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

    def _choose_record_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Kayıt klasörü", self.record_folder_edit.text())
        if path:
            self.record_folder_edit.setText(path)

    def _audio_value(self) -> str:
        index = self.audio_combo.currentIndex()
        text = self.audio_combo.currentText().strip()
        if index >= 0 and text == self.audio_combo.itemText(index):
            return self.audio_combo.itemData(index) or ""
        return text

    def _list_audio(self) -> None:
        from matematigin_mantigi.core.audio_capture import list_input_devices, resolve_input_device
        current = self._audio_value()
        names = list_input_devices()
        self.audio_combo.clear()
        self.audio_combo.addItem("(ses yok)", "")
        for n in names:
            ambiguous = resolve_input_device(n) is None and bool(re.search(r' #\d+$', n))
            self.audio_combo.addItem(f"{n} (belirsiz; seçilemez)" if ambiguous else n, n)
            if ambiguous:
                self.audio_combo.model().item(self.audio_combo.count() - 1).setEnabled(False)
        idx = self.audio_combo.findData(current)
        if current and idx < 0:
            available = resolve_input_device(current) is not None
            self.audio_combo.addItem(current if available else f"{current} (bulunamadı veya belirsiz)", current)
            idx = self.audio_combo.count() - 1
        self.audio_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _scan_cameras(self) -> None:
        from matematigin_mantigi.core.cameras import list_cameras
        current = self.camera_combo.currentData()
        panel = getattr(self.parent(), "webcam_panel", None)
        workers = ([panel.worker] + list(panel._pending_workers)) if panel else []
        running = [worker for worker in workers if worker.isRunning()]
        busy = {getattr(worker._source, "index", None) for worker in running}
        unknown = None in busy
        busy.discard(None)
        # Kaynağı bilinmeyen çalışan worker herhangi bir indeksi tutabilir.
        cams = [] if unknown else (list_cameras(skip=busy) if busy else list_cameras())
        self.camera_combo.clear()
        for index in sorted(busy):
            self.camera_combo.addItem(f"Kamera {index} (kullanımda veya açılıyor)", index)
        for cam in cams:
            self.camera_combo.addItem(cam.label, cam.index)
        if self.camera_combo.findData(current) < 0:
            self.camera_combo.addItem(f"Kamera {current} (bulunamadı)", current)
        idx = self.camera_combo.findData(current)
        self.camera_combo.setCurrentIndex(idx if idx >= 0 else 0)
        if unknown:
            self.camera_note.setText("Kullanımdaki kameranın kaynağı bilinmiyor; güvenlik için tarama yapılmadı.")
        elif busy:
            self.camera_note.setText(f"{len(cams)} kamera tarandı; kullanımda veya açılmakta olanlar yeniden açılmadı.")
        else:
            self.camera_note.setText(f"{len(cams)} kamera bulundu." if cams else "Kamera bulunamadı; bağlantı ve izinleri kontrol et.")
        self.camera_note.setText(self.camera_note.text() + " Kamera sırası değişirse farklı bir cihaz açılabilir; görüntüyü kontrol edin.")

    def _refresh_reading(self, *_) -> None:
        v = self.reading_slider.value()
        self.reading_value.setText("kapalı" if v == 0 else f"{v} ms/harf")

    def value(self) -> SettingsValues:
        return SettingsValues(font_file=self.font_path_edit.text().strip(),
                              reading_ms=self.reading_slider.value(),
                              hold_to_straight=self.hold_to_straight_check.isChecked(),
                              auto_key=self.auto_key_check.isChecked(),
                              chroma_enabled=self.chroma_check.isChecked(),
                              presenter_name=self.presenter_edit.text().strip(),
                              logo_file=self.logo_path_edit.text().strip(),
                              logo_size=self.logo_size_slider.value(),
                              camera_index=int(self.camera_combo.currentData() or 0),
                              record_fps=int(self.fps_combo.currentData() or 60),
                              record_height=int(self.res_combo.currentData() or 0),
                              record_folder=self.record_folder_edit.text(),
                              audio_device=self._audio_value(),
                              aspect_lock=self.aspect_lock_check.isChecked(),
                              frame_style=self.frame_style_combo.currentData(),
                              visible={k: cb.isChecked() for k, cb in self.visibility_checks.items()},
                              board_screen=self.board_screen_combo.currentData(),
                              preview_screen=self.preview_screen_combo.currentData(),
                              autostart=(self.autostart_check.isChecked()
                                         if self.autostart_check.isEnabled()
                                         and self.autostart_check.isChecked() != self._autostart_initial else None))

    def _apply(self) -> None:
        self.applied.emit(self.value())
        self.accept()
