#!/usr/bin/env python3
"""Tanıma sembol modeli eğitimi (yalnız geliştirme/eğitim; uygulamada çıkarım yok).

Girdi : tanima-ornekleri klasörü veya onun ZIP'i (birden çok verilebilir) ve isteğe bağlı --mnist.
Çıktı : numpy ağırlık dosyası (.npz). Anahtarlar: '<katman>__<i>' (ağırlık dizileri, sırayla), 'siniflar' (sembol
        sırası), 'girdi_boyutu' ([28, 28, 1]). Uygulama bu dosyayı saf numpy ile okuyacak.

Kurulum (yalnız eğitim): pip install -e ".[tanima-egitim]"   (TensorFlow uygulama bağımlılığına GİRMEZ)

Örnek:
    python tools/tanima_egit.py tanima-ornekleri.zip --epoch 15 --cikti tanima_agirliklari.npz
    python tools/tanima_egit.py ornekler/ --mnist --cikti tanima_agirliklari.npz

MNIST notu: MNIST CC BY-SA 3.0 lisanslıdır (atıf + ShareAlike). --mnist ile üretilen ağırlıkların dağıtımı için
hukuki değerlendirme gerekir; varsayılan çalıştırmada MNIST KULLANILMAZ.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

try:  # depo kökünden çalıştırıldığında paket kurulu olmayabilir
    from matematigin_mantigi.core import ornek_toplama as ot
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from matematigin_mantigi.core import ornek_toplama as ot

BOYUT = ot.KANVAS_BOYUT
SINIF_SAYISI = len(ot.SEMBOLLER)


def topla(kaynaklar) -> tuple[np.ndarray, np.ndarray, int]:
    """Klasör/ZIP kaynaklarını birleştirir. (X float32 (N,28,28,1) [0,1], y int (N,), atlanan sayısı).
    Bilinmeyen etiket atlanır ve sayılır; sessizce yutulmaz."""
    goruntuler, etiketler, atlanan = [], [], 0
    index = {s: i for i, s in enumerate(ot.SEMBOLLER)}
    for k in kaynaklar:
        for sembol, img in ot.ornekleri_oku(Path(k)):
            if sembol not in index:
                atlanan += 1
                continue
            goruntuler.append(img)
            etiketler.append(index[sembol])
    if not goruntuler:
        return np.zeros((0, BOYUT, BOYUT, 1), np.float32), np.zeros(0, np.int64), atlanan
    X = np.stack(goruntuler).astype(np.float32)[..., None] / 255.0
    return X, np.asarray(etiketler, np.int64), atlanan


def mnist_al(ornek: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """MNIST eğitim kümesinden rastgele `ornek` tane (0-9 etiketleri, sembol sırasıyla aynı indeks)."""
    import tensorflow as tf  # tembel import: yalnız --mnist ile
    (x, y), _ = tf.keras.datasets.mnist.load_data()
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))[:ornek]
    return x[idx].astype(np.float32)[..., None] / 255.0, y[idx].astype(np.int64)


def bol(X: np.ndarray, y: np.ndarray, *, oran: float, seed: int):
    """Tohumlu karıştırma ile eğitim/doğrulama bölmesi. ((Xt, yt), (Xv, yv))."""
    rng = np.random.default_rng(seed)
    p = rng.permutation(len(y))
    n = int(round(len(y) * oran))
    t, v = p[:n], p[n:]
    return (X[t], y[t]), (X[v], y[v])


def npz_yaz(yol: Path, katmanlar: dict[str, list[np.ndarray]], siniflar) -> None:
    """Katman adı -> ağırlık listesi sözlüğünü numpy .npz'ye yazar (TF'siz)."""
    veri: dict[str, np.ndarray] = {}
    for ad, dizi in katmanlar.items():
        for i, w in enumerate(dizi):
            veri[f"{ad}__{i}"] = np.asarray(w)
    veri["siniflar"] = np.asarray(list(siniflar))
    veri["girdi_boyutu"] = np.asarray([BOYUT, BOYUT, 1], np.int64)
    Path(yol).parent.mkdir(parents=True, exist_ok=True)
    np.savez(yol, **veri)


def model_kur():
    """Küçük CNN (28x28 gri -> 19 sınıf). TF'yi burada import eder."""
    import tensorflow as tf
    return tf.keras.Sequential([
        tf.keras.layers.InputLayer(input_shape=(BOYUT, BOYUT, 1), name="girdi"),
        tf.keras.layers.Conv2D(16, 3, padding="same", activation="relu", name="conv1"),
        tf.keras.layers.MaxPooling2D(2, name="havuz1"),
        tf.keras.layers.Conv2D(32, 3, padding="same", activation="relu", name="conv2"),
        tf.keras.layers.MaxPooling2D(2, name="havuz2"),
        tf.keras.layers.Flatten(name="duzlestir"),
        tf.keras.layers.Dense(64, activation="relu", name="dense1"),
        tf.keras.layers.Dense(SINIF_SAYISI, activation="softmax", name="cikti"),
    ])


def egit(args) -> dict:
    import tensorflow as tf
    tf.keras.utils.set_random_seed(args.seed)
    X, y, atlanan = topla(args.kaynak)
    if args.mnist:
        mx, my = mnist_al(args.mnist_ornek, args.seed)
        X, y = np.concatenate([X, mx]), np.concatenate([y, my])
    if len(y) < 10:
        raise SystemExit(f"Yetersiz örnek: {len(y)} (atlanan etiket: {atlanan})")
    (Xt, yt), (Xv, yv) = bol(X, y, oran=0.85, seed=args.seed)
    model = model_kur()
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"])
    gecmis = model.fit(Xt, yt, validation_data=(Xv, yv), epochs=args.epoch, batch_size=args.batch, verbose=2)
    katmanlar = {katman.name: [w.numpy() for w in katman.weights] for katman in model.layers if katman.weights}
    npz_yaz(args.cikti, katmanlar, ot.SEMBOLLER)
    son = {k: float(v[-1]) for k, v in gecmis.history.items()}
    return {"ornek": int(len(y)), "egitim": int(len(yt)), "dogrulama": int(len(yv)), "atlanan": atlanan,
            "son_metrikler": son, "cikti": str(args.cikti)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Tanıma sembol modeli eğitimi (yalnız eğitim).")
    p.add_argument("kaynak", nargs="+", type=Path, help="tanima-ornekleri klasörü ya da ZIP (birden çok olabilir)")
    p.add_argument("--mnist", action="store_true", help="MNIST rakamlarını da ekle (ShareAlike; bkz. üst not)")
    p.add_argument("--mnist-ornek", type=int, default=3000)
    p.add_argument("--epoch", type=int, default=15)
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--cikti", type=Path, default=Path("tanima_agirliklari.npz"))
    args = p.parse_args(argv)
    ozet = egit(args)
    print(ozet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
