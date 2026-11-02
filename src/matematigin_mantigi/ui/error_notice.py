"""Uygulama çapında, modal olmayan tek uyarı kutusu: ders ve kayıt sürerken hatayı öğretmene gösterir.

`post()` her iş parçacığından çağrılabilir (hata kancası kamera/kayıt iş parçacığından da gelir); kutu her zaman
GUI iş parçacığında, olay döngüsünün bir sonraki turunda açılır (kancanın içinden pencere kurulmaz). Aynı anahtar
oturumda bir kez gösterilir ve hep aynı kutu kullanılır: aynı hata art arda yüzlerce kez gelse de pencere yağmuru
olmaz. Kutu odağı çalmaz (kalem ve kısayollar tahtada kalır).

Uyarılar kayda girmeyen yerde (tasarım, "Temel ilke"): kayıt sürerken (kayıt kaydedilirken de) kutu hiç açılmaz;
uyarı araç çubuğunun kırmızı şeridine kısa bir satır olarak yazılır ve kayıt bitince kutuyla gösterilir. Kayıt kutu
açıkken başlarsa kutu kaydedici ilk kareyi yakalamadan gizlenir (prepare_recording), kayıttan sonra yeniden gelir.
Kayıt dışında kutu, kayda giren sahneyle en az çakışan ve araç çubuğunun altını (uyarı şeridi + kayıt düğmesi)
örtmeyen yere konur.

Ana pencere kapanınca (gizlenince) kutu da kapanır ve o sürede hiçbir pencere açılmaz: gizli ana pencerenin çocuğu
olarak gösterilen kutu Qt'nin otomatik çıkışını kuyruktan siliyordu, pencere kapanıyor ama süreç çıkmıyordu. Pencerenin
görünürlüğü Qt'nin kendi sinyaliyle (QWindow.visibleChanged) izlenir; Python'da yazılmış olay süzgeci uzun ömürlü
pencerede kalınca yorumlayıcı sonlanırken çağrılıp süreci ara sıra SIGSEGV ile düşürüyordu. Uygulama kapanırken
(aboutToQuit) `release()` pencereyle bütün bağı keser. Pencere kendisi kapanmadan önce ('Durdur ve çık') görülmemiş
uyarılar `take_all()` ile kapanış özetine alınır. Modül düzeyindeki `post()` ile gelen her uyarı başlığı ve metniyle
hatalar.log'a da yazılır (core/crash_log).
"""
from __future__ import annotations

import errno
import sys
from typing import Callable, Sequence

from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEventLoop, QObject, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QWindow
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from matematigin_mantigi.core import crash_log

_MARGIN = 8
POLL_MS = 200               # kayıt başladı mı / bitti mi yoklaması; yalnız bekleyen uyarı ya da görünür kutu varken
_MAX_ITEMS = 4              # kayıttan sonra tek kutuda gösterilen en çok uyarı (kutu ekrana sığsın)
ALERT_KEY = "uyari-kutusu"  # araç çubuğu uyarı şeridinde bu kaynağın anahtarı (app.py bağlar)
_OS_REASONS = {
    errno.EACCES: "erişim izni yok ya da dosya başka bir programda açık",
    errno.EPERM: "erişim izni yok",
    errno.ENOSPC: "diskte yer kalmadı",
    errno.EROFS: "disk salt okunur",
    errno.ENOENT: "klasör ya da dosya bulunamadı",
    errno.ENOTDIR: "yolda klasör yerine bir dosya var",
    # macOS: iCloud'un indiremediği (çevrimdışı) ya da eşitlemenin kilitlediği dosyayı okuma
    errno.EDEADLK: "dosya şu an okunamıyor; bu bilgisayara inmemiş ya da eşitleme tarafından kilitli olabilir",
}

Items = dict[str, tuple[str, str]]          # anahtar -> (başlık, metin); sıra geliş sırası


