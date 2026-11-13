from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
                             QMenu, QScrollArea, QSizePolicy, QSlider, QStyle, QStyleOptionButton, QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import PALETTE, SHAPE_META, TOOL_META, WIDTHS, Shape, Tool
from matematigin_mantigi.core.settings import ERASER_MIN, ERASER_MAX, ERASER_SIZES
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.shape_menu import ShapeMenu
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.widgets import DotButton, GlyphButton, RecordButton, SwatchButton, WrapButton

ALERT_PX, ALERT_MIN_PX = 10, 7      # uyarı şeridinin yazısı: olağan ve en küçük boy (px), bkz. _fit_alert_font

_BTN_CSS = (f"QPushButton {{ background: {theme.TOOLBAR_BTN}; color: {theme.TOOLBAR_MUTED}; border: none;"
            f" border-radius: 6px; padding: 5px 3px; font-size: 10px; font-weight: 600; }}"
            f"QPushButton:checked {{ background: {theme.ACCENT}; color: white; }}"
            f"QPushButton:disabled {{ color: {theme.TOOLBAR_DIM}; }}")


class _FitButton(WrapButton):
    """88px panelin metin düğmesi: karakter sayısı değil gerçek boyama alanı ölçülür.

    QPushButton'ın doğal minimum genişliği tüm scroll içeriğini büyütebilir; yatay
    kaydırma kapalıyken simge düğmeleri bile sağdan kırpılır. Paneli/kayıt alanını
    büyütmek yerine genişliği içeride tut, kelimeleri sar; tek kelime de sığmıyorsa
    elide et. text() ve ipucu her zaman tam komutu korur.
    """

    def setText(self, text: str) -> None:
        self._logical = text
        self.setToolTip(text)
        if hasattr(self, "_fit_width"):
            self.fit_width(self._fit_width, compact=self._compact)
        else:
            QPushButton.setText(self, text)

    def fit_width(self, width: int, *, compact: bool = False) -> None:
        self._fit_width, self._compact = width, compact
        self.setFixedWidth(width)
        self.ensurePolished()
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        opt.rect = QRect(0, 0, width, 100)
        room = self.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, opt, self).width()
        fm = QFontMetrics(self.font(), self)
        text = self._logical
        if compact and fm.horizontalAdvance(text) > room:
            words = text.split()
            for word in (words[:1] + words[-1:]):
                if len(word) == 1 and not word.isalnum():
                    text = word  # MINI: komutun simgesi + tam metinli ipucu.
                    break
        lines: list[str] = []
        for paragraph in text.splitlines():
            line = ""
            for word in paragraph.split():
                word = fm.elidedText(word, Qt.TextElideMode.ElideRight, room)
                # Qt'nin elidedText hesabı geniş harf aralığında üç noktanın
                # son aralığını eksik sayabilir; boyanacak sonucu da ölç.
                if fm.horizontalAdvance(word) > room:
                    stem = word.removesuffix("…")
                    while stem and fm.horizontalAdvance(stem + "…") > room:
                        stem = stem[:-1]
                    word = stem + "…" if fm.horizontalAdvance("…") <= room else ""
                candidate = f"{line} {word}" if line else word
                if line and fm.horizontalAdvance(candidate) > room:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
        shown = "\n".join(lines)
        QPushButton.setText(self, shown)
        text_size = fm.size(Qt.TextFlag.TextShowMnemonic, shown)
        self.setFixedHeight(self.style().sizeFromContents(QStyle.ContentsType.CT_PushButton,
                                                         opt, text_size, self).height())


@dataclass(frozen=True)
class _TierSpec:
    """Bir yükseklik kademesinin tüm ölçüleri. ToolBar.resizeEvent yalnız kademe
    değişince _apply_tier ile bunu uygular (gereksiz relayout yok)."""

    name: str
    glyph_h: int
    glyph_px: int
    show_label: bool
    swatch_d: int
    dot_d: int
    record_d: int
    spacing: int
    margins: tuple[int, int, int, int]
    nine_px: int
    captions_visible: bool         # başlık etiketleri + ayırıcılar
    dot_rows: tuple[tuple[int, ...], ...]
    single_line: bool              # WrapButton'lar sarmasın (tek satır)


