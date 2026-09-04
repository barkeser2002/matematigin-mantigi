"""Soru başına tuval anlık görüntüsü: oturum/<zaman>/<id>_<nn>.png"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtGui import QImage

from matematigin_mantigi import paths


class SessionStore:
    def __init__(self, root: Path | None = None, clock: Callable[[], datetime] = datetime.now):
        self.root = Path(root) if root is not None else paths.default_session_root()
        self.session_dir = self.root / clock().strftime("%Y%m%d-%H%M%S")
        self._counts: dict[str, int] = {}

    @staticmethod
    def _safe(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_\-ĞğÜüŞşİıÖöÇç]", "_", name) or "soru"

    def count(self, question_id: str) -> int:
        return self._counts.get(self._safe(question_id), 0)

    def save_snapshot(self, question_id: str, image: QImage) -> Path:
        key = self._safe(question_id)
        self._counts[key] = self._counts.get(key, 0) + 1
        self.session_dir.mkdir(parents=True, exist_ok=True)
        target = self.session_dir / f"{key}_{self._counts[key]:02d}.png"
        if not image.save(str(target), "PNG"):
            raise OSError(f"PNG yazılamadı: {target}")
        return target