def describe_os_error(err: OSError) -> str:
    """Dosya hatasının öğretmenin anlayacağı kısa Türkçe sebebi; bilinmeyen hatada sistemin kendi metni."""
    reason = _OS_REASONS.get(err.errno) if err.errno is not None else None
    return reason or err.strerror or str(err) or type(err).__name__


def place_outside(size: QSize, avoid: QRect | None, screens: Sequence[QRect], home: QRect,
                  keep_clear: QRect | None = None) -> QPoint:
    """Kutunun sol üst köşesi. Adaylar sırayla her ekranın (önce pencerenin ekranı `home`) sol alt, sol üst (araç
    çubuğu tarafı), sağ alt ve sağ üst köşesi. Önce `keep_clear`'ı (araç çubuğunun altı: uyarı şeridi ve kayıt
    düğmesi) örtmeyen, sonra kayda giren dikdörtgenle (avoid) en az çakışan aday kazanır; eşitlikte sıradaki ilk aday.
    Tek ekranda tam ekran sahne neredeyse her yeri kapladığından kutu (kayıt dışında) sahneye binebilir; sahnesiz
    ikinci bir ekran varsa kutu oraya gider."""
    w, h = size.width(), size.height()
    cands: list[QPoint] = []
    for g in [home] + [s for s in screens if s != home]:
        left, right = g.left() + _MARGIN, g.left() + g.width() - w - _MARGIN
        top, bottom = g.top() + _MARGIN, g.top() + g.height() - h - _MARGIN
        cands += [QPoint(left, bottom), QPoint(left, top), QPoint(right, bottom), QPoint(right, top)]

    def overlap(p: QPoint, rect: QRect | None) -> int:
        if rect is None:
            return 0
        r = QRect(p, size).intersected(rect)
        return max(0, r.width()) * max(0, r.height())
    return min(cands, key=lambda p: (overlap(p, keep_clear), overlap(p, avoid)))


def summary_text(entries: Sequence[tuple[str, str]]) -> str:
    """Birden çok uyarı tek metinde, başlıklarıyla alt alta (en yenileri; pencere ekrana sığsın diye en çok
    _MAX_ITEMS). Uyarı kutusu ve kapanış özeti (main_window) kullanır."""
    entries = list(entries)
    shown = entries[-_MAX_ITEMS:]
    parts = [f"{title}:\n{text}" for title, text in shown]
    if len(entries) > len(shown):
        parts.insert(0, f"(Önceki {len(entries) - len(shown)} uyarı burada gösterilmiyor; hepsi hatalar.log'da.)")
    return "\n\n".join(parts)


def _compose(items: Items) -> tuple[str, str]:
    """Kutunun başlığı ve metni. Kayıt sürerken biriken birden çok uyarı tek kutuda (summary_text)."""
    entries = list(items.values())
    if len(entries) == 1:
        return entries[0]
    return f"{len(entries)} uyarı", summary_text(entries)


