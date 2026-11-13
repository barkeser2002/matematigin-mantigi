"""'Tanıma örneği topla' penceresi: kullanıcı her sembolü kalemle çizer; Kaydet örneği JSON + 28x28 PNG olarak yazar.
Yalnız toplama: uygulamada tanıma (çıkarım) yok. Mantık core/ornek_toplama.py'de; burada yalnız çizim ve düğmeler."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QEvent, QPointF, QSize, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPainterPath
from PyQt6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget)

from matematigin_mantigi.core import ornek_toplama as ot
from matematigin_mantigi.ui import theme

KANVAS = 420          # widget ve gri tuval kenarı (piksel)
CIZGI_KALINLIGI = 16  # gri tuvalde mürekkep kalınlığı


class InkCanvas(QWidget):
    """Kalem/fare çizgilerini (x, y, basinç, zaman) noktaları olarak tutar; kayıt için gri tuval üretir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(KANVAS, KANVAS))
        self._cizgiler: list[list[dict]] = []
        self._aktif: list[dict] | None = None
        self._t0 = time.monotonic()

    # --- girdi -----------------------------------------------------------
    def _nokta(self, p: QPointF, basinc: float) -> dict:
        return {"x": round(float(p.x()), 2), "y": round(float(p.y()), 2),
                "basinc": round(float(basinc), 4), "zaman": round(time.monotonic() - self._t0, 4)}

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._aktif = [self._nokta(e.position(), 1.0)]
        self.update()

    def mouseMoveEvent(self, e):
        if self._aktif is not None:
            self._aktif.append(self._nokta(e.position(), 1.0))
            self.update()

    def mouseReleaseEvent(self, e):
        if self._aktif is not None:
            self._aktif.append(self._nokta(e.position(), 1.0))
            self._cizgiler.append(self._aktif)
            self._aktif = None
            self.update()

    def tabletEvent(self, e):
        p = e.position()
        basinc = float(e.pressure())
        t = e.type()
        if t == QEvent.Type.TabletPress:
            self._aktif = [self._nokta(p, basinc)]
        elif t == QEvent.Type.TabletMove and self._aktif is not None:
            self._aktif.append(self._nokta(p, basinc))
        elif t == QEvent.Type.TabletRelease and self._aktif is not None:
            self._aktif.append(self._nokta(p, basinc))
            self._cizgiler.append(self._aktif)
            self._aktif = None
        self.update()
        e.accept()

    # --- durum -----------------------------------------------------------
    def strokes(self) -> list[list[dict]]:
        return [list(c) for c in self._cizgiler]

    def has_ink(self) -> bool:
        return bool(self._cizgiler) or self._aktif is not None

    def clear(self) -> None:
        self._cizgiler = []
        self._aktif = None
        self.update()

    def gray(self) -> np.ndarray:
        """Mürekkep parlak (255), zemin siyah: normalle() bunu bekler."""
        img = QImage(KANVAS, KANVAS, QImage.Format.Format_Grayscale8)
        img.fill(0)
        p = QPainter(img)
        pen = QPen(QColor(255, 255, 255), CIZGI_KALINLIGI, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        for c in self._tum_cizgiler():
            yol = QPainterPath()
            yol.moveTo(QPointF(c[0]["x"], c[0]["y"]))
            for n in c[1:]:
                yol.lineTo(QPointF(n["x"], n["y"]))
            p.drawPath(yol)
            if len(c) == 1:
                p.drawPoint(QPointF(c[0]["x"], c[0]["y"]))
        p.end()
        ptr = img.constBits()
        ptr.setsize(img.sizeInBytes())
        bpl = img.bytesPerLine()
        return np.frombuffer(ptr, np.uint8).reshape(KANVAS, bpl)[:, :KANVAS].copy()

    def _tum_cizgiler(self) -> list[list[dict]]:
        return self._cizgiler + ([self._aktif] if self._aktif else [])

    # --- çizim -----------------------------------------------------------
    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        pen = QPen(QColor("#111111"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        for c in self._tum_cizgiler():
            yol = QPainterPath()
            yol.moveTo(QPointF(c[0]["x"], c[0]["y"]))
            for n in c[1:]:
                yol.lineTo(QPointF(n["x"], n["y"]))
            p.drawPath(yol)
        p.end()


class OrnekToplamaPenceresi(QWidget):
    """Sembol sırasıyla örnek toplar. Sembol başına hedef ot.HEDEF_ORNEK."""

    def __init__(self, fam, koku: Path, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.fam = fam
        self.koku = Path(koku)
        self._indeks = 0
        self.setWindowTitle("Tanıma örneği topla")

        self.symbol_label = QLabel()
        self.symbol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.symbol_label.setFont(theme.hand_font(fam, 96, 700))
        self.progress_label = QLabel()
        self.total_label = QLabel()
        self.notice_label = QLabel()
        self.notice_label.setWordWrap(True)

        self.canvas = InkCanvas()
        self.save_button = QPushButton("Kaydet")
        self.next_button = QPushButton("Sonraki")
        self.clear_button = QPushButton("Sil")
        self.export_button = QPushButton("ZIP olarak dışa aktar…")
        self.save_button.clicked.connect(self.save_current)
        self.next_button.clicked.connect(self.next_symbol)
        self.clear_button.clicked.connect(self.clear_current)
        self.export_button.clicked.connect(self.export_zip)

        buttons = QHBoxLayout()
        for b in (self.save_button, self.next_button, self.clear_button):
            buttons.addWidget(b)
        left = QVBoxLayout()
        left.addWidget(self.symbol_label)
        left.addWidget(self.progress_label)
        left.addWidget(self.total_label)
        left.addWidget(self.canvas, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addLayout(buttons)
        left.addWidget(self.notice_label)
        left.addWidget(self.export_button)
        self.setLayout(left)
        self._yenile()

    # --- durum -----------------------------------------------------------
    def current_symbol(self) -> str:
        return ot.SEMBOLLER[self._indeks]

    def _sayilar(self) -> dict[str, int]:
        return ot.ornek_sayilari(self.koku)

    def _yenile(self) -> None:
        sembol = self.current_symbol()
        self.symbol_label.setText(sembol.upper() if sembol.isalpha() else sembol)
        sayilar = self._sayilar()
        self.progress_label.setText(f"{min(sayilar[sembol], ot.HEDEF_ORNEK)} / {ot.HEDEF_ORNEK}")
        toplam, hedef = ot.ilerleme(sayilar)
        self.total_label.setText(f"Toplam: {toplam} / {hedef}")

    def _bildir(self, metin: str) -> None:
        self.notice_label.setText(metin)

    # --- düğmeler --------------------------------------------------------
    def save_current(self) -> bool:
        if not self.canvas.has_ink():
            self._bildir("Önce bu sembolü çiz, sonra Kaydet.")
            return False
        try:
            ot.ornek_kaydet(self.koku, self.current_symbol(), self.canvas.strokes(), self.canvas.gray())
        except (OSError, ValueError) as e:
            self._bildir(f"Kaydedilemedi: {e}")
            return False
        self.canvas.clear()
        self._yenile()
        self._bildir(f"Kaydedildi: {self.current_symbol()}")
        return True

    def clear_current(self) -> None:
        self.canvas.clear()
        self._bildir("Çizim temizlendi.")

    def next_symbol(self) -> None:
        if self.canvas.has_ink():
            self._bildir("Kaydedilmemiş çizim var: önce Kaydet ya da Sil.")
            return
        self._indeks = ot.sonraki_sembol(self._indeks)
        self._yenile()
        self._bildir("")

    def export_zip(self) -> None:
        yol, _ = QFileDialog.getSaveFileName(self, "Örnekleri ZIP olarak kaydet",
                                             str(Path.home() / "tanima-ornekleri.zip"), "ZIP (*.zip)")
        if not yol:
            return
        try:
            hedef = ot.zip_olustur(self.koku, Path(yol))
        except OSError as e:
            self._bildir(f"ZIP yazılamadı: {e}")
            return
        self._bildir(f"ZIP yazıldı: {hedef.name}")
