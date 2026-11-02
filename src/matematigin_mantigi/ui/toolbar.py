from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from matematigin_mantigi.core.models import PALETTE, TOOL_META, WIDTHS, Tool
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.widgets import DotButton, GlyphButton, RecordButton, SwatchButton, WrapButton

_BTN_CSS = (f"QPushButton {{ background: {theme.TOOLBAR_BTN}; color: {theme.TOOLBAR_MUTED}; border: none;"
            f" border-radius: 6px; padding: 5px 3px; font-size: 10px; font-weight: 600; }}"
            f"QPushButton:checked {{ background: {theme.ACCENT}; color: white; }}"
            f"QPushButton:disabled {{ color: {theme.TOOLBAR_DIM}; }}")


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
    captions_visible=False, dot_rows=(WIDTHS,), single_line=True,
)

# Eşikler ÖLÇÜMLE seçildi (nihai inceleme, madde 8): FULL içeriğinin sizeHint().height()'ı 853 px,
# yani ToolBar ~940 px'e kadar kaydırmasız sığıyor. Eski 1030 değeri brief'in yanlış tahminindendi
# (gerçek eski asgari 936'ydı) ve görev çubuğu görünen 1920x1080 TAM EKRAN penceresinde -- kullanıcının
# BİRİNCİL hedefi -- ToolBar'a kalan ~1000-1010 px'i COMPACT'a düşürüyordu, oysa FULL ~150 px boşlukla
# sığıyor. COMPACT için aynı pay: 790.
_FULL_MIN_H = 950
_COMPACT_MIN_H = 790


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
    editorRequested = pyqtSignal()
    layoutEditToggled = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self.tier = _FULL.name
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

        self.pen_settings_button = QPushButton("Kalem"); self.pen_settings_button.setStyleSheet(_BTN_CSS)
        self.pen_settings_button.clicked.connect(self.penSettingsRequested)
        self.settings_button = QPushButton("⚙ Ayarlar"); self.settings_button.setStyleSheet(_BTN_CSS)
        self.settings_button.clicked.connect(self.settingsRequested)
        self.editor_button = QPushButton("✎ Sorular"); self.editor_button.setStyleSheet(_BTN_CSS)
        self.editor_button.clicked.connect(self.editorRequested)
        self.layout_button = QPushButton("⧉ Düzen"); self.layout_button.setCheckable(True)
        self.layout_button.setStyleSheet(_BTN_CSS)
        self.layout_button.toggled.connect(self.layoutEditToggled)
        col.addWidget(self.pen_settings_button); col.addWidget(self.settings_button)
        col.addWidget(self.editor_button); col.addWidget(self.layout_button)
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

        cap = self._caption("KALINLIK"); col.addWidget(cap); self.section_captions.append(cap)
        self._width_group = QButtonGroup(self); self._width_group.setExclusive(True)
        self.width_buttons: dict[int, DotButton] = {}
        for w in WIDTHS:
            d = DotButton(w); self._width_group.addButton(d); self.width_buttons[w] = d
            d.clicked.connect(lambda _c=False, v=w: self.widthSelected.emit(v))
        # Beş DotButton'ın satır dağılımı kademeye göre değişir (FULL/COMPACT: 3+2,
        # MINI: 5'i tek satırda) -> ayrı bir alt QVBoxLayout, bkz. _set_dot_rows.
        self._dots_col = QVBoxLayout(); self._dots_col.setSpacing(0)
        col.addLayout(self._dots_col)
        self.dot_rows: list[QHBoxLayout] = []
        self._dot_row_shape: tuple[tuple[int, ...], ...] | None = None
        self.width_buttons[4].setChecked(True)
        col.addWidget(self._rule())

        cap = self._caption("SORU AKIŞI"); col.addWidget(cap); self.section_captions.append(cap)
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
        self.alert_label.setFont(theme.font(fam, 10, 700))
        self.alert_label.setStyleSheet(f"QLabel {{ color: white; background: {theme.REC_DOT}; border-radius: 5px;"
                                       f" padding: 4px 3px; margin: 0 5px; }}")
        self.alert_label.hide()
        outer.addWidget(self.alert_label)

        self.record_button = RecordButton()
        self.record_button.clicked.connect(lambda: self.recordToggled.emit(self.record_button.isChecked()))
        self.record_label = self._caption("KAYIT")
        outer.addWidget(self.record_button, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(self.record_label)

        self._apply_tier(_FULL)

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
        self._update_tier()

    def _update_tier(self) -> None:
        """Kademe, görünen uyarı şeridinin aldığı yer düşüldükten sonra kalan yüksekliğe göre seçilir: eşikler
        şeritsiz ölçüldü, şerit içeriği kaydırmaya itip düğme yazılarını kırpmasın."""
        alert = self.alert_label
        room = 0 if alert.isHidden() else alert.heightForWidth(self.width()) + self.layout().spacing()
        spec = _tier_for_height(self.height() - room)
        if spec.name != self.tier:
            self.tier = spec.name
            self._apply_tier(spec)

    def _apply_tier(self, spec: _TierSpec) -> None:
        for b in self.tool_buttons.values():
            b.set_metrics(spec.glyph_h, spec.glyph_px, spec.show_label)
        for s in self.swatches.values():
            s.set_diameter(spec.swatch_d)
        for d in self.width_buttons.values():
            d.set_size(spec.dot_d)
        self.record_button.set_diameter(spec.record_d)
        self._col.setSpacing(spec.spacing)
        self._col.setContentsMargins(*spec.margins)
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

    def set_recording_time(self, seconds: int) -> None:
        """Kayıt süresi araç çubuğunda sayar (kayda girmez): 'DURDUR · 01:23'."""
        self.record_label.setText(f"DURDUR · {seconds // 60:02d}:{seconds % 60:02d}")

    def set_alert(self, text: str | None) -> None:
        """Kayıt düğmesinin üstündeki kırmızı uyarı şeridi (araç çubuğu kayda girmez); None ya da boş gizler."""
        self.alert_label.setText(text or "")
        self.alert_label.setVisible(bool(text))
        self._update_tier()

    def set_undo_enabled(self, on: bool) -> None:
        self.undo_button.setEnabled(on)

    def set_shape_glyph(self, glyph: str) -> None:
        b = self.tool_buttons[Tool.SHAPE]
        b.glyph = glyph
        b.update()

    def set_layout_edit(self, on: bool) -> None:
        self.layout_button.blockSignals(True); self.layout_button.setChecked(on); self.layout_button.blockSignals(False)
