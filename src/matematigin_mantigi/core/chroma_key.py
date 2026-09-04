"""Program içi yeşil perde: HSV tabanlı yumuşak anahtar, kenar yumuşatma, dökülme bastırma."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ChromaParams:
    tolerance: int = 38                                  # 0..100
    feather_px: int = 2
    spill: float = 0.60                                  # 0..1
    key_hue: int = 60                                    # OpenCV hue (0..179); saf yeşil = 60
    bg_bgr: tuple[int, int, int] = (243, 246, 247)       # #f7f6f3


def green_mask(bgr: np.ndarray, p: ChromaParams) -> np.ndarray:
    """Ön plan alfası [0,1] float32. Ton uzaklığına göre yumuşak anahtar; doygunluk ve parlaklıkla kapılanır."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    t = max(0.0, min(1.0, p.tolerance / 100.0))
    hue_r = 8.0 + 30.0 * t
    dh = np.abs(h - float(p.key_hue))
    dh = np.minimum(dh, 180.0 - dh)
    hue_score = np.clip(1.0 - (dh - 0.6 * hue_r) / (0.4 * hue_r), 0.0, 1.0)
    s_min = 200.0 - 160.0 * t
    v_min = 110.0 - 80.0 * t
    bg = hue_score * np.clip((s - s_min) / 40.0, 0.0, 1.0) * np.clip((v - v_min) / 40.0, 0.0, 1.0)
    alpha = (1.0 - bg).astype(np.float32)
    if p.feather_px > 0:
        alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8))
        k = 2 * int(p.feather_px) + 1
        alpha = cv2.GaussianBlur(alpha, (k, k), 0)
    return alpha.astype(np.float32)


def suppress_spill(bgr: np.ndarray, alpha: np.ndarray, strength: float) -> np.ndarray:
    f = bgr.astype(np.float32)
    excess = np.clip(f[..., 1] - np.maximum(f[..., 0], f[..., 2]), 0.0, None)
    f[..., 1] -= float(strength) * excess
    return np.clip(f + 0.5, 0, 255).astype(np.uint8)


def composite(bgr: np.ndarray, alpha: np.ndarray, bg_bgr: tuple[int, int, int]) -> np.ndarray:
    a = alpha[..., None].astype(np.float32)
    bg = np.empty_like(bgr, dtype=np.float32)
    bg[:] = bg_bgr
    return np.clip(bgr.astype(np.float32) * a + bg * (1.0 - a) + 0.5, 0, 255).astype(np.uint8)


def apply_chroma_key(bgr: np.ndarray, p: ChromaParams) -> np.ndarray:
    alpha = green_mask(bgr, p)
    return composite(suppress_spill(bgr, alpha, p.spill), alpha, p.bg_bgr)
