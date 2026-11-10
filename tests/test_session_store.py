from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import os

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


def test_existing_snapshot_is_never_overwritten(tmp_path, qapp):
    clock = lambda: datetime(2026, 9, 4, 13, 5, 9)
    first = SessionStore(tmp_path, clock=clock)
    original = first.save_snapshot("S1", white())
    contents = original.read_bytes()
    second = SessionStore(tmp_path, clock=clock)
    new = second.save_snapshot("S1", white(20, 10))
    assert original.read_bytes() == contents
    assert new.name == "S1_02.png"
    assert QImage(str(new)).width() == 20


def _save_in_process(root):
    store = SessionStore(root, clock=lambda: datetime(2026, 9, 4, 13, 5, 9))
    return store.save_snapshot("S1", white()).name


def test_concurrent_processes_preserve_all_snapshots(tmp_path):
    import multiprocessing
    with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
        names = list(pool.map(_save_in_process, [tmp_path] * 12))
    assert len(set(names)) == 12
    assert all(not QImage(str(tmp_path / "20260904-130509" / name)).isNull() for name in names)
    assert not list(tmp_path.rglob("*.tmp"))


def test_external_target_appearing_at_link_time_is_preserved(tmp_path, qapp, monkeypatch):
    store = SessionStore(tmp_path)
    link = os.link
    calls = 0
    def once(source, target):
        nonlocal calls
        calls += 1
        if calls == 1:
            target.write_bytes(b"external")
        return link(source, target)
    monkeypatch.setattr(os, "link", once)
    result = store.save_snapshot("S1", white())
    assert (store.session_dir / "S1_01.png").read_bytes() == b"external"
    assert result.name == "S1_02.png"


def test_link_permission_failure_is_visible_and_temp_cleaned(tmp_path, qapp, monkeypatch):
    store = SessionStore(tmp_path)
    def denied(*args):
        raise PermissionError("link denied")
    monkeypatch.setattr(os, "link", denied)
    with pytest.raises(PermissionError, match="link denied"):
        store.save_snapshot("S1", white())
    assert store.count("S1") == 0
    assert list(store.session_dir.iterdir()) == []


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


def test_unsupported_hardlink_falls_back_without_overwriting(tmp_path, qapp, monkeypatch):
    import errno
    store = SessionStore(tmp_path)
    store.session_dir.mkdir(parents=True)
    old = store.session_dir / "S1_01.png"
    old.write_bytes(b"external")
    def unsupported(*args):
        raise OSError(errno.EOPNOTSUPP, "hardlinks unsupported")
    monkeypatch.setattr(os, "link", unsupported)
    result = store.save_snapshot("S1", white(20, 10))
    assert old.read_bytes() == b"external"
    assert result.name == "S1_02.png"
    assert QImage(str(result)).width() == 20
    assert not list(store.session_dir.glob("*.tmp"))


def test_fallback_partial_write_is_preserved_and_retry_succeeds(tmp_path, qapp, monkeypatch):
    import builtins
    import errno
    store = SessionStore(tmp_path)
    def unsupported(*args):
        raise OSError(errno.EOPNOTSUPP, "unsupported")
    monkeypatch.setattr(os, "link", unsupported)
    real_open = builtins.open
    class PartialWriter:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.stream.close()
        def write(self, data):
            self.stream.write(data[:10])
            raise OSError(errno.ENOSPC, "disk full")
    def partial_open(path, mode, *args, **kwargs):
        stream = real_open(path, mode, *args, **kwargs)
        return PartialWriter(stream) if mode == "xb" else stream
    monkeypatch.setattr(builtins, "open", partial_open)
    with pytest.raises(OSError, match="S1_01.png"):
        store.save_snapshot("S1", white())
    partial = store.session_dir / "S1_01.png"
    saved = partial.read_bytes()
    assert len(saved) == 10 and store.count("S1") == 0
    monkeypatch.setattr(builtins, "open", real_open)
    result = store.save_snapshot("S1", white())
    assert result.name == "S1_02.png" and not QImage(str(result)).isNull()
    assert partial.read_bytes() == saved


@pytest.mark.parametrize("winerror", [1, 50])
def test_windows_unsupported_link_errors_use_fallback(tmp_path, qapp, monkeypatch, winerror):
    store = SessionStore(tmp_path)
    def unsupported(*args):
        error = OSError("Windows unsupported")
        error.winerror = winerror
        raise error
    monkeypatch.setattr(os, "link", unsupported)
    assert not QImage(str(store.save_snapshot("S1", white()))).isNull()


def test_link_disk_failure_does_not_use_fallback(tmp_path, qapp, monkeypatch):
    import errno
    store = SessionStore(tmp_path)
    def disk_full(*args):
        raise OSError(errno.ENOSPC, "disk full")
    monkeypatch.setattr(os, "link", disk_full)
    with pytest.raises(OSError, match="disk full"):
        store.save_snapshot("S1", white())
    assert store.count("S1") == 0
    assert list(store.session_dir.iterdir()) == []


def test_concurrent_fallback_saves_use_distinct_files(tmp_path, qapp, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import errno
    def unsupported(*args):
        raise OSError(errno.EOPNOTSUPP, "unsupported")
    monkeypatch.setattr(os, "link", unsupported)
    clock = lambda: datetime(2026, 9, 4, 13, 5, 9)
    stores = [SessionStore(tmp_path, clock=clock) for _ in range(12)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda store: store.save_snapshot("S1", white()), stores))
    assert len(set(results)) == 12
    assert all(not QImage(str(path)).isNull() for path in results)
