import threading
import time

import numpy as np
from PyQt6.QtCore import Qt

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.webcam_panel import WebcamPanel

FAM = FontFamilies("Arial", "Arial", False)


class _SlowCamera:
    """`read()` gerçek bir sürücü arızasını taklit eder (çok yavaş): stop() çağrılsa da mevcut okuma
    bitmeden iş parçacığı _running bayrağını yeniden kontrol edemez."""

    def __init__(self, delay: float):
        self.delay = delay

    def open(self) -> bool:
        return True

    def read(self):
        time.sleep(self.delay)
        return np.zeros((10, 10, 3), np.uint8)

    def release(self) -> None:
        pass


class _TaggedCamera:
    """Ürettiği her karede kendi ETİKETİNİ taşıyan sahte kamera (tüm piksel değerleri = tag) -- hangi
    worker'ın kareyi ürettiğini görüntüden ayırt edebilmek için. `frames` tükenince None döner (worker
    bir süre sonra cameraError yayıp durur -- akışı kendi başına sürdürmesin diye küçük tutulur),
    `delay` her read()'i o kadar geciktirir."""

    def __init__(self, tag: int, delay: float = 0.0, frames: int = 1000):
        self.tag, self.delay, self.frames = tag, delay, frames
        self._i = 0

    def open(self) -> bool:
        return True

    def read(self):
        if self._i >= self.frames:
            return None
        if self.delay:
            time.sleep(self.delay)
        self._i += 1
        return np.full((10, 10, 3), self.tag, np.uint8)

    def release(self) -> None:
        pass


class _WedgedCamera:
    """`read()` bir `threading.Event` üzerinde SÜRESİZ bekler -- gerçekten takılı bir sürücüyü taklit
    eder (yalnız yavaş değil: `stop()`ün çevirdiği bayraklar bu bekleyişi asla kesmez, `finished` de
    hiç ateşlenmez). Test sonunda temizlik için verilen event'i ayarlamak (`event.set()`) bekleyen TÜM
    örnekleri birden serbest bırakır, iş parçacıklarının temiz sonlanmasını sağlar."""

    def __init__(self, event: threading.Event):
        self._event = event

    def open(self) -> bool:
        return True

    def read(self):
        self._event.wait()
        return None                  # event ayarlanınca (yalnız temizlikte): akışı sonlandır

    def release(self) -> None:
        pass


def test_shows_frames_and_toggles_on_click(qtbot, fake_camera):
    panel = WebcamPanel(FAM, lambda: fake_camera, ChromaParams())
    qtbot.addWidget(panel); panel.resize(600, 400); panel.show()
    with qtbot.waitSignal(panel.worker.frameReady, timeout=2000):
        panel.start()
    assert panel.has_camera and panel.overlay_label.text() == "yeşil perde: kaldırıldı"
    qtbot.mouseClick(panel.view, Qt.MouseButton.LeftButton)
    assert panel.chroma_enabled is True                        # tıklama değiştirmez; Ayarlar'dan
    panel.set_chroma_enabled(False)
    assert panel.overlay_label.text() == "yeşil perde: ham görüntü"
    panel.shutdown()
    assert panel.worker.isFinished()


def test_placeholder_without_camera(qtbot, dead_camera):
    panel = WebcamPanel(FAM, lambda: dead_camera, ChromaParams())
    qtbot.addWidget(panel); panel.show()
    with qtbot.waitSignal(panel.worker.cameraError, timeout=2000):
        panel.start()
    qtbot.waitUntil(lambda: not panel.has_camera, timeout=2000)
    assert "Kamera" in panel.view.placeholder_text
    panel.shutdown()


def test_start_can_be_skipped(qtbot, dead_camera):
    panel = WebcamPanel(FAM, lambda: dead_camera, ChromaParams())
    qtbot.addWidget(panel)
    panel.shutdown()          # never started: must not raise


