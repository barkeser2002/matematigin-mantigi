"""Beyaz tahta: kalıcı ekran çerçevesi içinde tam boy çizim tuvali; soru, ipucu ve webcam bölgeleri tahtanın
üstünde şeffaf katmanlar. Çerçeve bandına çizilemez. Başlık plakası üstte, sunucu adı webcam'in üstünde.
Düzen sınırları ve ızgara sadece düzen modunda görünür.
"""
from __future__ import annotations

from fractions import Fraction
import sys

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import FrameStyle
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.canvas import DrawingCanvas
from matematigin_mantigi.ui.frames import FRAME_SPECS, FrameContext, FrameSpec
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.zone import Zone

GRIP = 18   # kenar/köşe tutamağı kalınlığı (px)

_EDGE_CURSORS = {
    "move": Qt.CursorShape.SizeAllCursor,
    "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor,
    "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
}

EYE_SIZE = 20   # göz düğmesi çapı (px)

# Bölgelerin (lm.ZONE_KEYS) yapısal anahtarından settings.VISIBILITY_KEYS'teki karşılığına: düzen dosyası
# (duzen.json) hâlâ "soru"/"ipucu" gibi kısa Türkçe anahtarlarla çalışır, ama görünürlük göz düğmesi +
# AppSettings ile bu görev için eklenen "question_zone"/"hint_zone" dizeleriyle konuşur -- "webcam" ikisinde
# de aynı. WorkArea AppSettings'i görmediği için bu çeviri burada, tek yerde yaşar.
_ZONE_VIS_KEY = {"soru": "question_zone", "ipucu": "hint_zone", "webcam": "webcam"}


def _paint_ghost(p: QPainter, geo: QRect, label: str) -> None:
    """Gizli (göz düğmesiyle kapatılmış) bölge/öğe: normal kesikli çerçeve yerine soluk dolgu + anahtar
    etiketi -- sürüklenemez, ama düzen modunda kullanıcı nerede olduğunu görüp göz düğmesinden geri açabilir."""
    fill = QColor(theme.ACCENT); fill.setAlpha(45)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(fill)
    p.drawRect(QRectF(geo).adjusted(1, 1, -1, -1))
    muted = QColor(theme.ACCENT); muted.setAlpha(150)
    p.setPen(muted)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawText(geo.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, label)


class _EditOverlay(QWidget):
    """Düzen modunda ızgara ve bölge sınırlarını en üstte çizer; fareye şeffaftır."""

    def __init__(self, area: "WorkArea"):
        super().__init__(area)
        self.area = area
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.hide()

    def paintEvent(self, _e):
        area = self.area
        p = QPainter(self)
        inner = area.inner_rect()
        p.setPen(QPen(QColor(theme.ACCENT), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(inner).adjusted(1.5, 1.5, -1.5, -1.5))
        cw, ch = lm.cell_size(inner.width(), inner.height(), theme.GRID_GAP)
        grid_color = QColor(theme.ACCENT)
        grid_color.setAlpha(255 if getattr(area, "_snap_active", False) else 60)   # ızgara artık dekoratif
        pen = QPen(grid_color); pen.setStyle(Qt.PenStyle.DotLine); p.setPen(pen)
        for c in range(1, lm.GRID_COLS):
            x = inner.x() + round(c * (cw + theme.GRID_GAP) - theme.GRID_GAP / 2)
            p.drawLine(x, inner.top(), x, inner.bottom())
        for r in range(1, lm.GRID_ROWS):
            y = inner.y() + round(r * (ch + theme.GRID_GAP) - theme.GRID_GAP / 2)
            p.drawLine(inner.left(), y, inner.right(), y)
        for zone in area.zones():
            geo = zone.geometry()
            if not area._visible.get(_ZONE_VIS_KEY.get(zone.key, zone.key), True):
                _paint_ghost(p, geo, zone.key.upper())
                continue
            pen = QPen(QColor(theme.ACCENT), 2); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
            p.drawRoundedRect(QRectF(geo).adjusted(1, 1, -1, -1), theme.PANEL_RADIUS, theme.PANEL_RADIUS)
            p.fillRect(QRect(geo.right() - GRIP, geo.bottom() - GRIP, GRIP, GRIP), QColor(theme.ACCENT))
            p.setPen(QColor(theme.ACCENT))
            p.drawText(geo.adjusted(10, 6, -10, -6), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                       zone.key.upper())
        for key, widget in area._items.items():   # öğeler: tutamaksız (yalnız taşınır) ince kesikli çerçeve
            geo = widget.geometry()                # + anahtar etiketi -- yoksa düzen modunda görünmez hedef olurlar
            if not area._visible.get(key, True):
                _paint_ghost(p, geo, key.upper())
                continue
            pen = QPen(QColor(theme.ACCENT), 2); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(geo).adjusted(1, 1, -1, -1))
            p.setPen(QColor(theme.ACCENT))
            p.drawText(geo.adjusted(4, 2, -4, -2), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                       key.upper())
        p.end()


class InkLayer(QWidget):
    """Mürekkep katmanı: tuvalin çizgilerini soru ve ipucu bölgelerinin ÜSTÜNDE, webcam'in altında gösterir."""

    def __init__(self, board: DrawingCanvas, parent=None):
        super().__init__(parent)
        self.board = board
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        board.set_mirror(self)

    def paintEvent(self, _e):
        p = QPainter(self)
        self.board.paint_ink(p)
        p.end()


