"""Tanıma örneği toplama: saf (Qt'siz) kayıt mantığı. Sembol sırası, ilerleme, JSON/PNG formatı, 28x28 normalleştirme,
klasör yolu ve ZIP."""
import json
import zipfile

import numpy as np
import pytest

from matematigin_mantigi import paths
from matematigin_mantigi.core import ornek_toplama as ot


def _ink_square(size=200, x0=60, y0=40, w=80, h=120):
    img = np.zeros((size, size), np.uint8)
    img[y0:y0 + h, x0:x0 + w] = 255
    return img


def _stroke(pts):
    return [{"x": float(x), "y": float(y), "basinc": 0.5, "zaman": 0.01 * i} for i, (x, y) in enumerate(pts)]


def test_symbol_order_is_the_19_prototype_classes_without_duplicates():
    assert len(ot.SEMBOLLER) == 19
    assert len(set(ot.SEMBOLLER)) == 19
    assert ot.SEMBOLLER[:10] == tuple("0123456789")
    assert set(ot.SEMBOLLER[10:]) == {"+", "−", "×", "÷", "=", "(", ")", "x", "y"}


def test_target_is_30_per_symbol_and_adjustable():
    assert ot.HEDEF_ORNEK == 30
    sayilar = {s: 30 for s in ot.SEMBOLLER}
    assert ot.ilerleme(sayilar) == (19 * 30, 19 * 30)
    assert ot.ilerleme({"0": 7}) == (7, 19 * 30)


def test_next_symbol_wraps_and_keeps_order():
    assert ot.sonraki_sembol(0) == 1
    assert ot.sonraki_sembol(len(ot.SEMBOLLER) - 1) == 0


