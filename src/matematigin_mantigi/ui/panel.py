from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies


class _Header(QWidget):
    pressed = pyqtSignal(QPoint)
    doubleClicked = pyqtSignal()

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.pressed.emit(e.position().toPoint())
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(e)


class PanelFrame(QWidget):
    """Beyaz panel, 2px mürekkep kenar (sadece düzen modunda), radius 4, Caveat numaralı başlık."""

    headerPressed = pyqtSignal(QPoint)
    headerDoubleClicked = pyqtSignal()

    def __init__(self, number: str, title: str, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.key = ""
        self.fam = fam
        self.border_visible = False        # normal kullanımda çizgi yok; düzen modu açar
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.PANEL_BORDER, theme.PANEL_BORDER,
                                 theme.PANEL_BORDER, theme.PANEL_BORDER)
        outer.setSpacing(0)

        self.header_widget = _Header(self)
        self.header_widget.setFixedHeight(44)
        self.header_widget.pressed.connect(self.headerPressed)
        self.header_widget.doubleClicked.connect(self.headerDoubleClicked)
        self.header = QHBoxLayout(self.header_widget)
        self.header.setContentsMargins(18, 6, 18, 0)
        self.header.setSpacing(10)

        self.number_label = QLabel(number)
        self.number_label.setFont(theme.hand_font(fam, 34, 700))
        self.title_label = QLabel(title.upper())
        self.title_label.setFont(theme.font(fam, 11, 600, spacing_pct=114))
        self.title_label.setStyleSheet(f"color: {theme.MUTED};")
        self.header.addWidget(self.number_label)
        self.header.addWidget(self.title_label)
        self.header.addStretch(1)

        self.body_widget = QWidget(self)
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(24, 6, 24, 18)
        self.body.setSpacing(8)

        outer.addWidget(self.header_widget)
        outer.addWidget(self.body_widget, 1)

    def set_header_visible(self, on: bool) -> None:
        self.header_widget.setVisible(on)

    def set_border_visible(self, on: bool) -> None:
        self.border_visible = on
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(theme.PANEL))
        if self.border_visible:
            b = theme.PANEL_BORDER / 2
            p.setPen(QPen(QColor(theme.INK), theme.PANEL_BORDER))
            p.drawRoundedRect(QRectF(b, b, self.width() - 2 * b, self.height() - 2 * b),
                              theme.PANEL_RADIUS, theme.PANEL_RADIUS)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()),
                              theme.PANEL_RADIUS, theme.PANEL_RADIUS)
        p.end()
