"""Beyaz tahta: çalışma alanının tamamı çizim tuvali; soru, ipucu ve webcam bölgeleri tahtanın üstünde
şeffaf katmanlar. Normal kullanımda hiçbir çizgi yok; çerçeve, ızgara ve bölge sınırları sadece düzen modunda.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.canvas import DrawingCanvas
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.zone import Zone

GRIP = 18   # sağ-alt köşede boyutlandırma tutamağı (px)


class _EditOverlay(QWidget):
    """Düzen modunda çerçeve, ızgara ve bölge sınırlarını en üstte çizer; fareye şeffaftır."""

    def __init__(self, area: "WorkArea"):
        super().__init__(area)
        self.area = area
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.hide()

    def paintEvent(self, _e):
        area = self.area
        p = QPainter(self)
        p.setPen(QPen(QColor(theme.INK), theme.FRAME_INSET))
        half = theme.FRAME_INSET / 2
        p.drawRect(QRectF(half, half, self.width() - theme.FRAME_INSET, self.height() - theme.FRAME_INSET))
        inner = area.inner_rect()
        cw, ch = lm.cell_size(inner.width(), inner.height(), theme.GRID_GAP)
        pen = QPen(QColor(theme.ACCENT)); pen.setStyle(Qt.PenStyle.DotLine); p.setPen(pen)
        for c in range(1, lm.GRID_COLS):
            x = inner.x() + round(c * (cw + theme.GRID_GAP) - theme.GRID_GAP / 2)
            p.drawLine(x, inner.top(), x, inner.bottom())
        for r in range(1, lm.GRID_ROWS):
            y = inner.y() + round(r * (ch + theme.GRID_GAP) - theme.GRID_GAP / 2)
            p.drawLine(inner.left(), y, inner.right(), y)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for zone in area.zones():
            geo = zone.geometry()
            pen = QPen(QColor(theme.ACCENT), 2); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
            p.drawRoundedRect(QRectF(geo).adjusted(1, 1, -1, -1), theme.PANEL_RADIUS, theme.PANEL_RADIUS)
            p.fillRect(QRect(geo.right() - GRIP, geo.bottom() - GRIP, GRIP, GRIP), QColor(theme.ACCENT))
            p.setPen(QColor(theme.ACCENT))
            p.drawText(geo.adjusted(10, 6, -10, -6), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                       zone.key.upper())
        p.end()


class WorkArea(QWidget):
    layoutChanged = pyqtSignal(object)     # Layout dict
    editModeChanged = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self._zones: dict[str, Zone] = {}
        self._layout: lm.Layout = dict(lm.DEFAULT_LAYOUT)
        self.edit_mode = False
        self._drag: tuple[str, str, QPoint, QRect] | None = None   # key, "move"|"resize", press pos, start geom
        self.setMouseTracking(True)

        self.board = DrawingCanvas(self)

        self.status_label = QLabel("", self)
        self.status_label.setFont(theme.font(fam, 10, 500))
        self.status_label.setStyleSheet(f"color: {theme.MUTED}; background: transparent;")
        self.status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.brand = QLabel("Matematiğin Mantığı", self)
        self.brand.setFont(theme.hand_font(fam, 34, 700))
        self.brand.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: {theme.INK};"
                                 f" border-top-left-radius: 14px; border-top-right-radius: 14px; padding: 4px 30px 8px;")
        self.brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.brand.adjustSize()

        self.badge_slot = QWidget(self)          # MainWindow yerleştirir: RecordBadge
        self.badge_slot.hide()

        self.edit_bar = QWidget(self)
        self.edit_bar.setObjectName("editBar")
        self.edit_bar.setStyleSheet(f"#editBar {{ background: {theme.INK}; border-radius: 8px; }}")
        self.edit_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar = QHBoxLayout(self.edit_bar); bar.setContentsMargins(14, 6, 10, 6); bar.setSpacing(10)
        info = QLabel("DÜZEN MODU · bölgeyi sürükle, sağ-alt köşeden boyutlandır")
        info.setFont(theme.font(fam, 10, 600, spacing_pct=108)); info.setStyleSheet(f"color: {theme.TOOLBAR_MUTED};")
        self.reset_button = QPushButton("Sıfırla"); self.reset_button.setObjectName("pill")
        self.done_button = QPushButton("Bitti"); self.done_button.setObjectName("accent")
        self.reset_button.clicked.connect(self.reset_layout)
        self.done_button.clicked.connect(lambda: self.set_edit_mode(False))
        bar.addWidget(info); bar.addWidget(self.reset_button); bar.addWidget(self.done_button)
        self.edit_bar.hide()

        self.overlay = _EditOverlay(self)

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
        return dict(self._layout)

    def set_layout(self, layout: lm.Layout) -> None:
        self._layout = {k: lm.clamp(v) for k, v in layout.items() if k in lm.ZONE_KEYS}
        for k in lm.ZONE_KEYS:
            self._layout.setdefault(k, lm.DEFAULT_LAYOUT[k])
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
        self.overlay.setVisible(on)
        self.edit_bar.setVisible(on)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.relayout()
        self.editModeChanged.emit(on)

    def inner_rect(self) -> QRect:
        t, r, b, l = theme.WORK_PADDING
        return QRect(l, t, self.width() - l - r, self.height() - t - b)

    def relayout(self) -> None:
        self.board.setGeometry(self.rect())
        self.board.lower()
        inner = self.inner_rect()
        for key, zone in self._zones.items():
            x, y, w, h = lm.pixel_rect(self._layout[key], inner.width(), inner.height(), theme.GRID_GAP)
            zone.setGeometry(inner.x() + x, inner.y() + y, w, h)
            zone.raise_()
        self.status_label.adjustSize()
        self.status_label.move(16, self.height() - self.status_label.height() - 10)
        self.status_label.raise_()
        self.brand.move((self.width() - self.brand.width()) // 2, self.height() - self.brand.height())
        self.brand.raise_()
        top = 4
        self.badge_slot.move((self.width() - self.badge_slot.width()) // 2, top)
        self.badge_slot.raise_()
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()
        self.edit_bar.adjustSize()
        bar_y = top + (self.badge_slot.height() + 6 if self.badge_slot.isVisible() else 0)   # rozetin altına
        self.edit_bar.move((self.width() - self.edit_bar.width()) // 2, bar_y)
        self.edit_bar.raise_()
        self.overlay.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def recording_rect(self) -> tuple[int, int, int, int, float]:
        g = self.mapToGlobal(QPoint(0, 0))
        return g.x(), g.y(), self.width(), self.height(), float(self.devicePixelRatioF())

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.adjustSize()

    # --- edit mode mouse handling ---------------------------------------------
    def _hit(self, pos: QPoint) -> tuple[str, str] | None:
        for key in reversed(list(self._zones)):           # üstteki bölge önce
            geo = self._zones[key].geometry()
            if not geo.contains(pos):
                continue
            grip = QRect(geo.right() - GRIP, geo.bottom() - GRIP, GRIP + 1, GRIP + 1)
            return key, ("resize" if grip.contains(pos) else "move")
        return None

    def mousePressEvent(self, e: QMouseEvent):
        if self.edit_mode and e.button() == Qt.MouseButton.LeftButton:
            hit = self._hit(e.position().toPoint())
            if hit:
                key, mode = hit
                self._drag = (key, mode, e.position().toPoint(), QRect(self._zones[key].geometry()))
                e.accept(); return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.position().toPoint()
        if self._drag is None:
            if self.edit_mode:
                hit = self._hit(pos)
                self.setCursor(Qt.CursorShape.SizeFDiagCursor if hit and hit[1] == "resize"
                               else Qt.CursorShape.SizeAllCursor if hit else Qt.CursorShape.ArrowCursor)
            super().mouseMoveEvent(e); return
        key, mode, start, geo = self._drag
        d = pos - start
        zone = self._zones[key]
        if mode == "move":
            zone.move(geo.topLeft() + d)
        else:
            zone.resize(max(80, geo.width() + d.x()), max(60, geo.height() + d.y()))
        self.overlay.update()
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._drag is None:
            super().mouseReleaseEvent(e); return
        key, _mode, _start, _geo = self._drag
        self._drag = None
        inner = self.inner_rect()
        g = self._zones[key].geometry()
        self._layout[key] = lm.snap_rect(g.x() - inner.x(), g.y() - inner.y(), g.width(), g.height(),
                                         inner.width(), inner.height(), theme.GRID_GAP)
        self.relayout()
        self.layoutChanged.emit(self.layout())
        e.accept()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.PANEL))     # tahta beyaz; tuval üstünü kaplar
        p.end()
