import time
import wave

import numpy as np
import pytest

from matematigin_mantigi.core import audio_capture as ac


def test_list_and_resolve_prefer_wasapi_on_windows(monkeypatch):
    class SD:
        @staticmethod
        def query_hostapis():
            return [{"name": "MME"}, {"name": "Windows WASAPI"}]

        @staticmethod
        def query_devices(*a, **k):
            return [{"name": "Mik A", "max_input_channels": 1, "hostapi": 0},
                    {"name": "Hoparlör", "max_input_channels": 0, "hostapi": 1},
                    {"name": "Mik A", "max_input_channels": 2, "hostapi": 1},
                    {"name": "USB Mik", "max_input_channels": 1, "hostapi": 1}]
    monkeypatch.setattr(ac, "_sd", lambda: SD)
    assert ac.list_input_devices() == ["Mik A", "USB Mik"]
    assert ac.resolve_input_device("Mik A") == 2               # WASAPI kopyası, MME değil
    assert ac.resolve_input_device("usb") == 3                 # alt dize
    assert ac.resolve_input_device("yok böyle") is None and ac.resolve_input_device("") is None


def test_list_is_empty_without_portaudio(monkeypatch):
    def boom():
        raise OSError("PortAudio yok")
    monkeypatch.setattr(ac, "_sd", boom)
    assert ac.list_input_devices() == [] and ac.resolve_input_device("x") is None


def test_capture_writes_wav_and_measures_first_sample(tmp_path, monkeypatch):
    """Sahte PortAudio: callback'i ayrı iş parçacığından 20 ms'lik bloklarla besler."""
    import threading

    class FakeStream:
        def __init__(self, device, samplerate, channels, dtype, latency, callback):
            self.cb, self.rate, self.channels = callback, samplerate, channels
            self._run = threading.Event()

        def start(self):
            self._run.set()
            self._t = threading.Thread(target=self._feed, daemon=True); self._t.start()

        def _feed(self):
            class TI:
                inputBufferAdcTime = 0.0
                currentTime = 0.0
            block = np.full((int(self.rate * 0.02), self.channels), 1000, np.int16)
            for _ in range(25):                        # sabit 25 blok = 0,5 sn ses; duvar saatine bağlı değil
                self.cb(block, len(block), TI(), None)
                time.sleep(0.002)

        def stop(self):
            self._t.join(10)                           # tüm bloklar beslenmeden durmaz (yavaş CI'da da aynı sonuç)
            self._run.clear()

        def close(self):
            pass

    class SD:
        InputStream = FakeStream

        @staticmethod
        def query_hostapis():
            return [{"name": "CoreAudio"}]

        @staticmethod
        def query_devices(*a, **k):
            d = {"name": "MacBook Pro Microphone", "max_input_channels": 1, "hostapi": 0, "default_samplerate": 48000.0}
            return d if (a or k) else [d]
    monkeypatch.setattr(ac, "_sd", lambda: SD)
    cap = ac.AudioCapture("MacBook Pro Microphone")
    before = time.monotonic()
    cap.start(tmp_path / "a.wav")
    time.sleep(0.1)
    res = cap.stop()
    assert res.samplerate == 48000 and res.channels == 1
    # ilk örnek zamanı = geri çağrı anı - (sürücü gecikmesi + blok süresi 20 ms)
    assert res.first_sample_monotonic is not None and before - 0.05 <= res.first_sample_monotonic <= res.stopped_monotonic
    assert res.samples == 25 * 960 and abs(res.duration - 0.5) < 1e-6 and res.overflows == 0 and res.dropped_blocks == 0
    with wave.open(str(tmp_path / "a.wav")) as w:
        assert w.getframerate() == 48000 and w.getnframes() == res.samples and w.getsampwidth() == 2
    assert 0 < res.wall_duration < 5


@pytest.mark.skipif(not ac.list_input_devices(), reason="mikrofon yok")
def test_real_microphone_short_capture(tmp_path):
    cap = ac.AudioCapture(None)
    cap.start(tmp_path / "real.wav")
    time.sleep(0.6)
    res = cap.stop()
    assert res.samples > res.samplerate * 0.3 and res.first_sample_monotonic is not None
    assert res.dropped_blocks == 0
