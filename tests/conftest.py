import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS  # noqa: E402


@pytest.fixture
def sample_questions():
    return list(SAMPLE_QUESTIONS)


class FakeCamera:
    """N adet sentetik BGR kare üretir; sonra None döndürür."""

    def __init__(self, frames: int = 5, w: int = 320, h: int = 240, green: bool = True):
        self.frames, self.w, self.h, self.green = frames, w, h, green
        self.opened = False
        self.released = False
        self._i = 0

    def open(self) -> bool:
        self.opened = True
        return True

    def read(self):
        if self._i >= self.frames:
            return None
        self._i += 1
        img = np.empty((self.h, self.w, 3), np.uint8)
        img[:] = (30, 200, 40) if self.green else (90, 90, 90)
        img[self.h // 4: 3 * self.h // 4, self.w // 4: 3 * self.w // 4] = (20, 20, 220)
        return img

    def release(self) -> None:
        self.released = True


class DeadCamera:
    def open(self) -> bool:
        return False

    def read(self):
        return None

    def release(self) -> None:
        pass


@pytest.fixture
def fake_camera():
    return FakeCamera(frames=1000)


@pytest.fixture
def dead_camera():
    return DeadCamera()


@pytest.fixture
def ini_settings(tmp_path):
    from PyQt6.QtCore import QSettings
    from matematigin_mantigi.core.settings import AppSettings
    return AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))


@pytest.fixture
def window(qtbot, tmp_path, ini_settings, dead_camera):
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    ini_settings.set_pen(PenSettings(reading_ms=0))      # testlerde okuma animasyonu kapalı
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "oturum"), lambda: dead_camera,
                     tmp_path / "duzen.json")
    qtbot.addWidget(win)
    win.resize(1920, 1080)
    win.show()
    qtbot.waitExposed(win)
    win.activateWindow()          # Task 18 kısayolları WindowShortcut bağlamında çalışır
    return win
