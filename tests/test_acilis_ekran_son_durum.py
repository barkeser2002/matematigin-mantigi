"""Adı ve ayrı geometrisi olan gerçek Qt ekranlarıyla açılışı doğrular."""
import json
import os
import subprocess
import sys

import pytest


CHILD = r'''
import json
from pathlib import Path
import sys
import time
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox
from matematigin_mantigi import app as app_mod
from matematigin_mantigi.core.autostart import Autostart
from matematigin_mantigi.core.settings import AppSettings, SessionState
from matematigin_mantigi.ui.dual_screen import screen_key
from matematigin_mantigi.ui.main_window import MainWindow
from matematigin_mantigi.ui.theme import FontFamilies

app = QApplication([])
root = Path.cwd()
startup, mode, geometry_case = sys.argv[1:]
board = app.screens()[1]
avail = board.availableGeometry()
geometry = {
    "other": (30, 40, 1000, 700),
    "inside": (avail.x() + 60, avail.y() + 70, 640, 480),
    "oversized": (avail.x(), avail.y(), 4000, 2400),
    "missing": (9000, 9000, 640, 480),
    "partial": (avail.right() - 100, avail.y() + 40, 640, 480),
    "none": None,
}[geometry_case]
settings = AppSettings(QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat))
settings.set_visible("webcam", False)
settings.board_screen_key = screen_key(board)
assert settings.board_screen_key is not None
if mode != "first":
    settings.session_state = SessionState(fullscreen=mode == "fullscreen", geometry=geometry)
settings.sync()
# Yeni ayar nesnesi de diske yazılmış son durumu okumalı.
settings = AppSettings(QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat))
configured = []
original = MainWindow._configure_screens
def observe(self, *args, **kwargs):
    original(self, *args, **kwargs)
    configured.append(True)
MainWindow._configure_screens = observe
QMessageBox.exec = lambda box: (_ for _ in ()).throw(AssertionError(box.text()))
args = app_mod.parse_args(["mm", "--kamera-yok", "--duzen", str(root / "layout.json"),
                           *(["--baslangic"] if startup != "normal" else [])])
win = app_mod.build_window(args, FontFamilies("Arial", "Arial", False), settings,
                           Autostart(platform="linux", frozen=True, executable="/app/mm", config_home=root / "cfg"))
if startup == "delayed":
    actual_screens = QApplication.screens
    QApplication.screens = staticmethod(lambda: actual_screens()[:1])
win.show()
if startup == "delayed":
    app.processEvents()
    assert win._startup_screen_timer.isActive()
    QApplication.screens = actual_screens
deadline = time.monotonic() + 10
while not configured and time.monotonic() < deadline:
    app.processEvents()
assert configured, "Açılış ekranı ayarları uygulanmadı"
app.processEvents()
assert win.isFullScreen() is (mode != "window"), (mode, win.isFullScreen())
assert win.screen() is board, (win.screen().name(), board.name())
if mode == "window":
    assert avail.contains(win.frameGeometry()), (avail, win.frameGeometry())
    if geometry_case == "inside":
        g = win.geometry()
        assert (g.x(), g.y(), g.width(), g.height()) == geometry
else:
    assert win.size() == board.size(), (win.size(), board.size())
print(json.dumps({"screen": win.screen().name(), "fullscreen": win.isFullScreen(),
                  "geometry": win.geometry().getRect()}), flush=True)
win.close()
win.webcam_panel.shutdown()
app.processEvents()
'''


@pytest.mark.parametrize("startup", ["normal", "startup", "delayed"])
@pytest.mark.parametrize("board_size", [(1280, 720), (1920, 1080)])
@pytest.mark.parametrize("geometry_case", ["other", "inside", "oversized", "missing", "partial", "none"])
def test_window_mode_is_fitted_to_the_selected_board_screen(tmp_path, startup, board_size, geometry_case):
    _run_launch(tmp_path, startup, board_size, "window", geometry_case)


@pytest.mark.parametrize("startup", ["normal", "startup"])
@pytest.mark.parametrize("mode", ["fullscreen", "first"])
def test_fullscreen_and_first_launch_use_the_selected_board_screen(tmp_path, startup, mode):
    _run_launch(tmp_path, startup, (1280, 720), mode, "other")


def _run_launch(tmp_path, startup, board_size, mode, geometry_case):
    w, h = board_size
    config = tmp_path / "screens.json"
    config.write_text(json.dumps({"screens": [
        {"name": "monitor", "x": 0, "y": 0, "width": 1920, "height": 1080, "dpr": 1},
        {"name": "tablet", "x": 1920, "y": 0, "width": w, "height": h, "dpr": 1},
    ]}), encoding="utf-8")
    env = {**os.environ, "QT_QPA_PLATFORM": f"offscreen:configfile={config}",
           "XDG_CONFIG_HOME": str(tmp_path / "config")}
    child = subprocess.run([sys.executable, "-c", CHILD, startup, mode, geometry_case], cwd=tmp_path,
                           env=env, capture_output=True, text=True, timeout=60)
    assert child.returncode == 0, child.stdout + child.stderr
    result = json.loads(child.stdout.strip().splitlines()[-1])
    assert result["screen"] == "tablet"
    assert result["fullscreen"] is (mode != "window")
