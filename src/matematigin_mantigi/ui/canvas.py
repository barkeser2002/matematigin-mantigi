"""Tahta çizim yüzeyi: tablet basıncı, fare geri dönüşü, silgi, lazer (sönen iz), şekil (sürükle),
yazı (tıkla, yaz, Enter), 30 adım geri al."""
from __future__ import annotations

from collections import deque
import random
import math

from PyQt6.QtCore import QEvent, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QImage, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap,
                         QPointingDevice, QPolygonF, QResizeEvent, QTabletEvent)
from PyQt6.QtWidgets import QLineEdit, QWidget

from matematigin_mantigi.core.models import LineStyle, Nib, PenSettings, Shape, Tool
from matematigin_mantigi.core.settings import ERASER_MIN, ERASER_MAX
from matematigin_mantigi.core.shapes import CLOSED_SHAPES, constrain
from matematigin_mantigi.core.stroke import LASER_COLOR, MOUSE_PRESSURE, eraser_diameter, pressure_width
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.shape_paint import fill_color, paint_shape


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
    effectiveToolChanged = pyqtSignal()
    inputSourceChanged = pyqtSignal(str)        # "tablet" | "mouse"
    MAX_UNDO = 30
    LASER_FADE_MS = 1500                        # lazer izi bu sürede sönerek kaybolur
    show_grid = False                           # düz beyaz tahta; True ise 28px nokta ızgarası

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabletTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.tool = Tool.PEN
        self._eraser_tip = False
        self.cursor_pressure = MOUSE_PRESSURE
        self.shape = Shape.RECT
        self.fill_shapes = False                    # kapalı şekiller yarı saydam dolgulu mu (kalıcı, menüden)
        self._shape_mods = Qt.KeyboardModifier.NoModifier    # son sürükleme anındaki Shift/Alt
        self.color = QColor(theme.INK)
        self.base_width = 4
        self.eraser_size = eraser_diameter(self.base_width)
        self._pen_settings: PenSettings | None = None
        self._chalk_color = None
        self._chalk_brush = None
        self._strokes = QImage()
        self._overlay = QImage()
        self._undo: deque[tuple[QImage, int]] = deque(maxlen=self.MAX_UNDO)
        self._redo: deque[tuple[QImage, int]] = deque(maxlen=self.MAX_UNDO)
        self._stroke_before = QImage()
        self._stroke_path = QPainterPath()
        self._stroke_start: QPointF | None = None
        self._straight = False
        self._hold_corrected = False
        self._hold_anchor: QPointF | None = None
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._hold_timer.setInterval(600)
        self._hold_timer.timeout.connect(self._correct_held_stroke)
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
        if t != self.tool:
            self._tablet_down = self._mouse_down = False
            if self._last is not None:
                self.end_stroke()
        if t != Tool.TEXT and self.text_edit.isVisible():
            self.commit_text()
        self.tool = t
        self._eraser_tip = False
        self.effectiveToolChanged.emit()

    @property
    def effective_tool(self) -> Tool:
        return Tool.ERASER if self._eraser_tip else self.tool

    def _set_eraser_tip(self, erasing: bool) -> None:
        if self._eraser_tip != erasing:
            if self._last is not None:
                self.end_stroke()
            self._tablet_down = self._mouse_down = False
            self._eraser_tip = erasing
            self.effectiveToolChanged.emit()

    def cursor_width(self) -> float:
        pressure = self.cursor_pressure
        if self._pen_settings is not None and self._pen_settings.nib == Nib.FELT:
            pressure = .5 + (max(0., min(1., pressure)) - .5) * .5
        width = self._pen_width(pressure)
        return max(12., width * 4) if self._pen_settings and self._pen_settings.nib == Nib.HIGHLIGHTER else width

    def set_shape(self, s: Shape) -> None: self.shape = s
    def set_shape_fill(self, on: bool) -> None: self.fill_shapes = bool(on)
    def set_color(self, c: QColor) -> None: self.color = QColor(c)
    def set_base_width(self, w: int) -> None: self.base_width = int(w)
    def set_eraser_size(self, size: int) -> None:
        self.eraser_size = max(ERASER_MIN, min(ERASER_MAX, int(size)))

    def set_pen_settings(self, settings: PenSettings) -> None:
        self._pen_settings = settings
        if not settings.hold_to_straight:
            self._hold_timer.stop()

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
    def begin_stroke(self, pos: QPointF, pressure: float, eraser_tip: bool = False,
                     modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        self._hold_timer.stop()
        self._hold_corrected = False
        self._hold_anchor = QPointF(pos)
        self._set_eraser_tip(eraser_tip)
        self._active_tool = self.effective_tool
        if self._active_tool in (Tool.PEN, Tool.ERASER):
            self._push_undo()
            self._stroke_count += 1
        elif self._active_tool == Tool.LASER:
            self._laser_timer.stop()
            self._laser_alpha = 1.0
        elif self._active_tool == Tool.SHAPE:
            self._shape_start = pos
            self._shape_mods = modifiers
        elif self._active_tool == Tool.TEXT:
            self.begin_text(pos)
            return
        self._stroke_before = self._strokes.copy()
        self._stroke_start = QPointF(pos)
        self._straight = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        self._stroke_path = QPainterPath(pos)
        self._last, self._raw_last, self._last_p = pos, pos, pressure
        self._draw_segment(pos, pos, pressure)
        self.strokeStarted.emit()

    def extend_stroke(self, pos: QPointF, pressure: float,
                      modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        if self._last is None:
            return
        if self._active_tool == Tool.SHAPE:
            self._shape_mods = modifiers
            self._preview_shape(pos)
            self._last = pos
            return
        if self._active_tool == Tool.PEN and (self._straight or modifiers & Qt.KeyboardModifier.ShiftModifier):
            self._straight = True
            delta = pos - self._stroke_start
            angle = round(math.atan2(delta.y(), delta.x()) / (math.pi / 12)) * (math.pi / 12)
            length = math.hypot(delta.x(), delta.y())
            pos = self._stroke_start + QPointF(math.cos(angle) * length, math.sin(angle) * length)
            self._render_straight(pos, pressure)
            return
        if self._active_tool == Tool.PEN and self._hold_corrected:
            self._render_straight(pos, pressure)
            return
        if (self._active_tool == Tool.PEN and (self._pen_settings is None or self._pen_settings.hold_to_straight)
                and (self._hold_anchor is None or math.hypot(pos.x() - self._hold_anchor.x(),
                                                            pos.y() - self._hold_anchor.y()) > 2)):
            self._hold_anchor = QPointF(pos)
            self._hold_timer.start()
        self._raw_last = pos
        if self._active_tool == Tool.PEN and self._pen_settings is not None:
            smoothing = max(0, min(100, self._pen_settings.smoothing)) / 100
            pos = self._last + (pos - self._last) * (1 - smoothing * 0.8)
        self._draw_segment(self._last, pos, (self._last_p + pressure) / 2)
        self._last, self._last_p = pos, pressure

    def _correct_held_stroke(self) -> None:
        if (self._last is None or self._raw_last is None or self._active_tool != Tool.PEN
                or self._pen_settings is not None and not self._pen_settings.hold_to_straight):
            return
        delta = self._raw_last - self._stroke_start
        if math.hypot(delta.x(), delta.y()) < 10:
            return
        self._hold_corrected = True
        self._render_straight(self._raw_last, self._last_p)

    def _render_straight(self, pos: QPointF, pressure: float) -> None:
        self._strokes = self._stroke_before.copy()
        self._stroke_path = QPainterPath(self._stroke_start)
        self._draw_segment(self._stroke_start, pos, pressure)
        self._last = self._raw_last = QPointF(pos)
        self._last_p = pressure
        self.update()

    def end_stroke(self) -> None:
        self._hold_timer.stop()
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
        self._hold_timer.stop()
        self._last = self._raw_last = None
        if not self._undo:
            return
        self._redo.append((self._strokes.copy(), self._stroke_count))
        self._strokes, self._stroke_count = self._undo.pop()
        self._ensure_layers(self.size())
        self.update()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def redo(self) -> None:
        self._hold_timer.stop()
        self._last = self._raw_last = None
        if not self._redo:
            return
        self._undo.append((self._strokes.copy(), self._stroke_count))
        self._strokes, self._stroke_count = self._redo.pop()
        self.update()
        self.historyChanged.emit(self.can_undo(), self.is_empty())

    def clear(self) -> None:
        self._hold_timer.stop()
        self._last = self._raw_last = None
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
        self._hold_timer.stop()
        self._tablet_down = self._mouse_down = False
        self._last = self._raw_last = self._shape_start = None
        self._laser_timer.stop()
        self._laser_alpha = 1.0
        self._strokes.fill(Qt.GlobalColor.transparent)
        self._overlay.fill(Qt.GlobalColor.transparent)
        self._stroke_count = 0
        self._undo.clear()
        self._redo.clear()
        self.update()
        self.historyChanged.emit(False, True)

    def _push_undo(self) -> None:
        self._redo.clear()
        self._undo.append((self._strokes.copy(), self._stroke_count))

    # --- yazı aracı ------------------------------------------------------------
    def begin_text(self, pos: QPointF) -> None:
        """Tıklanan yerde yazı kutusu açar; Enter tahtaya işler, Esc iptal eder."""
        if self.text_edit.isVisible():
            self.commit_text()
        self._text_pos = pos
        # Tuval altta kalır; editör kartlar ve kamera ile aynı yığında olmalı.
        host = self.parentWidget() if self.mirror is not None else self
        if self.text_edit.parentWidget() is not host:
            self.text_edit.setParent(host)
        px = text_pixel_size(self.base_width)
        f = QFont(self.font()); f.setPixelSize(px); f.setWeight(QFont.Weight(600))
        self.text_edit.setFont(f)
        self.text_edit.setStyleSheet(f"QLineEdit {{ color: {self.color.name()}; background: rgba(255,255,255,230);"
                                     f" border: 1px dashed {theme.MUTED}; padding: 2px 6px; }}")
        self.text_edit.clear()
        self.text_edit.setMinimumWidth(min(480, max(220, self.width() - int(pos.x()) - 8)))
        self.text_edit.adjustSize()
        self._position_text_editor()
        self.text_edit.show(); self.text_edit.raise_(); self.text_edit.setFocus()

    def _position_text_editor(self) -> None:
        if self._text_pos is None:
            return
        anchor = self.mapTo(self.text_edit.parentWidget(), self._text_pos.toPoint())
        self.text_edit.move(anchor.x(), anchor.y() - self.text_edit.height() // 2)
        self.text_edit.raise_()

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

    def _line_style(self):
        style = self._pen_settings.line_style if self._pen_settings else LineStyle.SOLID
        return {LineStyle.SOLID: Qt.PenStyle.SolidLine, LineStyle.DASHED: Qt.PenStyle.DashLine,
                LineStyle.DOTTED: Qt.PenStyle.DotLine}[style]

    def _paint_shape(self, p: QPainter, a: QPointF, b: QPointF) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = pressure_width(self.base_width, 0.7)
        p.setPen(QPen(self.color, width, self._line_style(), Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        mods = self._shape_mods
        start, end = constrain(self.shape, (a.x(), a.y()), (b.x(), b.y()),
                               shift=bool(mods & Qt.KeyboardModifier.ShiftModifier),
                               alt=bool(mods & Qt.KeyboardModifier.AltModifier))
        fill = fill_color(self.color) if self.fill_shapes and self.shape in CLOSED_SHAPES else None
        paint_shape(p, self.shape, QPointF(*start), QPointF(*end), fill)

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
        nib = self._pen_settings.nib if tool == Tool.PEN and self._pen_settings else Nib.ROUND
        patterned = tool == Tool.PEN and self._line_style() != Qt.PenStyle.SolidLine
        if nib == Nib.HIGHLIGHTER or patterned:
            self._stroke_path.lineTo(b)
            self._strokes = self._stroke_before.copy()
        target = self._overlay if tool == Tool.LASER else self._strokes
        p = QPainter(target)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if tool == Tool.ERASER:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            width = float(self.eraser_size)
            color = QColor(0, 0, 0, 255)
        else:
            width = (self._pen_width(pressure) if tool == Tool.PEN
                     else pressure_width(self.base_width, pressure))
            color = QColor(LASER_COLOR) if tool == Tool.LASER else self.color
        if nib == Nib.HIGHLIGHTER:
            width = max(12., self._pen_width(.5) * 4)
            color = QColor(color)
            color.setAlpha(round(color.alpha() * .38))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        if nib == Nib.FELT:
            width = self._pen_width(.5 + (max(0., min(1., pressure)) - .5) * .5)
            color = QColor(color)
            color.setAlpha(round(color.alpha() * .85))
        brush = self._chalk_texture(color) if nib == Nib.CHALK else QBrush(color)
        if nib == Nib.HIGHLIGHTER or patterned:
            cap = Qt.PenCapStyle.FlatCap if nib in (Nib.FELT, Nib.HIGHLIGHTER) else Qt.PenCapStyle.RoundCap
            p.setPen(QPen(brush, width, self._line_style(), cap, Qt.PenJoinStyle.BevelJoin))
            if self._stroke_path.length() > 0:
                p.drawPath(self._stroke_path)
            else:
                p.fillRect(QRectF(a.x() - width / 2, a.y() - width / 2, width, width), brush)
        elif a == b:                                # tek dokunuş: sıfır uzunluklu çizgi çizilmez, nokta bas
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
        if nib == Nib.HIGHLIGHTER or patterned:
            self.update()
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
        dpr = self.devicePixelRatioF()
        need = QSize(max(1, int(e.size().width() * dpr)), max(1, int(e.size().height() * dpr)))
        if self._strokes.size() != need or self._strokes.devicePixelRatio() != dpr:
            old_size = self._strokes.deviceIndependentSize()
            for name in ("_last", "_raw_last", "_shape_start", "_text_pos", "_stroke_start", "_hold_anchor"):
                point = getattr(self, name)
                if point is not None:
                    setattr(self, name, QPointF(point.x() * e.size().width() / old_size.width(),
                                               point.y() * e.size().height() / old_size.height()))

            def scaled(image: QImage) -> QImage:
                out = image.scaled(need, Qt.AspectRatioMode.IgnoreAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                out.setDevicePixelRatio(dpr)
                return out

            self._strokes = scaled(self._strokes)
            self._overlay = scaled(self._overlay)
            self._undo = deque(((scaled(image), count) for image, count in self._undo), maxlen=self.MAX_UNDO)
            self._redo = deque(((scaled(image), count) for image, count in self._redo), maxlen=self.MAX_UNDO)
            if not self._stroke_before.isNull():
                from PyQt6.QtGui import QTransform
                transform = QTransform.fromScale(e.size().width() / old_size.width(),
                                                 e.size().height() / old_size.height())
                self._stroke_path = transform.map(self._stroke_path)
                self._stroke_before = scaled(self._stroke_before)
        self._ensure_layers(e.size())
        if self._text_pos is not None:
            # Ebeveyn yerleşimi kardeş katmanları bundan sonra yükseltebilir.
            QTimer.singleShot(0, self._position_text_editor)
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
        self.cursor_pressure = e.pressure()
        self._set_eraser_tip(eraser_tip)
        self.pressureChanged.emit(e.pressure())
        if t == QEvent.Type.TabletPress:
            if e.button() == Qt.MouseButton.LeftButton:
                self._tablet_down = True
                self.inputSourceChanged.emit("tablet")
                self.begin_stroke(e.position(), e.pressure(), eraser_tip, e.modifiers())
        elif t == QEvent.Type.TabletMove:
            if self._tablet_down:
                if e.buttons() & Qt.MouseButton.LeftButton:
                    self.extend_stroke(e.position(), e.pressure(), e.modifiers())
                else:
                    self._tablet_down = False
                    self.end_stroke()
        elif t == QEvent.Type.TabletRelease:
            if self._tablet_down and not (e.buttons() & Qt.MouseButton.LeftButton):
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
        self._set_eraser_tip(False)
        self.cursor_pressure = MOUSE_PRESSURE
        self.pressureChanged.emit(MOUSE_PRESSURE)
        self._mouse_down = True
        self.inputSourceChanged.emit("mouse")
        self.begin_stroke(e.position(), MOUSE_PRESSURE, modifiers=e.modifiers())
        e.accept()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if not self._mouse_down:
            e.ignore(); return
        self.extend_stroke(e.position(), MOUSE_PRESSURE, e.modifiers())
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if not self._mouse_down:
            e.ignore(); return
        self._mouse_down = False
        if self._active_tool != Tool.TEXT:
            self.end_stroke()
        e.accept()
