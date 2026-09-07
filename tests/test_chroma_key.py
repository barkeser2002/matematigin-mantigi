import numpy as np

from matematigin_mantigi.core.chroma_key import (ChromaParams, apply_chroma_key, composite,
                                                 green_mask, suppress_spill)


def scene(w=320, h=240):
    img = np.empty((h, w, 3), np.uint8)
    img[:] = (30, 200, 40)                 # yeşil perde (BGR), H≈58 S≈216 V=200
    img[60:180, 80:240] = (20, 20, 220)    # kırmızı kutu = öğretmen
    return img


def test_defaults_match_brief():
    p = ChromaParams()
    assert (p.tolerance, p.feather_px, p.spill, p.bg_bgr) == (38, 2, 0.60, (255, 255, 255))


def test_mask_is_0_on_green_and_1_on_subject():
    a = green_mask(scene(), ChromaParams(feather_px=0))
    assert a.shape == (240, 320) and a.dtype == np.float32
    assert a[10, 10] == 0.0 and a[120, 160] == 1.0


def test_green_becomes_panel_background_and_subject_survives():
    out = apply_chroma_key(scene(), ChromaParams())
    assert out.dtype == np.uint8 and out.shape == (240, 320, 3)
    assert np.allclose(out[10, 10], (255, 255, 255), atol=2)
    assert np.allclose(out[120, 160], (20, 20, 220), atol=2)


def test_bgra_output_has_transparent_screen_and_opaque_subject():
    from matematigin_mantigi.core.chroma_key import apply_chroma_key_bgra
    out = apply_chroma_key_bgra(scene(), ChromaParams())
    assert out.shape == (240, 320, 4) and out.dtype == np.uint8
    assert out[10, 10, 3] == 0 and out[120, 160, 3] == 255
    assert tuple(out[120, 160, :3]) == (20, 20, 220)


def test_feather_softens_edge():
    hard = green_mask(scene(), ChromaParams(feather_px=0))
    soft = green_mask(scene(), ChromaParams(feather_px=3))
    assert set(np.unique(hard)) <= {0.0, 1.0}
    edge = soft[54:66, 160]
    assert ((edge > 0.05) & (edge < 0.95)).any()


def test_spill_pulls_green_cast_down():
    px = np.full((4, 4, 3), (120, 180, 120), np.uint8)
    out = suppress_spill(px, np.ones((4, 4), np.float32), 0.6)
    assert tuple(out[0, 0]) == (120, 144, 120)          # 180 - 0.6 * 60


def test_composite_blends_half():
    fg = np.full((2, 2, 3), (0, 0, 0), np.uint8)
    out = composite(fg, np.full((2, 2), 0.5, np.float32), (200, 100, 0))
    assert tuple(out[0, 0]) == (100, 50, 0)


def test_tolerance_is_monotonic():
    grad = scene()
    grad[..., 1] = np.linspace(60, 255, grad.shape[1], dtype=np.uint8)[None, :]
    keyed = [(green_mask(grad, ChromaParams(tolerance=t, feather_px=0)) < 0.5).sum()
             for t in (0, 20, 38, 60, 100)]
    assert keyed == sorted(keyed)


def test_estimate_key_hue_from_green_border():
    from matematigin_mantigi.core.chroma_key import estimate_key_hue
    hue = estimate_key_hue(scene())
    assert hue is not None and 55 <= hue <= 62            # BGR (30,200,40) ≈ ton 58
    grey = np.full((120, 160, 3), 90, np.uint8)
    assert estimate_key_hue(grey) is None                 # doygun yeşil kenar yok
    inner = grey.copy(); inner[30:90, 40:120] = (30, 200, 40)
    assert estimate_key_hue(inner) is None                # yeşil sadece ortada, kenarlar gri
    import cv2
    yellowish = cv2.cvtColor(np.full((60, 80, 3), (38, 220, 200), np.uint8), cv2.COLOR_HSV2BGR)
    assert estimate_key_hue(yellowish) is None            # ton 38: yeşil perde aralığı (45-80) dışında


def test_input_not_mutated():
    src = scene(); before = src.copy()
    apply_chroma_key(src, ChromaParams())
    assert (src == before).all()
