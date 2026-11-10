"""Soru başına tuval anlık görüntüsü: oturum/<zaman>/<id>_<nn>.png"""
from __future__ import annotations

import errno
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QBuffer, QIODevice
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
        """Yazılamazsa OSError fırlatır (çağıran yakalayıp bildirir); sıra numarası yalnız başarıda ilerler."""
        key = self._safe(question_id)
        n = self._counts.get(key, 0) + 1
        self.session_dir.mkdir(parents=True, exist_ok=True)
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):
            raise OSError(f"PNG kodlanamadı: {self.session_dir}")
        # Ayrı dosya tamamlanmadan hedef görünmez. Sabit bağlantı, Windows dahil
        # hedef zaten varsa atomik olarak başarısız olur; os.replace böyle değildir.
        fd, name = tempfile.mkstemp(prefix=".snapshot-", suffix=".tmp", dir=self.session_dir)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(bytes(buffer.data()))
            fallback = False
            while True:
                target = self.session_dir / f"{key}_{n:02d}.png"
                if not fallback:
                    try:
                        os.link(temporary, target)
                        break
                    except FileExistsError:
                        n += 1
                        continue
                    except OSError as exc:
                        # WinError 1/50: dosya sistemi işlemi desteklemiyor.
                        # Erişim reddi, dolu disk vb. hatalar geri dönüş değildir.
                        winerror = getattr(exc, "winerror", None)
                        unsupported = (winerror in (1, 50) if winerror is not None else
                                       exc.errno in (errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP))
                        if not unsupported:
                            raise
                        fallback = True
                try:
                    stream = open(target, "xb")
                except FileExistsError:
                    n += 1
                    continue
                # CREATE_NEW çakışmayı önler ancak yazım bitene kadar kısmi PNG
                # görünür olabilir. Başarısız yazımı silmeyiz: başka bir süreç
                # dosyayı bu sırada değiştirmiş veya yerine yenisini koymuş olabilir.
                try:
                    with stream:
                        stream.write(bytes(buffer.data()))
                except OSError as exc:
                    raise OSError(exc.errno, f"PNG yazılamadı; kısmi dosya kalmış olabilir: {target}: {exc}") from exc
                break
        finally:
            temporary.unlink()
        self._counts[key] = n
        return target
