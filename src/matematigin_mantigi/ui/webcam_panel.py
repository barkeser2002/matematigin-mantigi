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
    frameReady = pyqtSignal(QImage)
    placeholderChanged = pyqtSignal(str)

    def _set_placeholder(self, text: str) -> None:
        self.view.set_placeholder(text)
        self.placeholderChanged.emit(text)

    MAX_PENDING_WORKERS = 2   # durdurulamamış (takılı) worker üst sınırı; doluyken start() yeni iş parçacığı açmaz

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

        self.fam = fam
        self.overlay_label = QLabel(self.view)
        self.overlay_label.setFont(theme.font(fam, 9, 600))
        self.overlay_label.setStyleSheet(f"color: {theme.PANEL_SOFT}; background: rgba(28,27,25,170);"
                                         f" border-radius: 6px; padding: 2px 7px;")
        self.overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # İş parçacığı kurucuda oluşturulur; start() sadece başlatır. OpenCvSource open() öncesi kamera açmaz.
        self._auto_key = True
        self._source_factory = source_factory      # start()'ın winding-down durumunda taze worker kurabilmesi için
        self._stop_requested = False                # shutdown() çağrıldı ama iş parçacığı henüz bitmedi mi (bkz. start())
        self._pending_workers: list[CameraWorker] = []   # emekli edilmiş ama hâlâ çalışan (durdurulamamış) worker'lar
        # DEĞİŞMEZ: self.worker HER ZAMAN yaşayan, geçerli bir nesnedir. Emekli edilen worker asla burada
        # kalmaz (emeklilik hemen ardından taze bir worker kurar) -- aksi hâlde emeklinin finished sinyali
        # onu sildiğinde start()/shutdown()/set_source_factory() "wrapped C/C++ object ... has been deleted"
        # ile patlardı (kapanışta MainWindow.closeEvent dahil; review'da 3/3 üretildi).
        self.worker = self._make_worker(source_factory)
        self._refresh_overlay()

    def _make_worker(self, source_factory: Callable[[], FrameSource]) -> CameraWorker:
        w = CameraWorker(source_factory(), self._params, self.chroma_enabled, auto_key=self._auto_key, parent=self,
                         open_retries=self.open_retries)
        w.frameReady.connect(self._on_frame)
        w.opened.connect(self._on_opened)
        w.cameraError.connect(self._on_error)
        return w

    def _on_frame(self, img: QImage) -> None:
        self.view.set_frame(img)
        self.frameReady.emit(img)

    def set_source_factory(self, source_factory: Callable[[], FrameSource]) -> None:
        """Kamera değişimi: eski iş parçacığı durur, yenisi aynı ayarlarla başlar."""
        was_running = self.worker.isRunning()
        self.shutdown()
        self._retire_worker(self.worker)
        self._source_factory = source_factory
        self.worker = self._make_worker(source_factory)      # DEĞİŞMEZ: emekli worker self.worker'da kalmaz
        self._stop_requested = False               # taze worker: winding-down bayrağı onunla ilgili değil
        self.has_camera = False
        # Panel BOŞTAYKEN (was_running False -- ör. bir önceki start() üst sınıra takıldığı için worker hiç
        # başlatılmamışsa) start() çağrılmaz; koşulsuz "bekleniyor" yazmak üst sınırda YANILTICI olurdu
        # (takılı kamera sürerken Ayarlar'dan kamera değiştirmek 'yanıt vermiyor'u siliyordu -- review bulgusu).
        self._set_placeholder("Kamera yanıt vermiyor" if self._at_pending_cap() else "Kamera bekleniyor…")
        if was_running:
            self.start()                 # üst sınır + "yanıt vermiyor" göstergesi tek yerde: start()

    def _reclaim_worker(self, worker: CameraWorker) -> None:
        """Emekli `worker` artık çalışmıyor: listeden ÇIKAR ve sil -- bu ikisi hep birlikte.

        Silmeyi worker'ın kendi `finished` sinyaline ertelemek ZORUNLU: hâlâ çalışan bir iş
        parçacığında `deleteLater()`'ı doğrudan çağırmak GUI iş parçacığını gerçek bir KİLİTLENMEYE
        sokar (elle doğrulandı, bkz. önceki review notları). Listeden çıkarmak da aynı ölçüde zorunlu:
        aksi hâlde liste SİLİNMİŞ bir C++ nesnesi tutar ve ona sonradan dokunmak (isRunning())
        "wrapped C/C++ object ... has been deleted" ile patlar -- bu kural sayesinde `_pending_workers`
        üyeleri HER ZAMAN yaşayan nesnelerdir. Hem doğrudan hem `finished` sinyalinden çağrılabilir;
        ikinci çağrı (nesne o sırada silinmiş olabilir) listede bulamayıp hemen döner."""
        if not any(w is worker for w in self._pending_workers):
            return
        self._pending_workers = [w for w in self._pending_workers if w is not worker]
        worker.deleteLater()

    def _live_pending_count(self) -> int:
        """Emeklilerden hâlâ ÇALIŞAN (durdurulamamış) olanların sayısı. Bitmiş olanları bu arada geri
        alır: `finished` kuyruğa alınan bir sinyaldir, henüz işlenmemiş olabilir."""
        for w in list(self._pending_workers):
            if not w.isRunning():
                self._reclaim_worker(w)
        return len(self._pending_workers)

    def _at_pending_cap(self) -> bool:
        """Üst sınır dolu mu: yeni iş parçacığı AÇILAMAZ, 'Kamera yanıt vermiyor' gösterilir."""
        return self._live_pending_count() >= self.MAX_PENDING_WORKERS

    def _retire_worker(self, worker: CameraWorker) -> None:
        """`worker`ı emekliye ayırır. Çağıranın hemen ardından self.worker'ı YENİLEMESİ zorunludur.

        ÖNCE sinyallerini (frameReady/opened/cameraError) koparır: aksi hâlde stop() sonrası hâlâ
        işlenmekte olan (in-flight) bir read() dönünce worker tek bir GEÇ kare/hata daha yayar -- bu,
        YENİ worker akmaya başladıktan SONRA bile aynı self.view'i etkileyip görünümü kısaca eskiye
        döndürebilir (kare) ya da paneli yanlışlıkla kamerasız duruma düşürebilir (hata) -- review'da
        350ms gecikmeli/hızlı iki sahte kamerayla ölçüldü.

        Sonra silinmeyi `finished`e bağlar (bkz. _reclaim_worker). Zaten çalışmıyorsa (bitmiş ya da hiç
        başlatılmamış -- üst sınırdayken kurulan worker gibi) hemen geri alınır; `finished` ile arasındaki
        yarışı da bu kapatır.

        `read()` GERÇEKTEN hiç dönmezse (yavaş değil, tamamen takılı bir sürücü) `finished` de asla
        ateşlenmez: worker `_pending_workers`te kalır. Sınırsız birikmesini start() engeller -- üst
        sınır doluyken yeni iş parçacığı AÇILMAZ, dolayısıyla emekli edilecek yeni bir çalışan worker
        da doğmaz (bkz. start())."""
        worker.frameReady.disconnect()
        worker.opened.disconnect()
        worker.cameraError.disconnect()
        self._pending_workers.append(worker)
        worker.finished.connect(lambda: self._reclaim_worker(worker))
        if not worker.isRunning():
            self._reclaim_worker(worker)

    def _refresh_overlay(self) -> None:
        mode = "kaldırıldı" if self.chroma_enabled else "ham görüntü"
        self.overlay_label.setText(f"yeşil perde: {mode}")
        self.overlay_label.adjustSize()
        self.overlay_label.move(8, 8)
        self.view.set_raw_mode(not self.chroma_enabled)

    def start(self) -> None:
        """`isRunning()` tek başına 'sağlıklı çalışıyor' anlamına gelmez: shutdown(timeout_ms) süresi
        dolduğunda (ör. sürücü read()'de takılıysa) worker HÂLÂ ÇALIŞIYOR olabilir, yalnız durmakta
        (_running=False, _abort=True) ama henüz bitmemiş. Böyle bir worker'ı 'zaten çalışıyor' sayıp
        dokunmamak kamerayı süresiz kapalı bırakırdı (bkz. review bulgusu) -- CameraWorker.stop() bir
        bloklayan read() çağrısını kesemez, yalnız bayrak çevirir. Eskiyi kendi kendine bitmeye bırakıp
        (bkz. _retire_worker) TAZE bir worker kuruyoruz; açık kalan bir aygıtı devralma ihtimaline karşı
        open_retries zaten birkaç saniye aralıklı yeniden deniyor.

        Kalıcı olarak takılı bir sürücüde emekliler hiç bitmez: üst sınıra ulaşınca yeni İŞ PARÇACIĞI
        açılmaz (yoksa her göz düğmesi tıklaması bir OS iş parçacığı + kamera kaynağı daha biriktirirdi)
        ve kullanıcıya durum gösterilir. Worker NESNESİ yine de tazedir -- self.worker asla emekli
        (silinmek üzere olan) bir nesneyi göstermez, bkz. __init__'teki DEĞİŞMEZ."""
        if self.worker.isRunning():
            if not self._stop_requested:
                return                              # gerçekten sağlıklı çalışıyor: dokunma
            self._retire_worker(self.worker)
            self.worker = self._make_worker(self._source_factory)
        self._stop_requested = False                # buradan sonra self.worker ya taze ya da durmuş
        if self._at_pending_cap():
            self.has_camera = False
            self._set_placeholder("Kamera yanıt vermiyor")
            return                                  # iş parçacığı açılmaz; self.worker yine de geçerli
        self.worker.start()

    def shutdown(self, timeout_ms: int = 2000) -> None:
        """timeout_ms: iş parçacığının durmasını bekleme üst sınırı. İş parçacığı normalde bir kare
        süresinde (~33ms) durur -- bu üst sınır yalnız `_source.read()` bir sürücü arızasıyla takılırsa
        işe yarar. Varsayılan (2000ms) pencere kapanışı için (kapanışta birkaç saniyelik gecikme kabul
        edilebilir); görünürlük yolunda (apply_ui_settings, göz düğmesiyle her tetiklenebilen rutin bir
        düzenleme eylemi) çok daha kısa bir değer geçilir ki takılı bir sürücü arayüzü iki saniye
        dondurmasın (bkz. main_window.py). Süre dolduğunda worker hâlâ çalışıyor olabilir -- bkz. start()."""
        if self.worker.isRunning():
            self.worker.stop()
            self._stop_requested = True
            self.worker.wait(timeout_ms)

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

    def set_families(self, fam: FontFamilies) -> None:
        """Yazı tipini (ve tahta yazı ölçeğini, Görev 7) değiştirir (Ayarlar > yazı tipi dosyası)."""
        self.fam = fam
        self.overlay_label.setFont(theme.font(fam, 9, 600))

    def _toggle(self) -> None:
        self.set_chroma_enabled(not self.chroma_enabled)
        self.chromaToggled.emit(self.chroma_enabled)

    def _on_opened(self, _w: int, _h: int) -> None:
        self.has_camera = True

    def _on_error(self, msg: str) -> None:
        self.has_camera = False
        self._set_placeholder(f"{msg} · Kamera izni / bağlantı kontrol edin")
