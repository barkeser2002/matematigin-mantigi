"""Tahta çizim yüzeyi: tablet basıncı, fare geri dönüşü, silgi, lazer (sönen iz), şekil (sürükle),
yazı (tıkla, yaz, Enter), 30 adım geri al."""
from __future__ import annotations

from collections import deque
import random

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap,
                         QPointingDevice, QPolygonF, QResizeEvent, QTabletEvent)
from PyQt6.QtWidgets import QLineEdit, QWidget

from matematigin_mantigi.core.models import Nib, PenSettings, Shape, Tool
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


def text_pixel_size(base_width: int) -> int:
    """Yazı aracının punto büyüklüğü kalınlık kademesinden türer: 1 -> 19 px, 12 -> 52 px."""
    return 16 + int(base_width) * 3


class DrawingCanvas(QWidget):
    strokeStarted = pyqtSignal()
    strokeFinished = pyqtSignal()
    historyChanged = pyqtSignal(bool, bool)     # can_undo, is_empty
    pressureChanged = pyqtSignal(float)
    inputSourceChanged = pyqtSignal(str)        # "tablet" | "mouse"
    MAX_UNDO = 30
    LASER_FADE_MS = 1500                        # lazer izi bu sürede sönerek kaybolur
    show_grid = False                           # düz beyaz tahta; True ise 28px nokta ızgarası

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabletTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.tool = Tool.PEN
        self.shape = Shape.RECT
        self.color = QColor(theme.INK)
        self.base_width = 4
        self._pen_settings: PenSettings | None = None
        self._chalk_color = None
        self._chalk_brush = None
        self._strokes = QImage()
        self._overlay = QImage()
        self._undo: deque[tuple[QImage, int]] = deque(maxlen=self.MAX_UNDO)
        self._stroke_count = 0
        self._tablet_down = False
        self._mouse_down = False
        self._last: QPointF | None = None
        self._raw_last: QPointF | None = None
        self._last_p = MOUSE_PRESSURE
        self._shape_start: QPointF | None = None
        self._active_tool = Tool.PEN
        self._tile = _dot_tile(1.0)
        self._laser_alpha = 1.0
        self._laser_timer = QTimer(self)
        self._laser_timer.setInterval(30)
        self._laser_timer.timeout.connect(self._laser_step)
        self._text_pos: QPointF | None = None
        self.mirror: QWidget | None = None
        self.text_edit = QLineEdit(self)
        self.text_edit.setPlaceholderText("Yaz, Enter ile işle, Esc iptal")
        self.text_edit.hide()
        self.text_edit.returnPressed.connect(self.commit_text)
        self.text_edit.installEventFilter(self)
        self._ensure_layers(QSize(1, 1))

    # --- public state --------------------------------------------------------
    def set_tool(self, t: Tool) -> None:
        if t != Tool.TEXT and self.text_edit.isVisible():
            self.commit_text()
        self.tool = t

    def set_shape(self, s: Shape) -> None: self.shape = s
    def set_color(self, c: QColor) -> None: self.color = QColor(c)
    def set_base_width(self, w: int) -> None: self.base_width = int(w)
    def set_pen_settings(self, settings: PenSettings) -> None:
        self._pen_settings = settings

    def _pen_width(self, pressure: float) -> float:
        settings = self._pen_settings
        if settings is None:
            return pressure_width(self.base_width, pressure)
        low = max(0.1, float(settings.min_width))
        high = max(low, float(settings.max_width))
        curve = max(0, min(100, settings.pressure_curve))
        exponent = 2.0 ** ((curve - 50) / 50)
        value = max(0.0, min(1.0, pressure)) ** exponent
        return (low + (high - low) * value) * max(1, self.base_width) / 4
    def can_undo(self) -> bool: return len(self._undo) > 0
    def is_empty(self) -> bool: return self._stroke_count == 0
    def strokes_image(self) -> QImage: return self._strokes

    def snapshot_image(self) -> QImage:
        out = QImage(self._strokes.size(), QImage.Format.Format_RGB32)
        out.setDevicePixelRatio(self._strokes.devicePixelRatio())
        out.fill(Qt.GlobalColor.white)
        p = QPainter(out); p.drawImage(0, 0, self._strokes)
        if self._text_pos is not None and self.text_edit.text().strip():
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            f = QFont(self.font()); f.setPixelSize(text_pixel_size(self.base_width)); f.setWeight(QFont.Weight(600))
            p.setFont(f); p.setPen(self.color)
            p.drawText(QPointF(self._text_pos.x() + 6, self._text_pos.y() + text_pixel_size(self.base_width) * 0.35),
                       self.text_edit.text().strip())
        p.end()
        return out

    def has_snapshot_content(self) -> bool:
        return not self.is_empty() or (self._text_pos is not None and bool(self.text_edit.text().strip()))

    # --- stroke API (used by tablet, mouse and tests) -------------------------
    def begin_stroke(self, pos: QPointF, pressure: float, eraser_tip: bool = False) -> None:
        self._active_tool = Tool.ERASER if eraser_tip else self.tool
        if self._active_tool in (Tool.PEN, Tool.ERASER):
            self._push_undo()
            self._stroke_count += 1
        elif self._active_tool == Tool.LASER:
            self._laser_timer.stop()
            self._laser_alpha = 1.0
        elif self._active_tool == Tool.SHAPE:
            self._shape_start = pos
        elif self._active_tool == Tool.TEXT:
            self.begin_text(pos)
            return
        self._last, self._raw_last, self._last_p = pos, pos, pressure
        self._draw_segment(pos, pos, pressure)
        self.strokeStarted.emit()

    def extend_stroke(self, pos: QPointF, pressure: float) -> None:
        if self._last is None:
            return
        if self._active_tool == Tool.SHAPE:
            self._preview_shape(pos)
            self._last = pos
            return
        self._raw_last = pos
        if self._active_tool == Tool.PEN and self._pen_settings is not None:
            smoothing = max(0, min(100, self._pen_settings.smoothing)) / 100
            pos = self._last + (pos - self._last) * (1 - smoothing * 0.8)
        self._draw_segment(self._last, pos, (self._last_p + pressure) / 2)
        self._last, self._last_p = pos, pressure

    def end_stroke(self) -> None:
        if (self._active_tool == Tool.PEN and self._last is not None
                and self._raw_last is not None and self._last != self._raw_last):
            self._draw_segment(self._last, self._raw_last, self._last_p)
        if self._active_tool == Tool.SHAPE and self._shape_start is not None and self._last is not None:
            self._overlay.fill(Qt.GlobalColor.transparent)
            self._push_undo()
            self._stroke_count += 1
            p = QPainter(self._strokes)
            self._paint_shape(p, self._shape_start, self._last)
            p.end()
            self._shape_start = None
            self.update()
        self._last = None
        self._raw_last = None
        if self._active_tool == Tool.LASER:
            self._laser_alpha = 1.0
            self._laser_timer.start()                 # iz hemen silinmez, sönerek kaybolur
        self.strokeFinished.emit()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def undo(self) -> None:
        if not self._undo:
            return
        self._strokes, self._stroke_count = self._undo.pop()
        self._ensure_layers(self.size())
        self.update()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def clear(self) -> None:
        if self.is_empty():
            return
        self._push_undo()
        self._strokes.fill(Qt.GlobalColor.transparent)
        self._stroke_count = 0
        self.update()
        self.historyChanged.emit(self.can_undo(), True)

    def reset_board(self) -> None:
        """Yeni soru için mürekkebi, geçici araçları ve soru içi geçmişi sıfırla."""
        self.cancel_text()
        self._tablet_down = self._mouse_down = False
        self._last = self._raw_last = self._shape_start = None
        self._laser_timer.stop()
        self._laser_alpha = 1.0
        self._strokes.fill(Qt.GlobalColor.transparent)
        self._overlay.fill(Qt.GlobalColor.transparent)
        self._stroke_count = 0
        self._undo.clear()
        self.update()
        self.historyChanged.emit(False, True)

    def _push_undo(self) -> None:
        self._undo.append((self._strokes.copy(), self._stroke_count))

    # --- yazı aracı ------------------------------------------------------------
    def begin_text(self, pos: QPointF) -> None:
        """Tıklanan yerde yazı kutusu açar; Enter tahtaya işler, Esc iptal eder."""
        if self.text_edit.isVisible():
            self.commit_text()
        self._text_pos = pos
        px = text_pixel_size(self.base_width)
        f = QFont(self.font()); f.setPixelSize(px); f.setWeight(QFont.Weight(600))
        self.text_edit.setFont(f)
        self.text_edit.setStyleSheet(f"QLineEdit {{ color: {self.color.name()}; background: rgba(255,255,255,230);"
                                     f" border: 1px dashed {theme.MUTED}; padding: 2px 6px; }}")
        self.text_edit.clear()
        self.text_edit.setMinimumWidth(min(480, max(220, self.width() - int(pos.x()) - 8)))
        self.text_edit.adjustSize()
        self.text_edit.move(int(pos.x()), int(pos.y()) - self.text_edit.height() // 2)
        self.text_edit.show(); self.text_edit.raise_(); self.text_edit.setFocus()

    def commit_text(self) -> None:
        text = self.text_edit.text().strip()
        pos = self._text_pos
        self.text_edit.hide(); self.text_edit.clear(); self._text_pos = None
        if not text or pos is None:
            return
        self.draw_text(pos, text)

    def cancel_text(self) -> None:
        self.text_edit.hide(); self.text_edit.clear(); self._text_pos = None

    def draw_text(self, pos: QPointF, text: str) -> None:
        self._push_undo()
        self._stroke_count += 1
        p = QPainter(self._strokes)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        f = QFont(self.font()); f.setPixelSize(text_pixel_size(self.base_width)); f.setWeight(QFont.Weight(600))
        p.setFont(f); p.setPen(self.color)
        p.drawText(QPointF(pos.x() + 6, pos.y() + text_pixel_size(self.base_width) * 0.35), text)   # taban çizgisi ~ tıklanan y
        p.end()
        self.update()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def eventFilter(self, obj, e):
        if obj is self.text_edit and e.type() == QEvent.Type.KeyPress and isinstance(e, QKeyEvent) \
                and e.key() == Qt.Key.Key_Escape:
            self.cancel_text()
            return True
        return super().eventFilter(obj, e)

    # --- şekil aracı ---------------------------------------------------------------
    def _preview_shape(self, pos: QPointF) -> None:
        self._overlay.fill(Qt.GlobalColor.transparent)
        p = QPainter(self._overlay)
        self._paint_shape(p, self._shape_start, pos)
        p.end()
        self.update()

    def _paint_shape(self, p: QPainter, a: QPointF, b: QPointF) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = pressure_width(self.base_width, 0.7)
        p.setPen(QPen(self.color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(a, b).normalized()
        if self.shape == Shape.LINE:
            p.drawLine(a, b)
        elif self.shape == Shape.RECT:
            p.drawRect(rect)
        elif self.shape == Shape.ELLIPSE:
            p.drawEllipse(rect)
        else:  # TRIANGLE: tepe üst-orta, taban alt kenar
            p.drawPolygon(QPolygonF([QPointF(rect.center().x(), rect.top()), rect.bottomRight(), rect.bottomLeft()]))

    # --- painting ------------------------------------------------------------
    def _chalk_texture(self, color: QColor) -> QBrush:
        key = color.rgba()
        if self._chalk_color != key:
            image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            rng = random.Random(31)
            for y in range(32):
                for x in range(32):
                    if rng.random() < .72:
                        image.setPixelColor(x, y, color)
            self._chalk_brush = QBrush(QPixmap.fromImage(image))
            self._chalk_color = key
        return self._chalk_brush

    def _draw_segment(self, a: QPointF, b: QPointF, pressure: float) -> None:
        tool = self._active_tool
        if tool in (Tool.TEXT, Tool.SHAPE, Tool.CLICK):   # yazı kutuyla, şekil bırakınca, tıklama hiç çizmez
            return
        target = self._overlay if tool == Tool.LASER else self._strokes
        p = QPainter(target)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if tool == Tool.ERASER:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            width = float(eraser_diameter(self.base_width))
            color = QColor(0, 0, 0, 255)
        else:
            width = (self._pen_width(pressure) if tool == Tool.PEN
                     else pressure_width(self.base_width, pressure))
            color = QColor(LASER_COLOR) if tool == Tool.LASER else self.color
        nib = self._pen_settings.nib if tool == Tool.PEN and self._pen_settings else Nib.ROUND
        if nib == Nib.FELT:
            width = self._pen_width(.5 + (max(0., min(1., pressure)) - .5) * .5)
            color = QColor(color)
            color.setAlpha(round(color.alpha() * .85))
        brush = self._chalk_texture(color) if nib == Nib.CHALK else QBrush(color)
        if a == b:                                # tek dokunuş: sıfır uzunluklu çizgi çizilmez, nokta bas
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(brush)
            if nib == Nib.FELT:
                p.drawRect(QRectF(a.x() - width / 2, a.y() - width / 2, width, width))
            else:
                p.drawEllipse(a, width / 2, width / 2)
        else:
            cap = Qt.PenCapStyle.FlatCap if nib == Nib.FELT else Qt.PenCapStyle.RoundCap
            p.setPen(QPen(brush, width, Qt.PenStyle.SolidLine, cap, Qt.PenJoinStyle.RoundJoin))
            p.drawLine(a, b)
        p.end()
        m = int(width) + 2
        self.update(QRectF(a, b).normalized().toAlignedRect().adjusted(-m, -m, m, m))

    def _laser_step(self) -> None:
        self._laser_alpha -= self._laser_timer.interval() / self.LASER_FADE_MS
        if self._laser_alpha <= 0:
            self._laser_timer.stop()
            self._laser_alpha = 1.0
            self._overlay.fill(Qt.GlobalColor.transparent)
        self.update()

    def laser_trail_visible(self) -> bool:
        return self._laser_timer.isActive() or self._last is not None and self._active_tool == Tool.LASER

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

    def paint_ink(self, p: QPainter) -> None:
        """Çizgi katmanı + lazer/şekil önizlemesi; tuval veya mürekkep katmanı çağırır."""
        p.drawImage(0, 0, self._strokes)
        p.setOpacity(self._laser_alpha if self._active_tool == Tool.LASER or self._laser_timer.isActive() else 1.0)
        p.drawImage(0, 0, self._overlay)
        p.setOpacity(1.0)

    def set_mirror(self, widget: QWidget | None) -> None:
        """Mürekkep bu widget'ta çizilir (bölgelerin üstünde); tuval sadece zemin boyar."""
        self.mirror = widget

    def update(self, *args) -> None:                          # type: ignore[override]
        super().update(*args)
        m = getattr(self, "mirror", None)
        if m is not None:
            m.update(*args)

    def paintEvent(self, e: QPaintEvent) -> None:
        p = QPainter(self)
        p.fillRect(e.rect(), QColor(theme.PANEL))
        if self.show_grid:
            p.fillRect(e.rect(), QBrush(self._tile))
        if getattr(self, "mirror", None) is None:
            self.paint_ink(p)
        p.end()

    # --- tablet path -----------------------------------------------------------
    def tabletEvent(self, e: QTabletEvent) -> None:
        if self.tool == Tool.CLICK:
            e.ignore(); return
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
        if self._active_tool != Tool.TEXT:
            self.end_stroke()
        e.accept()