def test_shutdown_timeout_bounds_the_wait_on_a_stuck_camera(qtbot):
    """Görev 6 düzeltmesi: shutdown(timeout_ms) verilirse worker.wait bu sınırla döner -- kamera
    sürücüsü read()'de takılsa bile (ör. flaky bir sürücü) çağıran, iş parçacığının GERÇEKTEN durmasını
    değil, en fazla timeout_ms kadar bekler. _SlowCamera 1.5sn'lik bir read() ile bunu taklit eder."""
    panel = WebcamPanel(FAM, lambda: _SlowCamera(1.5), ChromaParams())
    qtbot.addWidget(panel)
    panel.start()
    qtbot.wait(50)                            # ilk read() çağrısının başlamasına kısa bir pay
    t0 = time.monotonic()
    panel.shutdown(250)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0                      # 1.5sn'lik read()'i beklemedi, ~250ms sınırına uydu
    qtbot.waitUntil(lambda: panel.worker.isFinished(), timeout=3000)   # iş parçacığı temiz sonlanır


def test_shutdown_default_timeout_value_is_2000ms():
    """2. review turu: bu testin ÖNCEKİ hâli argümansız bir shutdown() çağrısının 2000 kullandığını
    ölçüyordu -- ama bu, eski (parametresiz, hep 2000'e sabit) kodda da AYNI ölçülürdü, hangi kodun
    çalıştığını hiç ayırt etmiyordu (reviewer bulgusu: 'a test that passes against the old code too is
    worse than no test'). İmzayı doğrudan okumak GERÇEKTEN ayırt eder: eski kodda "timeout_ms" adında
    bir parametre yoktu, bu satır orada KeyError ile patlardı."""
    import inspect
    sig = inspect.signature(WebcamPanel.shutdown)
    assert sig.parameters["timeout_ms"].default == 2000


def test_start_after_a_timed_out_shutdown_still_produces_frames(qtbot):
    """2. review turu (Important): CameraWorker.stop() bir bloklayan read() çağrısını kesemez, yalnız
    bayrak çevirir -- shutdown(timeout_ms) süresi dolduğunda worker HÂLÂ ÇALIŞIYOR olabilir. Eski start()
    ("if not self.worker.isRunning()") bunu 'zaten sağlıklı çalışıyor' sanıp hiçbir şey yapmazdı: kamera,
    eski iş parçacığı kendi kendine bitene kadar (belirsiz bir süre) kapalı kalırdı. read()'i gizleme
    süresinden (200ms) uzun (600ms) tutan sahte bir kamerayla: gizle, HEMEN göster, kare akışının
    GERÇEKTEN devam ettiğini doğrula (yalnızca bir metodun çağrıldığını değil)."""
    panel = WebcamPanel(FAM, lambda: _SlowCamera(0.6), ChromaParams())
    qtbot.addWidget(panel)
    panel.start()
    qtbot.wait(50)                              # ilk read() çağrısının başlamasına kısa bir pay
    panel.shutdown(200)                         # 200ms < 600ms'lik read(): worker hâlâ çalışıyor olacak
    old_worker = panel.worker
    assert old_worker.isRunning()               # yarış koşulunun ön koşulu: gerçekten hâlâ çalışıyor
    panel.start()                               # hemen tekrar göster (göz düğmesi)
    assert panel.worker is not old_worker        # taze bir worker'a geçildi -- eskisi kendi kendine bitecek
    with qtbot.waitSignal(panel.worker.frameReady, timeout=3000):
        pass                                     # kare GERÇEKTEN gelmeli -- eski kod burada süresiz kapalı kalırdı
    # Not: old_worker'a burada artık dokunmuyoruz -- gerçekten bitince _retire_worker onu finished
    # sinyaliyle siler; isFinished() ile yoklamaya devam etmek bu silinmeyle yarışıp
    # "wrapped C/C++ object ... has been deleted" hatasına çarpabilirdi.
    # ÖNEMLİ: taze (2.) worker sürekli çalışan, kendi kendine hiç durmayan bir iş parçacığıdır -- burada
    # kapatılmazsa test dönüşten SONRA da arka planda çalışmaya devam eder (SlowCamera'nın 0.6sn'lik
    # read()'ini sonsuza dek tekrarlayarak) ve SONRAKİ testlerle GIL/CPU için yarışıp onları (özellikle
    # zamanlayıcıya dayalı testleri) tıkayabilir -- bunu elle doğruladım (bu test + herhangi bir zamanlayıcı
    # tabanlı test art arda çalıştırılınca ikincisi asılı kalıyordu). qtbot.addWidget yalnız widget'ı
    # temizler, WebcamPanel'in KENDİ closeEvent'i yok -- iş parçacığını açıkça durdurmak testin sorumluluğu.
    panel.shutdown()
    assert panel.worker.isFinished()