def test_folder_is_user_data_dir_tanima_ornekleri(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    assert paths.default_tanima_ornek_root() == tmp_path / "tanima-ornekleri"
    assert ot.ornek_koku() == tmp_path / "tanima-ornekleri"


def test_normalize_is_28x28_uint8_and_centered_with_prototype_margin():
    out = ot.normalle(_ink_square())
    assert out.shape == (28, 28) and out.dtype == np.uint8
    ys, xs = np.where(out > 30)
    assert len(xs) > 0
    # Prototip: 24/32 iç kutu -> 28 tuvalde 21 px iç kutu; çizim bu kutuya sığar ve ortalanır.
    assert xs.max() - xs.min() + 1 <= 21 and ys.max() - ys.min() + 1 <= 21
    assert abs((xs.min() + xs.max()) / 2 - 13.5) <= 1.0
    assert abs((ys.min() + ys.max()) / 2 - 13.5) <= 1.0


def test_normalize_keeps_aspect_ratio():
    out = ot.normalle(_ink_square(w=80, h=120))
    ys, xs = np.where(out > 30)
    assert (ys.max() - ys.min()) > (xs.max() - xs.min())


def test_normalize_empty_drawing_is_all_zero():
    out = ot.normalle(np.zeros((50, 50), np.uint8))
    assert out.shape == (28, 28) and not out.any()


def test_png_roundtrip_is_gray_8bit(tmp_path):
    arr = np.arange(28 * 28, dtype=np.uint8).reshape(28, 28)
    p = tmp_path / "a.png"
    ot.png_yaz(p, arr)
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert np.array_equal(ot.png_oku(p), arr)


def test_save_sample_writes_json_and_28x28_png_with_expected_fields(tmp_path):
    cizgiler = [_stroke([(10, 10), (20, 30), (30, 60)]), _stroke([(50, 10), (50, 60)])]
    j, p = ot.ornek_kaydet(tmp_path, "7", cizgiler, _ink_square(), zaman="20261113-120000")
    assert j.parent == tmp_path / "7" and p.parent == tmp_path / "7"
    assert j.name == "7_20261113-120000_1.json" and p.name == "7_20261113-120000_1.png"
    veri = json.loads(j.read_text(encoding="utf-8"))
    assert veri["sembol"] == "7" and veri["sinif_indeksi"] == 7
    assert len(veri["cizgiler"]) == 2
    nokta = veri["cizgiler"][0][0]
    assert set(nokta) == {"x", "y", "basinc", "zaman"}
    assert set(veri["cizgi_sinirlari"]) == {"x0", "y0", "x1", "y1"}
    assert veri["cizgi_sinirlari"]["x0"] == 10 and veri["cizgi_sinirlari"]["x1"] == 50
    assert veri["cizim_kutu_boyutu"] == {"genislik": 41, "yukseklik": 51}
    assert veri["png"] == p.name
    assert ot.png_oku(p).shape == (28, 28)


def test_save_sample_numbers_do_not_overwrite(tmp_path):
    c = [_stroke([(1, 1), (5, 5)])]
    a, _ = ot.ornek_kaydet(tmp_path, "x", c, _ink_square(), zaman="T")
    b, _ = ot.ornek_kaydet(tmp_path, "x", c, _ink_square(), zaman="T")
    assert a.name.endswith("_1.json") and b.name.endswith("_2.json")


def test_save_rejects_unknown_symbol_and_empty_drawing(tmp_path):
    c = [_stroke([(1, 1), (5, 5)])]
    with pytest.raises(ValueError):
        ot.ornek_kaydet(tmp_path, "Z", c, _ink_square())
    with pytest.raises(ValueError):
        ot.ornek_kaydet(tmp_path, "1", [], _ink_square())
    assert not any(tmp_path.iterdir())


def test_counts_read_from_folder_and_zip_contains_all_samples(tmp_path):
    root = tmp_path / "tanima-ornekleri"
    c = [_stroke([(1, 1), (5, 5)])]
    ot.ornek_kaydet(root, "1", c, _ink_square(), zaman="T")
    ot.ornek_kaydet(root, "1", c, _ink_square(), zaman="T")
    ot.ornek_kaydet(root, "+", c, _ink_square(), zaman="T")
    sayilar = ot.ornek_sayilari(root)
    assert sayilar["1"] == 2 and sayilar["+"] == 1 and sayilar["0"] == 0
    assert ot.ilerleme(sayilar)[0] == 3

    zip_yolu = ot.zip_olustur(root, tmp_path / "disa.zip")
    with zipfile.ZipFile(zip_yolu) as z:
        names = sorted(z.namelist())
    assert "1/" + sorted(p.name for p in (root / "1").iterdir())[0] in names
    assert sum(n.endswith(".png") for n in names) == 3
    assert sum(n.endswith(".json") for n in names) == 3


def test_reader_returns_label_and_image_for_folder_and_zip(tmp_path):
    root = tmp_path / "tanima-ornekleri"
    c = [_stroke([(1, 1), (5, 5)])]
    ot.ornek_kaydet(root, "(", c, _ink_square(), zaman="T")
    ot.ornek_kaydet(root, "y", c, _ink_square(), zaman="T")
    for kaynak in (root, ot.zip_olustur(root, tmp_path / "k.zip")):
        ornekler = ot.ornekleri_oku(kaynak)
        etiketler = sorted(e for e, _ in ornekler)
        assert etiketler == ["(", "y"]
        assert all(img.shape == (28, 28) for _, img in ornekler)


def _png_filtreli(satirlar: list[bytes], filtre_fn) -> bytes:
    import struct
    import zlib

    def parca(tip, veri):
        return struct.pack(">I", len(veri)) + tip + veri + struct.pack(">I", zlib.crc32(tip + veri) & 0xFFFFFFFF)

    h, w = len(satirlar), len(satirlar[0])
    ham = b""
    onceki = bytes(w)
    for y, satir in enumerate(satirlar):
        ftip, kodlu = filtre_fn(satir, onceki)
        ham += bytes([ftip]) + kodlu
        onceki = satir
    return (b"\x89PNG\r\n\x1a\n" + parca(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + parca(b"IDAT", zlib.compress(ham)) + parca(b"IEND", b""))


@pytest.mark.parametrize("ftip", [0, 1, 2, 3, 4])
def test_png_decoder_handles_all_five_filter_types(ftip):
    def paeth(a, b, c):
        p = a + b - c
        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
        return a if pa <= pb and pa <= pc else (b if pb <= pc else c)

    def kodla(satir, onceki):
        out = bytearray()
        for k, x in enumerate(satir):
            a = satir[k - 1] if k else 0
            b = onceki[k]
            c = onceki[k - 1] if k else 0
            pred = {0: 0, 1: a, 2: b, 3: (a + b) // 2, 4: paeth(a, b, c)}[ftip]
            out.append((x - pred) & 0xFF)
        return ftip, bytes(out)

    rng = np.random.default_rng(ftip)
    satirlar = [bytes(rng.integers(0, 256, 28, dtype=np.uint8)) for _ in range(28)]
    bayt = _png_filtreli(satirlar, kodla)
    beklenen = np.array([list(s) for s in satirlar], np.uint8)
    assert np.array_equal(ot.png_coz(bayt), beklenen)
