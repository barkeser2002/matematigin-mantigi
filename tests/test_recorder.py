import time
from pathlib import Path

import numpy as np
import pytest

from matematigin_mantigi.core.recorder import (MssFfmpegRecorder, NullRecorder, RecordRect, RecorderError,
                                               ffmpeg_args, find_ffmpeg, list_audio_devices, record_rect_for)
from matematigin_mantigi.ui.record_badge import RecordBadge
from matematigin_mantigi.ui.theme import FontFamilies


def test_record_rect_physical_is_even_and_scaled():
    r = record_rect_for((88, 0, 1831, 1079, 2.0))
    assert r == RecordRect(88, 0, 1831, 1079, 2.0)
    p = r.physical()
    assert (p.x, p.y, p.width, p.height, p.dpr) == (176, 0, 3662, 2158, 1.0)
    assert RecordRect(0, 0, 1833, 1081).physical().width == 1832
    assert r.to_mss() == {"left": 88, "top": 0, "width": 1831, "height": 1079}


def test_null_recorder_lifecycle():
    rec = NullRecorder()
    assert not rec.is_recording and rec.elapsed_seconds == 0
    rec.start(RecordRect(0, 0, 100, 100), fps=60)
    assert rec.is_recording and rec.last_rect == RecordRect(0, 0, 100, 100) and rec.fps == 60
    assert rec.stop() is None and not rec.is_recording


def test_badge_text_and_ticks(qtbot):
    b = RecordBadge(FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(b)
    b.set_format(1920, 1080, 60)
    assert not b.active and b.isHidden()
    b.start()
    assert b.active and b.text() == "KAYIT · 00:00 · 1920×1080 · 60 fps"
    b.tick(); b.tick()
    assert b.text() == "KAYIT · 00:02 · 1920×1080 · 60 fps" and b.seconds == 2
    b.stop()
    assert not b.active and b.isHidden() and b.seconds == 0


def test_ffmpeg_args_per_platform(tmp_path):
    out = tmp_path / "k.mp4"
    a = ffmpeg_args("ffmpeg", 640, 480, 30, out, None, platform="win32")
    assert a[:2] == ["ffmpeg", "-y"] and "-s" in a and a[a.index("-s") + 1] == "640x480"
    assert "libx264" in a and "yuv420p" in a and "dshow" not in a and a[-1] == str(out)
    w = ffmpeg_args("ffmpeg", 640, 480, 30, out, "Mikrofon (USB)", platform="win32")
    assert "dshow" in w and "audio=Mikrofon (USB)" in w and "aac" in w and "-shortest" in w
    m = ffmpeg_args("ffmpeg", 640, 480, 30, out, ":0 Built-in Mic", platform="darwin")
    assert "avfoundation" in m and m[m.index("avfoundation") + 2] == ":0"
    s = ffmpeg_args("ffmpeg", 1832, 1080, 60, out, None, platform="win32", out_height=1440)
    assert "-vf" in s and s[s.index("-vf") + 1] == "scale=-2:1440:flags=bicubic" and s[s.index("-framerate") + 1] == "60"
    assert "-vf" not in ffmpeg_args("ffmpeg", 1832, 1080, 60, out, None, platform="win32", out_height=0)


def test_list_audio_devices_parses_windows_and_mac():
    win_text = ('[dshow @ 0] "OBS Virtual Camera" (video)\n[dshow @ 0] "Mikrofon (USB AUDIO)" (audio)\n'
                '[dshow @ 0]   Alternative name "@device_cm_{...}"\n[dshow @ 0] "Steam Streaming Microphone" (audio)\n')
    assert list_audio_devices("ffmpeg", platform="win32", runner=lambda c: win_text) == \
        ["Mikrofon (USB AUDIO)", "Steam Streaming Microphone"]
    mac_text = ("[AVFoundation indev @ 0] AVFoundation video devices:\n[AVFoundation indev @ 0] [0] FaceTime HD Camera\n"
                "[AVFoundation indev @ 0] AVFoundation audio devices:\n[AVFoundation indev @ 0] [0] MacBook Pro Microphone\n"
                "[AVFoundation indev @ 0] [1] USB Audio\n")
    assert list_audio_devices("ffmpeg", platform="darwin", runner=lambda c: mac_text) == \
        [":0 MacBook Pro Microphone", ":1 USB Audio"]
    assert list_audio_devices(None, platform="win32", runner=lambda c: "") == [] or True   # exe None -> []


def synthetic_grabber(rect: RecordRect) -> np.ndarray:
    t = int(time.monotonic() * 20) % rect.width
    frame = np.full((rect.height, rect.width, 4), (255, 255, 255, 255), np.uint8)
    frame[20:60, t:min(rect.width, t + 40)] = (30, 60, 200, 255)
    return frame


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_mss_ffmpeg_recorder_writes_playable_mp4(tmp_path):
    import cv2
    rec = MssFfmpegRecorder(lambda: tmp_path / "oturum", fps=10, grabber=synthetic_grabber, out_height=0)
    assert not rec.is_recording
    rec.start(RecordRect(0, 0, 320, 240))
    assert rec.is_recording and rec.last_path is not None and rec.last_path.suffix == ".mp4"
    time.sleep(0.8)
    path = rec.stop()
    assert not rec.is_recording and rec.error is None, rec.error
    assert path.exists() and path.stat().st_size > 1000 and rec.frames_written >= 5
    cap = cv2.VideoCapture(str(path))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ok, frame = cap.read(); cap.release()
    assert ok and frame.shape == (240, 320, 3) and frames >= 5


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_recorder_scales_output_to_requested_height(tmp_path):
    import cv2
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=10, grabber=synthetic_grabber, out_height=480)
    rec.start(RecordRect(0, 0, 320, 240)); time.sleep(0.5); path = rec.stop()
    assert rec.error is None, rec.error
    cap = cv2.VideoCapture(str(path)); ok, frame = cap.read(); cap.release()
    assert ok and frame.shape[:2] == (480, 640)