_FULL = _TierSpec(
    name="full", glyph_h=48, glyph_px=18, show_label=True,
    swatch_d=28, dot_d=22, record_d=56,
    spacing=6, margins=(10, 14, 10, 14), nine_px=40,
    captions_visible=True, dot_rows=(WIDTHS[:3], WIDTHS[3:]), single_line=False,
)
_COMPACT = _TierSpec(
    name="compact", glyph_h=38, glyph_px=16, show_label=True,
    swatch_d=24, dot_d=18, record_d=44,
    spacing=4, margins=(8, 8, 8, 8), nine_px=28,
    captions_visible=True, dot_rows=(WIDTHS[:3], WIDTHS[3:]), single_line=False,
)
_MINI = _TierSpec(
    # SwatchButton/RecordButton COMPACT ile aynı ölçüde kalıyor. DotButton çapı brifte
    # verilmemişti; 5 tanesi tek satırda 88px genişliğe sığsın diye COMPACT'ın 18'inden
    # küçük, 14 seçildi (5*14=70px < iç genişlik ~72px; 5*18=90px sığmazdı).
    name="mini", glyph_h=28, glyph_px=16, show_label=False,
    swatch_d=24, dot_d=14, record_d=44,
    spacing=4, margins=(8, 8, 8, 8), nine_px=28,
    captions_visible=False, dot_rows=(WIDTHS,), single_line=False,   # tek satır 93 px'e taşıp kırpılıyordu (iç genişlik 72)
)

# Eşikler ÖLÇÜMLE seçildi: kademenin içeriği (content.minimumSizeHint) + kaydırma alanının dışındaki kayıt
# düğmesi/etiketi/boşluklar (~89 px) kaydırmasız sığmalı. Tam ekran düğmesiyle (+28 px) ölçülen içerik:
# FULL ~910 px -> ToolBar >= ~1000 px; COMPACT ~757 px -> >= ~850 px; MINI ~600 px -> >= ~700 px.
# 1080p tam ekranda (1080 px) FULL, 1366x768 tam ekranda MINI kaydırmasız sığar. Eşikler yalnız başlangıç
# tahminidir: gerçek yazı tipi/DPI içeriği büyütürse _update_tier ölçülen gereksinimle bir alt kademeye iner,
# böylece kaydırma yalnız MINI bile sığmayan çok küçük pencerede (son çare) çıkar.
_FULL_MIN_H = 1030      # Tanıma düğmesi (+28 px) sonrası ölçülen FULL ~944 + çerçeve ~77 px
_COMPACT_MIN_H = 860
_TIERS = (_FULL, _COMPACT, _MINI)


def _tier_for_height(h: int) -> _TierSpec:
    if h >= _FULL_MIN_H:
        return _FULL
    if h >= _COMPACT_MIN_H:
        return _COMPACT
    return _MINI


