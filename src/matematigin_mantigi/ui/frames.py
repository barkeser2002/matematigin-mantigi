"""Çerçeve stilleri: Klasik (mevcut, WorkArea._paint_frame'den taşındı) ve HUD (yeni). Ayarlar açılır
listesi FRAME_SPECS'ten üretilir -- TOOL_META/SHAPE_META (core/models.py) ile aynı kayıt kalıbı.

Hiçbir boyacı WorkArea widget'ına dokunmaz: ihtiyacı olan her şey FrameContext içinde gelir. Böylece
boyacılar saf fonksiyon kalır, WorkArea'nın hiçbir iç durumuna (AppSettings dahil, WorkArea onu zaten
hiç görmez) bağımlı olmaz -- bkz. work_area.py'deki tekrarlanan "WorkArea AppSettings'i hiç görmez" notu.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF

from matematigin_mantigi.core.models import FrameStyle
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies


@dataclass(frozen=True)
class FrameContext:
    """Bir boyacının (paint_classic/paint_hud) çerçeveyi çizmek için ihtiyaç duyduğu her şey. WorkArea'ya
    geri referans YOK -- yalnız o anki dikdörtgenler, etkin bant kalınlığı, yazı ailesi ve bant metinleri."""
    rect: QRect         # tüm widget (letterbox dahil) -- WorkArea.rect()
    stage: QRect        # 16:9 sahne (Görev 3) -- WorkArea.stage_rect()
    inner: QRect        # tahta: sahne eksi bant -- WorkArea.inner_rect()
    band: int           # etkin bant kalınlığı (px); frame_band() ile aynı
    fam: FontFamilies   # tahtanın o an kullandığı (ölçekli) yazı ailesi
    presenter: str      # sunucu adı; boşsa (frame_titles kapalı ya da anahtar kapalı) çizilmez
    brand: str          # marka adı; boşsa çizilmez


@dataclass(frozen=True)
class FrameSpec:
    """TOOL_META/SHAPE_META (core/models.py) ile aynı kayıt kalıbı: Ayarlar'daki çerçeve stili açılır
    listesi FRAME_SPECS'ten üretilir. draws_brand/draws_presenter: bu stil sağ üst/alt bandına marka ve
    sunucu adını KENDİSİ çiziyorsa True -- WorkArea bu durumda eski plaka/el yazısı widget'larını gizler."""
    label: str
    band: int
    paint: Callable[[QPainter, FrameContext], None]
    draws_brand: bool = False
    draws_presenter: bool = False


# --- Klasik: WorkArea._paint_frame'den BİREBİR taşındı (Görev 8) -----------------------------------------