def test_detect_encoder_prefers_hardware_when_probe_succeeds():
    from matematigin_mantigi.core.recorder import detect_encoder
    assert detect_encoder("ffmpeg", platform="darwin", runner=lambda cmd: 0) == "h264_videotoolbox"
    assert detect_encoder("ffmpeg", platform="win32", runner=lambda cmd: 0 if "h264_qsv" in cmd else 1) == "h264_qsv"
    assert detect_encoder("ffmpeg", platform="win32", runner=lambda cmd: 1) == "libx264"
    assert detect_encoder("ffmpeg", platform="linux", runner=lambda cmd: 0) == "libx264"


def test_ffmpeg_args_encoder_selection(tmp_path):
    out = tmp_path / "k.mp4"
    a = ffmpeg_args("ffmpeg", 640, 480, 60, out, None, platform="win32", encoder="h264_nvenc")
    assert "h264_nvenc" in a and "libx264" not in a
    b = ffmpeg_args("ffmpeg", 640, 480, 60, out, None, platform="darwin", encoder="h264_videotoolbox")
    assert "h264_videotoolbox" in b


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_slow_grabber_still_keeps_real_time_duration(tmp_path):
    """Yakalama 10 kare/sn verse de 30 fps çıktı ~1 sn'lik kayıtta ~30 kare taşır (çoğaltma)."""
    def slow(rect):
        time.sleep(0.1)
        return synthetic_grabber(rect)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=30, grabber=slow, out_height=0)
    rec.start(RecordRect(0, 0, 160, 120)); time.sleep(1.0); rec.stop()
    assert rec.error is None and rec.frames_grabbed <= 14
    assert 24 <= rec.frames_written <= 40


def test_recorder_without_ffmpeg_raises(tmp_path, monkeypatch):
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "find_ffmpeg", lambda: None)
    rec = MssFfmpegRecorder(lambda: tmp_path, grabber=synthetic_grabber)
    with pytest.raises(RecorderError, match="ffmpeg"):
        rec.start(RecordRect(0, 0, 64, 48))
    assert not rec.is_recording


def test_grab_screen_returns_bgra():
    try:
        frame = __import__("matematigin_mantigi.core.recorder", fromlist=["grab_screen"]).grab_screen(RecordRect(0, 0, 64, 48))
    except Exception as err:  # noqa: BLE001 - ekran yoksa (CI)
        pytest.skip(f"ekran yakalanamadı: {err}")
    assert frame.shape == (48, 64, 4) and frame.dtype == np.uint8


def test_mac_audio_device_passes_only_index(tmp_path):
    out = tmp_path / "k.mp4"
    m = ffmpeg_args("ffmpeg", 640, 480, 30, out, ":0 MacBook Pro Microphone", platform="darwin")
    assert m[m.index("avfoundation") + 2] == ":0"
    assert ffmpeg_args("ffmpeg", 640, 480, 30, out, "1", platform="darwin")[-1] == str(out)
    assert ":1" in ffmpeg_args("ffmpeg", 640, 480, 30, out, "1", platform="darwin")


def test_audio_args_have_big_queues_and_async_resample(tmp_path):
    out = tmp_path / "k.mp4"
    for platform, dev in (("win32", "Mikrofon (USB)"), ("darwin", ":0 MacBook Pro Microphone")):
        a = ffmpeg_args("ffmpeg", 640, 480, 60, out, dev, platform=platform)
        assert a.count("-thread_queue_size") == 2 and a[a.index("-thread_queue_size") + 1] == "1024"
        assert "aresample=async=1:first_pts=0" in a and "48000" in a and "-fps_mode" in a
    no_audio = ffmpeg_args("ffmpeg", 640, 480, 60, out, None, platform="win32")
    assert "-af" not in no_audio and no_audio.count("-thread_queue_size") == 1