class ToolBar(QWidget):
    """Bölge 9: dış araç çubuğu. Kayıtta görünmez.

    İçerik (self.content) bir QScrollArea içinde: pencere kısaldıkça düğmeler önce
    üç kademede küçülür (FULL -> COMPACT -> MINI, bkz. _TierSpec), en küçük kademenin
    altında da kaydırma bir güvenlik ağı olarak devreye girer. Kayıt düğmesi ve üstündeki
    uyarı şeridi (set_alert) bu kaydırma alanının DIŞINDA, dış layout'ta durur; böylece hep
    görünür ve tıklanabilir.
    """

    FULLSCREEN_TEXT, WINDOWED_TEXT = "⛶ Tam ekran", "❐ Pencere"

    toolSelected = pyqtSignal(object)      # Tool
    customColorRequested = pyqtSignal()
    shapeSelected = pyqtSignal(object)     # Shape (görsel şekil menüsünden)
    shapeFillSelected = pyqtSignal(bool)   # dolgu: True yarı saydam, False boş
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
    editorRequested = pyqtSignal()
    sampleRequested = pyqtSignal()         # Tanıma örneği topla penceresi
    layoutEditToggled = pyqtSignal(bool)
    fullscreenRequested = pyqtSignal()

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self._size_tool = Tool.PEN
        self.tier = _FULL.name
        self._tier_need: dict[str, int] = {}          # kademe -> kaydırmasız gereken içerik yüksekliği (ölçülünce)
        self.setFixedWidth(theme.TOOLBAR_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {theme.INK};")
        self.setAutoFillBackground(True)

        # --- kaydırılabilir iç içerik -----------------------------------
        self.content = QWidget()
        self.content.setStyleSheet("background: transparent;")
        col = QVBoxLayout(self.content)
        col.setContentsMargins(10, 14, 10, 14)
        col.setSpacing(6)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._col = col

        self.section_captions: list[QLabel] = []
        self.separators: list[QFrame] = []

        self._nine = QLabel("9"); self._nine.setFont(theme.hand_font(fam, 40, 700))
        self._nine.setStyleSheet(f"color: {theme.PANEL_SOFT};")
        col.addWidget(self._nine, 0, Qt.AlignmentFlag.AlignHCenter)
        cap = self._caption("KAYITTA\nGÖRÜNMEZ"); col.addWidget(cap); self.section_captions.append(cap)

        self.pen_settings_button = _FitButton("Kalem"); self.pen_settings_button.setStyleSheet(_BTN_CSS)
        self.pen_settings_button.clicked.connect(self.penSettingsRequested)
        self.settings_button = _FitButton("⚙ Ayarlar"); self.settings_button.setStyleSheet(_BTN_CSS)
        self.settings_button.clicked.connect(self.settingsRequested)
        self.editor_button = _FitButton("✎ Sorular"); self.editor_button.setStyleSheet(_BTN_CSS)
        self.editor_button.clicked.connect(self.editorRequested)
        self.sample_button = _FitButton("▦ Tanıma"); self.sample_button.setStyleSheet(_BTN_CSS)
        self.sample_button.setToolTip("Tanıma örneği topla: kendi sembol çizimlerini kaydet")
        self.sample_button.clicked.connect(self.sampleRequested)
        self.layout_button = _FitButton("⧉ Düzen"); self.layout_button.setCheckable(True)
        self.layout_button.setStyleSheet(_BTN_CSS)
        self.layout_button.toggled.connect(self.layoutEditToggled)
        self.fullscreen_button = _FitButton(self.FULLSCREEN_TEXT); self.fullscreen_button.setStyleSheet(_BTN_CSS)
        self.fullscreen_button.clicked.connect(self.fullscreenRequested)
        self._fullscreen, self._recording = False, False
        self._sync_fullscreen_button()
        col.addWidget(self.pen_settings_button); col.addWidget(self.settings_button)
        col.addWidget(self.editor_button); col.addWidget(self.sample_button); col.addWidget(self.layout_button)
        col.addWidget(self.fullscreen_button)
        col.addWidget(self._rule())

        self._tool_group = QButtonGroup(self); self._tool_group.setExclusive(True)
        self.tool_buttons: dict[Tool, GlyphButton] = {}
        for tool, (label, glyph) in TOOL_META.items():
            b = GlyphButton(glyph, label)
            self._tool_group.addButton(b)
            self.tool_buttons[tool] = b
            b.clicked.connect(lambda _c=False, t=tool: self.toolSelected.emit(t))   # seçiliyken de yayar (şekil döngüsü)
            col.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        shape_btn = self.tool_buttons[Tool.SHAPE]
        shape_btn.setToolTip("Seçiliyken tekrar basınca (ya da sağ tık) şekil menüsü açılır")
        shape_btn.rightClicked.connect(self.open_shape_menu)
        self.shape_menu = ShapeMenu(self)
        self.shape_menu.shapeSelected.connect(self._on_shape_chosen)
        self.shape_menu.fillSelected.connect(self.shapeFillSelected)
        self.shape_menu_gate = None            # bağlanınca: () -> int (bkz. open_shape_menu)
        self.set_shape(Shape.RECT)
        self.tool_buttons[Tool.PEN].setChecked(True)
        col.addWidget(self._rule())

        self._swatch_group = QButtonGroup(self); self._swatch_group.setExclusive(True)
        self.swatches: dict[str, SwatchButton] = {}
        palette_col = QVBoxLayout(); palette_col.setSpacing(0)
        row = QHBoxLayout(); row.setSpacing(0)
        for i, hx in enumerate(PALETTE):
            s = SwatchButton(hx); self._swatch_group.addButton(s); self.swatches[hx] = s
            s.clicked.connect(lambda _c=False, h=hx: self.colorSelected.emit(h))
            if i % 2 == 0 and i:
                palette_col.addLayout(row); row = QHBoxLayout(); row.setSpacing(0)
            row.addWidget(s)
        palette_col.addLayout(row)
        self.swatches[PALETTE[0]].setChecked(True)
        self.custom_color_button = QPushButton()
        icon = QPixmap(10, 10); icon.fill(Qt.GlobalColor.transparent)
        painter = QPainter(icon); painter.setPen(QColor(theme.PANEL_SOFT))
        painter.drawLine(1, 5, 9, 5); painter.drawLine(5, 1, 5, 9); painter.end()
        self.custom_color_button.setIcon(QIcon(icon))
        self.custom_color_button.setIconSize(QSize(10, 10))
        self.custom_color_button.setFixedWidth(12)
        self.custom_color_button.setStyleSheet(_BTN_CSS + "QPushButton { padding: 0; } QPushButton::menu-indicator { width: 0; }")
        self.custom_color_button.setAccessibleName("Özel renk ve son dört renk")
        self.color_menu = QMenu(self.custom_color_button)
        self.custom_color_button.setMenu(self.color_menu)
        self.set_custom_colors([])
        palette_row = QHBoxLayout(); palette_row.setSpacing(0)
        palette_row.addLayout(palette_col); palette_row.addWidget(self.custom_color_button)
        col.addLayout(palette_row)

        cap = self._caption("KALINLIK"); col.addWidget(cap); self.section_captions.append(cap)
        self._width_group = QButtonGroup(self); self._width_group.setExclusive(True)
        self.width_buttons: dict[int, DotButton] = {}
        for w in WIDTHS:
            d = DotButton(w); self._width_group.addButton(d); self.width_buttons[w] = d
            d.clicked.connect(lambda _c=False, v=w: self._select_preset(v))
        # Beş DotButton'ın satır dağılımı kademeye göre değişir (FULL/COMPACT: 3+2,
        # MINI: 5'i tek satırda) -> ayrı bir alt QVBoxLayout, bkz. _set_dot_rows.
        self._dots_col = QVBoxLayout(); self._dots_col.setSpacing(0)
        col.addLayout(self._dots_col)
        self.dot_rows: list[QHBoxLayout] = []
        self._dot_row_shape: tuple[tuple[int, ...], ...] | None = None
        self.width_buttons[4].setChecked(True)
        self.size_label = self._caption("Silgi · 34 px")
        self.size_label.hide()
        col.addWidget(self.size_label)
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(ERASER_MIN, ERASER_MAX)
        self.size_slider.setValue(34)
        self.size_slider.setToolTip("Silgi çapı (px) · [ küçült / ] büyüt")
        self.size_slider.setAccessibleName("Silgi çapı")
        self.size_slider.valueChanged.connect(self.widthSelected)
        self.size_slider.hide()
        col.addWidget(self.size_slider)
        col.addWidget(self._rule())

        cap = self._caption("SORU AKIŞI"); col.addWidget(cap); self.section_captions.append(cap)
        self.work_button = _FitButton("Soruyu işle"); self.work_button.setStyleSheet(_BTN_CSS)
        self.work_button.clicked.connect(self.workToggled)
        self.prev_button = _FitButton("← Önceki soru"); self.prev_button.setStyleSheet(_BTN_CSS)
        self.prev_button.clicked.connect(self.prevRequested)
        self.next_button = _FitButton("Sıradaki soru →"); self.next_button.setStyleSheet(_BTN_CSS)
        self.next_button.clicked.connect(self.nextRequested)
        self.progress_label = self._caption("0/0")
        self.progress_label.setWordWrap(True)         # "0/3 tamamlandı · S1" iki satıra kırılır
        col.addWidget(self.work_button); col.addWidget(self.prev_button); col.addWidget(self.next_button)
        col.addWidget(self.progress_label)
        col.addWidget(self._rule())

        hrow = QHBoxLayout(); hrow.setSpacing(4)
        self.undo_button = _FitButton("↶"); self.undo_button.setStyleSheet(_BTN_CSS)
        self.undo_button.clicked.connect(self.undoRequested); self.undo_button.setEnabled(False)
        self.clear_button = _FitButton("✕"); self.clear_button.setStyleSheet(_BTN_CSS)
        self.clear_button.clicked.connect(self.clearRequested)
        hrow.addWidget(self.undo_button); hrow.addWidget(self.clear_button)
        col.addLayout(hrow)
        col.addStretch(1)

        # --- dış layout: kaydırma alanı + hep görünür kayıt düğmesi ------
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scroll_area.viewport().setStyleSheet("background: transparent;")
        self.scroll_area.setWidget(self.content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 10)
        outer.setSpacing(6)
        outer.addWidget(self.scroll_area, 1)

        # Uyarı şeridi (set_alert): kayıt düğmesinin hemen üstünde, kaydırma alanının dışında -- hep görünür.
        # Kayıt yalnız sahneyi yakalar; tahtadaki durum satırı ve rozet kayda girdiği için uyarı yeri burası.
        self.alert_label = QLabel()
        self.alert_label.setWordWrap(True)
        self.alert_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alert_label.setFont(theme.font(fam, ALERT_PX, 700))
        self.alert_label.setStyleSheet(f"QLabel {{ color: white; background: {theme.REC_DOT}; border-radius: 5px;"
                                       f" padding: 4px 3px; margin: 0 5px; }}")
        self.alert_label.hide()
        self._alerts: dict[str, str] = {}               # set_alert: kaynak anahtarı -> metin
        outer.addWidget(self.alert_label)

        self.record_button = RecordButton()
        self.record_button.clicked.connect(lambda: self.recordToggled.emit(self.record_button.isChecked()))
        self.record_label = self._caption("KAYIT")
        outer.addWidget(self.record_button, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(self.record_label)

        self._apply_tier(_FULL)
        self._fit_ready = True

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_fit()

    def _refresh_fit(self) -> None:
        self._tier_need.clear()
        self._apply_tier(next(t for t in _TIERS if t.name == self.tier))
        self._update_tier()

    # --- helpers -----------------------------------------------------------
    def _caption(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setFont(theme.font(self.fam, 9, 600, spacing_pct=110))
        lab.setStyleSheet(f"color: {theme.MUTED_DARK}; background: transparent;")
        lab.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return lab

    def _rule(self) -> QFrame:
        r = QFrame(); r.setFixedHeight(1); r.setStyleSheet(f"background: {theme.TOOLBAR_LINE};")
        self.separators.append(r)
        return r

    # --- kademe (FULL / COMPACT / MINI) -------------------------------------
    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._fit_alert_font()
        self._update_tier()

    def _fit_alert_font(self) -> None:
        """Şeritte kelime içinde satır kırılmaz: en uzun kelime satıra sığana dek yazı küçülür (en çok ALERT_MIN_PX'e),
        kısa metinde olağan boyuna döner. Sığmayan kelime kırpılıyordu: 'kaydediliyor…' Linux'ta 72 px'lik satıra
        6 px payla sığarken Windows'un yazı tipi ölçüsüyle sığmadı (CI). Şerit araç çubuğu boyunca uzanır; genişlik
        ondan hesaplanır (gizliyken etiketin kendi geometrisi henüz güncel değildir)."""
        alert = self.alert_label
        words = alert.text().split()
        alert.ensurePolished()                          # stil sayfasının kenar ve dolgusu contentsMargins'e işlensin
        lay, m = self.layout().contentsMargins(), alert.contentsMargins()
        room = self.width() - lay.left() - lay.right() - m.left() - m.right()
        px = ALERT_PX
        font = theme.font(self.fam, px, 700)
        while px > ALERT_MIN_PX and words and max(QFontMetrics(font, alert).horizontalAdvance(w) for w in words) > room:
            px -= 1
            font = theme.font(self.fam, px, 700)
        if font != alert.font():
            alert.setFont(font)

    def _update_tier(self) -> None:
        """Kademe, görünen uyarı şeridinin aldığı yer düşüldükten sonra kalan yüksekliğe göre seçilir: eşikler
        şeritsiz ölçüldü, şerit içeriği kaydırmaya itip düğme yazılarını kırpmasın."""
        alert = self.alert_label
        room = 0 if alert.isHidden() else alert.heightForWidth(self.width()) + self.layout().spacing()
        spec = _tier_for_height(self.height() - room)
        if self.isVisible():
            spec = self._first_fitting(spec)
        if spec.name != self.tier:
            self.tier = spec.name
            self._apply_tier(spec)

    def _first_fitting(self, spec: _TierSpec) -> _TierSpec:
        """Yükseklik eşiğinin seçtiği kademeden başlayıp içeriği kaydırmasız sığan ilk kademeyi verir (MINI son
        çare). Kademenin gereksinimi sabit genişlikteki tüm satırlarla ölçülür;
        gösterim/metin değişiminde _refresh_fit önbelleği geçersiz kılar."""
        lay, alert = self.layout(), self.alert_label
        chrome = (lay.contentsMargins().top() + lay.contentsMargins().bottom() + lay.spacing()
                  + lay.spacing() + self.record_label.sizeHint().height())
        if not alert.isHidden():
            chrome += alert.heightForWidth(self.width()) + lay.spacing()
        for t in _TIERS[_TIERS.index(spec):]:
            # RecordButton özel çizilir; sizeHint() (-1, -1) döner. Gerçek sabit
            # çapı, mevcut değil denenen kademeden al (FULL ile MINI farklı).
            avail = self.height() - chrome - t.record_d
            need = self._tier_need.get(t.name)
            if need is None:
                keep = self.tier
                self._apply_tier(t)
                self.content.layout().activate()
                # minimumSizeHint, sarılan QLabel satırlarını saymaz. Genişlik
                # sabit: heightForWidth, düğmelerle etiketlerin tüm satırlarını içerir.
                need = self._tier_need[t.name] = max(
                    self.content.minimumSizeHint().height(),
                    self.content.layout().totalHeightForWidth(self.width()),
                )
                if keep != t.name:
                    self._apply_tier(next(x for x in _TIERS if x.name == keep))
                    self.content.layout().activate()
            if need <= avail or t is _MINI:
                return t
        return _MINI

    def _apply_tier(self, spec: _TierSpec) -> None:
        for b in self.tool_buttons.values():
            b.set_metrics(spec.glyph_h, spec.glyph_px, spec.show_label)
        for s in self.swatches.values():
            s.set_diameter(spec.swatch_d)
        for d in self.width_buttons.values():
            d.set_size(spec.dot_d)
            # Küçük panelde çap kaydırıcısı kalsın; yinelenen hazır boyut
            # satırı macOS'un daha yüksek doğal kontrol ölçülerinde taşır.
            d.setVisible(self._size_tool != Tool.ERASER or spec is not _MINI)
        self.record_button.set_diameter(spec.record_d)
        self._col.setSpacing(spec.spacing)
        self._col.setContentsMargins(*spec.margins)
        inner = self.width() - spec.margins[0] - spec.margins[2]
        self.size_label.setFixedWidth(inner)
        self.size_label.setWordWrap(True)
        self.size_slider.setFixedWidth(inner)
        for b in (self.pen_settings_button, self.settings_button, self.editor_button, self.sample_button,
                  self.layout_button, self.fullscreen_button, self.work_button,
                  self.prev_button, self.next_button):
            b.fit_width(inner, compact=spec is _MINI)
        # QLabel'ın uzun kelime minimumu da scroll içeriğini yatayda büyütmesin.
        # Sabit panel genişliğinde yüksekliği Qt'nin heightForWidth hesabı belirler.
        for cap in (*self.section_captions, self.progress_label):
            cap.setFixedWidth(inner)
            cap.setWordWrap(True)
        half = (inner - 4) // 2
        self.undo_button.fit_width(half)
        self.clear_button.fit_width(inner - 4 - half)
        self._nine.setFont(theme.hand_font(self.fam, spec.nine_px, 700))
        for cap in self.section_captions:
            cap.setVisible(spec.captions_visible)
        for sep in self.separators:
            sep.setVisible(spec.captions_visible)
        for wb in (self.work_button, self.prev_button, self.next_button):
            wb.set_single_line(spec.single_line)
        self._set_dot_rows(spec.dot_rows)

    def _set_dot_rows(self, groups: tuple[tuple[int, ...], ...]) -> None:
        """DotButton'ları groups'a göre satırlara dağıtır (yalnız dağılım değişince)."""
        if groups == self._dot_row_shape:
            return
        self._dot_row_shape = groups
        for row in self.dot_rows:
            while row.count():
                row.takeAt(0)          # widget'ı bırakır, yalnız bu satırdan söker
            self._dots_col.removeItem(row)
        self.dot_rows = []
        for group in groups:
            wrow = QHBoxLayout(); wrow.setSpacing(0); wrow.addStretch(1)
            for w in group:
                wrow.addWidget(self.width_buttons[w])
            wrow.addStretch(1)
            self._dots_col.addLayout(wrow)
            self.dot_rows.append(wrow)

    # --- silent setters (no signals) ---------------------------------------
    def set_tool(self, t: Tool) -> None:
        b = self.tool_buttons[t]; b.blockSignals(True); b.setChecked(True); b.blockSignals(False)

    def set_custom_colors(self, colors: list[str]) -> None:
        self.color_menu.clear()
        choose = self.color_menu.addAction("Özel renk seç…")
        choose.triggered.connect(self.customColorRequested)
        if colors:
            self.color_menu.addSeparator()
        for hx in colors[:4]:
            action = self.color_menu.addAction(hx)
            action.setData(hx)
        if not getattr(self, "_color_menu_wired", False):
            self.color_menu.triggered.connect(self._recent_color_selected)
            self._color_menu_wired = True

    def _recent_color_selected(self, action) -> None:
        if action.data():
            self.colorSelected.emit(action.data())

    def set_color(self, hx: str) -> None:
        self._swatch_group.setExclusive(False)
        for color, button in self.swatches.items():
            button.setChecked(color == hx)
        self._swatch_group.setExclusive(True)
        self.custom_color_button.setToolTip(f"Özel renk seç / Son 4 özel renk · Seçili: {hx}")

    def _select_preset(self, w: int) -> None:
        value = ERASER_SIZES[WIDTHS.index(w)] if self._size_tool == Tool.ERASER else w
        self.widthSelected.emit(value)

    def set_size_context(self, tool: Tool, width: int) -> None:
        erasing = tool == Tool.ERASER
        changed = erasing != (self._size_tool == Tool.ERASER)
        self._size_tool = tool
        self.size_slider.setVisible(erasing)
        self.size_label.setVisible(erasing)
        for w, b in self.width_buttons.items():
            size = ERASER_SIZES[WIDTHS.index(w)] if erasing else w
            b.setToolTip(f"{'Silgi çapı' if erasing else 'Kalem kalınlığı'} · {size} px")
            b.setAccessibleName(b.toolTip())
        self.set_width(width)
        if changed:
            self._refresh_fit()

    def set_width(self, w: int) -> None:
        erasing = self._size_tool == Tool.ERASER
        self._width_group.setExclusive(False)
        for key, button in self.width_buttons.items():
            value = ERASER_SIZES[WIDTHS.index(key)] if erasing else key
            button.setChecked(value == w)
        self._width_group.setExclusive(True)
        if erasing:
            self.size_slider.blockSignals(True)
            self.size_slider.setValue(w)
            self.size_slider.blockSignals(False)
            self.size_label.setText(f"Silgi · {w} px")

    def set_work_label(self, text: str) -> None:
        if self.work_button.text() != text:
            self.work_button.setText(text)
            self._refresh_fit()

    def set_progress(self, text: str) -> None:
        if self.progress_label.text() != text:
            self.progress_label.setText(text)
            self._refresh_fit()

    def set_recording(self, on: bool) -> None:
        self.record_button.blockSignals(True); self.record_button.setChecked(on); self.record_button.blockSignals(False)
        self.record_label.setText("DURDUR" if on else "KAYIT")
        self.record_button.update()
        self._recording = on
        self._sync_fullscreen_button()

    def set_fullscreen(self, on: bool) -> None:
        """Pencere tam ekrana girince/çıkınca düğmenin yazısı değişir (sinyal yaymaz)."""
        self._fullscreen = on
        self._sync_fullscreen_button()

    def _sync_fullscreen_button(self) -> None:
        b = self.fullscreen_button
        text = self.WINDOWED_TEXT if self._fullscreen else self.FULLSCREEN_TEXT
        if b.text() != text:
            b.setText(text)
            if hasattr(self, "_fit_ready"):
                self._refresh_fit()
        b.setEnabled(not self._recording)           # kayıt sürerken pencere değişirse yanlış alan kayda girer
        if self._recording:
            b.setToolTip("Kayıt sürerken tam ekran/pencere değiştirilemez (kayıt alanı kaymasın). Kaydı durdurunca F11 / Esc çalışır.")
        else:
            b.setToolTip("Tam ekrandan pencereye dön (F11 / Esc)" if self._fullscreen else "Tam ekran (F11)")

    def set_recording_time(self, seconds: int) -> None:
        """Kayıt süresi araç çubuğunda sayar (kayda girmez): 'DURDUR · 01:23'."""
        self.record_label.setText(f"DURDUR · {seconds // 60:02d}:{seconds % 60:02d}")

    def set_alert(self, key: str, text: str | None) -> None:
        """Kayıt düğmesinin üstündeki kırmızı uyarı şeridi (araç çubuğu kayda girmez). Her kaynak kendi anahtarıyla
        yazar ve yalnız kendi uyarısını kaldırır (None ya da boş): kayıt kapanışının temizliği başka bir kaynağın
        uyarısını silmez. Birden çok uyarıda en son yazılan görünür, ötekilerin sayısı '(+N)' (şerit tek satır boyu
        kadar kalsın, kaydırma alanını yemesin)."""
        self._alerts.pop(key, None)
        if text:
            self._alerts[key] = text                    # dict sırası korunur: en son yazılan sonda
        texts = list(self._alerts.values())
        shown = texts[-1] + (f" (+{len(texts) - 1})" if len(texts) > 1 else "") if texts else ""
        self.alert_label.setText(shown)
        self.alert_label.setVisible(bool(texts))
        self._fit_alert_font()
        self._update_tier()

    def set_undo_enabled(self, on: bool) -> None:
        self.undo_button.setEnabled(on)

    def set_shape_glyph(self, glyph: str) -> None:
        b = self.tool_buttons[Tool.SHAPE]
        b.glyph = glyph
        b.update()

    def set_shape(self, shape: Shape) -> None:
        """Şekil düğmesi seçili şeklin kendi çizimini gösterir (sinyal yayılmaz)."""
        b = self.tool_buttons[Tool.SHAPE]
        b.shape_icon = shape
        b.glyph = SHAPE_META[shape][1]
        b.setToolTip(f"Şekil: {SHAPE_META[shape][0]} · seçiliyken tekrar basınca (ya da sağ tık) şekil menüsü açılır")
        self.shape_menu.set_current(shape)
        b.update()

    def set_shape_fill(self, on: bool) -> None:
        self.shape_menu.set_fill(on)

    def open_shape_menu(self) -> None:
        """shape_menu_gate: -1 açılmaz; 0 açık kalır; >0 o kadar ms sonra kendiliğinden kapanır (kayıt sürerken)."""
        gate = self.shape_menu_gate() if self.shape_menu_gate is not None else 0
        if gate < 0:
            return
        self.shape_menu.set_auto_close_ms(gate)
        b = self.tool_buttons[Tool.SHAPE]
        screen = b.screen() or QApplication.primaryScreen()
        self.shape_menu.popup_beside(b.mapToGlobal(QPoint(b.width() + 6, 0)), screen.availableGeometry())

    def _on_shape_chosen(self, shape: Shape) -> None:
        self.set_shape(shape)
        self.shapeSelected.emit(shape)

    def set_layout_edit(self, on: bool) -> None:
        self.layout_button.blockSignals(True); self.layout_button.setChecked(on); self.layout_button.blockSignals(False)