def paint_classic(p: QPainter, ctx: FrameContext) -> None:
    """Gösterişli çerçeve: degrade bant, nokta dokusu, turuncu iç çizgi, köşe süsleri.

    WorkArea._paint_frame'in gövdesi BİREBİR buraya taşındı -- yalnız beş mekanik ikame: theme.FRAME_BAND ->
    ctx.band, self.inner_rect() -> ctx.inner, self.stage_rect() -> ctx.stage, self.rect() -> ctx.rect,
    self.height() -> ctx.rect.height(). Çizim mantığına, renklere, sabit sayılara DOKUNULMADI: mevcut piksel
    testleri (tests/test_work_area.py, örn. test_frame_paints_ink_band_and_can_be_hidden ve
    test_frame_dots_follow_the_stage) bu taşımanın birebir olduğunun kanıtıdır."""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    band = ctx.band
    inner = ctx.inner
    stage = ctx.stage
    grad = QLinearGradient(0, 0, 0, ctx.rect.height())
    grad.setColorAt(0.0, QColor("#2a2925")); grad.setColorAt(0.5, QColor(theme.INK)); grad.setColorAt(1.0, QColor("#0f0e0d"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRect(ctx.rect)                                               # bant
    p.setBrush(QColor("#3a3834"))                                      # sahne kenarında ince nokta dokusu
    for x in range(stage.left() + 6, stage.right() - 3, 8):            # bant tabanlı olsaydı üst/alt
        p.drawEllipse(QPointF(x, stage.top() + 5), 1.0, 1.0)           # sıralar kaydın dışında kalırdı
        p.drawEllipse(QPointF(x, stage.bottom() - 4), 1.0, 1.0)
    for y in range(stage.top() + 6, stage.bottom() - 3, 8):
        p.drawEllipse(QPointF(stage.left() + 5, y), 1.0, 1.0)
        p.drawEllipse(QPointF(stage.right() - 4, y), 1.0, 1.0)
    p.setBrush(QColor(theme.PANEL))
    p.drawRoundedRect(QRectF(inner), 12, 12)                           # yuvarlak iç köşeli tahta
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(theme.HINT_CARD_BORDER), 2))                  # turuncu iç çizgi
    p.drawRoundedRect(QRectF(inner).adjusted(-4, -4, 4, 4), 14, 14)
    p.setPen(QPen(QColor(theme.FRAME_LINE), 1))                        # gri dış çizgi
    p.drawRoundedRect(QRectF(inner).adjusted(-band / 2 - 2, -band / 2 - 2, band / 2 + 2, band / 2 + 2), 18, 18)
    pen = QPen(QColor(theme.BULB), 3); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
    L = 22                                                             # köşe süsleri (L şeklinde)
    for cx, cy, sx, sy in ((inner.left() - 8, inner.top() - 8, 1, 1), (inner.right() + 9, inner.top() - 8, -1, 1),
                           (inner.left() - 8, inner.bottom() + 9, 1, -1), (inner.right() + 9, inner.bottom() + 9, -1, -1)):
        p.drawLine(QPointF(cx, cy), QPointF(cx + sx * L, cy))
        p.drawLine(QPointF(cx, cy), QPointF(cx, cy + sy * L))


# --- HUD: yeni (Görev 8) ----------------------------------------------------------------------------------
# Referans görseli tarif: task-8-brief.md (ajan görseli görmedi, tarif bağlayıcı). Birebir kopya
# beklenmiyor -- kullanıcının onayı "benzerine yakın" yeterli. Aşağıdaki yardımcılar tarifteki unsurlara
# karşılık gelir: _hud_rail (kademeli üst/alt ray + daire/halka), _hud_label_band (sağ üst/alt yazı bandı),
# _hud_left_ruler (sol cetvel şeridi), _hud_corner_bracket (sol köşe köşebentleri), _hud_corner_motif
# (sol köşelerdeki yarı saydam mavi 'kopya kâğıdı' motifi), _hud_right_edge (sağ kenar ray+baklava+halka).
#
# TÜMÜ ctx.stage köşeleri + ctx.band'den türetilir, sabit piksel yok -- pencere her boyutta (inner negatife
# düşse bile) çökmemeli. Bunu sağlayan tek kısıt: hiçbir yerde ctx.inner'ın (negatif olabilen) genişlik/
# yüksekliğiyle BÖLME yapılmaz; bölmeler yalnız ctx.band (her zaman > 0, paint_hud'a girmeden önce
# denetlenir) ve sabit sayılarladır (bkz. paint_hud'un baştaki koruması).

def _hud_rail_anchor_y(stage: QRect, band: int, top: bool) -> int:
    """Üst/alt rayın kademe ÖNCESİ dayandığı y: paint_hud VE testler (bkz. _hud_rail_geometry) AYNI
    sabiti kullansın diye _hud_rail'den ayrı bir fonksiyonda tutulur -- elle kopyalanmasın."""
    return stage.top() + round(band * 0.42) if top else stage.bottom() - round(band * 0.42)


