import subprocess
import time
from pathlib import Path

import numpy as np
import pytest

from matematigin_mantigi.core.recorder import (MssFfmpegRecorder, NullRecorder, RecordRect, RecorderError,
                                               audio_rate_correction, ffmpeg_args, find_ffmpeg, mux_args, record_rect_for)
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


def test_ffmpeg_args_video_only(tmp_path):
    out = tmp_path / "k.mp4"
    a = ffmpeg_args("ffmpeg", 640, 480, 30, out, platform="win32")
    assert a[:2] == ["ffmpeg", "-y"] and "-s" in a and a[a.index("-s") + 1] == "640x480"
    assert "libx264" in a and "yuv420p" in a and a[-1] == str(out) and "-nostats" in a
    assert a[a.index("-thread_queue_size") + 1] == "8"            # Retina'da kare ~20 MB: kuyruk küçük kalmalı
    assert "dshow" not in a and "avfoundation" not in a and "-c:a" not in a
    s = ffmpeg_args("ffmpeg", 1832, 1080, 60, out, platform="win32", out_height=1440)
    assert s[s.index("-vf") + 1] == "scale=-2:1440:flags=bilinear" and s[s.index("-framerate") + 1] == "60"
    assert "-vf" not in ffmpeg_args("ffmpeg", 1832, 1080, 60, out, platform="win32", out_height=0)


def test_mux_args_offsets_and_rate_fix(tmp_path):
    v, a, out = tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4"
    early = mux_args("ffmpeg", v, a, out, 0.25)                   # ses 250 ms önce başladı: başı atılır
    assert early[early.index("-ss") + 1] == "0.250" and "-itsoffset" not in early
    late = mux_args("ffmpeg", v, a, out, -0.1)                    # ses geç başladı: geciktirilir
    assert late[late.index("-itsoffset") + 1] == "0.100" and "-ss" not in late
    assert "-c:v" in early and early[early.index("-c:v") + 1] == "copy" and "aac" in early and early[-1] == str(out)
    fixed = mux_args("ffmpeg", v, a, out, 0.0, asetrate=48003)
    assert fixed[fixed.index("-af") + 1] == "asetrate=48003,aresample=48000"
    assert "-af" not in mux_args("ffmpeg", v, a, out, 0.0)


def test_audio_rate_correction_only_for_long_clear_drift():
    from matematigin_mantigi.core.audio_capture import AudioResult
    from pathlib import Path as _P
    short = AudioResult(_P("a.wav"), 48000, 1, 48000 * 30, 0.0, 30.0 - 0.02)
    assert audio_rate_correction(short) is None                   # 30 sn: gürültü > gerçek kayma
    long_ok = AudioResult(_P("a.wav"), 48000, 1, 48000 * 1200, 0.0, 1200.0)
    assert audio_rate_correction(long_ok) is None                 # kayma yok
    drift = AudioResult(_P("a.wav"), 48000, 1, 48000 * 1200, 0.0, 1200.0 - 0.36)   # 300 ppm hızlı mikrofon saati
    assert audio_rate_correction(drift) == 48014
    broken = AudioResult(_P("a.wav"), 48000, 1, 48000 * 600, 0.0, 700.0)          # %14: ölçüm hatası, dokunma
    assert audio_rate_correction(broken) is None


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
    a = ffmpeg_args("ffmpeg", 640, 480, 60, out, platform="win32", encoder="h264_nvenc")
    assert "h264_nvenc" in a and "libx264" not in a
    b = ffmpeg_args("ffmpeg", 640, 480, 60, out, platform="darwin", encoder="h264_videotoolbox")
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


class FakeAudioCapture:
    """Gerçek mikrofon yerine 1 kHz sinüs üretir; ilk örnek zamanı start() anıdır."""
    instances: list = []

    def __init__(self, device):
        self.device = device
        self.samplerate, self.channels = 48000, 1
        self.first_sample_monotonic = None
        self.path = None
        FakeAudioCapture.instances.append(self)

    def start(self, path):
        self.path = Path(path); self.first_sample_monotonic = time.monotonic()

    def stop(self):
        import wave
        from matematigin_mantigi.core.audio_capture import AudioResult
        stopped = time.monotonic()
        n = int((stopped - self.first_sample_monotonic) * self.samplerate)
        t = np.arange(n) / self.samplerate
        pcm = (np.sin(2 * np.pi * 1000 * t) * 12000).astype(np.int16)
        with wave.open(str(self.path), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(self.samplerate); w.writeframes(pcm.tobytes())
        return AudioResult(self.path, self.samplerate, 1, n, self.first_sample_monotonic, stopped)


def _stream_seconds(exe, path, flag):
    import re as _re
    err = subprocess.run([exe, "-hide_banner", "-i", str(path), flag, "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = _re.findall(r"time=(\d+):(\d+):([\d.]+)", err)
    h, mi, sec = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(sec)


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_recorder_muxes_audio_aligned_with_video(tmp_path):
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture)
    rec.start(RecordRect(0, 0, 160, 120)); time.sleep(1.5); path = rec.stop()
    assert rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
    assert path.exists() and rec.audio_result is not None and rec.audio_result.samples > 48000
    assert rec.av_offset_ms is not None and 0 <= rec.av_offset_ms < 500      # ses videodan önce başladı
    assert not (tmp_path / path.name.replace(".mp4", ".video.mp4")).exists()  # ara dosyalar silindi
    assert not list(tmp_path.glob("*.wav"))
    exe = find_ffmpeg()
    v, a = _stream_seconds(exe, path, "-an"), _stream_seconds(exe, path, "-vn")
    assert abs(v - a) < 0.15, (v, a)
    log = next(tmp_path.glob("kayit_*.log"))
    assert log.exists()


@pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")
def test_recorder_keeps_video_when_microphone_fails(tmp_path):
    class Broken:
        def __init__(self, device): pass
        def start(self, path): raise RuntimeError("aygıt yok")
        def stop(self): raise AssertionError("çağrılmamalı")
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Yok", audio_factory=Broken)
    rec.start(RecordRect(0, 0, 160, 120)); time.sleep(0.5); path = rec.stop()
    assert path.exists() and rec.error is None and "Mikrofon açılamadı" in rec.audio_error
