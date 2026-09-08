"""Webcam bölgesi: çerçevesiz, tahtanın sağ alt köşesinde. Yeşil perde kalkınca zemin tahta beyazı."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QRect, Qt, pyqtSignal
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
        self.setToolTip("Yeşil perde ayarı: ⚙ Ayarlar")

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
        e.ignore()                          # tıklama perdeyi değiştirmez (Ayarlar'dan); olay tahtaya iletilir

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._frame is None:
            # kamera yokken çizim yok; sadece küçük gri durum yazısı (tahta temiz kalır)
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect().adjusted(8, 34, -8, -8), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                       | Qt.TextFlag.TextWordWrap, self.placeholder_text)
        else:
            target = self._frame.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x = (self.width() - target.width()) // 2
            y = self.height() - target.height()               # alt kenara yaslı
            p.drawImage(QRect(x, y, target.width(), target.height()), self._frame)
        p.end()


class WebcamPanel(Zone):
    chromaToggled = pyqtSignal(bool)

    def __init__(self, fam: FontFamilies, source_factory: Callable[[], FrameSource],
                 params: ChromaParams, chroma_enabled: bool = True, parent=None, open_retries: int = 0):
        self.open_retries = open_retries          # kamera açılmazsa (izin bekleniyor) 2 sn arayla yeniden deneme
        super().__init__(parent)
        self._params = params
        self.chroma_enabled = chroma_enabled
        self.has_camera = False
        self.body.setContentsMargins(0, 0, 0, 0)

        self.view = CameraView(self)
        self.body.addWidget(self.view, 1)

        self.overlay_label = QLabel(self.view)
        self.overlay_label.setFont(theme.font(fam, 9, 600))
        self.overlay_label.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: rgba(28,27,25,170);"
                                         f" border-radius: 6px; padding: 2px 7px;")
        self.overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # İş parçacığı kurucuda oluşturulur; start() sadece başlatır. OpenCvSource open() öncesi kamera açmaz.
        self._auto_key = True
        self.worker = self._make_worker(source_factory)
        self._refresh_overlay()

    def _make_worker(self, source_factory: Callable[[], FrameSource]) -> CameraWorker:
        w = CameraWorker(source_factory(), self._params, self.chroma_enabled, auto_key=self._auto_key, parent=self,
                         open_retries=self.open_retries)
        w.frameReady.connect(lambda img: self.view.set_frame(img))
        w.opened.connect(self._on_opened)
        w.cameraError.connect(self._on_error)
        return w

    def set_source_factory(self, source_factory: Callable[[], FrameSource]) -> None:
        """Kamera değişimi: eski iş parçacığı durur, yenisi aynı ayarlarla başlar."""
        was_running = self.worker.isRunning()
        self.shutdown()
        self.worker.deleteLater()
        self.has_camera = False
        self.view.set_placeholder("Kamera bekleniyor…")
        self.worker = self._make_worker(source_factory)
        if was_running:
            self.worker.start()

    def _refresh_overlay(self) -> None:
        mode = "kaldırıldı" if self.chroma_enabled else "ham görüntü"
        self.overlay_label.setText(f"yeşil perde: {mode}")
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

    def set_auto_key(self, on: bool) -> None:
        self._auto_key = on
        self.worker.set_auto_key(on)

    def _toggle(self) -> None:
        self.set_chroma_enabled(not self.chroma_enabled)
        self.chromaToggled.emit(self.chroma_enabled)

    def _on_opened(self, _w: int, _h: int) -> None:
        self.has_camera = True

    def _on_error(self, msg: str) -> None:
        self.has_camera = False
        self.view.set_placeholder(f"{msg} · Kamera izni / bağlantı kontrol edin")