def _hud_rail_geometry(stage: QRect, band: int, y: int, sign: int) -> tuple[float, float, float, float]:
    """_hud_rail'in çizdiği kademe/ikinci-çizgi/nokta dizisinin SAYISAL geometrisi (hiçbir şey çizmez).
    Boyacı (_hud_rail) VE testler AYNI formülü kullansın diye ayrıldı (review bulgusu): bir piksel probu
    yalnız rayın kendisinin ulaşabileceği bir koordinatı (özellikle kademeli çizginin y'si, y2) hedeflemek
    istiyorsa bunu elle kopyalamak yerine buradan almalı -- yoksa _hud_rail devre dışı bırakıldığında (ya
    da geometrisi değiştiğinde) test farkı fark etmeyebilir (bkz. task-8-report.md, "IMPORTANT 2" bulgusu).
    Döndürür: (notch, y2, by, span) -- y2: kademeli çizginin/ortadaki nokta+halkanın y'si; by: ikinci
    (parlak mavi) çizginin y'si; span: dolu noktaların yayıldığı x aralığı (ortası tam stage.center().x())."""
    step = max(4, band // 3)
    notch = min(max(band * 2, 30), max(1, stage.width() // 3))
    y2 = y + sign * step
    by = y2 - sign * max(3, band // 8)
    span = (stage.right() - notch * 1.1) - (stage.left() + notch * 1.1)
    return notch, y2, by, span


def _hud_rail(p: QPainter, stage: QRect, band: int, y: int, sign: int) -> None:
    """Üst/alt ray: ince lacivert yatay çizgi, iki uçta kademeli kırılma; hemen üstünde/altında daha kısa
    parlak mavi ikinci çizgi; üzerinde birkaç dolu daire ve bir halka. sign=+1 üst ray (çentik aşağı iner,
    ikinci çizgi üstte), sign=-1 alt ray (üstün dikey aynası: çentik yukarı, ikinci çizgi altta).
    Geometri _hud_rail_geometry'den gelir (testlerle paylaşılan TEK kaynak, bkz. orada)."""
    mid, blue = QColor(theme.HUD_MID), QColor(theme.HUD_BLUE)
    notch, y2, by, span = _hud_rail_geometry(stage, band, y, sign)
    x0, x1 = stage.left(), stage.right()
    p.setPen(QPen(mid, max(1.0, band / 18)))
    p.drawLine(QPointF(x0 + notch * 0.5, y), QPointF(x0 + notch, y2))
    p.drawLine(QPointF(x0 + notch, y2), QPointF(x1 - notch, y2))
    p.drawLine(QPointF(x1 - notch, y2), QPointF(x1 - notch * 0.5, y))
    p.setPen(QPen(blue, max(1.0, band / 26)))
    p.drawLine(QPointF(x0 + notch * 1.3, by), QPointF(x1 - notch * 1.3, by))
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(mid)
    for frac in (0.2, 0.4, 0.6, 0.8):
        p.drawEllipse(QPointF(x0 + notch * 1.1 + span * frac, y2), 2.4, 2.4)
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(mid, 1.4))
    p.drawEllipse(QPointF(x0 + notch * 1.1 + span * 0.5, y2), 5.0, 5.0)     # halka, ortadaki noktayı çevreler


def _hud_label_band(p: QPainter, stage: QRect, band: int, fam: FontFamilies, text: str, top: bool) -> None:
    """Sağ üst (top=True, sunucu adı) / sağ alt (top=False, marka) köşede içi dolu lacivert bant: sol kenarı
    eğik (paralelkenar gibi), beyaz büyük harf yazı bandın genişliğine göre ortalanır. Solunda birkaç eğik
    taksim çizgisi (///), köşenin en ucunda küçük bir halka. Metin boşsa (frame_titles ya da brand/presenter
    anahtarı kapalı) bant yine de çizilir, yalnız içi boş kalır -- WorkArea boş dize geçer (bkz. work_area.py
    paintEvent)."""
    ink = QColor(theme.HUD_INK)
    h = max(14, round(band * 0.86))
    skew = round(h * 0.55)
    label = theme.tr_upper(text) if text.strip() else ""
    font = theme.font(fam, max(8, round(band * 0.32)), 700, spacing_pct=104)
    text_w = QFontMetrics(font).horizontalAdvance(label) if label else 0
    w = max(h * 1.6, text_w + h)
    right = stage.right()
    y = stage.top() if top else stage.bottom() - h

    path = QPainterPath()
    if top:
        path.moveTo(right - w + skew, y); path.lineTo(right, y)
        path.lineTo(right, y + h); path.lineTo(right - w, y + h)
    else:                                                              # dikey ayna: eğik köşe alta geçer
        path.moveTo(right - w, y); path.lineTo(right, y)
        path.lineTo(right, y + h); path.lineTo(right - w + skew, y + h)
    path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(ink)
    p.drawPath(path)

    p.setPen(QPen(ink, max(1.0, band / 20)))                            # taksim çizgileri
    for i in range(3):
        tx = right - w - band * 0.3 - i * band * 0.24
        p.drawLine(QPointF(tx, y + h * 0.9), QPointF(tx + h * 0.45, y + h * 0.1))

    p.setPen(QPen(ink, 1.4)); p.setBrush(Qt.BrushStyle.NoBrush)          # köşenin ucunda küçük halka
    p.drawEllipse(QPointF(right - 3, y if top else y + h), 3.2, 3.2)

    if label:
        p.setPen(QColor(theme.PANEL)); p.setFont(font)
        p.drawText(QRectF(right - w, y, w, h), Qt.AlignmentFlag.AlignCenter, label)


def _hud_left_ruler(p: QPainter, stage: QRect, band: int) -> None:
    """Sol kenar: dikey cetvel/çentik şeridi -- farklı uzunlukta kısa yatay çizgiler, kenarın üst-orta
    bölgesinde."""
    ink = QColor(theme.HUD_INK)
    x = stage.left() + band * 0.3
    top = stage.top() + band * 1.8
    length = max(1.0, stage.height() * 0.22)
    n = 7
    p.setPen(QPen(ink, max(1.0, band / 24)))
    for i in range(n):
        y = top + i * (length / (n - 1))
        w = band * (0.5 if i % 2 == 0 else 0.28)
        p.drawLine(QPointF(x, y), QPointF(x + w, y))


def _hud_corner_bracket(p: QPainter, x: int, y: int, band: int, sy: int) -> None:
    """Kalın açılı köşebent (yalnız sol köşeler): yatay kol sağa, dikey kol sy yönünde -- köşeyi saran L
    biçimi, lacivertten açık maviye degrade. sy=+1 sol üst (kol aşağı), sy=-1 sol alt (kol yukarı, ayna).
    Kollar bant kalınlığını AŞMAZ (uzunluk < band): tahta alanı (ctx.inner) boş beyaz kalmalı."""
    length = max(16, round(band * 0.85))
    thick = max(3, round(band * 0.16))
    grad = QLinearGradient(x, y, x + length, y + sy * length)
    grad.setColorAt(0.0, QColor(theme.HUD_INK)); grad.setColorAt(1.0, QColor(theme.HUD_SOFT))
    p.setPen(QPen(QBrush(grad), thick))
    p.drawLine(QPointF(x, y), QPointF(x + length, y))
    p.drawLine(QPointF(x, y), QPointF(x, y + sy * length))


def _hud_corner_motif(p: QPainter, x: int, y: int, band: int, sy: int) -> None:
    """'Mavi kopya kâğıdı' motifi (sol üst/alt köşe): yarı saydam üçgen kama + üstünde ince daire yayları +
    yayların üzerinde küçük noktalar, ince bir çizgiyle birleşir. sy=+1 sol üst (kama aşağı iner), sy=-1
    sol alt (dikey ayna). Boyut bant kalınlığını AŞMAZ (tahta boş beyaz kalsın diye)."""
    size = max(20, round(band * 0.95))
    soft = QColor(theme.HUD_SOFT); soft.setAlpha(85)
    wedge = QPainterPath()
    wedge.moveTo(x, y); wedge.lineTo(x + size, y); wedge.lineTo(x, y + sy * size)
    wedge.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(soft)
    p.drawPath(wedge)
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(theme.HUD_SOFT), 1.2))
    for r in (size * 0.45, size * 0.75):
        p.drawArc(QRectF(x - r, y - r, 2 * r, 2 * r), 0, sy * 90 * 16)
    p1 = QPointF(x + size * 0.55, y + sy * size * 0.22)
    p2 = QPointF(x + size * 0.32, y + sy * size * 0.5)
    p.setPen(QPen(QColor(theme.HUD_MID), 0.8)); p.drawLine(p1, p2)
    p.setPen(QPen(QColor(theme.HUD_MID), 1.0)); p.setBrush(QColor(theme.HUD_MID))
    p.drawEllipse(p1, 1.8, 1.8); p.drawEllipse(p2, 1.8, 1.8)


def _hud_right_edge(p: QPainter, stage: QRect, band: int) -> None:
    """Sağ kenar: ortada dikey lacivert ray parçası + baklava (çevron) biçimi, altında bir halka."""
    mid = QColor(theme.HUD_MID)
    cx = stage.right() - band * 0.5
    cy = stage.center().y()
    length = band * 1.8
    p.setPen(QPen(mid, max(1.0, band / 16)))
    p.drawLine(QPointF(cx, cy - length / 2), QPointF(cx, cy + length / 2))
    s = band * 0.26
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(mid)
    p.drawPolygon(QPolygonF([QPointF(cx, cy - s), QPointF(cx + s, cy), QPointF(cx, cy + s), QPointF(cx - s, cy)]))
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(mid, 1.4))
    p.drawEllipse(QPointF(cx, cy + length / 2 + s * 1.8), s * 0.7, s * 0.7)


