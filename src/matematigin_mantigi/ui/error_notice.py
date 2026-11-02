"""Uygulama çapında, modal olmayan tek uyarı kutusu: ders ve kayıt sürerken hatayı öğretmene gösterir.

`post()` her iş parçacığından çağrılabilir (hata kancası kamera/kayıt iş parçacığından da gelir); kutu her zaman
GUI iş parçacığında, olay döngüsünün bir sonraki turunda açılır (kancanın içinden pencere kurulmaz). Aynı anahtar
oturumda bir kez gösterilir ve hep aynı kutu kullanılır: aynı hata art arda yüzlerce kez gelse de pencere yağmuru
olmaz. Kutu odağı çalmaz (kalem ve kısayollar tahtada kalır) ve kayda giren sahneyle en az çakışan yere konur.
"""
from __future__ import annotations

import errno
import sys
from typing import Callable, Sequence

from PyQt6 import sip
from PyQt6.QtCore import QObject, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

_MARGIN = 8
_OS_REASONS = {
    errno.EACCES: "erişim izni yok ya da dosya başka bir programda açık",
    errno.EPERM: "erişim izni yok",
    errno.ENOSPC: "diskte yer kalmadı",
    errno.EROFS: "disk salt okunur",
    errno.ENOENT: "klasör ya da dosya bulunamadı",
    errno.ENOTDIR: "yolda klasör yerine bir dosya var",
}


def describe_os_error(err: OSError) -> str:
    """Dosya hatasının öğretmenin anlayacağı kısa Türkçe sebebi; bilinmeyen hatada sistemin kendi metni."""
    reason = _OS_REASONS.get(err.errno) if err.errno is not None else None
    return reason or err.strerror or str(err) or type(err).__name__


def place_outside(size: QSize, avoid: QRect | None, screens: Sequence[QRect], home: QRect) -> QPoint:
    """Kutunun sol üst köşesi: kayda giren dikdörtgenle (avoid) en az çakışan aday. Adaylar sırayla her ekranın
    (önce pencerenin ekranı `home`) sol alt, sol üst (araç çubuğu tarafı), sağ alt ve sağ üst köşesi; eşitlikte
    sıradaki ilk aday kazanır. Tek ekranda tam ekran sahne neredeyse her yeri kapladığından kutu kısmen kayda
    girebilir; sahnesiz ikinci bir ekran varsa kutu oraya gider."""
    w, h = size.width(), size.height()
    cands: list[QPoint] = []
    for g in [home] + [s for s in screens if s != home]:
        left, right = g.left() + _MARGIN, g.left() + g.width() - w - _MARGIN
        top, bottom = g.top() + _MARGIN, g.top() + g.height() - h - _MARGIN
        cands += [QPoint(left, bottom), QPoint(left, top), QPoint(right, bottom), QPoint(right, top)]

    def overlap(p: QPoint) -> int:
        if avoid is None:
            return 0
        r = QRect(p, size).intersected(avoid)
        return max(0, r.width()) * max(0, r.height())
    return min(cands, key=overlap)


class ErrorNotice(QObject):
    """Tek, modal olmayan uyarı kutusunun sahibi. GUI iş parçacığında kurulmalı (QApplication'dan sonra)."""

    _requested = pyqtSignal(str, str, str)          # başlık, metin, anahtar

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        # Hep kuyruklu: başka iş parçacığından gelen istek GUI'ye taşınır, GUI'den gelen de kancanın içinde değil
        # olay döngüsünün bir sonraki turunda işlenir.
        self._requested.connect(self._show, Qt.ConnectionType.QueuedConnection)
        self.box: QMessageBox | None = None
        self._shown: set[str] = set()
        self._anchor: QWidget | None = None
        self._avoid: Callable[[], QRect | None] | None = None

    def set_anchor(self, widget: QWidget | None, avoid: Callable[[], QRect | None] | None = None) -> None:
        """widget: kutunun sahibi (ana pencere; tam ekranda kutu onun üstünde kalsın). avoid: kayda giren dikdörtgen
        (ekran koordinatında), kutu onunla en az çakışacak yere konur."""
        self._anchor, self._avoid = widget, avoid

    def post(self, title: str, text: str, key: str | None = None) -> None:
        """Herhangi bir iş parçacığından güvenle çağrılır; istisna fırlatmaz."""
        try:
            self._requested.emit(title, text, key or title)
        except Exception:  # noqa: BLE001 - (ör. kapanışta silinmiş nesne) uyarı gösterilemezse de uygulama düşmez
            pass

    def _live(self, w: QWidget | None) -> QWidget | None:
        return None if w is None or sip.isdeleted(w) else w

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
        self.box = box
        return box

    def _position(self, size: QSize) -> QPoint | None:
        anchor = self._live(self._anchor)
        screen = (anchor.screen() if anchor is not None else None) or QGuiApplication.primaryScreen()
        if screen is None:
            return None
        avoid = self._avoid() if self._avoid is not None else None
        return place_outside(size, avoid, [s.availableGeometry() for s in QGuiApplication.screens()],
                             screen.availableGeometry())

    def _show(self, title: str, text: str, key: str) -> None:
        if key in self._shown:                     # aynı uyarı bu oturumda gösterildi: yeni pencere açılmaz
            return
        self._shown.add(key)
        try:
            box = self._ensure_box()
            box.setWindowTitle(title)
            box.setText(text)
            if not box.isVisible():
                box.adjustSize()
                try:
                    pos = self._position(box.size())
                    if pos is not None:
                        box.move(pos)
                except Exception:  # noqa: BLE001 - konum hesaplanamazsa Qt'nin varsayılan yeri
                    pass
                box.show()
        except Exception as err:  # noqa: BLE001 - uyarı gösterilemezse de uygulama düşmez
            _to_stderr(title, f"{text} (uyarı kutusu açılamadı: {err})")


def _to_stderr(title: str, text: str) -> None:
    try:
        if sys.stderr is not None:
            print(f"{title}: {text}", file=sys.stderr)
    except Exception:  # noqa: BLE001
        pass


_instance: ErrorNotice | None = None


def install() -> ErrorNotice:
    """Uygulamanın uyarı kutusunu GUI iş parçacığında kurar (QApplication kurulduktan sonra çağrılır)."""
    global _instance
    _instance = ErrorNotice(QApplication.instance())
    return _instance


def post(title: str, text: str, key: str | None = None) -> None:
    """Uygulama çapındaki uyarı kutusuna yazar; kurulmamışsa (QApplication öncesi, testler) yalnız stderr'e."""
    n = _instance
    if n is not None and not sip.isdeleted(n):
        n.post(title, text, key)
    else:
        _to_stderr(title, text)
