"""Görsel şekil menüsü: her şekil kendi çizimiyle bir düğme, ızgara düzeninde açılır kutu."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QFrame, QGridLayout

from matematigin_mantigi.core.models import SHAPE_META, SHAPE_ORDER, Shape
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.shape_paint import paint_shape_icon


class ShapeIconButton(QAbstractButton):
    SIZE = 56

    def __init__(self, shape: Shape, parent=None):
        super().__init__(parent)
        self.shape = shape
        self.setCheckable(True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setToolTip(SHAPE_META[shape][0])
        self.setAccessibleName(SHAPE_META[shape][0])
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT if on else (theme.TOOLBAR_LINE if self.underMouse() else theme.TOOLBAR_BTN)))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 6, 6)
        p.setPen(QPen(QColor("#ffffff" if on else theme.TOOLBAR_MUTED), 2.2, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        paint_shape_icon(p, self.shape, self.width() / 2, self.height() / 2, self.width() * .56)
        p.end()


class ShapeMenu(QFrame):
    """Seçilince shapeSelected yayar ve kapanır. COLUMNS sütunlu ızgara; dar ekrana sığar."""
    shapeSelected = pyqtSignal(object)      # Shape
    COLUMNS = 4

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("shapeMenu")
        self.setStyleSheet(f"#shapeMenu {{ background: {theme.TOOLBAR_LINE}; border: 1px solid {theme.TOOLBAR_DIM};"
                           f" border-radius: 8px; }}")
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8); grid.setSpacing(6)
        self.buttons: dict[Shape, ShapeIconButton] = {}
        for i, shape in enumerate(SHAPE_ORDER):
            b = ShapeIconButton(shape)
            b.clicked.connect(lambda _c=False, s=shape: self._choose(s))
            self.buttons[shape] = b
            grid.addWidget(b, i // self.COLUMNS, i % self.COLUMNS)
        self.adjustSize()

    def set_current(self, shape: Shape) -> None:
        for s, b in self.buttons.items():
            b.setChecked(s == shape)

    def _choose(self, shape: Shape) -> None:
        self.set_current(shape)
        self.hide()
        self.shapeSelected.emit(shape)

    def popup_beside(self, anchor_global: QPoint, screen_rect) -> None:
        """Düğmenin sağında açar, ekran dışına taşarsa içeri çeker."""
        self.adjustSize()
        x, y = anchor_global.x(), anchor_global.y()
        x = max(screen_rect.left(), min(x, screen_rect.right() - self.width() + 1))
        y = max(screen_rect.top(), min(y, screen_rect.bottom() - self.height() + 1))
        self.move(x, y)
        self.show()