def paint_hud(p: QPainter, ctx: FrameContext) -> None:
    """HUD çerçevesi (Görev 8): beyaz zemin üstünde lacivert 'teknik çizim' bandı -- kademeli üst/alt
    raylar, sağ üst/alt yazı bantları (sunucu adı/marka), sol cetvel şeridi, sol köşe köşebentleri ve yarı
    saydam mavi köşe motifleri (tarif: task-8-brief.md). Birebir kopya değil, 'benzerine yakın' yeterli
    (kullanıcının onayı). TÜM koordinatlar ctx.stage + ctx.band'den türetilir; pencere her boyutta -- çok
    küçük olsa, hatta ctx.inner negatife düşse bile -- çökmeden çalışmalı (bkz. hemen altındaki koruma:
    stage/band geçersizse yalnız beyaz zemin kalır, daha ileri gidilmez)."""
    p.fillRect(ctx.rect, QColor(theme.PANEL))
    stage, band = ctx.stage, ctx.band
    if stage.width() <= 0 or stage.height() <= 0 or band <= 0:
        return
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _hud_rail(p, stage, band, _hud_rail_anchor_y(stage, band, top=True), +1)
    _hud_rail(p, stage, band, _hud_rail_anchor_y(stage, band, top=False), -1)
    _hud_label_band(p, stage, band, ctx.fam, ctx.presenter, top=True)
    _hud_label_band(p, stage, band, ctx.fam, ctx.brand, top=False)
    _hud_left_ruler(p, stage, band)
    _hud_corner_bracket(p, stage.left(), stage.top(), band, +1)
    _hud_corner_bracket(p, stage.left(), stage.bottom(), band, -1)
    _hud_corner_motif(p, stage.left(), stage.top(), band, +1)
    _hud_corner_motif(p, stage.left(), stage.bottom(), band, -1)
    _hud_right_edge(p, stage, band)


FRAME_SPECS: dict[FrameStyle, FrameSpec] = {
    FrameStyle.CLASSIC: FrameSpec("Klasik (koyu bant)", theme.FRAME_BAND, paint_classic),
    FrameStyle.HUD: FrameSpec("HUD (teknik çizim)", theme.HUD_BAND, paint_hud,
                              draws_brand=True, draws_presenter=True),
}
