from datetime import datetime
import time

import numpy as np
import pytest

from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecordRect, find_ffmpeg


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_same_second_preserves_existing_recordings(tmp_path):
    clock = lambda: datetime(2026, 1, 1)
    old = tmp_path / 'kayit_20260101-000000.mp4'
    old.write_bytes(b'eski kayit')
    grab = lambda r: np.zeros((r.height, r.width, 4), dtype=np.uint8)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=10, clock=clock, grabber=grab, out_height=0)
    paths = []
    for _ in range(2):
        rec.start(RecordRect(0, 0, 64, 48))
        paths.append(rec.stop())
    assert old.read_bytes() == b'eski kayit'
    assert len(set(paths)) == 2 and old not in paths
    assert all(p.exists() for p in paths)


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_permanent_capture_failure_stops_writer_and_reports_raw(tmp_path):
    calls = 0
    def grab(r):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError('ekran kilitli')
        return np.zeros((r.height, r.width, 4), dtype=np.uint8)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=10, grabber=grab, out_height=0)
    rec.start(RecordRect(0, 0, 64, 48))
    deadline = time.monotonic() + 4
    while not rec.failed and time.monotonic() < deadline:
        time.sleep(.02)
    try:
        assert rec.failed, 'kalıcı yakalama hatası sessizce sürüyor'
    finally:
        path = rec.stop()
    assert 'yakalan' in rec.error.lower()
    assert str(path) in rec.error
    assert path.exists()


def test_capture_hang_detected_even_when_encoder_write_blocks(tmp_path):
    import threading
    from types import SimpleNamespace
    from matematigin_mantigi.core.recorder import _Session
    rect = RecordRect(0, 0, 8, 8)
    release = threading.Event()
    writing = threading.Event()
    def grab(_):
        release.wait(10)
        return np.zeros((8, 8, 4), dtype=np.uint8)
    class Stdin:
        def write(self, data):
            writing.set()
            release.wait(10)
    rec = MssFfmpegRecorder(lambda: tmp_path, grabber=grab)
    s = _Session(rect, "libx264", tmp_path / "out", tmp_path / "raw", tmp_path / "log")
    s.proc = SimpleNamespace(stdin=Stdin())
    thread = threading.Thread(target=rec._loop, args=(s, rect, np.zeros((8, 8, 4), dtype=np.uint8), 8, 8, 10))
    thread.start()
    try:
        assert writing.wait(2)
        assert s.stop_event.wait(3.5), "encoder write blocks capture watchdog"
        assert s.failed and s.capture_error
    finally:
        release.set()
        s.stop_event.set()
        thread.join(6)


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_wav_created_after_reservation_remains_untouched(tmp_path, monkeypatch):
    from matematigin_mantigi.core import audio_capture as ac
    from tests.test_audio_capture import FakeSoundDevice
    monkeypatch.setattr(ac, "_sd", lambda: FakeSoundDevice(0))
    class RivalCapture(ac.AudioCapture):
        def start(self, path):
            path.write_bytes(b"foreign recording")
            super().start(path)
    grab = lambda r: np.zeros((r.height, r.width, 4), dtype=np.uint8)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=10, grabber=grab, out_height=0,
                            audio_device="mic", audio_factory=RivalCapture)
    rec.start(RecordRect(0, 0, 64, 48))
    wav = next(tmp_path.glob("*.wav"))
    rec.stop()
    assert wav.read_bytes() == b"foreign recording"
    assert rec.audio_error and "Mikrofon açılamadı" in rec.audio_error


def test_hardlink_fallback_does_not_replace_existing_destination(tmp_path, monkeypatch):
    import errno
    import os
    video, out = tmp_path / "raw", tmp_path / "out"
    video.write_bytes(b"raw")
    out.write_bytes(b"foreign")
    def unsupported(*_):
        raise OSError(errno.EOPNOTSUPP, "no hard links")
    monkeypatch.setattr(os, "link", unsupported)
    with pytest.raises(FileExistsError):
        MssFfmpegRecorder._move_video_without_overwrite(video, out)
    assert out.read_bytes() == b"foreign" and video.read_bytes() == b"raw"
