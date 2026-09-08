from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies


class RecordBadge(QWidget):
    ticked = pyqtSignal(int)        # saniye; araç çubuğu da sayar

    def __init__(self, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.seconds = 0
        self.active = False
        self.show_on_board = True     # False: rozet tahtada görünmez (kayda girmesin), zamanlayıcı yine çalışır
        self._fmt = "1920×1080"
        self._fps = 60
        self.setObjectName("recordBadge")
        self.setStyleSheet(f"#recordBadge {{ background: {theme.INK}; border-radius: 12px; }}")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)   # düz QWidget stil zeminini ancak böyle boyar
        row = QHBoxLayout(self); row.setContentsMargins(12, 4, 14, 4); row.setSpacing(8)
        self.dot = QLabel(); self.dot.setFixedSize(10, 10)
        self.dot.setStyleSheet(f"background: {theme.REC_DOT}; border-radius: 5px;")
        self.label = QLabel(); self.label.setFont(theme.font(fam, 11, 600, spacing_pct=106))
        self.label.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: transparent;")
        row.addWidget(self.dot); row.addWidget(self.label)
        self._timer = QTimer(self); self._timer.setInterval(1000); self._timer.timeout.connect(self.tick)
        self._blink = QTimer(self); self._blink.setInterval(600); self._blink.timeout.connect(self._toggle_dot)
        self.hide()

    def set_format(self, width: int, height: int, fps: int) -> None:
        self._fmt, self._fps = f"{width}×{height}", fps
        self._refresh()

    def text(self) -> str:
        return f"KAYIT · {self.seconds // 60:02d}:{self.seconds % 60:02d} · {self._fmt} · {self._fps} fps"

    def start(self) -> None:
        self.seconds, self.active = 0, True
        self._refresh(); self.setVisible(self.show_on_board); self._timer.start(); self._blink.start()
        self.ticked.emit(0)

    def stop(self) -> None:
        self.active, self.seconds = False, 0
        self._timer.stop(); self._blink.stop(); self.dot.setVisible(True); self.hide()

    def tick(self) -> None:
        self.seconds += 1
        self._refresh()
        self.ticked.emit(self.seconds)

    def _toggle_dot(self) -> None:
        self.dot.setVisible(not self.dot.isVisible())

    def _refresh(self) -> None:
        self.label.setText(self.text())
        self.adjustSize()
