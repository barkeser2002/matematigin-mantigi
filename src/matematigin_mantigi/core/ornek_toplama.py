"""Tanıma örneği toplama: saf (Qt'siz) kayıt mantığı.

Her örnek iki dosya olarak yazılır: `<koku>/<sembol>/<sembol>_<zaman>_<n>.json` (çizgiler, sınırlar, boyut) ve aynı adla
28x28 gri `.png` (eğitim girdisi). Normalleştirme prototipteki (mm-tanima/symbol/train.py normalize) mantıktır: >30
piksel kutusu kırpılır, en-boy oranı korunarak iç kutuya küçültülür, tuvalde ortalanır. Prototip 32x32 tuvalde 24x24 iç
kutu kullanıyordu; burada 28x28 tuvalde orantılı 21x21 iç kutu kullanılır. Küçültme PIL yerine numpy ile yapılır
(yeni bağımlılık yok), bu yüzden LANCZOS ile piksel düzeyinde birebir aynı değildir.
"""
from __future__ import annotations

import json
import struct
import time
import zipfile
import zlib
from pathlib import Path

import numpy as np

from matematigin_mantigi import paths

SEMBOLLER: tuple[str, ...] = (
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "+", "−", "×", "÷", "=", "(", ")", "x", "y",
)
HEDEF_ORNEK = 30            # her sembol için hedef sayı (ayarlanabilir sabit)
KANVAS_BOYUT = 28           # eğitim girdisi
_ESIK = 30            # prototipteki mürekkep eşiği (>30)


def ornek_koku() -> Path:
    return paths.default_tanima_ornek_root()


def sonraki_sembol(indeks: int) -> int:
    return (indeks + 1) % len(SEMBOLLER)


def ilerleme(sayilar: dict[str, int]) -> tuple[int, int]:
    """(toplanan, hedef toplam) — hedef toplam sembol sayısı × HEDEF_ORNEK."""
    toplam = sum(min(sayilar.get(s, 0), HEDEF_ORNEK) for s in SEMBOLLER)
    return toplam, len(SEMBOLLER) * HEDEF_ORNEK


def _yeniden_boyutla(a: np.ndarray, h2: int, w2: int) -> np.ndarray:
    """Çift doğrusal (bilinear) küçültme/büyütme, numpy ile."""
    h, w = a.shape
    ys = (np.arange(h2) + 0.5) * h / h2 - 0.5
    xs = (np.arange(w2) + 0.5) * w / w2 - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, h - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    x1 = np.clip(x0 + 1, 0, w - 1)
    wy = np.clip(ys - y0, 0, 1)[:, None]
    wx = np.clip(xs - x0, 0, 1)[None, :]
    f = a.astype(np.float64)
    top = f[y0][:, x0] * (1 - wx) + f[y0][:, x1] * wx
    bot = f[y1][:, x0] * (1 - wx) + f[y1][:, x1] * wx
    return top * (1 - wy) + bot * wy


def normalle(gri: np.ndarray, boyut: int = KANVAS_BOYUT) -> np.ndarray:
    """Tuval gri görüntüsünü (mürekkep parlak) eğitim girdisine çevirir: uint8, boyut×boyut."""
    a = np.asarray(gri, dtype=np.uint8)
    yy, xx = np.where(a > _ESIK)
    if len(xx) == 0:
        return np.zeros((boyut, boyut), np.uint8)
    kirpik = a[yy.min():yy.max() + 1, xx.min():xx.max() + 1]
    h, w = kirpik.shape
    ici = round(24 * boyut / 32)
    olcek = min(1.0, ici / w, ici / h)
    h2, w2 = max(1, round(h * olcek)), max(1, round(w * olcek))
    kucuk = np.clip(_yeniden_boyutla(kirpik, h2, w2), 0, 255).round().astype(np.uint8)
    cikti = np.zeros((boyut, boyut), np.uint8)
    oy, ox = (boyut - h2) // 2, (boyut - w2) // 2
    cikti[oy:oy + h2, ox:ox + w2] = kucuk
    return cikti


