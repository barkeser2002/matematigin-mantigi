from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QLabel, QPushButton

from matematigin_mantigi.ui import theme


class WrapButton(QPushButton):
    """Dar araç çubuğu düğmesi: uzun etiketi ilk boşluktan iki satıra kırar.
    text() her zaman mantıksal (tek satır) metni döndürür.
    set_single_line(True) sarmayı kapatır (MINI kademede tek satır zorunlu)."""

    WRAP_OVER = 9

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._logical = ""
        self._single_line = False
        self.setText(text)

    def setText(self, text: str) -> None:
        self._logical = text
        wrap = not self._single_line and len(text) > self.WRAP_OVER and " " in text
        shown = text.replace(" ", "\n", 1) if wrap else text
        super().setText(shown)

    def text(self) -> str:
        return self._logical

    def set_single_line(self, on: bool) -> None:
        if on == self._single_line:
            return
        self._single_line = on
        self.setText(self._logical)


class GlyphButton(QAbstractButton):
    """Araç düğmesi: büyük glif + etiket. Seçiliyken accent zemin.
    Boyut sabit değil: set_metrics ile yükseklik/glif boyutu/etiket görünürlüğü ölçeklenir.
    Genişlik (W) her kademede sabit kalır, yalnız yükseklik küçülür."""

    rightClicked = pyqtSignal()
    W = 56
    H = 48
    GLYPH_PX = 18
    LABEL_PX = 9

    def __init__(self, glyph: str, label: str, parent=None):
        super().__init__(parent)
        self.glyph, self.label = glyph, label
        self.shape_icon = None          # Shape ise glif yerine şeklin kendi çizimi (Şekil düğmesi)
        self.glyph_px = self.GLYPH_PX
        self.show_label = True
        self.setCheckable(True)
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            e.accept()               # menü bırakınca açılır: basışta açılan açılır pencere bırakmayı yutardı
            return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.RightButton:
            if self.rect().contains(e.position().toPoint()):
                self.rightClicked.emit()
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def set_metrics(self, h: int, glyph_px: int, show_label: bool) -> None:
        self.glyph_px = glyph_px
        self.show_label = show_label
        self.setFixedSize(self.W, h)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT if on else theme.TOOLBAR_BTN))
        p.drawRoundedRect(QRectF(0, 0, w, h), 6, 6)
        p.setPen(QColor("#ffffff" if on else theme.TOOLBAR_MUTED))
        f = QFont(self.font()); f.setPixelSize(self.glyph_px); p.setFont(f)
        glyph_box = QRectF(0, h * (4 / 48), w, h / 2) if self.show_label else QRectF(0, 0, w, h)
        if self.shape_icon is not None:
            from matematigin_mantigi.ui.shape_paint import paint_shape_icon
            p.setPen(QPen(p.pen().color(), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.setBrush(Qt.BrushStyle.NoBrush)
            paint_shape_icon(p, self.shape_icon, glyph_box.center().x(), glyph_box.center().y(),
                             min(glyph_box.height(), w) * .8)
            if self.show_label:
                f.setPixelSize(self.LABEL_PX); f.setWeight(QFont.Weight(600)); p.setFont(f)
                p.setPen(QColor("#ffffff" if on else theme.TOOLBAR_MUTED))
                p.drawText(QRectF(0, h * (28 / 48), w, h / 3), Qt.AlignmentFlag.AlignCenter, theme.tr_upper(self.label))
            p.end()
            return
        if self.show_label:
            # Oranlar orijinal 56x48 düzeninden türetildi: glif üstte yarım yükseklik,
            # 9px etiket altta üçte bir yükseklik (48 tabanına göre 4/48 ve 28/48 ofsetleri).
            p.drawText(QRectF(0, h * (4 / 48), w, h / 2), Qt.AlignmentFlag.AlignCenter, self.glyph)
            f.setPixelSize(self.LABEL_PX); f.setWeight(QFont.Weight(600)); p.setFont(f)
            p.drawText(QRectF(0, h * (28 / 48), w, h / 3), Qt.AlignmentFlag.AlignCenter, theme.tr_upper(self.label))
        else:
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self.glyph)
        p.end()


class SwatchButton(QAbstractButton):
    """Renk dairesi; seçiliyken kalın açık halka. Çap set_diameter ile ölçeklenir."""

    DIAMETER = 28

    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setCheckable(True)
        self.setFixedSize(self.DIAMETER, self.DIAMETER)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_diameter(self, d: int) -> None:
        self.setFixedSize(d, d)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.width() / 2
        r = c - 3
        center = QPointF(c, c)
        if self.isChecked():
            p.setPen(QPen(QColor(theme.PANEL_SOFT), 3))
        else:
            p.setPen(QPen(QColor(theme.TOOLBAR_LINE), 1))
        p.setBrush(QBrush(QColor(self.color_hex)))
        p.drawEllipse(center, r, r)
        p.end()


class DotButton(QAbstractButton):
    """Kalınlık ön ayarı: 1/2/4/8/12 px -> nokta. SIZE artık örnek değişkeni
    (set_size ile ölçeklenir); nokta çapı SIZE/BASE_SIZE oranıyla küçülür."""

    DOT = {1: 5, 2: 7, 4: 10, 8: 14, 12: 18}
    BASE_SIZE = 22

    def __init__(self, value: int, parent=None):
        super().__init__(parent)
        self.value = value
        self.SIZE = self.BASE_SIZE
        self.setCheckable(True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_size(self, size: int) -> None:
        self.SIZE = size
        self.setFixedSize(size, size)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.DOT.get(self.value, 10) * (self.SIZE / self.BASE_SIZE)
        c = self.SIZE / 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.PANEL_SOFT if self.isChecked() else theme.TOOLBAR_DIM))
        p.drawEllipse(QPointF(c, c), d / 2, d / 2)
        p.end()


class RecordButton(QAbstractButton):
    """Daire, accent kenar; kayıtta yuvarlatılmış kare. Çap set_diameter ile ölçeklenir."""

    DIAMETER = 56

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(self.DIAMETER, self.DIAMETER)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_diameter(self, d: int) -> None:
        self.setFixedSize(d, d)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.width() / 2
        scale = r / 28          # 28 = orijinal yarıçap (56/2)
        c = QPointF(r, r)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.setBrush(QColor(theme.TOOLBAR_BTN))
        p.drawEllipse(c, 26 * scale, 26 * scale)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT))
        if self.isChecked():
            side = 18 * scale
            off = 19 * scale
            p.drawRoundedRect(QRectF(off, off, side, side), 4 * scale, 4 * scale)
        else:
            p.drawEllipse(c, 11 * scale, 11 * scale)
        p.end()


class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    doubleClicked = pyqtSignal()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(e)
