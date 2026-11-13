"""tools/tanima_egit.py saf kısmı: ZIP/klasör okuma, veri birleştirme, bölme, npz yazımı. TensorFlow gerekmez."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from matematigin_mantigi.core import ornek_toplama as ot

BETIK = Path(__file__).resolve().parents[1] / "tools" / "tanima_egit.py"


@pytest.fixture(scope="module")
def egit():
    spec = importlib.util.spec_from_file_location("tanima_egit", BETIK)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tanima_egit"] = mod
    spec.loader.exec_module(mod)
    return mod


def _ornek(koku, sembol, n=1):
    c = [[{"x": 1.0, "y": 1.0, "basinc": 1.0, "zaman": 0.0}, {"x": 20.0, "y": 30.0, "basinc": 1.0, "zaman": 0.1}]]
    gri = np.zeros((100, 100), np.uint8)
    gri[20:60, 20:25] = 255
    for _ in range(n):
        ot.ornek_kaydet(koku, sembol, c, gri, zaman="T")


def test_script_has_no_module_level_tensorflow_import():
    kaynak = BETIK.read_text(encoding="utf-8")
    ust_seviye = [s for s in kaynak.splitlines() if s.startswith(("import tensorflow", "from tensorflow"))]
    assert ust_seviye == []          # TF yalnız eğitimde, fonksiyon içinde import edilir


def test_reads_folder_and_zip_into_normalized_float_tensor(egit, tmp_path):
    koku = tmp_path / "tanima-ornekleri"
    _ornek(koku, "1", 2)
    _ornek(koku, "x", 1)
    for kaynak in (koku, ot.zip_olustur(koku, tmp_path / "a.zip")):
        X, y, atlanan = egit.topla([kaynak])
        assert X.shape == (3, 28, 28, 1) and X.dtype == np.float32
        assert 0.0 <= X.min() and X.max() <= 1.0
        assert sorted(ot.SEMBOLLER[i] for i in y) == ["1", "1", "x"]
        assert atlanan == 0


def test_unknown_label_is_skipped_and_counted(egit, tmp_path):
    koku = tmp_path / "tanima-ornekleri"
    _ornek(koku, "2", 1)
    veri = json.loads(next(koku.rglob("*.json")).read_text(encoding="utf-8"))
    veri["sembol"] = "Q"                       # bilinmeyen etiket
    next(koku.rglob("*.json")).write_text(json.dumps(veri), encoding="utf-8")
    X, y, atlanan = egit.topla([koku])
    assert len(y) == 0 and atlanan == 1


def test_multiple_sources_are_merged_in_order(egit, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _ornek(a, "3", 1)
    _ornek(b, "4", 2)
    X, y, _ = egit.topla([a, b])
    assert [ot.SEMBOLLER[i] for i in y] == ["3", "4", "4"]


def test_split_is_seeded_and_keeps_all_rows(egit):
    y = np.arange(100) % 19
    X = np.zeros((100, 28, 28, 1), np.float32)
    tr1, va1 = egit.bol(X, y, oran=0.8, seed=7)
    tr2, va2 = egit.bol(X, y, oran=0.8, seed=7)
    assert len(tr1[1]) + len(va1[1]) == 100 and len(tr1[1]) == 80
    assert np.array_equal(tr1[1], tr2[1]) and np.array_equal(va1[1], va2[1])


def test_npz_export_keys_and_content(egit, tmp_path):
    katmanlar = {
        "conv1": [np.ones((3, 3, 1, 12), np.float32), np.zeros(12, np.float32)],
        "dense": [np.ones((4, 19), np.float32), np.zeros(19, np.float32)],
    }
    yol = tmp_path / "w.npz"
    egit.npz_yaz(yol, katmanlar, ot.SEMBOLLER)
    with np.load(yol) as z:
        anahtarlar = set(z.files)
        assert {"conv1__0", "conv1__1", "dense__0", "dense__1", "siniflar", "girdi_boyutu"} <= anahtarlar
        assert z["conv1__0"].shape == (3, 3, 1, 12)
        assert list(z["siniflar"]) == list(ot.SEMBOLLER)
        assert list(z["girdi_boyutu"]) == [28, 28, 1]


def test_zip_and_folder_datasets_have_same_label_counts(egit, tmp_path):
    koku = tmp_path / "tanima-ornekleri"
    _ornek(koku, "+", 3)
    _ornek(koku, "=", 1)
    X1, y1, _ = egit.topla([koku])
    X2, y2, _ = egit.topla([ot.zip_olustur(koku, tmp_path / "z.zip")])
    assert sorted(y1.tolist()) == sorted(y2.tolist())
