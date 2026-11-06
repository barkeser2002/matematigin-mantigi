import os
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from matematigin_mantigi.core import recorder as r
from tests.test_recorder import _mux_lesson


def test_link_does_not_unlink_replaced_source(tmp_path, monkeypatch):
    raw, out = tmp_path / 'raw', tmp_path / 'out'
    raw.write_bytes(b'original')
    real_link = os.link
    def swap(source, dest):
        real_link(source, dest)
        os.rename(source, tmp_path / 'saved')
        raw.write_bytes(b'foreign')
    monkeypatch.setattr(os, 'link', swap)
    r.MssFfmpegRecorder._move_video_without_overwrite(raw, out)
    assert raw.read_bytes() == b'foreign'
    assert out.read_bytes() == b'original'


@pytest.mark.skipif(r.find_ffmpeg() is None, reason='ffmpeg yok')
def test_successful_mux_preserves_replaced_raw_paths(tmp_path, monkeypatch):
    real_run = r.subprocess.run
    def swap_after_mux(args, **kwargs):
        result = real_run(args, **kwargs)
        if str(args[-1]) == str(tmp_path / 'kayit_x.mp4') and result.returncode == 0:
            for path in (tmp_path / 'kayit_x.video.mp4', tmp_path / 'kayit_x.wav'):
                os.rename(path, path.with_suffix(path.suffix + '.saved'))
                path.write_bytes(b'foreign')
        return result
    monkeypatch.setattr(r.subprocess, 'run', swap_after_mux)
    _mux_lesson(tmp_path, video_s=2, heard_s=2, stop_s=2)
    assert (tmp_path / 'kayit_x.video.mp4').read_bytes() == b'foreign'
    assert (tmp_path / 'kayit_x.wav').read_bytes() == b'foreign'


def test_writer_hang_detected_with_healthy_capture(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'WRITER_STALL_S', .3, raising=False)
    release, writing = threading.Event(), threading.Event()
    class Stdin:
        def write(self, data):
            writing.set()
            release.wait(4)
    rect = r.RecordRect(0, 0, 8, 8)
    rec = r.MssFfmpegRecorder(lambda: tmp_path, grabber=lambda _: np.zeros((8, 8, 4), np.uint8))
    s = r._Session(rect, 'libx264', tmp_path/'out', tmp_path/'raw', tmp_path/'log')
    s.proc = SimpleNamespace(stdin=Stdin())
    thread = threading.Thread(target=rec._loop, args=(s, rect, np.zeros((8, 8, 4), np.uint8), 8, 8, 10))
    thread.start()
    try:
        assert writing.wait(1)
        assert s.stop_event.wait(1.5), 'sağlıklı yakalamaya rağmen kodlayıcı donması algılanmadı'
        assert s.failed and not s.capture_error
    finally:
        s.stop_event.set()
        release.set()
        thread.join(4)


def test_watchdog_ignores_idle_writer_and_stops_on_shutdown(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'WRITER_STALL_S', .15)
    rect = r.RecordRect(0, 0, 8, 8)
    rec = r.MssFfmpegRecorder(lambda: tmp_path)
    s = r._Session(rect, 'libx264', tmp_path/'out', tmp_path/'raw', tmp_path/'log')
    watcher = threading.Thread(target=rec._watch_capture, args=(s,))
    watcher.start()
    try:
        assert not s.stop_event.wait(.4)  # before first write, or between frames
        assert not s.failed
        s.stop_event.set()
        s.write_started_at = time.monotonic() - 1  # finalization is not recording
        watcher.join(1)
        assert not s.failed and not s.encoder_stalled
    finally:
        s.stop_event.set()
        watcher.join(1)
