"""Çalışma alanı: OBS benzeri taşınabilir/boyutlandırılabilir paneller, marka plakası, kayıt dikdörtgeni.

Normal kullanımda hiçbir çizgi çizilmez; 10px çerçeve, ızgara ve panel kenarları sadece düzen modunda görünür.
"""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies

GRIP = 18   # sağ-alt köşede boyutlandırma tutamağı (px)


class WorkArea(QWidget):
    layoutChanged = pyqtSignal(object)     # Layout dict
    editModeChanged = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self._panels: dict[str, PanelFrame] = {}
        self._layout: lm.Layout = dict(lm.DEFAULT_LAYOUT)
        self.edit_mode = False
        self.maximized: str | None = None
        self._drag: tuple[str, str, QPoint, QRect] | None = None   # key, "move"|"resize", press pos, start geom
        self.setMouseTracking(True)

        self.brand = QLabel("Matematiğin Mantığı", self)
        self.brand.setFont(theme.hand_font(fam, 38, 700))
        self.brand.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: {theme.INK};"
                                 f" border-top-left-radius: 14px; border-top-right-radius: 14px; padding: 6px 34px 10px;")
        self.brand.adjustSize()

        self.badge_slot = QWidget(self)          # Task 13 yerleştirir: RecordBadge
        self.badge_slot.hide()

        self.edit_bar = QWidget(self)
        self.edit_bar.setObjectName("editBar")
        self.edit_bar.setStyleSheet(f"#editBar {{ background: {theme.INK}; border-radius: 8px; }}")
        self.edit_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar = QHBoxLayout(self.edit_bar); bar.setContentsMargins(14, 6, 10, 6); bar.setSpacing(10)
        info = QLabel("DÜZEN MODU · başlıktan sürükle, sağ-alt köşeden boyutlandır, çift tık = büyüt")
        info.setFont(theme.font(fam, 10, 600, spacing_pct=108)); info.setStyleSheet(f"color: {theme.TOOLBAR_MUTED};")
        self.reset_button = QPushButton("Sıfırla"); self.reset_button.setObjectName("pill")
        self.done_button = QPushButton("Bitti"); self.done_button.setObjectName("accent")
        self.reset_button.clicked.connect(self.reset_layout)
        self.done_button.clicked.connect(lambda: self.set_edit_mode(False))
        bar.addWidget(info); bar.addWidget(self.reset_button); bar.addWidget(self.done_button)
        self.edit_bar.hide()

    # --- panels & layout ----------------------------------------------------
    def add_panel(self, key: str, panel: PanelFrame) -> None:
        panel.key = key
        panel.setParent(self)
        panel.headerPressed.connect(lambda pt, p=panel: self._forward_child_press(p, pt))
        panel.headerDoubleClicked.connect(lambda k=key: self._toggle_maximized(k))
        self._panels[key] = panel
        panel.show()
        self.relayout()

    def layout(self) -> lm.Layout:                      # type: ignore[override]
        return dict(self._layout)

    def set_layout(self, layout: lm.Layout) -> None:
        self._layout = {k: lm.clamp(v) for k, v in layout.items() if k in lm.PANEL_KEYS}
        for k in lm.PANEL_KEYS:
            self._layout.setdefault(k, lm.DEFAULT_LAYOUT[k])
        self.relayout()

    def reset_layout(self) -> None:
        self.set_layout(dict(lm.DEFAULT_LAYOUT))
        self.layoutChanged.emit(self.layout())

    def set_maximized(self, key: str | None) -> None:
        self.maximized = key if key in self._panels else None
        self.relayout()

    def _toggle_maximized(self, key: str) -> None:
        self.set_maximized(None if self.maximized == key else key)

    def set_edit_mode(self, on: bool) -> None:
        if on == self.edit_mode:
            return
        self.edit_mode = on
        for panel in self._panels.values():
            panel.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, on)
            panel.set_border_visible(on)          # çizgiler sadece düzen modunda
        self.edit_bar.setVisible(on)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        self.editModeChanged.emit(on)

    def inner_rect(self) -> QRect:
        t, r, b, l = theme.WORK_PADDING
        return QRect(l, t, self.width() - l - r, self.height() - t - b)

    def relayout(self) -> None:
        inner = self.inner_rect()
        for key, panel in self._panels.items():
            if self.maximized is not None:
                panel.setVisible(key == self.maximized)
                if key == self.maximized:
                    panel.setGeometry(inner)
                continue
            panel.setVisible(True)
            x, y, w, h = lm.pixel_rect(self._layout[key], inner.width(), inner.height(), theme.GRID_GAP)
            panel.setGeometry(inner.x() + x, inner.y() + y, w, h)
        self.brand.move((self.width() - self.brand.width()) // 2, self.height() - self.brand.height() - theme.FRAME_INSET)
        self.edit_bar.adjustSize()
        self.edit_bar.move((self.width() - self.edit_bar.width()) // 2, theme.FRAME_INSET + 4)
        self.edit_bar.raise_()
        self.badge_slot.move((self.width() - self.badge_slot.width()) // 2, theme.FRAME_INSET + 4)
        self.badge_slot.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def recording_rect(self) -> tuple[int, int, int, int, float]:
        g = self.mapToGlobal(QPoint(0, 0))
        return g.x(), g.y(), self.width(), self.height(), float(self.devicePixelRatioF())

    # --- edit mode mouse handling ---------------------------------------------
    def _hit(self, pos: QPoint) -> tuple[str, str] | None:
        for key, panel in self._panels.items():
            if not panel.isVisible():
                continue
            geo = panel.geometry()
            if not geo.contains(pos):
                continue
            grip = QRect(geo.right() - GRIP, geo.bottom() - GRIP, GRIP + 1, GRIP + 1)
            if grip.contains(pos):
                return key, "resize"
            header = QRect(geo.x(), geo.y(), geo.width(), panel.header_widget.height() + theme.PANEL_BORDER)
            if header.contains(pos):
                return key, "move"
        return None

    def mousePressEvent(self, e: QMouseEvent):
        if self.edit_mode and e.button() == Qt.MouseButton.LeftButton and self.maximized is None:
            hit = self._hit(e.position().toPoint())
            if hit:
                key, mode = hit
                self._drag = (key, mode, e.position().toPoint(), QRect(self._panels[key].geometry()))
                self._panels[key].raise_()
                self.edit_bar.raise_()
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
        panel = self._panels[key]
        if mode == "move":
            panel.move(geo.topLeft() + d)
        else:
            panel.resize(max(80, geo.width() + d.x()), max(60, geo.height() + d.y()))
        e.accept()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if self._drag is None:
            super().mouseReleaseEvent(e); return
        key, _mode, _start, _geo = self._drag
        self._drag = None
        inner = self.inner_rect()
        g = self._panels[key].geometry()
        self._layout[key] = lm.snap_rect(g.x() - inner.x(), g.y() - inner.y(), g.width(), g.height(),
                                         inner.width(), inner.height(), theme.GRID_GAP)
        self.relayout()
        self.layoutChanged.emit(self.layout())
        e.accept()

    def _forward_child_press(self, panel: PanelFrame, local: QPoint) -> None:
        """PanelFrame.headerPressed -> düzen modunda sürüklemeyi başlat (paneller fareye şeffaf değilse)."""
        if not self.edit_mode or self.maximized is not None:
            return
        pos = panel.mapTo(self, panel.header_widget.mapTo(panel, local))
        self._drag = (panel.key, "move", pos, QRect(panel.geometry()))
        panel.raise_(); self.edit_bar.raise_()

    # --- painting -----------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.PAGE))
        if not self.edit_mode:
            p.end()
            return                                   # normal kullanımda hiçbir çizgi yok
        p.setPen(QPen(QColor(theme.INK), theme.FRAME_INSET))
        half = theme.FRAME_INSET / 2
        p.drawRect(QRectF(half, half, self.width() - theme.FRAME_INSET, self.height() - theme.FRAME_INSET))
        if self.maximized is None:
            inner = self.inner_rect()
            cw, ch = lm.cell_size(inner.width(), inner.height(), theme.GRID_GAP)
            pen = QPen(QColor(theme.ACCENT)); pen.setStyle(Qt.PenStyle.DotLine); p.setPen(pen)
            for c in range(1, lm.GRID_COLS):
                x = inner.x() + round(c * (cw + theme.GRID_GAP) - theme.GRID_GAP / 2)
                p.drawLine(x, inner.top(), x, inner.bottom())
            for r in range(1, lm.GRID_ROWS):
                y = inner.y() + round(r * (ch + theme.GRID_GAP) - theme.GRID_GAP / 2)
                p.drawLine(inner.left(), y, inner.right(), y)
            p.setPen(QPen(QColor(theme.ACCENT), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for panel in self._panels.values():
                geo = panel.geometry()
                p.drawRoundedRect(QRectF(geo).adjusted(1, 1, -1, -1), theme.PANEL_RADIUS, theme.PANEL_RADIUS)
                p.fillRect(QRect(geo.right() - GRIP, geo.bottom() - GRIP, GRIP, GRIP), QColor(theme.ACCENT))
        p.end()