def png_yaz(yol: Path, arr: np.ndarray) -> None:
    """8-bit gri PNG (stdlib: zlib + struct). Yeni bağımlılık yok."""
    a = np.asarray(arr, dtype=np.uint8)
    h, w = a.shape

    def parca(tip: bytes, veri: bytes) -> bytes:
        return struct.pack(">I", len(veri)) + tip + veri + struct.pack(">I", zlib.crc32(tip + veri) & 0xFFFFFFFF)

    satirlar = b"".join(b"\x00" + a[i].tobytes() for i in range(h))   # filtre 0 (yok)
    png = (b"\x89PNG\r\n\x1a\n"
           + parca(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
           + parca(b"IDAT", zlib.compress(satirlar, 9))
           + parca(b"IEND", b""))
    Path(yol).write_bytes(png)


def png_oku(yol: Path) -> np.ndarray:
    return png_coz(Path(yol).read_bytes())


def png_coz(veri: bytes) -> np.ndarray:
    """8-bit gri, ilaçsız PNG'yi çözer (5 filtre türü dahil). Dış kütüphane yok."""
    if veri[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("PNG değil")
    i, idat, w, h = 8, b"", 0, 0
    while i < len(veri):
        (uzunluk,) = struct.unpack(">I", veri[i:i + 4])
        tip = veri[i + 4:i + 8]
        govde = veri[i + 8:i + 8 + uzunluk]
        if tip == b"IHDR":
            w, h, bit, renk, _, _, ilace = struct.unpack(">IIBBBBB", govde)
            if (bit, renk, ilace) != (8, 0, 0):
                raise ValueError("yalnız 8-bit gri, ilaçsız PNG desteklenir")
        elif tip == b"IDAT":
            idat += govde
        i += 12 + uzunluk
    ham = zlib.decompress(idat)
    cikti = np.zeros((h, w), np.int32)
    onceki = np.zeros(w, np.int32)
    p = 0
    for y in range(h):
        ftip = ham[p]
        x = np.frombuffer(ham[p + 1:p + 1 + w], np.uint8).astype(np.int32)
        p += 1 + w
        r = np.zeros(w, np.int32)
        for k in range(w):
            a = int(r[k - 1]) if k else 0
            b = int(onceki[k])
            c = int(onceki[k - 1]) if k else 0
            if ftip == 0:
                pred = 0
            elif ftip == 1:
                pred = a
            elif ftip == 2:
                pred = b
            elif ftip == 3:
                pred = (a + b) // 2
            elif ftip == 4:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            else:
                raise ValueError("bilinmeyen PNG filtresi")
            r[k] = (int(x[k]) + pred) & 0xFF
        cikti[y] = r
        onceki = r
    return cikti.astype(np.uint8)


def _sonraki_numara(klasor: Path, sembol: str, zaman: str) -> int:
    n = 1
    while (klasor / f"{sembol}_{zaman}_{n}.json").exists() or (klasor / f"{sembol}_{zaman}_{n}.png").exists():
        n += 1
    return n


def _sinir(cizgiler: list[list[dict]]) -> tuple[float, float, float, float]:
    xs = [n["x"] for c in cizgiler for n in c]
    ys = [n["y"] for c in cizgiler for n in c]
    return min(xs), min(ys), max(xs), max(ys)


def ornek_kaydet(koku: Path, sembol: str, cizgiler: list[list[dict]], kanvas_gri: np.ndarray,
                 zaman: str | None = None) -> tuple[Path, Path]:
    """Bir örneği JSON + 28x28 PNG olarak yazar. Geçersiz sembol ya da boş çizim ValueError verir."""
    if sembol not in SEMBOLLER:
        raise ValueError(f"bilinmeyen sembol: {sembol!r}")
    cizgiler = [c for c in cizgiler if c]
    if not cizgiler:
        raise ValueError("boş çizim kaydedilmez")
    zaman = zaman or time.strftime("%Y%m%d-%H%M%S")
    klasor = Path(koku) / sembol
    klasor.mkdir(parents=True, exist_ok=True)
    n = _sonraki_numara(klasor, sembol, zaman)
    ad = f"{sembol}_{zaman}_{n}"
    x0, y0, x1, y1 = _sinir(cizgiler)
    kanvas = np.asarray(kanvas_gri)
    veri = {
        "sembol": sembol,
        "sinif_indeksi": SEMBOLLER.index(sembol),
        "cizgiler": cizgiler,
        "cizgi_sinirlari": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
        "cizim_kutu_boyutu": {"genislik": round(x1 - x0) + 1, "yukseklik": round(y1 - y0) + 1},
        "kanvas": {"genislik": int(kanvas.shape[1]), "yukseklik": int(kanvas.shape[0])},
        "png": ad + ".png",
        "boyut_png": [KANVAS_BOYUT, KANVAS_BOYUT],
    }
    png = klasor / (ad + ".png")
    json_yolu = klasor / (ad + ".json")
    png_yaz(png, normalle(kanvas))
    json_yolu.write_text(json.dumps(veri, ensure_ascii=False, indent=1), encoding="utf-8")
    return json_yolu, png


def ornek_sayilari(koku: Path) -> dict[str, int]:
    koku = Path(koku)
    return {s: len(list((koku / s).glob("*.json"))) if (koku / s).is_dir() else 0 for s in SEMBOLLER}


def zip_olustur(koku: Path, hedef: Path) -> Path:
    """Örnek klasörünü (sembol alt klasörleri dahil) ZIP'ler. Kökün kendisi arşivde <sembol>/... olarak durur."""
    koku, hedef = Path(koku), Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(hedef, "w", zipfile.ZIP_DEFLATED) as z:
        for dosya in sorted(koku.rglob("*")):
            if dosya.is_file():
                z.write(dosya, dosya.relative_to(koku).as_posix())
    return hedef


def ornekleri_oku(kaynak: Path) -> list[tuple[str, np.ndarray]]:
    """Klasör ya da ZIP'ten (etiket, 28x28 uint8) listesi. Etiket JSON'daki 'sembol' alanıdır (klasör adı değil)."""
    kaynak = Path(kaynak)
    sonuc: list[tuple[str, np.ndarray]] = []
    if kaynak.is_dir():
        for j in sorted(kaynak.rglob("*.json")):
            veri = json.loads(j.read_text(encoding="utf-8"))
            sonuc.append((veri["sembol"], png_oku(j.with_name(veri["png"]))))
        return sonuc
    with zipfile.ZipFile(kaynak) as z:
        for ad in sorted(n for n in z.namelist() if n.endswith(".json")):
            veri = json.loads(z.read(ad).decode("utf-8"))
            png_ad = ad[: -len(".json")] + ".png"
            sonuc.append((veri["sembol"], png_coz(z.read(png_ad))))
    return sonuc