class WorkArea(QWidget):
    layoutChanged = pyqtSignal(object)     # Layout dict
    editModeChanged = pyqtSignal(bool)
    visibilityToggled = pyqtSignal(str, bool)   # anahtar (VISIBILITY_KEYS ile aynı dize), yeni durum
    fontScaleChanged = pyqtSignal(float)         # düzen çubuğundaki yazı boyutu kaydırıcısı, 0.7 - 1.6

    ASPECT_W, ASPECT_H = 16, 9
    # Sahne 32k x 18k adımlarıyla ölçülür: oran TAM 16:9 kalır ve iki kenar da çift olur.
    STAGE_STEP_W, STAGE_STEP_H = 2 * ASPECT_W, 2 * ASPECT_H
    MIN_STAGE_K = 4                            # 128x72; theme.FRAME_BAND (Klasik) için kalibre edilmiş taban --
                                                # başka bir bant için _min_stage_k() ölçekler, bkz. orada

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        # Tahtanın O AN kullandığı (ölçekli) aile -- FrameContext.fam buradan gelir. self.fam'den AYRI
        # tutulur (nihai inceleme, madde 2): set_families self.fam'i BİLEREK güncellemez çünkü "MM" logo
        # monogramının kendi boyut kaydırıcısı var; çerçeve bandının yazıları ise Görev 7'nin yazı ölçeğine
        # VE Ayarlar'dan seçilen yazı tipine uymak zorunda (bkz. frames.FrameContext.fam docstring'i).
        self._board_fam = fam
        self._zones: dict[str, Zone] = {}
        self._layout: lm.Layout = dict(lm.DEFAULT_LAYOUT)
        self._item_pos: dict[str, lm.ItemPos] = {}    # yalnız sürüklenmiş öğeler; eksik anahtar = bugünkü formül
        self._items: dict[str, QWidget] = {}          # relayout() sırasında yeniden kurulur (rozet tembel okunsun)
        # Görünürlük: WorkArea AppSettings görmez, bu yalnız MainWindow.apply_ui_settings'in bildirdiği
        # (set_item_visible) durumun bir ÖNBELLEĞİ -- göz düğmesinin açık/kapalı çizimi, _hit'in gizliyi
        # sürüklemeyi reddetmesi ve overlay'in hayalet çizimi için. Anahtar dizeleri VISIBILITY_KEYS ile
        # aynı ("question_zone"/"hint_zone"/"webcam" + ITEM_KEYS); eksik anahtar = varsayılan görünür.
        self._visible: dict[str, bool] = {}
        self._eye_buttons: dict[str, QPushButton] = {}
        self.edit_mode = False
        self.frame_visible = True
        self.frame_style: FrameStyle = FrameStyle.CLASSIC
        self.aspect_lock = True
        self._drag: tuple[str, str, QPoint, QRect] | None = None   # key, mode ("move" ya da kenar kodu), press pos, start geom
        self._snap_active = False                           # Ctrl basılı mı: overlay ızgarayı buna göre belirginleştirir
        self.setMouseTracking(True)

        self.board = DrawingCanvas(self)
        self.ink = InkLayer(self.board, self)

        self.status_label = QLabel("", self)
        self.status_label.setFont(theme.font(fam, 10, 500))
        self.status_label.setStyleSheet(f"color: {theme.MUTED}; background: transparent;")
        self.status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # başlık plakası: çerçevenin üst bandında, ortada
        self.brand = QLabel("Matematiğin Mantığı", self)
        self.brand.setFont(theme.hand_font(fam, 30, 700))
        self.brand.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: {theme.INK};"
                                 f" border: 2px solid {theme.HINT_CARD_BORDER}; border-top: none;"
                                 f" border-bottom-left-radius: 14px; border-bottom-right-radius: 14px; padding: 2px 28px 6px;")
        self.brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.brand.adjustSize()

        # sunucu adı: el yazısı, webcam'in üstünde
        self.name_label = QLabel("Koray Varol", self)
        self.name_label.setFont(theme.hand_font(fam, 28, 700))
        self.name_label.setStyleSheet(f"color: {theme.INK}; background: transparent;")
        self.name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.name_label.adjustSize()

        self.badge_slot = QWidget(self)          # MainWindow yerleştirir: RecordBadge
        self.badge_slot.hide()

        self.edit_bar = QWidget(self)
        self.edit_bar.setObjectName("editBar")
        self.edit_bar.setStyleSheet(f"#editBar {{ background: {theme.INK}; border-radius: 8px; }}")
        self.edit_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar = QHBoxLayout(self.edit_bar); bar.setContentsMargins(14, 6, 10, 6); bar.setSpacing(10)
        snap_key = "⌘/Ctrl" if sys.platform == "darwin" else "Ctrl"
        info = QLabel(f"DÜZEN MODU · bölgeyi sürükle, kenarlardan serbestçe boyutlandır · {snap_key}: ızgaraya yapıştır")
        info.setFont(theme.font(fam, 10, 600, spacing_pct=108)); info.setStyleSheet(f"color: {theme.TOOLBAR_MUTED};")
        # Yazı boyutu kaydırıcısı (Görev 7): WorkArea AppSettings görmediği için kalıcı değeri kendi
        # BAŞINA bilmez -- yalnız fontScaleChanged yayar, MainWindow ayara yazıp apply_ui_settings ->
        # set_font_scale ile mevcut değeri geri bildirir (visibilityToggled/set_item_visible ile aynı kalıp).
        self.font_scale_label = QLabel("Yazı %100")
        self.font_scale_label.setFont(theme.font(fam, 10, 600, spacing_pct=108))
        self.font_scale_label.setStyleSheet(f"color: {theme.TOOLBAR_MUTED};")
        self.font_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.font_scale_slider.setRange(70, 160)      # %70 - %160; FontFamilies.scale = değer / 100
        self.font_scale_slider.setValue(100)
        self.font_scale_slider.setFixedWidth(110)
        self.font_scale_slider.valueChanged.connect(self._on_font_scale_slider)
        self.reset_button = QPushButton("Sıfırla"); self.reset_button.setObjectName("pill")
        self.done_button = QPushButton("Bitti"); self.done_button.setObjectName("accent")
        self.reset_button.clicked.connect(self.reset_layout)
        self.done_button.clicked.connect(lambda: self.set_edit_mode(False))
        bar.addWidget(info); bar.addWidget(self.font_scale_label); bar.addWidget(self.font_scale_slider)
        bar.addWidget(self.reset_button); bar.addWidget(self.done_button)
        self.edit_bar.hide()

        self.overlay = _EditOverlay(self)

        # logo: sol üst köşe; dosya yoksa "MM" monogramı (en son: set_logo relayout çağırır)
        self.logo_label = QLabel(self)
        self.logo_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_is_file = False
        self.logo_size = self.LOGO_SIZE
        self.set_logo("")

    # --- zones & layout ----------------------------------------------------
    def add_zone(self, key: str, zone: Zone) -> None:
        zone.key = key
        zone.setParent(self)
        zone.set_board(self.board)
        self._zones[key] = zone
        zone.show()
        self.relayout()

    def zone(self, key: str) -> Zone:
        return self._zones[key]

    def zones(self) -> list[Zone]:
        return list(self._zones.values())

    def layout(self) -> lm.Layout:                      # type: ignore[override]
        return {**self._layout, **self._item_pos}

    def set_layout(self, layout: lm.Layout) -> None:
        # lm.clamp_free alansız çağrılır (self.inner_rect() ile DEĞİL): bu bir yükleme yolu (ör. MainWindow
        # kurucusundaki load_layout() -> set_layout() zinciri), piksel tabanını burada yeniden türetmek yanlış
        # olurdu -- kaydedilen kesirli düzen çözünürlükten bağımsızdır, o anki pencerenin (hatta doğru
        # boyutlanmış olsa bile) ölçüsüne göre büyütülüp küçültülmemeli. Piksel tabanı yalnız onu YARATAN
        # sürüklemede uygulanır (bkz. clamp_free docstring'i); burada yalnız ızgara sınırları kalır.
        self._layout = {k: lm.clamp_free(v) for k, v in layout.items() if k in lm.ZONE_KEYS}
        for k in lm.ZONE_KEYS:
            self._layout.setdefault(k, lm.DEFAULT_LAYOUT[k])
        # Öğelerde varsayılan YOK: verilen düzende anılmayan bir öğe anahtarı, "hiç sürüklenmemiş" demektir
        # -- relayout() o öğe için bugünkü formülü kullanır (bkz. _place_item). Zone'larla simetrik olarak
        # TAM DEĞİŞTİRİR (birleştirmez): reset_layout() böylece öğe geçersiz kılmalarını da sıfırlar.
        self._item_pos = {k: v for k, v in layout.items() if k in lm.ITEM_KEYS}
        self.relayout()

    def reset_layout(self) -> None:
        self.set_layout(dict(lm.DEFAULT_LAYOUT))
        self.layoutChanged.emit(self.layout())

    def set_edit_mode(self, on: bool) -> None:
        if on == self.edit_mode:
            return
        self.edit_mode = on
        for zone in self._zones.values():
            zone.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, on)
        # Tahta da şeffaf olmalı; yoksa tıklama en üstteki çocuğa (tuvale) gider, buraya ulaşmaz.
        self.board.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, on)
        # Rozetin tıklanabilir işlevi hiç yok; düzen modundan bağımsız hep fareye şeffaf kalmalı
        # (RecordBadge kurucusu zaten bunu ayarlıyor — burada `on`'a bağlarsak düzen moduna her
        # girip çıkışta True->False->... diye üzerine yazıp orijinal hatayı geri getiriyorduk).
        self.badge_slot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.overlay.setVisible(on)
        self.edit_bar.setVisible(on)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.relayout()
        self.editModeChanged.emit(on)

    def set_frame_visible(self, on: bool) -> None:
        if on == self.frame_visible:
            return                                  # değer değişmedi: sıcak yolda boşuna relayout etme (madde 5)
        self.frame_visible = on
        self._apply_chrome()
        self.relayout()
        self.update()

    def set_frame_style(self, style: FrameStyle) -> None:
        """Ayarlar > Tahta'daki çerçeve stili açılır listesinden gelir (Görev 8). set_frame_visible ile
        aynı kalıp: sakla, chrome görünürlüğünü eşitle (bkz. _apply_chrome), relayout() -- yeni stilin bandı
        (FRAME_SPECS[style].band) klasikten farklı olabilir, bu da inner_rect()'i ve ona bağlı her bölgeyi
        yeniden akıtır -- sonra update().

        DEĞER DEĞİŞMEDİYSE hiçbir şey yapmaz (nihai inceleme, madde 5): apply_ui_settings bu üç ayarı
        (aspect_lock/frame_visible/frame_style) HER göz düğmesi tıklamasında ve HER yazı boyutu kaydırıcısı
        tıkında yeniden uygular, ama değer o çağrıların neredeyse hiçbirinde değişmez -- ölçülen maliyet
        90 tıklık bir sürüklemede 450 relayout / 362 ms. Chrome eşitlemesi bu erken dönüşe takılmaz:
        apply_ui_settings zaten set_item_visible("frame_titles", ...) ve set_presenter_name ile
        _apply_chrome()'u KOŞULSUZ çağırır; rozetin doğru boyutlanması da Görev 7'nin düzelttiği
        badge.set_families -> work_area.set_families sırasıyla YAPISAL olarak garanti (bkz. main_window.py),
        bu üç çağrının tesadüfi relayout()'una yaslanmıyor."""
        if style == self.frame_style:
            return
        self.frame_style = style
        self._apply_chrome()
        self.relayout()
        self.update()

    def _chrome_state(self) -> tuple[FrameSpec, bool]:
        """(etkin FrameSpec, çerçeve kendi başlıklarını fiilen çiziyor mu). İkincisi hem _apply_chrome'un
        eski plaka/el yazısı widget'larını gizleyip göstermesi HEM DE paintEvent'in FrameContext.presenter/
        brand'e boş dize mi gerçek metin mi geçeceği için TEK yerden hesaplanır -- ikisi ayrışırsa (bkz.
        Görev 8 brief'i) HUD bandı yazı çizerken eski widget görünür kalır gibi bir tutarsızlık olmasın."""
        return FRAME_SPECS[self.frame_style], self.frame_visible and self._visible.get("frame_titles", True)

    def _apply_chrome(self) -> None:
        """Etkin çerçeve stili sunucu adını/markayı KENDİSİ çiziyorsa (FrameSpec.draws_presenter/
        draws_brand) VE "frame_titles" açıksa, eski plaka (self.brand) ve el yazısı (self.name_label)
        widget'larını gizler -- ikisi üst üste binmesin. Kapalıyken (stil çizmiyor, çerçeve kapalı ya da
        frame_titles kapalı) eski widget'lar yalnız kendi görünürlük anahtarlarına (brand/presenter) döner.
        WorkArea AppSettings'i görmediği için bu hesap TAMAMEN self._visible önbelleğinden yapılır --
        set_item_visible/set_frame_style/set_frame_visible/set_presenter_name hangi sırayla çağrılırsa
        çağrılsın SONUÇ tutarlı olsun diye hepsi bunu tetikler (bkz. çağıranlar)."""
        spec, titles_on = self._chrome_state()
        hide_brand = spec.draws_brand and titles_on
        hide_presenter = spec.draws_presenter and titles_on
        self.brand.setVisible(self._visible.get("brand", True) and not hide_brand)
        self.name_label.setVisible(self._visible.get("presenter", True) and not hide_presenter
                                    and bool(self.name_label.text().strip()))

    def set_aspect_lock(self, on: bool) -> None:
        if on == self.aspect_lock:
            return                                  # değer değişmedi: bkz. set_frame_style (madde 5)
        self.aspect_lock = on
        self.relayout()
        self.update()

    LOGO_SIZE = 48      # varsayılan; üst banda asılı, plaka gibi

    def set_logo(self, path: str, size: int | None = None) -> None:
        """PNG/JPG logo; boşsa veya yüklenemezse yuvarlak 'MM' monogramı. size: piksel (Ayarlar)."""
        size = int(size or self.LOGO_SIZE)
        self.logo_size = size
        pm = QPixmap(path) if path else QPixmap()
        self.logo_is_file = not pm.isNull()
        if self.logo_is_file:
            pm = pm.scaled(size * 3, size, Qt.AspectRatioMode.KeepAspectRatio,       # geniş logolar için en 3x
                           Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setText(""); self.logo_label.setStyleSheet("background: transparent;")
            self.logo_label.setPixmap(pm)
            self.logo_label.setFixedSize(pm.size())
        else:
            self.logo_label.setPixmap(QPixmap())
            self.logo_label.setText("MM")
            self.logo_label.setFont(theme.hand_font(self.fam, max(10, int(size * 0.42)), 700))
            self.logo_label.setFixedSize(size, size)
            self.logo_label.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: {theme.INK};"
                                          f" border: 2px solid {theme.HINT_CARD_BORDER}; border-radius: {size // 2}px;")
        self.relayout()

    def set_families(self, fam: FontFamilies) -> None:
        """WorkArea'nın kendi etiketlerinin (durum satırı, marka plakası, sunucu adı) yazı tipini/ölçeğini
        günceller -- Ayarlar'daki yazı tipi dosyası VE düzen çubuğundaki yazı boyutu kaydırıcısı (Görev 7)
        buradan geçer. `self.fam` BİLEREK dokunulmaz kalır: `set_logo`'daki "MM" monogramı kendi
        `logo_size` kaydırıcısına sahip, tahta yazı ölçeğinin kapsamı dışında (bkz. set_logo).

        `self._board_fam` ise GÜNCELLENİR: çerçeve boyacısına giden FrameContext.fam odur (bkz. paintEvent).
        HUD'un bant yazıları (sunucu adı/marka) böylece kaydırıcıyı ve seçilen yazı tipini izler -- eskiden
        self.fam geçiliyordu ve tahtadaki en göze çarpan iki yazı ölçeğin DIŞINDA kalıyordu (madde 2)."""
        self._board_fam = fam
        self.status_label.setFont(theme.font(fam, 10, 500))
        self.brand.setFont(theme.hand_font(fam, 30, 700))
        self.name_label.setFont(theme.hand_font(fam, 28, 700))
        self.relayout()

    def set_font_scale(self, v: float) -> None:
        """Ayarlardaki kalıcı değeri (settings.font_scale) kaydırıcıya yansıtır; apply_ui_settings her
        çağrıda bunu da çağırır (set_item_visible ile aynı "dışarıdan bildirilen durum" kalıbı).
        Sinyali TEKRAR YAYMAZ (blockSignals) -- yoksa MainWindow <-> WorkArea arasında sonsuz döngü
        olurdu (fontScaleChanged -> settings.font_scale -> apply_ui_settings -> set_font_scale -> ...)."""
        val = round(v * 100)
        self.font_scale_slider.blockSignals(True)
        self.font_scale_slider.setValue(val)
        self.font_scale_slider.blockSignals(False)
        self.font_scale_label.setText(f"Yazı %{val}")

    def _on_font_scale_slider(self, val: int) -> None:
        """Kullanıcı kaydırıcıyı sürükledikçe: etiket hemen güncellenir, MainWindow'a (fontScaleChanged)
        bildirilir -- ayara yazmak ve apply_ui_settings ile tahtaya uygulamak dışarının işi."""
        self.font_scale_label.setText(f"Yazı %{val}")
        self.fontScaleChanged.emit(val / 100)

    def set_presenter_name(self, text: str) -> None:
        """Yalnız METNİ taşır; GÖRÜNÜRLÜĞÜ artık tek başına belirlemez (bkz. set_item_visible("presenter", ..)) --
        göz düğmesi ile Ayarlar'daki ad kutusu birbirini ezmesin diye ayrıldı. Boş ad hâlâ etiketi gizler
        (gösterilecek bir şey yok), ama dolu bir ad "presenter" kapalıyken görünmez kalır. Görünürlük artık
        _apply_chrome() üzerinden hesaplanır (Görev 8): etkin çerçeve stili bu adı kendi bandına çiziyorsa
        (bkz. _chrome_state) eski etiket burada da gizli kalmalı."""
        self.name_label.setText(text)
        self._apply_chrome()
        self.name_label.adjustSize()
        self.relayout()

    def set_item_visible(self, key: str, on: bool) -> None:
        """MainWindow.apply_ui_settings'in her görünürlük anahtarı için çağırdığı bildirim: WorkArea
        AppSettings'i hiç görmez, yalnız BU çağrıdan öğrenir -- göz düğmesinin işaretli durumu, _hit'in
        gizliyi sürüklemeyi reddetmesi ve overlay'in hayalet çizimi bunu okur. Gerçek widget görünürlüğü
        (bölge/marka/logo/rozet/durum) hâlâ apply_ui_settings'in kendi setVisible çağrılarında uygulanır --
        TEK istisna "presenter"/"brand"/"frame_titles": bunlar _apply_chrome() üzerinden burada uygulanır
        (Görev 8) çünkü etkin çerçeve stili bu ikisini kendi bandına çizebilir (bkz. _apply_chrome)."""
        self._visible[key] = on
        btn = self._eye_buttons.get(key)
        if btn is not None:
            btn.setChecked(on)
        self._apply_chrome()
        self.overlay.update()

    def frame_band(self) -> int:
        return FRAME_SPECS[self.frame_style].band if self.frame_visible else 0

    def _min_stage_k(self) -> int:
        """stage_rect()'in 'çok küçük pencere' eşiği (review bulgusu, Görev 8 sonrası): MIN_STAGE_K=4 yalnız
        theme.FRAME_BAND (Klasik'in bandı, 26px) için kalibre edilmişti -- HUD gibi daha kalın bantlı
        (52px) bir stil seçiliyken AYNI sabit kullanılırsa true-branch'in ürettiği sahne HUD'un bandını
        iki kere barındıramayacak kadar küçük kalabiliyor, inner_rect() negatife düşüyordu (ör. 200x120
        pencerede HUD inner'ı 88x4'e, sonra biraz daha küçük pencerelerde negatife düşüyordu).

        Eşik, o an etkin banda ORANLA ölçeklenir: band <= theme.FRAME_BAND iken (Klasik VE çerçeve
        kapalıyken, frame_band()==0 dahil) MATEMATİKSEL OLARAK MIN_STAGE_K'nin BİREBİR AYNISINI verir --
        bu iki durum bugüne kadar test edilen HER ŞEY, davranışları hiç değişmez (regresyon riski yok).
        Yalnız band FRAME_BAND'den kalınsa (bugün yalnız HUD) eşik `ceil(MIN_STAGE_K * band / FRAME_BAND)`
        ile büyütülür -- yani Klasik'in k=4'te bıraktığı inner/band ORANI korunur.

        UYARI: pencerenin kendisi 2*band'den küçükse (ör. HUD'ta 104px'in altında bir yükseklik) bu eşik
        hiçbir şeyi kurtaramaz -- self.rect() geri dönüşü bile o boyutta kalır, inner yine negatif çıkar.
        Bu FİZİKSEL bir sınır (bandı iki kere barındıracak yer yok), eşik ayarıyla çözülemez; tasarımın
        garantisi yalnız ÇÖKMEMEK (bkz. frames.paint_hud'un stage/band koruması), pozitif inner değil."""
        band = self.frame_band()
        if band <= theme.FRAME_BAND:
            return self.MIN_STAGE_K
        return -(-(self.MIN_STAGE_K * band) // theme.FRAME_BAND)     # ceil(MIN_STAGE_K * band / FRAME_BAND)

    def stage_rect(self) -> QRect:
        """Tahtanın 16:9 sahnesi: pencerede ortalanır, artan yer bant olarak kalır.

        Ölçü 32k x 18k adımıyla seçilir; sadece çifte indirmek yetmez, oran yine kayar (ör. 1830x1030
        = 1.7767) ve ffmpeg `scale=-2:1440` bunu 2560 yerine 2558 piksel yapar. Ayrıca k, ekran
        ölçeğinin (dpr) paydasının katına indirilir: RecordRect.physical() mantıksal ölçüyü dpr ile
        çarpıp genişlikle yüksekliğe BAĞIMSIZ _even() uyguluyor, Windows'ta 125/150/175% ölçek kesirli
        dpr ürettiği için (app.py: PassThrough) hizalanmamış bir sahne orada yine 1 piksel kaybederdi.
        Böylece dpr 1, 1.25, 1.5, 1.75, 2'de fiziksel ölçü tam sayı, çift ve oran tam 16:9 kalır.
        aspect_lock kapalıysa (ya da pencere sahneyi taşıyamayacak kadar küçükse) tüm alan sahnedir."""
        if not self.aspect_lock:
            return self.rect()
        full_w, full_h = self.width(), self.height()
        k = min(full_w // self.STAGE_STEP_W, full_h // self.STAGE_STEP_H)
        q = Fraction(self.devicePixelRatioF()).limit_denominator(8).denominator
        k -= k % q                                              # dpr = p/q iken 18k*dpr ve 32k*dpr çift kalsın
        if k < self._min_stage_k():                             # çok küçük pencere: eski davranışa dön,
            return self.rect()                                  # yoksa inner_rect negatife düşerdi
        w, h = self.STAGE_STEP_W * k, self.STAGE_STEP_H * k
        return QRect((full_w - w) // 2, (full_h - h) // 2, w, h)

    def inner_rect(self) -> QRect:
        """Çizilebilir alan: sahnedeki çerçeve bandının içi."""
        b = self.frame_band()
        t, r, btm, l = theme.WORK_PADDING
        s = self.stage_rect()
        return QRect(s.x() + l + b, s.y() + t + b, s.width() - l - r - 2 * b, s.height() - t - btm - 2 * b)

    def relayout(self) -> None:
        stage = self.stage_rect()
        inner = self.inner_rect()
        self.board.setGeometry(inner)
        self.board.lower()
        for key, zone in self._zones.items():
            x, y, w, h = lm.pixel_rect(self._layout[key], inner.width(), inner.height(), theme.GRID_GAP)
            zone.setGeometry(inner.x() + x, inner.y() + y, w, h)
            zone.raise_()
        self.ink.setGeometry(inner)
        self.ink.raise_()                                   # mürekkep soru/ipucu üstünde
        if "webcam" in self._zones:
            self._zones["webcam"].raise_()                  # kişi mürekkebin üstünde

        # Öğeler (marka, logo, sunucu adı, rozet, durum satırı): rozet MainWindow tarafından __init__'ten
        # SONRA gerçek RecordBadge ile değiştirildiği için (main_window.py:83) self.badge_slot burada HER
        # relayout()'ta yeniden okunur -- __init__'te bir kez yakalansaydı öksüz placeholder'a saplanırdı.
        self._items = {
            "status": self.status_label, "brand": self.brand, "logo": self.logo_label,
            "presenter": self.name_label, "badge": self.badge_slot,
        }
        self.status_label.adjustSize()
        self.brand.adjustSize()
        webcam = self._zones.get("webcam")
        anchor = webcam.geometry() if webcam is not None else inner
        self.name_label.adjustSize()
        # Sırayla: kayıtlı geçersiz kılma varsa onu kullan (stage_rect'e göre kesirli), yoksa bugünkü
        # formül (else dalı = regresyon yüzeyi, hiç sürüklenmemiş öğe birebir aynı görünmeli). raise_()
        # sırası bilerek KORUNUR (status -> brand -> logo -> presenter -> badge -> overlay).
        self._place_item("status", self.status_label, stage,
                         QPoint(inner.x() + 12, inner.bottom() - self.status_label.height() - 6))
        self._place_item("brand", self.brand, stage,
                         QPoint(stage.x() + (stage.width() - self.brand.width()) // 2, stage.y()))
        self._place_item("logo", self.logo_label, stage,
                         QPoint(inner.x() + 12, stage.y() + 2))      # sahnenin üst bandına asılı: kayda girer
        self._place_item("presenter", self.name_label, stage,
                         QPoint(anchor.right() - self.name_label.width() - 8,
                                anchor.top() - self.name_label.height() - 2))
        self._place_item("badge", self.badge_slot, stage,
                         QPoint(inner.right() - self.badge_slot.width() - 12, inner.y() + 4))
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()
        self.edit_bar.adjustSize()
        self.edit_bar.move(stage.x() + (stage.width() - self.edit_bar.width()) // 2,
                           stage.y() + self.brand.height() + 8)
        self.edit_bar.raise_()
        self.overlay.update()
        self._sync_eye_buttons()

    def _place_item(self, key: str, widget: QWidget, stage: QRect, default: QPoint) -> None:
        """Kayıtlı bir geçersiz kılma (`self._item_pos[key]`, stage_rect'e göre kesirli) varsa onu
        kullanır; yoksa `default`'u (bugünkü sert kodlu formül) kullanır.

        Sonuç HER İKİ yolda da sahneye KIRPILIR (nihai inceleme, madde 9). mouseReleaseEvent öğeyi yalnız
        SÜRÜKLEME anında sahneye sokuyordu; oysa widget'ın genişliği içeriğe ve fonta bağlı MUTLAK bir
        değer: yazı ölçeği 1,6'ya çekilince marka plakası 1000x650 pencerede, hiç sürüklenmemiş VARSAYILAN
        konumunda bile sahneyi ~14 px taşıyordu -- taşan kısım kayda girmez, yani kullanıcı sağ kenarını
        her kayıtta sessizce kaybederdi. Yalnız KONUM kaydırılır, BOYUT değiştirilmez (boyut içerik
        kaynaklı); sahneden geniş/uzun bir öğe sol/üst kenara hizalanır -- mouseMoveEvent'in öğe dalıyla
        BİREBİR aynı formül, böylece sürükleme ile yeniden akıtma aynı sonucu verir."""
        override = self._item_pos.get(key)
        if override is not None:
            dx, dy = lm.item_pixel_from_pos(override, stage.width(), stage.height())
            x, y = stage.x() + dx, stage.y() + dy
        else:
            x, y = default.x(), default.y()
        x = max(stage.x(), min(x, stage.x() + stage.width() - widget.width()))
        y = max(stage.y(), min(y, stage.y() + stage.height() - widget.height()))
        widget.move(x, y)
        widget.raise_()

    # --- göz düğmeleri (yalnız düzen modunda) ---------------------------------------
    def _make_eye_button(self, key: str) -> QPushButton:
        btn = QPushButton("👁", self)
        btn.setCheckable(True)
        btn.setChecked(self._visible.get(key, True))
        btn.setFixedSize(EYE_SIZE, EYE_SIZE)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("Göster/gizle")
        btn.setStyleSheet(
            f"QPushButton {{ background: {theme.INK}; color: {theme.MUTED_DARK}; border: 1px solid {theme.ACCENT};"
            f" border-radius: {EYE_SIZE // 2}px; font-size: 10px; padding: 0px; }}"
            f"QPushButton:checked {{ background: {theme.ACCENT}; color: {theme.PANEL_SOFT}; }}")
        btn.hide()          # yalnız set_edit_mode(True) iken görünür (bkz. _sync_eye_buttons)
        btn.clicked.connect(lambda checked, k=key: self._toggle_visibility(k, checked))
        return btn

    def _toggle_visibility(self, key: str, on: bool) -> None:
        """Bir göz düğmesine tıklanınca: WorkArea kendi bilgisini hemen günceller (buton düzen modunda
        her zaman doğru görünsün) VE dışarıya (MainWindow) bildirir -- ayara yazmak ve diğer widget'ların
        gerçek setVisible çağrılarını tetiklemek dışarının işi (bkz. set_item_visible docstring'i)."""
        self.set_item_visible(key, on)
        self.visibilityToggled.emit(key, on)

    def _sync_eye_buttons(self) -> None:
        """relayout()'un sonunda çağrılır: her bölge ve her öğe için köşesine bir göz düğmesi yerleştirir
        (yoksa oluşturur), işaretli durumunu bilinen görünürlükten alır, yalnız düzen modunda gösterir.

        `placed` bu turda konmuş düğmelerin dikdörtgenleridir: küçük pencerelerde birden çok sahip
        (ör. `ipucu` bölgesi + marka plakası + rozet) sahnenin SAĞ ÜST köşesinde buluşur ve düğmeleri
        üst üste biner -- üstte kalan hariç hepsi tıklanamaz olur (nihai inceleme, madde 10'un ölçtüğü
        çakışma; 700x500'de gözlendi). _place_eye_button çakışanı sola kaydırır, bkz. orada."""
        placed: list[QRect] = []
        for zkey, zone in self._zones.items():
            self._place_eye_button(_ZONE_VIS_KEY.get(zkey, zkey), zone.geometry(), True, placed)
        for key, widget in self._items.items():
            self._place_eye_button(key, widget.geometry(), False, placed)

    def _free_eye_x(self, x: int, y: int, placed: list[QRect]) -> int:
        """(x, y) bu turda konmuş bir düğmeyle çakışıyorsa soldaki ilk BOŞ yuvayı döndürür (aynı satırda
        kalır: y'yi değiştirmek bölgelerin köşe tutamağı kaçış yolunu -- bkz. _place_eye_button -- yeniden
        bozardı). Sola yer kalmazsa özgün x'e döner: çakışma iyileştirilemedi, ama düğme hiç değilse
        pencerenin içinde kalır."""
        step = EYE_SIZE + 2
        cand = x
        while cand >= 0:
            if not any(QRect(cand, y, EYE_SIZE, EYE_SIZE).intersects(r) for r in placed):
                return cand
            cand -= step
        return x

    def _place_eye_button(self, key: str, geo: QRect, is_zone: bool, placed: list[QRect] | None = None) -> None:
        """Düğme normalde köşenin üst-sağında, bölgenin/öğenin GEOMETRİSİNİN TAMAMEN DIŞINDA durur (üst
        kenarla çakışmaz) -- bir öğenin taşıma alanı hiç etkilenmesin diye kasıtlı; düğme gerçek bir Qt
        çocuğu olduğundan tıklamayı _hit()'ten önce yakalar.

        Bu "üstte, dışarıda" yerleşim `geo.top() < EYE_SIZE` iken WorkArea'nın KENDİ üst kenarının da
        dışına taşar -- pencere `WorkArea`'ya sıfır kenar boşluğuyla bitişik olduğundan (main_window.py)
        bu, düğmeyi tamamen erişilemez kılar (pencerenin dışında/başlık çubuğunda kalır). Bu, çerçeve
        (frame_visible=False) kapalıyken ya da pencere tam/dardan-16:9 iken YAYGIN bir durumdur, uç durum
        değil -- bkz. review bulgusu (1920x1080, 1280x720, 1600x900 hepsi `soru`/`brand`/`logo` için
        negatif y üretiyordu).

        Öğeler için düzeltme basit: y'yi 0'a kelepçelemek yeterli (öğelerin köşe tutamağı yok). Bölgeler
        için AYNI kelepçe GRIP=18 < EYE_SIZE=20 olduğundan `_hit()`'in nw/ne köşe tutamağı önceliğini
        (bkz. modül üstü not) yeniden bozar: düğme bölgenin içine, tutamağın ÜSTÜNE biner ve o köşeden
        yeniden boyutlandırmayı kalıcı olarak imkansız kılardı. Bölgeler bu yüzden farklı bir kaçış
        yolu kullanır: üstte yer yoksa düğme köşe tutamağının (GRIP + 1 px pay ile) HEMEN ALTINA, bölgenin
        içine itilir -- x ekseni sağda kaldığı için yalnız "ne" ile çakışma riski vardı, bu da onu giderir.

        Son adım (`placed` verilmişse): aynı turda konmuş bir düğmeyle çakışma varsa sola kaydır --
        bkz. _free_eye_x ve _sync_eye_buttons."""
        if key not in self._eye_buttons:
            self._eye_buttons[key] = self._make_eye_button(key)
        btn = self._eye_buttons[key]
        x = geo.right() - EYE_SIZE
        y = geo.top() - EYE_SIZE
        if y < 0:
            y = geo.top() + GRIP + 1 if is_zone else 0
        x = max(0, min(x, self.width() - EYE_SIZE))
        y = max(0, min(y, self.height() - EYE_SIZE))
        if placed is not None:
            x = self._free_eye_x(x, y, placed)
            placed.append(QRect(x, y, EYE_SIZE, EYE_SIZE))
        btn.move(x, y)
        btn.setChecked(self._visible.get(key, True))
        btn.setVisible(self.edit_mode)
        btn.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def recording_rect(self) -> tuple[int, int, int, int, float]:
        """Kayda giren dikdörtgen: 16:9 sahnenin tamamı (kenar bantları kayda girmez)."""
        s = self.stage_rect()
        g = self.mapToGlobal(s.topLeft())
        return g.x(), g.y(), s.width(), s.height(), float(self.devicePixelRatioF())

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.adjustSize()

    def set_click_mode(self, on: bool) -> None:
        """on: 'Tıkla' aracı, bölge çocukları tıklanır. off: çizim aracı, her basış tahtaya gider."""
        for zone in self._zones.values():
            zone.set_click_through(not on)

    def set_tool_cursor(self, cursor) -> None:
        """Araç imleci tahtada ve bölgelerde aynı; tıklanabilir çocuklar (kart, kamera, düğme) kendi imlecini korur."""
        self.board.setCursor(cursor)
        for zone in self._zones.values():
            zone.setCursor(cursor)

    # --- edit mode mouse handling ---------------------------------------------
    def _hit(self, pos: QPoint) -> tuple[str, str] | None:
        # Öğeler her zaman bölgelerin üstünde çizilir (relayout()'un raise_ sırası) -- ör. rozetin
        # varsayılan konumu ipucu'yla, marka plakası da soru/ipucu'nun üst kenarıyla görsel olarak çakışır.
        # Bölgenin KÖŞE tutamakları (nw/ne/sw/se) yine de HER ZAMAN kazanır -- yoksa marka plakasının
        # altında soru/ipucu'yu köşeden yeniden boyutlandırmak imkansız olurdu (bkz.
        # test_edit_mode_resize_from_nw_corner_moves_and_resizes). TEK KENAR tutamakları (n/s/e/w) ise
        # köşelerden FARKLI davranır ve öğelere öncelik VERMEZ: bunlar "taşı" isabetiyle aynı fallback'e
        # düşer, üstteki bir öğe varsa o kazanır. Kasıtlı bir dengeleme -- köşeler küçük (GRIP=18px'lik
        # kare), ama kenar bir bölgenin tüm çevresini saran uzun bir şerit; kenarlara da koşulsuz öncelik
        # verilseydi rozet/logo gibi küçük öğelerin alanının BÜYÜK KISMI tıklanamaz hâle gelirdi (review'da
        # ölçülen: rozette isabetlerin ~%79'u, logo'da ~%42'si, marka plakasında ~%34'ü bir bölgenin kenar
        # tutamağına gidiyordu, öğenin kendisine değil -- bkz. test_hit_test_center_of_logo_and_badge_...).
        # UYARI: GRIP'i büyütmek ya da bir öğenin varsayılan/sürüklenmiş konumunu bir bölge kenarına daha
        # da yaklaştırmak bu dengeyi yeniden bozabilir; o testler bunu köşe ve kenar için ayrı ayrı bekçiler.
        # Hem bölge hem öğe isabet sırası GERÇEK Qt yığınından (self.children(), raise_() tarafından güncel
        # tutulur) türetilir -- sözlük ekleme sırasını çizim sırasıyla elle senkron tutmaya dayanmaz
        # (nihai inceleme, madde 6: öğeler zaten böyleydi, bölgeler değildi; bugün aynı sonucu veriyorlar
        # ama relayout()'un raise_() sırası değişirse bölge önceliği sessizce kayardı).
        stacking = self.children()
        zone_fallback: tuple[str, str] | None = None
        for key in sorted(self._zones, key=lambda k: stacking.index(self._zones[k]), reverse=True):
            if not self._visible.get(_ZONE_VIS_KEY.get(key, key), True):
                continue                                   # gizli bölge yokmuş gibi davranılır, sürüklenmez
            geo = self._zones[key].geometry()
            if not geo.contains(pos):
                continue
            near_l = pos.x() - geo.left() <= GRIP
            near_r = geo.right() - pos.x() <= GRIP
            near_t = pos.y() - geo.top() <= GRIP
            near_b = geo.bottom() - pos.y() <= GRIP
            if near_t and near_l: return key, "nw"          # köşe: koşulsuz kazanır
            if near_t and near_r: return key, "ne"
            if near_b and near_l: return key, "sw"
            if near_b and near_r: return key, "se"
            if near_t: zone_fallback = (key, "n")            # tek kenar: öğe üstteyse o kazanır
            elif near_b: zone_fallback = (key, "s")
            elif near_l: zone_fallback = (key, "w")
            elif near_r: zone_fallback = (key, "e")
            else: zone_fallback = (key, "move")
            break
        # Öğeler için aynı yığın (yukarıda bir kez okundu): _items'ın kuruluş sırasıyla _place_item çağrı
        # sırasını elle senkron tutmaya dayanmaz, ileride biri değişip diğeri değişmezse bile görüneni
        # yansıtmaya devam eder.
        for key in sorted(self._items, key=lambda k: stacking.index(self._items[k]), reverse=True):
            if not self._visible.get(key, True):
                continue                                    # gizli öğe yokmuş gibi davranılır, sürüklenmez
            if self._items[key].geometry().contains(pos):
                return key, "move"
        return zone_fallback

    def _widget(self, key: str) -> QWidget:
        """`key` bir bölge mi öğe mi -- `_drag` tarafından tutulan geometri hangi çocuğa uygulanacak."""
        return self._zones[key] if key in self._zones else self._items[key]

    def mousePressEvent(self, e: QMouseEvent):
        if self.edit_mode and e.button() == Qt.MouseButton.LeftButton:
            hit = self._hit(e.position().toPoint())
            if hit:
                key, mode = hit
                self._drag = (key, mode, e.position().toPoint(), QRect(self._widget(key).geometry()))
                e.accept(); return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.position().toPoint()
        if self._drag is None:
            if self.edit_mode:
                hit = self._hit(pos)
                self.setCursor(_EDGE_CURSORS.get(hit[1], Qt.CursorShape.ArrowCursor) if hit
                               else Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(e); return
        key, mode, start, geo = self._drag
        d = pos - start
        self._snap_active = bool(e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
        x, y, w, h = geo.x(), geo.y(), geo.width(), geo.height()
        if mode == "move":
            x += d.x(); y += d.y()
        else:
            if "e" in mode:
                w = geo.width() + d.x()
            if "w" in mode:
                w = geo.width() - d.x(); x = geo.x() + d.x()
            if "s" in mode:
                h = geo.height() + d.y()
            if "n" in mode:
                h = geo.height() - d.y(); y = geo.y() + d.y()
            if w < lm.MIN_FREE_W:                            # asgari genişlik: karşı kenarı sabit tut
                if "w" in mode:
                    x -= lm.MIN_FREE_W - w
                w = lm.MIN_FREE_W
            if h < lm.MIN_FREE_H:
                if "n" in mode:
                    y -= lm.MIN_FREE_H - h
                h = lm.MIN_FREE_H
        if key in self._zones:                                # canlı kırpma: tahtadan dışarı sürüklenemez
            inner = self.inner_rect()
            if mode == "move":
                w = min(w, inner.width())
                h = min(h, inner.height())
                x = max(inner.x(), min(x, inner.x() + inner.width() - w))
                y = max(inner.y(), min(y, inner.y() + inner.height() - h))
            else:
                # Boyutlandırmada taşanı kes; tüm kutuyu kaydırmak karşı kenarı da oynatır.
                x, y, w, h = QRect(x, y, w, h).intersected(inner).getRect()
        else:                                                  # öğeler sahneye göre kırpılır (inner_rect
            stage = self.stage_rect()                          # DEĞİL: marka/logo bandın üstünde durur)
            w = min(w, stage.width())
            h = min(h, stage.height())
            x = max(stage.x(), min(x, stage.x() + stage.width() - w))
            y = max(stage.y(), min(y, stage.y() + stage.height() - h))
        self._widget(key).setGeometry(x, y, w, h)
        self.overlay.update()
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._drag is None:
            super().mouseReleaseEvent(e); return
        key, _mode, _start, _geo = self._drag
        self._drag = None
        self._snap_active = False
        if key in self._zones:
            inner = self.inner_rect()
            g = self._zones[key].geometry()
            ctrl = bool(e.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
            to_geom = lm.snap_rect if ctrl else lm.free_rect
            self._layout[key] = to_geom(g.x() - inner.x(), g.y() - inner.y(), g.width(), g.height(),
                                        inner.width(), inner.height(), theme.GRID_GAP)
        else:
            stage = self.stage_rect()                          # KARAR: öğe konumu stage_rect'e göre kesirli
            g = self._items[key].geometry()
            self._item_pos[key] = lm.item_pos_from_pixel(g.x() - stage.x(), g.y() - stage.y(),
                                                          stage.width(), stage.height())
        self.relayout()
        self.layoutChanged.emit(self.layout())
        e.accept()

    def paintEvent(self, _e):
        p = QPainter(self)
        # Sahne dışındaki bant koyu kalır: çerçeve kapalıyken de kayda girmeyen ölü bölge belli olsun
        # (oran kilidi kapalıyken sahne = tüm alan, yani eski tek renk görüntü).
        p.fillRect(self.rect(), QColor(theme.INK))
        p.fillRect(self.stage_rect(), QColor(theme.PANEL))
        if self.frame_visible:
            spec, titles_on = self._chrome_state()
            # presenter/brand metni yalnız etkin stil onu KENDİSİ çiziyorsa (draws_presenter/draws_brand)
            # VE ilgili görünürlük açıksa geçilir -- kapalıyken FrameContext'e boş dize gider, boyacı
            # (paint_hud) bandı yine çizer ama içi boş kalır (bkz. Görev 8 brief'i, frame_titles).
            ctx = FrameContext(
                rect=self.rect(), stage=self.stage_rect(), inner=self.inner_rect(), band=self.frame_band(),
                fam=self._board_fam,                       # self.fam DEĞİL: bkz. set_families (madde 2)
                presenter=self.name_label.text() if titles_on and self._visible.get("presenter", True) else "",
                brand=self.brand.text() if titles_on and self._visible.get("brand", True) else "",
            )
            spec.paint(p, ctx)
        p.end()
