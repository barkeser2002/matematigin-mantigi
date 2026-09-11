"""Tahta üstünde şeffaf bölge. Çocuk bileşenlerin yakalamadığı fare/tablet olayları tahtaya iletilir,
böylece soru metninin üstüne de çizilebilir."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QTabletEvent
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget


class Zone(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.key = ""
        self.board: QWidget | None = None
        self._click_through = False
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setTabletTracking(True)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 14, 18, 14)
        self.body.setSpacing(10)

    def set_board(self, board: QWidget | None) -> None:
        self.board = board

    # --- tıklama geçirgenliği --------------------------------------------------
    def set_click_through(self, on: bool) -> None:
        """on: çizim aracı aktif; kart, düğme, kamera gibi çocuklar fareye şeffaf olur, her basış tahtaya gider.
        off: 'Tıkla' aracı; çocuklar normal tıklanır."""
        self._click_through = on
        self._apply_click_through()

    def _apply_click_through(self) -> None:
        on = getattr(self, "_click_through", False)
        for w in self.findChildren(QWidget):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, on)

    # --- olay iletimi ---------------------------------------------------------
    def _to_board(self, pos: QPointF) -> QPointF:
        assert self.board is not None
        return QPointF(self.board.mapFromGlobal(self.mapToGlobal(pos.toPoint())))

    def _forward_mouse(self, e: QMouseEvent) -> None:
        if self.board is None:
            e.ignore()
            return
        ne = QMouseEvent(e.type(), self._to_board(e.position()), e.globalPosition(),
                         e.button(), e.buttons(), e.modifiers())
        QApplication.sendEvent(self.board, ne)
        e.setAccepted(ne.isAccepted())

    def mousePressEvent(self, e: QMouseEvent) -> None:
        self._forward_mouse(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        self._forward_mouse(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._forward_mouse(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        self._forward_mouse(e)

    def tabletEvent(self, e: QTabletEvent) -> None:
        if self.board is None or not self._click_through:
            e.ignore()      # 'Tıkla' modunda kalem olayı yutulmaz; Qt fare olayı üretir, kart tıklanır
            return
        ne = QTabletEvent(e.type(), e.pointingDevice(), self._to_board(e.position()), e.globalPosition(),
                          e.pressure(), e.xTilt(), e.yTilt(), e.tangentialPressure(), e.rotation(), e.z(),
                          e.modifiers(), e.button(), e.buttons())
        QApplication.sendEvent(self.board, ne)
        e.setAccepted(ne.isAccepted())
