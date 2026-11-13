"""Şekil düzeltme ölçümü: kalem çizgisi politikası (correct_stroke) sentetik veride ne kadar doğru/yanlış kabul eder.

Çalıştırma (kök dizinde):  .venv/bin/python scripts/sekil_olcum.py --out $TMPDIR/sekil.json

Veri: prototipteki (mm-tanima/shape/bench.py) sentetik üreticilerle aynı aileler + el yazısı benzeri kıvrımlı
yazı. Etiketler üreticinin niyetidir; gerçek insan çizimi DEĞİLDİR. Doğruluk: pozitif örneklerin beklenen
türle eşleşmesi (tanınmayan = hata). Yanlış kabul: serbest/negatif çizimin herhangi bir şekle dönmesi.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from matematigin_mantigi.core.shape_recognition import correct_stroke


CLASSES = ['line', 'circle', 'ellipse', 'triangle', 'rectangle', 'polygon']
LABELS = CLASSES + ['unknown']


def resample_at(p, fractions):
    distances = np.r_[0., np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    distances /= distances[-1]
    return np.column_stack([np.interp(fractions, distances, p[:, j]) for j in range(2)])


def rounded_polygon(vertices, rounding):
    """Her köşede quadratic Bézier; kalan kenarlar düz, yuvarlama oranı 0..0.16."""
    parts = []
    for i, b in enumerate(vertices):
        a, c = vertices[i-1], vertices[(i+1) % len(vertices)]
        before, after = b + rounding*(a-b), b + rounding*(c-b)
        t = np.linspace(0, 1, 30, endpoint=False)[:, None]
        parts.append((1-t)**2*before + 2*(1-t)*t*b + t*t*after)
        next_before = c + rounding*(b-c)
        parts.append(after + t*(next_before-after))
    p = np.vstack(parts)
    return np.vstack([p, p[0]])


def generate_shape(kind, rng, index):
    sigma = float(rng.uniform(1, 4))
    regime = index % 10
    size = float(rng.uniform(35, 70) if regime == 0 else
                 rng.uniform(700, 1200) if regime == 1 else rng.uniform(80, 550))
    rotation = float(rng.uniform(-np.pi, np.pi))
    rounding = float(rng.uniform(0, 0.16))
    gap = float(rng.uniform(0, 0.035))  # çevre uzunluğu payı, bbox payı DEĞİL
    count = int(rng.integers(35, 701))
    aspect = 1.
    subtype = kind
    if kind == 'line':
        p = np.column_stack([np.linspace(-.5, .5, 800), np.zeros(800)])
        # Hafif kavisli çizme; büyük eğrilikler doğru olarak reddedilebilir.
        p[:, 1] += rng.uniform(-0.014, 0.014)*np.sin(np.linspace(0, np.pi, len(p)))
        rounding, gap = 0., 0.
    elif kind in ('circle', 'ellipse'):
        aspect = 1. if kind == 'circle' else float(rng.uniform(.22, .84))
        a = np.linspace(0, 2*np.pi, 1400)
        p = np.column_stack([.5*np.cos(a), .5*aspect*np.sin(a)])
        rounding = 0.
    else:
        if kind == 'triangle':
            vertices = np.array([[-.5, -.35], [.5, -.35], [rng.uniform(-.32, .32), rng.uniform(.3, .65)]])
            aspect = float(rng.uniform(.45, 1.2))
            vertices[:, 1] *= aspect
        elif kind == 'rectangle':
            aspect = 1. if index % 4 == 0 else float(rng.uniform(.22, .95))
            subtype = 'square' if aspect == 1. else 'rectangle'
            vertices = np.array([[-.5, -.5*aspect], [.5, -.5*aspect], [.5, .5*aspect], [-.5, .5*aspect]])
        else:
            n = 5 + index % 3
            regular = index % 2 == 0
            subtype = ('regular' if regular else 'irregular') + '_' + str(n)
            angles = np.arange(n)*2*np.pi/n
            if not regular:
                angles += rng.uniform(-.15, .15, n)
            radii = np.ones(n)*.5 if regular else rng.uniform(.29, .58, n)
            # Bazı düzensiz şekiller içbükeydir.
            if not regular and index % 5 == 0:
                radii[index % n] *= .6
            vertices = np.column_stack([radii*np.cos(angles), radii*np.sin(angles)])
        p = rounded_polygon(vertices, rounding)
    # Kapalı şekiller rastgele fazda başlar; gap bazen köşenin üzerinden geçer.
    if kind != 'line':
        base = resample_at(p, np.linspace(0, 1, 1401))[:-1]
        base = np.roll(base, int(rng.integers(len(base))), axis=0)
        p = np.vstack([base, base[0]])
    # Gamma aralıkları: tablet hızından kaynaklanan düzensiz örnekleme yoğunluğu.
    intervals = rng.gamma(rng.uniform(.5, 3.), 1., count-1)
    u = np.r_[0., np.cumsum(intervals)]
    u = u/u[-1]*(1-gap)
    p = resample_at(p, u)
    matrix = np.array([[np.cos(rotation), -np.sin(rotation)], [np.sin(rotation), np.cos(rotation)]])
    origin = rng.uniform(-2000, 4000, 2)
    p = p @ matrix.T * size + origin
    # Düşük frekanslı el yalpalaması + bağımsız Gaussian tablet titreşimi.
    drift = rng.normal(0., sigma*.45, (9, 2))
    p += np.column_stack([np.interp(u, np.linspace(0, 1, 9), drift[:, j]) for j in range(2)])
    p += rng.normal(0., sigma, p.shape)
    timestamps = np.r_[0., np.cumsum(rng.uniform(.003, .025, len(p)-1))]
    metadata = {'sigma_px': sigma, 'size_px': size, 'rotation': rotation,
                'rounding': rounding, 'perimeter_gap_fraction': gap,
                'aspect': aspect, 'subtype': subtype, 'n_points': len(p)}
    return np.column_stack([p, timestamps]), metadata


def generate_freehand(rng, index):
    """Yedi negatif aile; belirsiz kapalı organik çizgiler de bilerek dahil."""
    n = int(rng.integers(60, 601))
    t = np.linspace(0, 1, n)
    family = ['random_walk', 'lissajous', 'spiral', 'open_wave', 'noise', 'closed_blob', 'arc'][index % 7]
    if family == 'random_walk':
        anchors = np.cumsum(rng.normal(0, 1, (int(rng.integers(12, 30)), 2)), axis=0)
        p = resample_at(anchors, t)
    elif family == 'lissajous':
        p = np.column_stack([np.sin((2+index % 3)*2*np.pi*t), np.sin((3+index % 4)*2*np.pi*t + rng.uniform(.2, 1))])
    elif family == 'spiral':
        turns = rng.uniform(1.3, 3.8)
        r = np.linspace(.05, 1, n)
        p = np.column_stack([r*np.cos(turns*2*np.pi*t), r*np.sin(turns*2*np.pi*t)])
    elif family == 'open_wave':
        p = np.column_stack([t, rng.uniform(.12, .5)*np.sin(rng.uniform(1.2, 4)*2*np.pi*t)])
    elif family == 'closed_blob':
        a = 2*np.pi*t
        r = 1 + rng.uniform(.12, .30)*np.sin(3*a+rng.uniform(0, 6)) + rng.uniform(.04, .13)*np.cos(5*a)
        p = np.column_stack([r*np.cos(a), r*np.sin(a)])
    elif family == 'arc':
        a = np.linspace(0, rng.uniform(.7, 1.7)*np.pi, n)
        p = np.column_stack([np.cos(a), rng.uniform(.4, 1.)*np.sin(a)])
    else:
        p = rng.normal(0, 1, (n, 2))
    p -= p.mean(axis=0)
    p *= rng.uniform(70, 600) / max(np.linalg.norm(np.ptp(p, axis=0)), 1e-9)
    angle = rng.uniform(0, 2*np.pi)
    p = p @ np.array([[np.cos(angle), np.sin(angle)], [-np.sin(angle), np.cos(angle)]])
    p += rng.uniform(-1000, 2500, 2) + rng.normal(0, rng.uniform(1, 4), p.shape)
    return np.column_stack([p, t]), {'subtype': family, 'n_points': n}


def handwriting_like(rng, index):
    """El yazısı benzeri: yatay taban boyunca küçük döngüler ve dalgalar (harf benzeri). Gerçek el yazısı değil."""
    loops = int(rng.integers(2, 6))
    pieces = []
    for k in range(loops):
        radius = rng.uniform(8, 22)
        a = np.linspace(0, 2 * np.pi * rng.uniform(0.6, 1.1), 60)
        cx, cy = k * radius * rng.uniform(1.6, 2.4), rng.uniform(-6, 6)
        pieces.append(np.column_stack([cx + radius * np.cos(a), cy + radius * np.sin(a) * rng.uniform(0.7, 1.2)]))
        pieces.append(np.column_stack([np.linspace(cx, cx + radius * 2, 25),
                                       np.sin(np.linspace(0, np.pi, 25)) * rng.uniform(2, 9)]))
    p = np.vstack(pieces)
    p -= p.mean(axis=0)
    p *= rng.uniform(40, 260) / max(np.linalg.norm(np.ptp(p, axis=0)), 1e-9)
    p += rng.normal(0, rng.uniform(0.5, 2.5), p.shape)
    t = np.linspace(0, 1, len(p))
    return np.column_stack([p, t]), {'subtype': 'handwriting_like', 'n_points': len(p)}


def shrink(points, target_extent):
    """Serbest çizimi bbox köşegeni yaklaşık target_extent olacak biçimde ölçekler (merkez korunur)."""
    p = points[:, :2].copy()
    center = (p.max(axis=0) + p.min(axis=0)) / 2
    scale = target_extent / max(np.linalg.norm(np.ptp(p, axis=0)), 1e-9)
    return np.column_stack([(p - center) * scale + center, points[:, 2]])


def measure(seed, per_class, freehand, small_freehand, handwriting):
    rng = np.random.default_rng(seed)
    shape_cases = []
    for label in CLASSES:
        for i in range(per_class):
            points, meta = generate_shape(label, rng, i)
            shape_cases.append((label, points, meta))
    negatives = []
    for i in range(freehand):
        points, meta = generate_freehand(rng, i)
        negatives.append(('freehand', points, meta))
    small = []
    for i in range(small_freehand):
        points, meta = generate_freehand(rng, i)
        small.append(('small_freehand', shrink(points, rng.uniform(20, 60)), meta))
    writing = []
    for i in range(handwriting):
        points, meta = handwriting_like(rng, i)
        writing.append(('handwriting', points, meta))

    per_class_hits = {k: 0 for k in CLASSES}
    per_class_total = {k: 0 for k in CLASSES}
    wrong_type = 0
    timings = []
    for label, points, meta in shape_cases:
        start = time.perf_counter_ns()
        result = correct_stroke(points[:, :2])
        timings.append((time.perf_counter_ns() - start) / 1e6)
        per_class_total[label] += 1
        if result is not None and result['type'] == label:
            per_class_hits[label] += 1
        elif result is not None:
            wrong_type += 1
    positive = sum(per_class_hits.values())
    total_positive = sum(per_class_total.values())

    def accepted(cases):
        hits = 0
        for _, points, _ in cases:
            start = time.perf_counter_ns()
            if correct_stroke(points[:, :2]) is not None:
                hits += 1
            timings.append((time.perf_counter_ns() - start) / 1e6)
        return hits, len(cases)

    free_hits, free_total = accepted(negatives)
    small_hits, small_total = accepted(small)
    writing_hits, writing_total = accepted(writing)
    small_positive = [c for c in shape_cases if c[2]['size_px'] < 70]
    small_pos_hits = sum(1 for label, points, _ in small_positive
                         if (r := correct_stroke(points[:, :2])) is not None and r['type'] == label)
    return {
        'seed': seed,
        'synthetic_only': True,
        'dogruluk': positive / total_positive,
        'dogruluk_sayi': f'{positive}/{total_positive}',
        'sinif_dogrulugu': {k: per_class_hits[k] / per_class_total[k] for k in CLASSES},
        'yanlis_tur': wrong_type,
        'serbest_cizim_yanlis_kabul': free_hits / free_total,
        'serbest_cizim_yanlis_kabul_sayi': f'{free_hits}/{free_total}',
        'kucuk_boyut_yanlis_kabul': small_hits / small_total,
        'kucuk_boyut_yanlis_kabul_sayi': f'{small_hits}/{small_total}',
        'el_yazisi_benzeri_yanlis_kabul': writing_hits / writing_total,
        'el_yazisi_benzeri_yanlis_kabul_sayi': f'{writing_hits}/{writing_total}',
        'kucuk_sekil_dogrulugu': small_pos_hits / max(1, len(small_positive)),
        'kucuk_sekil_sayi': f'{small_pos_hits}/{len(small_positive)}',
        'ortalama_ms_per_cizim': float(np.mean(timings)),
        'p95_ms': float(np.quantile(timings, .95)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=20261113)
    parser.add_argument('--per-class', type=int, default=100)
    parser.add_argument('--freehand', type=int, default=280)
    parser.add_argument('--small-freehand', type=int, default=200)
    parser.add_argument('--handwriting', type=int, default=200)
    parser.add_argument('--out', default='')
    args = parser.parse_args()
    result = measure(args.seed, args.per_class, args.freehand, args.small_freehand, args.handwriting)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