def test_retiring_worker_is_disconnected_and_cannot_paint_a_stale_frame(qtbot):
    """FINDING 1 (3. review turu): _make_worker her worker için frameReady/opened/cameraError bağlar;
    rebuild (start()'ın taze worker yolu ya da set_source_factory) eskisini bağlı bırakırsa, stop()
    sonrası hâlâ işlenmekte olan (in-flight) bir read() dönünce eski worker YENİ worker akmaya
    başladıktan SONRA bile tek bir GEÇ kare daha yayar -- bu, aynı self.view'i besleyip görünümü
    kısaca eskiye döndürür (review'da 350ms gecikmeli/hızlı iki sahte kamerayla ölçüldü). Yavaş (350ms'de
    tek geç kare) bir sahte + sürekli akan hızlı bir sahte ile: eski worker'ın geç karesi geleceği
    pencerede view.set_frame'e YAZILAN HİÇBİR karenin eski worker'ın etiketini taşımadığını doğrular --
    `panel.view._frame`'i tek bir anda yoklamak yerine (hızlı worker sürekli akıp kendini düzeltebilir,
    testi yanlışlıkla yeşile çevirebilir; sınırlı sayıda kareyle durdurmak da hızlı worker'ın KENDİ
    cameraError'ını -- ve o da view'i placeholder'a, `_frame=None`'a döndürür -- tetikleyip testi
    kararsız kılar) set_frame çağrılarının TAMAMI kaydedilir. chroma_enabled=False: piksel değerleri
    yeşil perde işlemeden etkilenmesin diye (etiketler tam olarak korunsun)."""
    slow = _TaggedCamera(tag=10, delay=0.35)
    panel = WebcamPanel(FAM, lambda: slow, ChromaParams(), chroma_enabled=False)
    qtbot.addWidget(panel)
    panel.start()
    qtbot.wait(50)                                   # slow'un read()'i hâlâ sürüyor (350ms'lik)
    panel.shutdown(50)                               # çok kısa: eski worker hâlâ çalışıyor olacak
    fast = _TaggedCamera(tag=20, delay=0.0)           # sürekli akar (frames sınırlı değil)
    panel._source_factory = lambda: fast
    panel.start()
    with qtbot.waitSignal(panel.worker.frameReady, timeout=2000):
        pass                                          # yeni (fast) worker akmaya başladı
    seen_tags = []
    real_set_frame = panel.view.set_frame
    panel.view.set_frame = lambda img: (seen_tags.append(img.pixelColor(0, 0).red()), real_set_frame(img))[1]
    qtbot.wait(500)                                   # eski (slow) worker'ın geç karesi bu pencerede gelmeli
    assert 10 not in seen_tags                        # eski worker'ın etiketi hiç yazılmamalı
    assert seen_tags and all(t == 20 for t in seen_tags)   # yazılanların tamamı yeni worker'ın etiketi
    panel.shutdown()                                  # temizlik: taze worker'ı da durdur


