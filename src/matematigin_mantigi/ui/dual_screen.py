"""Çift ekran seçimi için korumacı, Qt mantıksal koordinat kontrolleri.

Bu kontroller tek başına MSS fiziksel piksel eşleşmesini veya pencerenin
kayıt alanına taşmadığını kanıtlamaz; önizleme güvenliği için yeterli değildir.
"""


def screen_key(screen):
    if screen is None:
        return None
    try:
        key = tuple(str(getattr(screen, field)() or "") for field in
                    ("name", "manufacturer", "model", "serialNumber"))
        return key if key[0] else None
    except (AttributeError, RuntimeError):
        return None


def resolve_screen_key(screens, key):
    if not isinstance(key, (tuple, list)) or len(key) != 4 or not key[0]:
        return None
    matches = [screen for screen in screens if screen_key(screen) == tuple(key)]
    return matches[0] if len(matches) == 1 else None


def resolve_screen(screens, name: str, serial: str):
    """Tam kimliğe uyan tek ekranı döndür; yoksa veya belirsizse dönme."""
    if not name:
        return None
    matches = [screen for screen in screens
               if screen.name() == name and screen.serialNumber() == serial]
    return matches[0] if len(matches) == 1 else None


def screens_are_separate(first, second) -> bool:
    """İki ayrı ekranın boş olmayan mantıksal geometrileri kesişmiyor mu?"""
    if first is None or second is None or first is second:
        return False
    a, b = first.geometry(), second.geometry()
    return not a.isEmpty() and not b.isEmpty() and not a.intersects(b)


def layout_supported(screens, board, preview) -> bool:
    """Bütün ekranlar aynı, ölçülebilir ölçekte ve geometrileri ayrı olmalı."""
    screens = list(screens)
    if board not in screens or preview not in screens or len(screens) < 2:
        return False
    try:
        ratios = [float(s.devicePixelRatio()) for s in screens]
        if any(not (0 < r < 10) or abs(r - ratios[0]) > 0.001 for r in ratios):
            return False
        return all(screens_are_separate(a, b) for i, a in enumerate(screens) for b in screens[i + 1:])
    except (AttributeError, RuntimeError, ValueError, TypeError):
        return False
