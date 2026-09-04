"""Bölge 2 çizim yüzeyi: tablet basıncı, fare geri dönüşü, silgi, lazer, 30 adım geri al."""
from __future__ import annotations

from collections import deque

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap,
                         QPointingDevice, QResizeEvent, QTabletEvent)
from PyQt6.QtWidgets import QWidget

from matematigin_mantigi.core.models import Tool
from matematigin_mantigi.core.stroke import LASER_COLOR, MOUSE_PRESSURE, eraser_diameter, pressure_width
from matematigin_mantigi.ui import theme


def _grown(old: QImage, size: QSize, dpr: float) -> QImage:
    new = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    new.setDevicePixelRatio(dpr)
    new.fill(Qt.GlobalColor.transparent)
    if not old.isNull():
        p = QPainter(new); p.drawImage(0, 0, old); p.end()
    return new


def _dot_tile(dpr: float) -> QPixmap:
    s = theme.DOT_SPACING
    pm = QPixmap(int(s * dpr), int(s * dpr)); pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(theme.DOT))
    p.drawEllipse(QPointF(s / 2, s / 2), 1.0, 1.0); p.end()
    return pm


class DrawingCanvas(QWidget):
    strokeStarted = pyqtSignal()
    strokeFinished = pyqtSignal()
    historyChanged = pyqtSignal(bool, bool)     # can_undo, is_empty
    pressureChanged = pyqtSignal(float)
    inputSourceChanged = pyqtSignal(str)        # "tablet" | "mouse"
    MAX_UNDO = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabletTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.tool = Tool.PEN
        self.color = QColor(theme.INK)
        self.base_width = 4
        self._strokes = QImage()
        self._overlay = QImage()
        self._undo: deque[tuple[QImage, int]] = deque(maxlen=self.MAX_UNDO)
        self._stroke_count = 0
        self._tablet_down = False
        self._mouse_down = False
        self._last: QPointF | None = None
        self._last_p = MOUSE_PRESSURE
        self._active_tool = Tool.PEN
        self._tile = _dot_tile(1.0)
        self._ensure_layers(QSize(1, 1))

    # --- public state --------------------------------------------------------
    def set_tool(self, t: Tool) -> None: self.tool = t
    def set_color(self, c: QColor) -> None: self.color = QColor(c)
    def set_base_width(self, w: int) -> None: self.base_width = int(w)
    def can_undo(self) -> bool: return len(self._undo) > 0
    def is_empty(self) -> bool: return self._stroke_count == 0
    def strokes_image(self) -> QImage: return self._strokes

    def snapshot_image(self) -> QImage:
        out = QImage(self._strokes.size(), QImage.Format.Format_RGB32)
        out.setDevicePixelRatio(self._strokes.devicePixelRatio())
        out.fill(Qt.GlobalColor.white)
        p = QPainter(out); p.drawImage(0, 0, self._strokes); p.end()
        return out

    # --- stroke API (used by tablet, mouse and tests) -------------------------
    def begin_stroke(self, pos: QPointF, pressure: float, eraser_tip: bool = False) -> None:
        self._active_tool = Tool.ERASER if eraser_tip else self.tool
        if self._active_tool in (Tool.PEN, Tool.ERASER):
            self._undo.append((self._strokes.copy(), self._stroke_count))
            self._stroke_count += 1
        self._last, self._last_p = pos, pressure
        self._draw_segment(pos, pos, pressure)
        self.strokeStarted.emit()

    def extend_stroke(self, pos: QPointF, pressure: float) -> None:
        if self._last is None:
            return
        self._draw_segment(self._last, pos, (self._last_p + pressure) / 2)
        self._last, self._last_p = pos, pressure

    def end_stroke(self) -> None:
        self._last = None
        if self._active_tool == Tool.LASER:
            self._overlay.fill(Qt.GlobalColor.transparent)
            self.update()
        self.strokeFinished.emit()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def undo(self) -> None:
        if not self._undo:
            return
        self._strokes, self._stroke_count = self._undo.pop()
        self.update()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def clear(self) -> None:
        if self.is_empty():
            return
        self._undo.append((self._strokes.copy(), self._stroke_count))
        self._strokes.fill(Qt.GlobalColor.transparent)
        self._stroke_count = 0
        self.update()
        self.historyChanged.emit(self.can_undo(), True)

    # --- painting ------------------------------------------------------------
    def _draw_segment(self, a: QPointF, b: QPointF, pressure: float) -> None:
        tool = self._active_tool
        if tool in (Tool.TEXT, Tool.SHAPE):       # bu sürümde arayüz taslağı
            return
        target = self._overlay if tool == Tool.LASER else self._strokes
        p = QPainter(target)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if tool == Tool.ERASER:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            width = float(eraser_diameter(self.base_width))
            color = QColor(0, 0, 0, 255)
        else:
            width = pressure_width(self.base_width, pressure)
            color = QColor(LASER_COLOR) if tool == Tool.LASER else self.color
        if a == b:                                # tek dokunuş: sıfır uzunluklu çizgi çizilmez, nokta bas
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawEllipse(a, width / 2, width / 2)
        else:
            p.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(a, b)
        p.end()
        m = int(width) + 2
        self.update(QRectF(a, b).normalized().toAlignedRect().adjusted(-m, -m, m, m))

    def _ensure_layers(self, logical: QSize) -> None:
        dpr = self.devicePixelRatioF()
        need = QSize(max(1, int(logical.width() * dpr)), max(1, int(logical.height() * dpr)))
        if (self._strokes.isNull() or self._strokes.width() < need.width()
                or self._strokes.height() < need.height()):
            self._strokes = _grown(self._strokes, need, dpr)
            self._overlay = _grown(self._overlay, need, dpr)
        if self._tile.devicePixelRatio() != dpr:
            self._tile = _dot_tile(dpr)

    def resizeEvent(self, e: QResizeEvent) -> None:
        self._ensure_layers(e.size())
        super().resizeEvent(e)

    def paintEvent(self, e: QPaintEvent) -> None:
        p = QPainter(self)
        p.fillRect(e.rect(), QColor(theme.PANEL))
        p.fillRect(e.rect(), QBrush(self._tile))
        p.drawImage(0, 0, self._strokes)
        p.drawImage(0, 0, self._overlay)
        p.end()

    # --- tablet path -----------------------------------------------------------
    def tabletEvent(self, e: QTabletEvent) -> None:
        t = e.type()
        eraser_tip = e.pointerType() == QPointingDevice.PointerType.Eraser
        if t == QEvent.Type.TabletPress:
            if e.button() == Qt.MouseButton.LeftButton:
                self._tablet_down = True
                self.inputSourceChanged.emit("tablet")
                self.begin_stroke(e.position(), e.pressure(), eraser_tip)
        elif t == QEvent.Type.TabletMove:
            self.pressureChanged.emit(e.pressure())
            if self._tablet_down:
                self.extend_stroke(e.position(), e.pressure())
        elif t == QEvent.Type.TabletRelease:
            if self._tablet_down:
                self._tablet_down = False
                self.end_stroke()
        else:
            e.ignore()
            return
        e.accept()      # kabul edilen tablet olayı için Qt fare olayı üretmez

    # --- mouse fallback ---------------------------------------------------------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if self._tablet_down or e.button() != Qt.MouseButton.LeftButton:
            e.ignore(); return
        self._mouse_down = True
        self.inputSourceChanged.emit("mouse")
        self.begin_stroke(e.position(), MOUSE_PRESSURE)
        e.accept()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if not self._mouse_down:
            e.ignore(); return
        self.extend_stroke(e.position(), MOUSE_PRESSURE)
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if not self._mouse_down:
            e.ignore(); return
        self._mouse_down = False
        self.end_stroke()
        e.accept()
