"""Webcam bölgesi: çerçevesiz, tahtanın sağ alt köşesinde. Yeşil perde kalkınca zemin tahta beyazı."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt6.QtWidgets import QLabel, QWidget

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.camera_worker import CameraWorker, FrameSource
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.zone import Zone


class CameraView(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame: QImage | None = None
        self.placeholder_text = "Kamera bekleniyor…"
        self.raw_mode = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Yeşil perdeyi aç/kapat")

    def set_frame(self, img: QImage) -> None:
        self._frame = img
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._frame = None
        self.placeholder_text = text
        self.update()

    def set_raw_mode(self, raw: bool) -> None:
        self.raw_mode = raw
        self.update()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        e.accept()                          # kamera tıklaması tahtaya çizim olarak gitmez

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.raw_mode:
            p.fillRect(self.rect(), QColor(theme.CAM_RAW))
        if self._frame is None:
            # siluet: baş + gövde büstü, tahta zemininde açık gri; alt kenara yaslı, taşmaz
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(theme.DOT))
            cx, base = self.width() / 2, self.height()
            r = min(self.width(), self.height()) * 0.30
            p.drawEllipse(QPointF(cx, base - r * 1.55), r * 0.45, r * 0.45)
            p.drawRoundedRect(QRectF(cx - r, base - r, 2 * r, 2 * r), r, r)
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect().adjusted(8, 34, -8, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                       self.placeholder_text)          # üstteki durum etiketinin altında
        else:
            target = self._frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = (self.width() - target.width()) // 2
            y = self.height() - target.height()               # alt kenara yaslı
            p.drawImage(QRect(x, y, target.width(), target.height()), self._frame)
        p.end()


class WebcamPanel(Zone):
    chromaToggled = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, source_factory: Callable[[], FrameSource],
                 params: ChromaParams, chroma_enabled: bool = True, parent=None):
        super().__init__(parent)
        self._params = params
        self.chroma_enabled = chroma_enabled
        self.has_camera = False
        self.body.setContentsMargins(0, 0, 0, 0)

        self.view = CameraView(self)
        self.view.clicked.connect(self._toggle)
        self.body.addWidget(self.view, 1)

        self.overlay_label = QLabel(self.view)
        self.overlay_label.setFont(theme.font(fam, 9, 600))
        self.overlay_label.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: rgba(28,27,25,170);"
                                         f" border-radius: 6px; padding: 2px 7px;")
        self.overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # İş parçacığı kurucuda oluşturulur; start() sadece başlatır. OpenCvSource open() öncesi kamera açmaz.
        self.worker = CameraWorker(source_factory(), params, chroma_enabled, parent=self)
        self.worker.frameReady.connect(lambda img: self.view.set_frame(img))
        self.worker.opened.connect(self._on_opened)
        self.worker.cameraError.connect(self._on_error)
        self._refresh_overlay()

    def _refresh_overlay(self) -> None:
        mode = "kaldırıldı" if self.chroma_enabled else "ham görüntü"
        self.overlay_label.setText(f"yeşil perde: {mode} · tıkla: aç/kapat")
        self.overlay_label.adjustSize()
        self.overlay_label.move(8, 8)
        self.view.set_raw_mode(not self.chroma_enabled)

    def start(self) -> None:
        if not self.worker.isRunning():
            self.worker.start()

    def shutdown(self) -> None:
        if self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)

    def set_chroma_enabled(self, on: bool) -> None:
        self.chroma_enabled = on
        self.worker.set_chroma_enabled(on)
        self._refresh_overlay()

    def set_params(self, p: ChromaParams) -> None:
        self._params = p
        self.worker.set_params(p)

    def _toggle(self) -> None:
        self.set_chroma_enabled(not self.chroma_enabled)
        self.chromaToggled.emit(self.chroma_enabled)

    def _on_opened(self, _w: int, _h: int) -> None:
        self.has_camera = True

    def _on_error(self, msg: str) -> None:
        self.has_camera = False
        self.view.set_placeholder(f"{msg} · Kamera izni / bağlantı kontrol edin")