class ErrorNotice(QObject):
    """Tek, modal olmayan uyarı kutusunun sahibi. GUI iş parçacığında kurulmalı (QApplication'dan sonra)."""

    _requested = pyqtSignal(str, str, str)          # başlık, metin, anahtar

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        # Hep kuyruklu: başka iş parçacığından gelen istek GUI'ye taşınır, GUI'den gelen de kancanın içinde değil
        # olay döngüsünün bir sonraki turunda işlenir.
        self._requested.connect(self._show, Qt.ConnectionType.QueuedConnection)
        self.box: QMessageBox | None = None
        self._shown: set[str] = set()                 # gösterilen ya da gösterilmeyi bekleyen anahtarlar
        self._current: Items = {}                     # görünen kutunun içeriği; Tamam'a basılınca boşalır
        self._pending: Items = {}                     # kayıt sürerken gelenler: kayıt bitince gösterilir
        self._anchor: QWidget | None = None
        self._anchor_window: QWindow | None = None    # çapanın yerel penceresi: görünürlüğü buradan izlenir
        self._released = False                        # uygulama kapanıyor: pencereyle bağ kesildi
        self._starting = False                        # kayıt başlatılıyor: prepare_recording'den start() dönene dek
        self._avoid: Callable[[], QRect | None] | None = None
        self._keep_clear: Callable[[], QRect | None] | None = None
        self._is_recording: Callable[[], bool] | None = None
        self._show_alert: Callable[[str | None], None] | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_MS)
        self._poll_timer.timeout.connect(self._poll)

    def set_anchor(self, widget: QWidget | None, avoid: Callable[[], QRect | None] | None = None,
                   keep_clear: Callable[[], QRect | None] | None = None) -> None:
        """widget: kutunun sahibi (ana pencere; tam ekranda kutu onun üstünde kalsın). avoid: kayda giren dikdörtgen,
        keep_clear: kutunun örtmemesi gereken yer (araç çubuğunun altı); ikisi de ekran koordinatında. Ana pencere
        kapanınca (gizlenince) kutu da kapanır; pencere gizliyken kutu açılmaz. Görünürlük pencerenin kendi
        sinyaliyle izlenir (QWindow.visibleChanged), olay süzgeciyle değil: Python'da yazılmış süzgeç pencerede
        kalınca yorumlayıcı sonlanırken çağrılıyor, süreç ara sıra SIGSEGV (-11) ile ölüyordu (U1). None: bağ kesilir."""
        self._unwatch_anchor()
        self._anchor, self._avoid, self._keep_clear = widget, avoid, keep_clear
        self._watch_anchor(widget)

    def release(self) -> None:
        """Uygulama kapanıyor (QApplication.aboutToQuit; app.py bağlar): ana pencereyle bütün bağ kesilir (görünürlük
        bağlantısı, pencereyi yakalayan çapa ve kayıt yolu lambdaları), kutu silinir, yoklama durur; sonra gelen uyarı
        pencere açmaz (stderr'e, günlükte zaten var). Pencere yorumlayıcı sonlanırken silindiğinde kutunun hiçbir
        Python kodu çağrılmaz. İstisna fırlatmaz."""
        self._released = True
        try:
            self.set_anchor(None)
            self.set_recording_route(None, None)
            self._poll_timer.stop()
        except Exception:  # noqa: BLE001 - çıkış hiçbir koşulda düşmez
            pass
        box, self.box = self._live(self.box), None
        if box is None:
            return
        for signal, slot in ((box.finished, self._on_box_finished), (box.destroyed, self._on_box_destroyed)):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):   # bağlantı zaten yok
                pass
        try:
            box.hide()
            sip.delete(box)
        except Exception:  # noqa: BLE001
            pass

    def _watch_anchor(self, widget: QWidget | None) -> None:
        live = self._live(widget)
        if live is None:
            return
        top = live.window()
        handle = top.windowHandle()
        if handle is None:                  # pencere henüz gösterilmedi: yerel pencere (ve tutamağı) şimdi kurulur
            top.winId()
            handle = top.windowHandle()
        if handle is not None:
            handle.visibleChanged.connect(self._on_anchor_visibility)
            self._anchor_window = handle

    def _unwatch_anchor(self) -> None:
        handle, self._anchor_window = self._anchor_window, None
        if handle is None or sip.isdeleted(handle):
            return
        try:
            handle.visibleChanged.disconnect(self._on_anchor_visibility)
        except (TypeError, RuntimeError):   # bağlantı zaten yok
            pass

    def set_recording_route(self, is_recording: Callable[[], bool] | None,
                            show_alert: Callable[[str | None], None] | None) -> None:
        """is_recording: kayıt sürüyor mu (kaydedilirken de evet). show_alert(metin | None): araç çubuğunun uyarı
        şeridine yazar / şeritten kaldırır. Kayıt sürerken kutu açılmaz, uyarı şeride gider; kayıt bitince bekleyen
        uyarılar kutuyla gösterilir (bunu bekleyen uyarı varken çalışan kısa aralıklı yoklama yakalar)."""
        self._is_recording, self._show_alert = is_recording, show_alert
        self._update_polling()

    def recording_changed(self) -> None:
        """Kayıt başlamış ya da bitmiş olabilir: yoklamayı beklemeden bakar (app.py kayıt rozetinin tikine bağlar; rozet
        kayıt başlar başlamaz tik atar)."""
        self._poll()

    def prepare_recording(self) -> None:
        """Kayıt başlamak üzere (MainWindow.recordingAboutToStart; app.py bağlar): kaydedici ilk kareyi start() içinde,
        hemen yakalar. Görünür kutu ŞİMDİ gizlenir, uyarı şeride geçer; Tamam'a basılmadığı için kayıt bitince yeniden
        gösterilir. Eskiden kutu ancak rozetin ilk tikinde, start() döndükten sonra gizleniyor, kaydın ilk karelerine
        giriyordu (kutu hatalar.log'un tam yolunu, yani kullanıcı adını taşır). Gizlemek de yetmiyordu: gizlenen
        pencere olay döngüsü dönene dek ekranda (exposed) kalıyor, ekran yakalayıcısı onu ilk ~3 karede çiziyordu
        (U6). Kutu gizlendiyse olay döngüsü kullanıcı girdisi hariç bir kez döner. O turda ve start() dönene dek
        (sonraki olay turu) kayıt sürüyor sayılır: yoklama ya da sıradaki yeni uyarı kutuyu geri getirmez, şeride
        yazar. Kayıt başlamazsa (başlatma hatası) o turda kutu geri gelir. İstisna fırlatmaz."""
        self._starting = True
        try:
            if self._stash_box():
                self._update_alert()
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        except Exception as err:  # noqa: BLE001 - kayıt başlatmayı hiçbir koşulda engellemez
            _to_stderr("Uyarı kutusu", f"gizlenemedi: {err}")
        QTimer.singleShot(0, self._start_settled)
        self._update_polling()

    def _start_settled(self) -> None:
        """prepare_recording'den sonraki ilk olay turu: start() döndü, kayıt başladı ya da başlamadı. Başlamadıysa
        bekleyen uyarılar (gizlenen kutu dahil) hemen kutuyla gelir. İstisna fırlatmaz."""
        self._starting = False
        if self._is_recording is not None:
            self._poll()

    def post(self, title: str, text: str, key: str | None = None) -> None:
        """Herhangi bir iş parçacığından güvenle çağrılır; istisna fırlatmaz."""
        try:
            self._requested.emit(title, text, key or title)
        except Exception:  # noqa: BLE001 - (ör. kapanışta silinmiş nesne) uyarı gösterilemezse de uygulama düşmez
            pass

    def _live(self, w: QWidget | None) -> QWidget | None:
        return None if w is None or sip.isdeleted(w) else w

    def _anchor_gone(self) -> bool:
        """Çapa (ana pencere) verilmiş ama kapandı, gizli ya da silindi; ya da uygulama kapanıyor: pencere açılmaz.
        Gizli ana pencerenin çocuğu olarak gösterilen kutu Qt'nin kuyruktaki otomatik çıkışını siliyordu ('Durdur ve
        çık'tan sonra pencere kapanıyor, süreç görünmez kalıyordu; Tamam'dan sonra da çıkmıyordu)."""
        if self._released or QCoreApplication.closingDown():
            return True
        if self._anchor is None:
            return False
        anchor = self._live(self._anchor)
        # isHidden: kapanırken pencere gizli sayılır ama isVisible() bir an daha True kalır (visibleChanged o arada).
        return anchor is None or anchor.isHidden() or not anchor.isVisible()

    def _on_anchor_visibility(self, visible: bool) -> None:
        """Ana pencere kapanınca (gizlenince) görünen kutu da kapanır; içeriği Tamam'a basılmadığı için bekleyenlere
        geçer, yoklama durur. Pencere yeniden gösterilirse bekleyenler gelir (QWindow.visibleChanged yuvası; simge
        durumunda yayılmaz). İstisna fırlatmaz."""
        try:
            if not visible:
                self._stash_box()
            self._update_polling()
        except Exception:  # noqa: BLE001 - yuva hiçbir koşulda istisna fırlatmaz
            pass

    def _recording(self) -> bool:
        if self._starting:                          # kayıt başlatılıyor: ilk kareye kutu girmesin
            return True
        if self._is_recording is None:
            return False
        try:
            return bool(self._is_recording())
        except Exception:  # noqa: BLE001 - sorulamazsa kutu gösterilir: uyarı kaybolmasın
            return False

    def _show(self, title: str, text: str, key: str) -> None:
        if key in self._shown:                     # aynı uyarı bu oturumda gösterildi: yeni pencere açılmaz
            return
        self._shown.add(key)
        self._deliver({key: (title, text)})

    def _deliver(self, items: Items) -> None:
        try:
            if self._recording():
                # Kayıt sürüyor: kutu kayda girer (sahnenin üstünde, kayıt düğmesini ve şeridi örterek, hatalar.log'un
                # yolunu videoya yazarak). Uyarı şeride; ayrıntı kayıt bitince kutuyla.
                self._stash_box()
                self._pending.update(items)
                self._update_alert()
            elif self._anchor_gone():
                # Ana pencere kapandı/gizli: pencere açılmaz (süreç çıkabilsin). Uyarı bekler; pencere yeniden
                # gösterilirse gelir. Gösterilemediği geliştirme konsolunda görünsün (günlükte zaten var).
                self._pending.update(items)
                for title, text in items.values():
                    _to_stderr(title, f"{text} (ana pencere kapalı; uyarı kutusu açılmadı)")
            else:
                self._display(items)
        except Exception as err:  # noqa: BLE001 - uyarı gösterilemezse de uygulama düşmez
            title, text = next(iter(items.values()), ("Uyarı", ""))
            _to_stderr(title, f"{text} (uyarı kutusu açılamadı: {err})")
        self._update_polling()

    def _ensure_box(self) -> QMessageBox:
        # Modal bir pencere (ör. soru editörü) açıksa kutu onun çocuğu olur: yoksa modal pencere kutuyu tıklanamaz
        # kılardı. Görünürken sahip değiştirilmez.
        parent = QApplication.activeModalWidget() or self._live(self._anchor)
        box = self._live(self.box)
        if box is not None and (box.isVisible() or box.parent() is parent):
            return box
        if box is not None:
            box.deleteLater()
        box = QMessageBox(QMessageBox.Icon.Warning, "", "", QMessageBox.StandardButton.Ok, parent)
        box.setModal(False)                                        # QMessageBox varsayılanı modal
        box.setWindowModality(Qt.WindowModality.NonModal)
        box.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)   # kalemden/kısayollardan odak çalmaz
        box.finished.connect(self._on_box_finished)
        box.destroyed.connect(self._on_box_destroyed)
        self.box = box
        return box

    def _display(self, items: Items) -> None:
        box = self._ensure_box()
        # Görünür kutuya gelen uyarı öncekilere eklenir: Tamam'a basılmamış uyarılar silinmesin (anahtarları
        # 'gösterildi' sayıldığından bir daha hiç gelmezlerdi). Yeni kutu yalnız yeni içerikle açılır.
        self._current = {**self._current, **items} if box.isVisible() else dict(items)
        title, text = _compose(self._current)
        box.setWindowTitle(title)
        box.setText(text)
        if not box.isVisible():
            # Son boyut ancak gösterilirken kesinleşir (QMessageBox showEvent'te boyutlanır): önceden tahmin
            # edilen boyutla konan kutu stil sayfasıyla büyüyüp ekrandan taşıyordu. Konum ilk çizimden önce,
            # aynı olay turunda verilir.
            box.show()
        # Görünür kutuda da konum gerçek boyutla yeniden verilir: daha uzun ikinci uyarı kutuyu (setText'te) büyütür,
        # sol üst köşe yerinde kalınca alt kenar ve Tamam düğmesi ekranın altından taşıyordu.
        try:
            pos = self._position(box.frameGeometry().size())
            if pos is not None:
                box.move(pos)
        except Exception:  # noqa: BLE001 - konum hesaplanamazsa Qt'nin varsayılan yeri
            pass

    def _position(self, size: QSize) -> QPoint | None:
        anchor = self._live(self._anchor)
        screen = (anchor.screen() if anchor is not None else None) or QGuiApplication.primaryScreen()
        if screen is None:
            return None
        avoid = self._avoid() if self._avoid is not None else None
        keep = self._keep_clear() if self._keep_clear is not None else None
        return place_outside(size, avoid, [s.availableGeometry() for s in QGuiApplication.screens()],
                             screen.availableGeometry(), keep)

    # --- kayıt yolu: şerit, bekleyen uyarılar, yoklama ---------------------------------------------------------
    def _stash_box(self) -> bool:
        """Kutu görünürken kayıt başladı: kutu kayda girmesin; içeriği kayıt bitince yeniden gösterilir."""
        box = self._live(self.box)
        if box is None or not box.isVisible():
            return False
        stash, self._current = self._current, {}
        box.hide()                                  # QDialog.hide finished yaymaz: içerik 'görüldü' sayılmaz
        self._pending = {**stash, **self._pending}
        return True

    def _update_alert(self) -> None:
        if self._show_alert is None:
            return
        n = len(self._pending)
        if n == 0:
            text = None
        else:
            what = next(iter(self._pending.values()))[0] if n == 1 else f"{n} uyarı"
            text = f"⚠ {what} — ayrıntı kayıt bitince"
        try:
            self._show_alert(text)
        except Exception:  # noqa: BLE001 - şerit yazılamazsa (kapanış) uyarı yine bekler
            pass

    def _poll(self) -> None:
        """Bekleyen uyarı ya da görünür kutu varken çalışır: kayıt başladıysa görünür kutu gizlenir, kayıt bittiyse
        şerit temizlenir ve bekleyenler kutuyla gösterilir (ana pencere görünürse). İş kalmayınca zamanlayıcı durur."""
        try:
            if self._recording():
                if self._stash_box():
                    self._update_alert()
            elif self._pending and not self._anchor_gone():
                items, self._pending = self._pending, {}
                self._update_alert()
                self._display(items)
        except Exception as err:  # noqa: BLE001 - zamanlayıcı yuvası hiçbir koşulda istisna fırlatmaz
            _to_stderr("Uyarı kutusu", f"gösterilemedi: {err}")
        self._update_polling()

    def _update_polling(self) -> None:
        try:
            box = self._live(self.box)
            busy = (self._is_recording is not None and not self._anchor_gone()
                    and bool(self._pending or (box is not None and box.isVisible())))
            if busy and not self._poll_timer.isActive():
                self._poll_timer.start()
            elif not busy and self._poll_timer.isActive():
                self._poll_timer.stop()
        except Exception:  # noqa: BLE001 - (kapanışta silinmiş zamanlayıcı)
            pass

    # --- kapanış özeti ------------------------------------------------------------------------------------------
    def take_all(self) -> list[tuple[str, str]]:
        """Görülmemiş bütün uyarılar, geliş sırasıyla (başlık, metin): görünen kutunun Tamam'a basılmamış içeriği ve
        kayıt sırasında biriken bekleyenler. Hepsi bırakılır: kutu kapanır ve geri gelmez, şerit temizlenir, yoklama
        durur; anahtarlar gösterildi sayılır. Pencere kendisi kapanmadan önce ('Durdur ve çık', o an kayıt yok)
        kaydın sonucuyla tek pencerede gösterilmek için (main_window). İstisna fırlatmaz."""
        items = {**self._current, **self._pending}
        self._current, self._pending = {}, {}
        try:
            box, self.box = self._live(self.box), None
            if box is not None:
                box.hide()                          # finished yaymaz; silinince _current boş: yeniden gösterilmez
                box.deleteLater()
            self._update_alert()
        except Exception:  # noqa: BLE001 - kapanış özeti hiçbir koşulda düşmez
            pass
        self._update_polling()
        return list(items.values())

    # --- kutunun kapanışı ---------------------------------------------------------------------------------------
    def _on_box_finished(self, *_) -> None:
        self._current = {}                          # Tamam (ya da Esc): uyarı görüldü
        self._update_polling()

    def _on_box_destroyed(self, *_) -> None:
        # Kutu, kullanıcı Tamam'a basmadan yok oldu: sahibi olan geçici modal pencere (ör. QMessageBox.warning)
        # kapanınca çocuğu olan kutu da silinir. Anahtar gösterildi sayıldığından aynı uyarı bir daha hiç gelmezdi.
        if self._current:
            QTimer.singleShot(0, self._reshow)

    def _reshow(self) -> None:
        """Yok olan kutunun içeriğini çapa (ana pencere) altında yeniden gösterir (kayıt sürüyorsa şeride). Çapa da
        yok olduysa ya da uygulama kapanıyorsa gösterilmez; anahtarlar serbest kalır, aynı uyarı yeniden gelebilir."""
        try:
            if not self._current or self._live(self.box) is not None:
                return
            items, self._current = self._current, {}
            if QCoreApplication.closingDown() or (self._anchor is not None and self._live(self._anchor) is None):
                self._shown.difference_update(items)
                return
            self._deliver(items)
        except Exception:  # noqa: BLE001
            pass


