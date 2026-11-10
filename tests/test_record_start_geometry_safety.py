import pytest
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QTimer, Qt

from matematigin_mantigi.core.recorder import MssFfmpegRecorder, MicrophoneStartError, RecorderState


@pytest.mark.parametrize('preflight', [False, True])
def test_minimize_during_silent_confirmation_never_starts(window, monkeypatch, tmp_path, preflight):
    calls, warnings = [], []
    class Recorder(MssFfmpegRecorder):
        def start(self, rect, fps=60, **kwargs):
            calls.append(kwargs)
            if kwargs.get('require_audio'):
                raise MicrophoneStartError('Mikrofon açılamadı')
            raise AssertionError('Simge durumunda kayıt başlatıldı')
    window.settings.audio_device = 'mic' if preflight else None
    monkeypatch.setattr('matematigin_mantigi.core.audio_capture.resolve_input_device', lambda _: 0)
    window.recorder = Recorder(lambda: tmp_path, audio_device=window.settings.audio_device)
    def answer(*args):
        window.showMinimized()
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', answer)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    window.toggle_recording(True)
    assert len(calls) == int(preflight)
    assert window.recorder.state is RecorderState.IDLE
    assert not window.toolbar.record_button.isChecked()
    assert window._record_rect is None and not window._record_starting
    assert warnings


@pytest.mark.parametrize('change', ['restore', 'queued', 'close'])
def test_confirmation_changes_are_not_erased(window, qtbot, monkeypatch, change):
    from matematigin_mantigi.core.recorder import NullRecorder
    warnings = []
    class Recorder(NullRecorder):
        audio_device = None
    window.recorder = Recorder()
    window.settings.audio_device = 'missing'
    monkeypatch.setattr('matematigin_mantigi.core.audio_capture.resolve_input_device', lambda _: None)
    def answer(*args):
        qtbot.keyClick(window, Qt.Key.Key_R)  # nested input must not start another recording
        if change == 'restore':
            window.showMinimized()
            window.showNormal()
        elif change == 'queued':
            QTimer.singleShot(0, window.showMinimized)
        else:
            window.close()
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', answer)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    window.toggle_recording(True)
    assert not window.recorder.is_recording and window.recorder.last_rect is None
    assert window._record_rect is None and not window._record_starting
    assert warnings


def test_confirmation_settles_before_first_frame(window, monkeypatch):
    from matematigin_mantigi.core.recorder import NullRecorder
    events = []
    class Recorder(NullRecorder):
        audio_device = None
        def start(self, rect, fps=60):
            events.append('capture')
            super().start(rect, fps)
    window.recorder = Recorder()
    window.settings.audio_device = 'missing'
    monkeypatch.setattr('matematigin_mantigi.core.audio_capture.resolve_input_device', lambda _: None)
    def answer(*args):
        QTimer.singleShot(0, lambda: events.append('modal-close-events'))
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', answer)
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Ok)
    window.toggle_recording(True)
    assert events == ['modal-close-events', 'capture']
    window.toggle_recording(False)


def test_real_recorder_failed_microphone_keeps_raw_audio_on_minimize(window, monkeypatch, tmp_path):
    from matematigin_mantigi.core.recorder import find_ffmpeg
    from tests.test_recorder import synthetic_grabber
    if find_ffmpeg() is None:
        pytest.skip('ffmpeg yok')
    class BrokenAudio:
        def __init__(self, device):
            pass
        def start(self, path):
            path.write_bytes(b'raw audio')
            raise RuntimeError('device busy')
        def stop(self):
            pass
    window.settings.audio_device = 'mic'
    monkeypatch.setattr('matematigin_mantigi.core.audio_capture.resolve_input_device', lambda _: 0)
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path, fps=10, grabber=synthetic_grabber,
                                                audio_device='mic', audio_factory=BrokenAudio, out_height=0)
    def answer(*args):
        window.showMinimized()
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', answer)
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: QMessageBox.StandardButton.Ok)
    window.toggle_recording(True)
    assert rec.state is RecorderState.IDLE and rec.audio_device == 'mic'
    assert [p.read_bytes() for p in tmp_path.glob('*.wav')] == [b'raw audio']
    assert not list(tmp_path.glob('*.mp4'))
