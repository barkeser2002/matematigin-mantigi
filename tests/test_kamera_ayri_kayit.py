"""Ayrı kamera kaydı: gerçek kodlayıcı, küçük sentetik ekran ve ham kamera."""
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QMessageBox

from conftest import FakeCamera
from test_recorder import FakeAudioCapture, small_synthetic_grabber
from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg, media_duration, no_window


@pytest.fixture(autouse=True)
def modallar_ve_temizlik(monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.StandardButton.Ok)
    for name in ("question", "warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, name, lambda *a, **k: QMessageBox.StandardButton.Yes)
    yield
    from test_main_window import _release_windows_left_open
    _release_windows_left_open()


@pytest.fixture
def kayit_penceresi(window, tmp_path, qtbot, monkeypatch):
    monkeypatch.setattr("matematigin_mantigi.core.audio_capture.resolve_input_device", lambda name: 0)
    window.settings.audio_device = "Sahte"
    window.settings.record_height = 0
    window.settings.record_fps = 30
    window.webcam_panel.set_source_factory(lambda: FakeCamera(frames=100000, w=1280, h=720))
    window.webcam_panel.start()
    qtbot.waitUntil(lambda: window.webcam_panel.has_camera)
    window.recorder = MssFfmpegRecorder(lambda: tmp_path, fps=30, out_height=0,
                                      grabber=small_synthetic_grabber, audio_device="Sahte",
                                      audio_factory=FakeAudioCapture,
                                      clock=lambda: datetime(2026, 11, 13, 10, 0, 0))
    return window


def kaydet(win, qtbot):
    win.toggle_recording(True)
    qtbot.waitUntil(lambda: win.recorder.frames_written >= 35, timeout=15000)
    win.toggle_recording(False)
    qtbot.waitUntil(lambda: win._stop_worker is None, timeout=60000)
    assert win.recorder.last_path.exists() and not win.recorder.error
    return win.recorder.last_path


def kamera_dogrula(main):
    cam = main.with_suffix(".kamera.mp4")
    assert cam.exists()
    cap = cv2.VideoCapture(str(cam))
    try:
        ok, frame = cap.read()
        assert ok and frame.shape[:2] == (720, 1280)
        # Yeşil perde ve önizlemenin 640 px sınırı ham dosyaya uygulanmaz.
        assert frame[50, 50, 1] > 150
    finally:
        cap.release()
    exe = find_ffmpeg()
    assert abs(media_duration(exe, cam) - media_duration(exe, main)) <= 0.5
    p = subprocess.run([exe, "-hide_banner", "-i", str(cam)], capture_output=True, **no_window())
    assert b"Video:" in p.stderr and b"Audio:" in p.stderr
    if shutil.which("ffprobe"):
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(cam)],
                               capture_output=True, check=True, **no_window())
        streams = json.loads(probe.stdout)["streams"]
        assert {s["codec_type"] for s in streams} == {"video", "audio"}
        assert next(s for s in streams if s["codec_type"] == "video")["width"] == 1280
    meta = json.loads(cam.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["resolution"] == [1280, 720] and meta["fps"] == 30
    assert abs(meta["start_offset_seconds"]) < 0.5
    assert meta["audio_muxed"] is True
    return cam


def test_kapaliyken_yalniz_ana_dosya(kayit_penceresi, qtbot, tmp_path):
    kaydet(kayit_penceresi, qtbot)
    assert not list(tmp_path.glob("*.kamera.*"))


def test_acikken_iki_oynatilabilir_sesli_dosya(kayit_penceresi, qtbot):
    kayit_penceresi.settings.record_camera = True
    kamera_dogrula(kaydet(kayit_penceresi, qtbot))

from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.settings_dialog import SettingsDialog
from matematigin_mantigi.ui.theme import FontFamilies


def test_ayar_varsayilan_kapali_kalici_ve_formda(qtbot, tmp_path):
    ini = str(tmp_path / "kamera.ini")
    s = AppSettings(QSettings(ini, QSettings.Format.IniFormat))
    assert s.record_camera is False
    dlg = SettingsDialog(s, FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(dlg)
    assert not dlg.record_camera_check.isChecked()
    dlg.record_camera_check.setChecked(True)
    assert dlg.value().record_camera is True
    s.record_camera = dlg.value().record_camera
    s._q.sync()
    assert AppSettings(QSettings(ini, QSettings.Format.IniFormat)).record_camera is True


def test_kodlayici_hatasi_ana_kaydi_bozmaz(kayit_penceresi, qtbot, monkeypatch):
    from matematigin_mantigi.core.camera_recorder import CameraRecorder
    from matematigin_mantigi.ui import error_notice
    notices = []
    monkeypatch.setattr(error_notice, "post", lambda *a, **k: notices.append((a, k)))
    def fail(self, frame, fps):
        raise OSError("sentetik kamera kodlayıcı hatası")
    monkeypatch.setattr(CameraRecorder, "_open", fail)
    win = kayit_penceresi
    win.settings.record_camera = True
    win.toggle_recording(True)
    qtbot.waitUntil(lambda: bool(win._camera_warning), timeout=15000)
    assert win.recorder.is_recording
    assert "camera-file" in win.toolbar._alerts
    assert "sentetik" not in win.toolbar._alerts["camera-file"]
    assert str(win.recorder.last_path.parent) not in win.work_area.status_label.text()
    qtbot.waitUntil(lambda: win.recorder.frames_written >= 35, timeout=15000)
    win.toggle_recording(False)
    qtbot.waitUntil(lambda: win._stop_worker is None, timeout=60000)
    assert media_duration(find_ffmpeg(), win.recorder.last_path) > 0
    assert not win.recorder.error
    assert any("sentetik kamera kodlayıcı hatası" in str(n) for n in notices)


def test_ayni_saniye_adlari_eslesir_ilk_dosya_korunur(kayit_penceresi, qtbot):
    import hashlib
    win = kayit_penceresi
    win.settings.record_camera = True
    first = kaydet(win, qtbot)
    cam = kamera_dogrula(first)
    digest = hashlib.sha256(cam.read_bytes()).hexdigest()
    second = kaydet(win, qtbot)
    assert second.name == "kayit_20261113-100000-2.mp4"
    kamera_dogrula(second)
    assert hashlib.sha256(cam.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("disabled", [True, False])
def test_kamera_kapali_veya_yokken_dosya_yok(window, tmp_path, qtbot, disabled):
    window.settings.record_camera = True
    if disabled:
        window.settings.set_visible("webcam", False)
        window.apply_ui_settings()
    window.recorder = MssFfmpegRecorder(lambda: tmp_path, fps=30, out_height=0, grabber=small_synthetic_grabber)
    window.settings.record_fps = 30
    kaydet(window, qtbot)
    assert not list(tmp_path.glob("*.kamera.*"))


def test_ham_wav_yoksa_sessiz_ve_uyarili(kayit_penceresi, qtbot):
    win = kayit_penceresi
    win.settings.audio_device = ""
    win.settings.record_camera = True
    main = kaydet(win, qtbot)
    camera = main.with_suffix(".kamera.mp4")
    assert media_duration(find_ffmpeg(), camera) > 0
    meta = json.loads(camera.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["audio_muxed"] is False and "sessiz" in meta["warning"]
    assert "sessiz" not in win.work_area.status_label.text()


def test_takilan_yazici_canli_uyari_verir_ana_kayit_surer(kayit_penceresi, qtbot, monkeypatch):
    import threading
    from matematigin_mantigi.core.camera_recorder import CameraRecorder
    entered, release = threading.Event(), threading.Event()
    original = CameraRecorder._open
    def slow(self, frame, fps):
        original(self, frame, fps)
        original_pipe = self._proc.stdin
        class Pipe:
            def write(_, data):
                entered.set()
                release.wait(15)
                return original_pipe.write(data)
            def close(_):
                original_pipe.close()
        self._proc.stdin = Pipe()
    monkeypatch.setattr(CameraRecorder, "_open", slow)
    monkeypatch.setattr(CameraRecorder, "STALL_SECONDS", 0.3)
    win = kayit_penceresi
    win.settings.record_camera = True
    win.toggle_recording(True)
    try:
        qtbot.waitUntil(entered.is_set, timeout=15000)
        qtbot.waitUntil(lambda: bool(win._camera_warning), timeout=3000)
        assert win.recorder.is_recording
        before = win.recorder.frames_written
        qtbot.waitUntil(lambda: win.recorder.frames_written > before + 5, timeout=15000)
        assert "camera-file" in win.toolbar._alerts
    finally:
        release.set()
        win.toggle_recording(False)
        qtbot.waitUntil(lambda: win._stop_worker is None, timeout=60000)
    assert win.recorder.last_path.exists() and not win.recorder.error
