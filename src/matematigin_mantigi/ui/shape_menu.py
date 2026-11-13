"""Görsel şekil menüsü: her şeklin simgesi ve adı bir düğmede, 5 sütunlu ızgara; altta dolgu seçimi.

Açılır kutu (Popup) geçicidir: şekil seçilince, dışarı tıklanınca ya da auto_close_ms dolunca kendisi kapanır.
Kayıt sürerken kısa süre (ToolBar.shape_menu_gate) açık kalır; sahneye kalıcı bir pencere bırakmaz.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QAbstractButton, QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from matematigin_mantigi.core.models import SHAPE_META, SHAPE_ORDER, Shape
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.shape_paint import paint_shape_icon


class ShapeIconButton(QAbstractButton):
    """Simge (üstte) + şekil adı (altta, en çok iki satır). Kalemle rahat seçilecek kadar büyük."""
    W, H = 76, 70
    ICON_PX = 30

    def __init__(self, shape: Shape, parent=None):
        super().__init__(parent)
        self.shape = shape
        self.label = SHAPE_META[shape][0]
        self.setCheckable(True)
        self.setFixedSize(self.W, self.H)
        self.setToolTip(self.label)
        self.setAccessibleName(self.label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        on = self.isChecked()
        ink = QColor("#ffffff" if on else theme.TOOLBAR_MUTED)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.ACCENT if on else (theme.TOOLBAR_LINE if self.underMouse() else theme.TOOLBAR_BTN)))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 6, 6)
        p.setPen(QPen(ink, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        paint_shape_icon(p, self.shape, self.width() / 2, 6 + self.ICON_PX / 2, self.ICON_PX)
        font = QFont(self.font())
        font.setPixelSize(10)
        font.setWeight(QFont.Weight(600))
        p.setFont(font)
        p.setPen(ink)
        p.drawText(QRectF(3, 40, self.width() - 6, self.height() - 42),
                   int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), self.label)
        p.end()


class ShapeMenu(QFrame):
    """Şekil seçilince shapeSelected yayar ve kapanır; dolgu düğmesi menüyü açık bırakır (fillSelected)."""
    shapeSelected = pyqtSignal(object)      # Shape
    fillSelected = pyqtSignal(bool)         # True: dolgulu, False: boş
    COLUMNS = 5

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("shapeMenu")
        self.setStyleSheet(f"#shapeMenu {{ background: {theme.TOOLBAR_LINE}; border: 1px solid {theme.TOOLBAR_DIM};"
                           f" border-radius: 8px; }}"
                           f" #shapeMenu QPushButton {{ background: {theme.TOOLBAR_BTN}; color: {theme.TOOLBAR_MUTED};"
                           f" border: none; border-radius: 6px; padding: 4px 12px; }}"
                           f" #shapeMenu QPushButton:checked {{ background: {theme.ACCENT}; color: #ffffff; }}")
        outer = QGridLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)
        grid_host = QWidget(self)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        self.buttons: dict[Shape, ShapeIconButton] = {}
        for i, shape in enumerate(SHAPE_ORDER):
            b = ShapeIconButton(shape, grid_host)
            b.clicked.connect(self._on_shape_button)
            self.buttons[shape] = b
            grid.addWidget(b, i // self.COLUMNS, i % self.COLUMNS)
        outer.addWidget(grid_host, 0, 0)

        fill_row = QWidget(self)
        row = QHBoxLayout(fill_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        caption = QLabel("Dolgu", fill_row)
        caption.setStyleSheet(f"color: {theme.TOOLBAR_MUTED}; font-size: 11px; font-weight: 600;")
        row.addWidget(caption)
        self._fill_group = QButtonGroup(self)
        self._fill_group.setExclusive(True)
        self.fill_buttons: dict[bool, QPushButton] = {}
        for on, text in ((False, "Boş"), (True, "Yarı saydam")):
            btn = QPushButton(text, fill_row)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip("Kapalı şekiller (dikdörtgen, daire, çokgen…) yarı saydam dolar; açık çizgilerde etkisi yok")
            self._fill_group.addButton(btn)
            btn.clicked.connect(self._on_fill_button)
            self.fill_buttons[on] = btn
            row.addWidget(btn)
        outer.addWidget(fill_row, 1, 0)
        self.fill_buttons[False].setChecked(True)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.auto_close_ms = 0
        self.adjustSize()

    # --- durum -------------------------------------------------------------------------------------
    def set_current(self, shape: Shape) -> None:
        for s, b in self.buttons.items():
            b.setChecked(s == shape)

    def set_fill(self, on: bool) -> None:
        self.fill_buttons[bool(on)].setChecked(True)

    def set_auto_close_ms(self, ms: int) -> None:
        self.auto_close_ms = max(0, int(ms))

    # --- olaylar -----------------------------------------------------------------------------------
    def _on_shape_button(self) -> None:
        self._choose(self.sender().shape)

    def _on_fill_button(self) -> None:
        self.fillSelected.emit(self.sender() is self.fill_buttons[True])

    def _choose(self, shape: Shape) -> None:
        self.set_current(shape)
        self.hide()
        self.shapeSelected.emit(shape)

    def hideEvent(self, e) -> None:
        self._timer.stop()
        super().hideEvent(e)

    def popup_beside(self, anchor_global: QPoint, screen_rect) -> None:
        """Düğmenin sağında açar, ekran dışına taşarsa içeri çeker. auto_close_ms > 0 ise o süre sonunda kapanır."""
        self.adjustSize()
        x, y = anchor_global.x(), anchor_global.y()
        x = max(screen_rect.left(), min(x, screen_rect.right() - self.width() + 1))
        y = max(screen_rect.top(), min(y, screen_rect.bottom() - self.height() + 1))
        self.move(x, y)
        self.show()
        if self.auto_close_ms > 0:
            self._timer.start(self.auto_close_ms)
