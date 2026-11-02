from datetime import datetime

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage

from matematigin_mantigi.core.session_store import SessionStore


def white(w=40, h=30):
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(Qt.GlobalColor.white)
    return img


def test_snapshots_are_numbered_per_question(tmp_path, qapp):
    store = SessionStore(tmp_path, clock=lambda: datetime(2026, 9, 4, 13, 5, 9))
    assert store.session_dir == tmp_path / "20260904-130509"
    assert not store.session_dir.exists()             # tembel oluşturma
    a = store.save_snapshot("S1", white())
    b = store.save_snapshot("S1", white())
    c = store.save_snapshot("S2", white())
    assert [p.name for p in (a, b, c)] == ["S1_01.png", "S1_02.png", "S2_01.png"]
    assert store.count("S1") == 2 and store.count("S9") == 0
    assert not QImage(str(a)).isNull() and QImage(str(a)).width() == 40


def test_unsafe_ids_are_sanitised(tmp_path, qapp):
    store = SessionStore(tmp_path)
    p = store.save_snapshot("S/1:x", white())
    assert p.name == "S_1_x_01.png" and p.exists()


def test_failed_save_does_not_consume_a_number(tmp_path, qapp, monkeypatch):
    """Yazılamayan görüntü sıra numarası tüketmesin: sonraki başarılı kayıt S1_02 değil S1_01 olur (klasörde
    S1_01'siz bir S1_02 öğretmeni şaşırtır)."""
    store = SessionStore(tmp_path)
    monkeypatch.setattr(QImage, "save", lambda *a, **k: False)
    with pytest.raises(OSError):
        store.save_snapshot("S1", white())
    monkeypatch.undo()
    assert store.count("S1") == 0
    assert store.save_snapshot("S1", white()).name == "S1_01.png"
