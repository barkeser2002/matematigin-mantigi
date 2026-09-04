from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QLabel

from matematigin_mantigi.ui import theme


class GlyphButton(QAbstractButton):
    """56x48 araç düğmesi: büyük glif + 9px etiket. Seçiliyken accent zemin."""

    def __init__(self, glyph: str, label: str, parent=None):
        super().__init__(parent)
        self.glyph, self.label = glyph, label
        self.setCheckable(True)
        self.setFixedSize(56, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT if on else theme.TOOLBAR_BTN))
        p.drawRoundedRect(QRectF(0, 0, 56, 48), 6, 6)
        p.setPen(QColor("#ffffff" if on else theme.TOOLBAR_MUTED))
        f = QFont(self.font()); f.setPixelSize(18); p.setFont(f)
        p.drawText(QRectF(0, 4, 56, 24), Qt.AlignmentFlag.AlignCenter, self.glyph)
        f.setPixelSize(9); f.setWeight(QFont.Weight(600)); p.setFont(f)
        p.drawText(QRectF(0, 28, 56, 16), Qt.AlignmentFlag.AlignCenter, self.label.upper())
        p.end()


class SwatchButton(QAbstractButton):
    """22px renk dairesi; seçiliyken 3px açık halka."""

    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setCheckable(True)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(14, 14)
        if self.isChecked():
            p.setPen(QPen(QColor(theme.PANEL_SOFT), 3))
        else:
            p.setPen(QPen(QColor(theme.TOOLBAR_LINE), 1))
        p.setBrush(QBrush(QColor(self.color_hex)))
        p.drawEllipse(c, 11, 11)
        p.end()


class DotButton(QAbstractButton):
    """Kalınlık ön ayarı: 2/4/8 px -> 8/12/16 px nokta."""

    DOT = {2: 8, 4: 12, 8: 16}

    def __init__(self, value: int, parent=None):
        super().__init__(parent)
        self.value = value
        self.setCheckable(True)
        self.setFixedSize(28, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.DOT.get(self.value, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.PANEL_SOFT if self.isChecked() else theme.TOOLBAR_DIM))
        p.drawEllipse(QPointF(14, 12), d / 2, d / 2)
        p.end()


class RecordButton(QAbstractButton):
    """56px daire, accent kenar; kayıtta 18px yuvarlatılmış kare."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(56, 56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(theme.ACCENT), 2))
        p.setBrush(QColor(theme.TOOLBAR_BTN))
        p.drawEllipse(QPointF(28, 28), 26, 26)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT))
        if self.isChecked():
            p.drawRoundedRect(QRectF(19, 19, 18, 18), 4, 4)
        else:
            p.drawEllipse(QPointF(28, 28), 11, 11)
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