def test_worker_accumulation_is_bounded_and_surfaces_a_placeholder_when_camera_never_responds(qtbot):
    """FINDING 2 (3. review turu): read() GERÇEKTEN hiç dönmezse (yavaş değil, tamamen takılı bir
    sürücü) finished de asla ateşlenmez -- eskiden _delete_worker_safely'nin sildiği o zamandı. Her göz
    düğmesi tıklaması (gizle/göster) bu durumda BİR DAHA iş parçacığı + kamera kaynağı biriktirirdi,
    sınırsızca. Aynı (yalnız test sonunda ayarlanan) olayda bekleyen bir sahte kamerayla, üst sınırdan
    (MAX_PENDING_WORKERS=2) fazla art arda gizle/göster: bekleyen worker sayısı sınırlı kalmalı VE
    kullanıcıya 'Kamera yanıt vermiyor' gösterilmeli."""
    event = threading.Event()
    try:
        panel = WebcamPanel(FAM, lambda: _WedgedCamera(event), ChromaParams())
        qtbot.addWidget(panel)
        panel.start()
        qtbot.wait(50)
        for _ in range(WebcamPanel.MAX_PENDING_WORKERS + 2):   # kapasiteden FAZLA döngü
            panel.shutdown(50)                                  # 50ms << sonsuz: hep hâlâ çalışıyor olacak
            panel.start()
        assert len(panel._pending_workers) <= WebcamPanel.MAX_PENDING_WORKERS
        assert "yanıt vermiyor" in panel.view.placeholder_text
    finally:
        # event.set() bekleyen TÜM read() çağrılarını serbest bırakır (izlenen ve TERK EDİLMİŞ worker
        # dahil -- _retire_worker artık ikisine de finished.connect(deleteLater) bağlıyor, bkz. review
        # düzeltmesi). Birkaç worker aynı anda bitip deleteLater() kuyruklayabildiğinden (üçü de aynı
        # event'i bekliyordu) tek seferlik kısa bir bekleme yerine olay döngüsünü tekrar tekrar
        # döndürüyoruz -- hepsi GERÇEKTEN temizlenip test süreç çıkışını tıkamasın diye bolca pay.
        event.set()
        for _ in range(20):
            qtbot.wait(100)


def test_panel_stays_usable_after_a_wedged_camera_recovers(qtbot):
    """4. review turu (CRITICAL): üst sınıra ULAŞILDIĞINDA eski kod `self.worker`ı EMEKLİ EDİLMİŞ
    worker'da bırakıyordu (erken return; onu yenileyen tek dal ulaşılamaz hâle geliyordu). Oysa emekli
    worker'a `finished.connect(deleteLater)` bağlıdır: takılı sürücü sonradan TOPARLAYIP read()'ten
    dönerse -- ki normal sonuç budur -- Qt o C++ nesnesini siler ve `self.worker` SARKAN bir referans
    olur. start(), shutdown() ve set_source_factory() ÜÇÜ DE ilk satırında self.worker'a dokunur:
    "RuntimeError: wrapped C/C++ object of type CameraWorker has been deleted". Hiçbir çağıran bunu
    yakalamaz -- MainWindow.closeEvent doğrudan shutdown() çağırdığı için UYGULAMA KAPANIŞTA ÇÖKER.
    Artık üst sınırda da TAZE bir worker kurulur (yalnız start() EDİLMEZ): bir nesne + sıfır iş
    parçacığı karşılığında self.worker hep geçerli kalır."""
    event = threading.Event()
    released: list[int] = []

    class _CountingWedgedCamera(_WedgedCamera):
        """Bloklanan read() GERÇEKTEN döndüğünde iz bırakır -- 'sürücü toparladı'yı deterministik
        bekleyebilmek için (iş parçacıkları o dönüşün hemen ardından biter)."""

        def read(self):
            out = super().read()
            released.append(1)
            return out

    panel = WebcamPanel(FAM, lambda: _CountingWedgedCamera(event), ChromaParams())
    qtbot.addWidget(panel)
    panel.start()
    qtbot.wait(50)
    for _ in range(WebcamPanel.MAX_PENDING_WORKERS + 1):     # üst sınıra ULAŞ (terk edilen worker burada doğardı)
        panel.shutdown(50)                                   # 50ms << sonsuz: worker hep hâlâ çalışıyor olacak
        panel.start()
    assert "yanıt vermiyor" in panel.view.placeholder_text   # ön koşul: gerçekten üst sınırdayız

    event.set()                                              # SÜRÜCÜ TOPARLAR: bloklanan read()'ler döner
    qtbot.waitUntil(lambda: len(released) >= WebcamPanel.MAX_PENDING_WORKERS, timeout=5000)
    for _ in range(20):
        qtbot.wait(50)     # deleteLater kuyruğu İŞLENSİN: sarkan referans tam burada oluşuyordu

    panel.start()                        # eski kod: RuntimeError -- silinmiş C++ nesnesine dokunur
    assert panel.worker.isRunning()      # ve panel toparlamayı da görür: yer açıldı, kamera geri gelir
    panel.shutdown(50)                   # eski kod: aynı RuntimeError (closeEvent'in çağırdığı yol)
    panel.set_source_factory(lambda: _WedgedCamera(event))   # eski kod: aynı RuntimeError
    panel.shutdown()
    assert not panel.worker.isRunning()  # temizlik: geride çalışan iş parçacığı bırakma