def _to_stderr(title: str, text: str) -> None:
    try:
        if sys.stderr is not None:
            print(f"{title}: {text}", file=sys.stderr)
    except Exception:  # noqa: BLE001
        pass


class Notice(Exception):
    """hatalar.log'daki uyarı girdisi: kullanıcıya gösterilen uyarı, başlığı ve metniyle (fırlatılmaz)."""


def _log(title: str, text: str, key: str) -> None:
    """Uyarıyı hatalar.log'a yazar (günlük kurulu değilse hiçbir şey): kutu ya da kapanış özeti okunmadan kapansa da
    sonradan ne olduğu görülür. Günlük aynı türü (ve aynı yolu) oturumda bir kez yazar, sonra 10., 100. tekrarı;
    fırlatılmamış istisnaların hepsi tek anahtara düştüğü için türün adı uyarının anahtarını taşır: her uyarı kendi
    girdisini alır, aynı uyarının tekrarı günlüğü doldurmaz. İstisna fırlatmaz."""
    try:
        entry = type(Notice.__name__, (Notice,), {"__qualname__": f"{Notice.__qualname__}[{key}]"})
        crash_log.log_handled(entry(f"{title}: {text}"), "uyarı")
    except Exception:  # noqa: BLE001 - günlük yazılamazsa da uyarı gösterilir
        pass


_instance: ErrorNotice | None = None


def install() -> ErrorNotice:
    """Uygulamanın uyarı kutusunu GUI iş parçacığında kurar (QApplication kurulduktan sonra çağrılır)."""
    global _instance
    _instance = ErrorNotice(QApplication.instance())
    return _instance


def post(title: str, text: str, key: str | None = None) -> None:
    """Uygulama çapındaki uyarı kutusuna yazar ve hatalar.log'a da ekler; kutu kurulmamışsa (QApplication öncesi,
    testler) yalnız stderr'e. Hata kancasının uyarısı (crash_log -> ErrorNotice.post) günlüğe kancanın kendisince
    traceback'iyle yazılır; burada ikinci kez yazılmaz. Herhangi bir iş parçacığından çağrılabilir."""
    _log(title, text, key or title)
    n = _instance
    if n is not None and not sip.isdeleted(n):
        n.post(title, text, key)
    else:
        _to_stderr(title, text)


def take_all() -> list[tuple[str, str]]:
    """Uygulama çapındaki kutunun görülmemiş uyarıları (ErrorNotice.take_all); kutu kurulmamışsa boş liste."""
    n = _instance
    if n is None or sip.isdeleted(n):
        return []
    return n.take_all()