def test_set_source_factory_keeps_the_not_responding_placeholder_while_at_the_cap(qtbot):
    """5. review turu (Important): üst sınır kontrolü ve göstergesi artık yalnız start()'ta. Ama
    set_source_factory start()'ı YALNIZCA worker çalışıyorsa çağırır -- panel BOŞTAYKEN (bir önceki
    start() üst sınıra takıldığı için worker hiç başlatılmamışsa) çağırmaz ve koşulsuz yazdığı
    "Kamera bekleniyor…" olduğu gibi kalırdı. Pratikte: takılı kamera hâlâ yanıt vermezken Ayarlar'dan
    kamera değiştirmek, doğru olan 'yanıt vermiyor' uyarısını 'bekleniyor' ile değiştiriyordu -- oysa
    beklenen bir şey yok, yeni kaynağı deneyecek bir zamanlayıcı da yok (bir sonraki açık start()'a
    kadar). Gösterge artık iki yolda da aynı koşulu (_at_pending_cap) okur."""
    event = threading.Event()
    try:
        panel = WebcamPanel(FAM, lambda: _WedgedCamera(event), ChromaParams())
        qtbot.addWidget(panel)
        panel.start()
        qtbot.wait(50)
        for _ in range(WebcamPanel.MAX_PENDING_WORKERS + 1):   # üst sınıra ULAŞ
            panel.shutdown(50)
            panel.start()
        assert "yanıt vermiyor" in panel.view.placeholder_text  # ön koşul 1: gerçekten üst sınırdayız
        assert not panel.worker.isRunning()                     # ön koşul 2: panel BOŞTA (worker hiç başlamadı)

        panel.set_source_factory(lambda: _WedgedCamera(event))  # Ayarlar'dan kamera değişimi
        assert "yanıt vermiyor" in panel.view.placeholder_text  # eski kod: "Kamera bekleniyor…"
        assert not panel.has_camera
    finally:
        event.set()                     # bekleyen tüm read()'leri serbest bırak (bkz. üstteki testler)
        for _ in range(20):
            qtbot.wait(100)


def test_panel_shows_understandable_message_when_frames_keep_failing(qtbot):
    """Kamera iş parçacığı bozuk karelerde sessizce ölmesin: panel donuk kare yerine anlaşılır bilgi gösterir."""
    class Broken:
        released = False
        def open(self): return True
        def read(self):
            raise ValueError("yapay sürücü hatası")
        def release(self): Broken.released = True
    panel = WebcamPanel(FAM, lambda: Broken(), ChromaParams())
    qtbot.addWidget(panel); panel.show()
    with qtbot.waitSignal(panel.worker.cameraError, timeout=5000):
        panel.start()
    qtbot.waitUntil(lambda: "Kamera görüntüsü alınamadı" in panel.view.placeholder_text, timeout=2000)
    # Kaynak, hata sinyalinden SONRA iş parçacığının finally'sinde bırakılır: GUI mesajı gösterdiğinde henüz
    # bırakılmamış olabilir (Windows CI'da yarış). Bırakılmayı bekle.
    qtbot.waitUntil(lambda: Broken.released, timeout=2000)
    assert not panel.has_camera
    panel.shutdown()
