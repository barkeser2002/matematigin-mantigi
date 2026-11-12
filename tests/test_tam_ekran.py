"""Tam ekran: düğme, F11/Esc ile pencereye dönüş, yan panelde kaydırmasız yerleşim."""
import json

import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from matematigin_mantigi.core.recorder import RecorderState
from test_main_window import close_question_never_blocks  # noqa: F401  (autouse: modal donmasın)


def _full(win, qtbot):
    win.showFullScreen()
    qtbot.waitUntil(win.isFullScreen)


def _focus_targets(win):
    return {
        "pencere": win,
        "tuval": win.canvas,
        "arac_dugmesi": win.toolbar.settings_button,
        "kayit_dugmesi": win.toolbar.record_button,
        "kaydirma": win.toolbar.scroll_area.viewport(),
    }


@pytest.mark.parametrize("key", [Qt.Key.Key_F11, Qt.Key.Key_Escape])
@pytest.mark.parametrize("hedef", ["pencere", "tuval", "arac_dugmesi", "kayit_dugmesi", "kaydirma"])
def test_f11_ve_esc_kayit_yokken_tam_ekrandan_pencereye_doner(window, qtbot, key, hedef):
    _full(window, qtbot)
    w = _focus_targets(window)[hedef]
    w.setFocus()
    qtbot.keyClick(w, key)
    qtbot.waitUntil(lambda: not window.isFullScreen(), timeout=3000)


def test_f11_pencereden_tam_ekrana_gecer(window, qtbot):  
    assert not window.isFullScreen()
    qtbot.keyClick(window.toolbar.settings_button, Qt.Key.Key_F11)
    qtbot.waitUntil(window.isFullScreen, timeout=3000)


def test_esc_yazi_kutusu_aciksa_once_kutuyu_kapatir(window, qtbot):  
    _full(window, qtbot)
    window.canvas.begin_text(QPointF(100, 100))
    assert window.canvas.text_edit.isVisible()
    qtbot.keyClick(window.canvas.text_edit, Qt.Key.Key_Escape)
    assert not window.canvas.text_edit.isVisible()
    assert window.isFullScreen()
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not window.isFullScreen(), timeout=3000)


def test_esc_duzen_modundayken_once_duzenden_cikar(window, qtbot):  
    _full(window, qtbot)
    window.work_area.set_edit_mode(True)
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert not window.work_area.edit_mode and window.isFullScreen()
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not window.isFullScreen(), timeout=3000)


def test_kilit_kayit_bitince_kalkar_ve_f11_yeniden_calisir(window, qtbot):  
    _full(window, qtbot)
    window.toggle_recording(True)
    qtbot.keyClick(window, Qt.Key.Key_F11)
    assert window.isFullScreen()
    window.toggle_recording(False)
    qtbot.waitUntil(lambda: window.toolbar.record_button.isEnabled(), timeout=15000)
    assert window.recorder.state is not RecorderState.RECORDING
    qtbot.keyClick(window, Qt.Key.Key_F11)
    qtbot.waitUntil(lambda: not window.isFullScreen(), timeout=3000)


def _onizleme_ac(window, qtbot):
    from PyQt6.QtGui import QGuiApplication
    from matematigin_mantigi.ui.main_window import _Preview
    p = _Preview(None)
    p.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
    qtbot.addWidget(p)
    p.show()
    qtbot.waitExposed(p)
    p.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is p, timeout=3000)
    window._preview = p
    p.fullscreenKey.connect(window._toggle_fullscreen)     # _configure_screens'in yaptığı bağ
    p.escapeKey.connect(window._escape)
    return p


@pytest.mark.parametrize("key", [Qt.Key.Key_F11, Qt.Key.Key_Escape])
def test_onizleme_penceresi_etkinken_de_tam_ekrandan_cikilir(window, qtbot, key):
    """Çift ekranda kamera önizlemesine tıklanınca etkin pencere o olur; WindowShortcut ana pencerede
    kaldığı için F11/Esc hiç çalışmıyordu."""
    _full(window, qtbot)
    p = _onizleme_ac(window, qtbot)
    qtbot.keyClick(p, key)
    qtbot.waitUntil(lambda: not window.isFullScreen(), timeout=3000)
    window._preview = None


def test_esc_ayarlar_gibi_baska_pencerede_tam_ekrani_kapatmaz(window, qtbot):
    from PyQt6.QtWidgets import QDialog
    _full(window, qtbot)
    d = QDialog(window)
    qtbot.addWidget(d)
    d.show()
    d.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is d, timeout=3000)
    qtbot.keyClick(d, Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not d.isVisible(), timeout=3000)     # Esc kendi işini yaptı
    assert window.isFullScreen()


# --- düğme -----------------------------------------------------------------------------------
def test_tam_ekran_dugmesi_gorunur_ve_durum_gosterir(window, qtbot):  
    b = window.toolbar.fullscreen_button
    assert b.isVisible() and b.isEnabled()
    assert "Tam ekran" in b.text() and "F11" in b.toolTip()
    qtbot.mouseClick(b, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(window.isFullScreen, timeout=3000)
    qtbot.waitUntil(lambda: "Pencere" in b.text(), timeout=3000)
    assert "F11" in b.toolTip()
    qtbot.mouseClick(b, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not window.isFullScreen(), timeout=3000)
    qtbot.waitUntil(lambda: "Tam ekran" in b.text(), timeout=3000)


def test_durum_baska_yoldan_degisince_dugme_uyumlu_kalir(window, qtbot):  
    window.showFullScreen()
    qtbot.waitUntil(lambda: "Pencere" in window.toolbar.fullscreen_button.text(), timeout=3000)
    window.showNormal()
    qtbot.waitUntil(lambda: "Tam ekran" in window.toolbar.fullscreen_button.text(), timeout=3000)


def test_kayit_surerken_dugme_kilitli_ve_nedeni_ipucunda(window, qtbot):  
    _full(window, qtbot)
    b = window.toolbar.fullscreen_button
    window.toggle_recording(True)
    assert not b.isEnabled() and "kayıt" in b.toolTip().lower()
    qtbot.keyClick(window, Qt.Key.Key_F11)
    assert window.isFullScreen()
    assert window.toolbar.alert_label.isVisible() and "pencere" in window.toolbar.alert_label.text().lower()
    window.toggle_recording(False)
    qtbot.waitUntil(lambda: b.isEnabled(), timeout=15000)
    assert "F11" in b.toolTip()


# --- yan panel kaydırması ---------------------------------------------------------------------
def _ekran(tmp_path, monkeypatch, w, h):
    return w, h


@pytest.mark.parametrize("h", [1080, 1040, 1000, 980, 950, 900, 768, 728, 700])
def test_yan_panel_tam_ekran_yuksekliklerinde_kaydirmasiz_sigar(qtbot, h):
    from matematigin_mantigi.ui.theme import FontFamilies
    from matematigin_mantigi.ui.toolbar import ToolBar
    tb = ToolBar(FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(tb)
    tb.show()
    tb.resize(88, h)
    QApplication.processEvents()
    sa = tb.scroll_area
    assert not sa.verticalScrollBar().isVisible(), (h, tb.tier, tb.content.sizeHint().height(), sa.viewport().height())
    assert tb.content.sizeHint().height() <= sa.viewport().height(), (h, tb.tier)
    from PyQt6.QtWidgets import QAbstractButton
    vp = sa.viewport().rect()
    for btn in tb.content.findChildren(QAbstractButton):
        if not btn.isVisible():
            continue
        r = btn.rect().translated(btn.mapTo(sa.viewport(), btn.rect().topLeft()))
        assert vp.contains(r), (h, tb.tier, btn.text())
    assert tb.fullscreen_button.isVisible()


CHILD = r"""
import json, sys, tempfile
from pathlib import Path
from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import QAbstractButton, QApplication
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, PenSettings
from matematigin_mantigi.core.recorder import NullRecorder
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.main_window import MainWindow
from matematigin_mantigi.ui.theme import FontFamilies

app = QApplication([])
# Varsayılan platform fontuna ek olarak gerçek, genişletilmiş bir sans ile de sına.
# Punto tek başına yetmez: düğmelerin QSS'si 10px, fakat aile/glif genişliği miras alınır.
if len(sys.argv) > 1 and sys.argv[1] != "default":
    from PyQt6.QtGui import QFont
    from matematigin_mantigi import paths
    from matematigin_mantigi.ui.theme import load_fonts
    fam = load_fonts(paths.FONTS_DIR)
    font = QFont(fam.sans, 11)
    font.setStretch(int(sys.argv[1]))
    app.setFont(font)
tmp = Path(tempfile.mkdtemp())
st = AppSettings(QSettings(str(tmp / "x.ini"), QSettings.Format.IniFormat))
st.set_pen(PenSettings(reading_ms=0))
win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), st, NullRecorder(),
                 SessionStore(tmp / "oturum"), lambda i: None, tmp / "duzen.json")
win.show()
win.showFullScreen()
scr = win.screen().geometry()
def sonuc():
    tb = win.toolbar; sa = tb.scroll_area; vp = sa.viewport()
    taşan = [b.text() for b in tb.content.findChildren(QAbstractButton)
             if b.isVisible() and not vp.rect().contains(b.rect().translated(b.mapTo(vp, b.rect().topLeft())))]
    from PyQt6.QtWidgets import QPushButton, QStyle, QStyleOptionButton
    metin_tasan = []
    for b in tb.content.findChildren(QPushButton):
        if not b.isVisible():
            continue
        opt = QStyleOptionButton()
        b.initStyleOption(opt)
        room = b.style().subElementRect(QStyle.SubElement.SE_PushButtonContents, opt, b)
        shown = QPushButton.text(b)  # WrapButton.text() mantıksal metindir; boyanan satırları ölç.
        if any(b.fontMetrics().horizontalAdvance(line) > room.width() for line in shown.splitlines()):
            metin_tasan.append([b.text(), shown, room.width()])
    print(json.dumps({"tam": win.isFullScreen(), "w": win.width(), "h": win.height(), "tier": tb.tier,
                      "bar": sa.verticalScrollBar().isVisible(), "tasan": taşan,
                      "metin_tasan": metin_tasan, "viewport": [vp.width(), vp.height()],
                      "icerik": [tb.content.width(), tb.content.height()],
                      "dugme": tb.fullscreen_button.text()}))
    app.quit()
def bekle(n=0):
    if (win.isFullScreen() and win.width() == scr.width() and win.height() == scr.height()) or n > 300:
        QTimer.singleShot(200, sonuc)
    else:
        QTimer.singleShot(20, lambda: bekle(n + 1))
bekle()
QTimer.singleShot(20000, app.quit)
app.exec()
"""


@pytest.mark.parametrize("stretch,dpi", [("default", 96), (160, 96), (160, 120)])
@pytest.mark.parametrize("w,h", [(1920, 1080), (1366, 768), (1280, 720)])
def test_gercek_pencere_tam_ekranda_yan_panel_kaydirmasiz(tmp_path, w, h, stretch, dpi):
    """Gerçek MainWindow, w x h ekranda tam ekran: araç çubuğunda dikey kaydırma çubuğu yok, düğmeler sığıyor."""
    import os
    import subprocess
    import sys
    # Yapılandırma fiziksel piksel ister; (w,h) hedef mantıksal Qt boyutudur.
    cfg = {"screens": [{"name": "S", "x": 0, "y": 0, "width": round(w * dpi / 96),
                        "height": round(h * dpi / 96), "logicalDpi": dpi,
                        "logicalBaseDpi": 96, "dpr": 1.0}]}
    (tmp_path / "ekranlar.json").write_text(json.dumps(cfg), encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen:configfile=ekranlar.json", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    p = subprocess.run([sys.executable, "-c", CHILD, str(stretch)], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=90)
    lines = [ln for ln in p.stdout.splitlines() if ln.startswith("{")]
    assert p.returncode == 0 and lines, (p.returncode, p.stdout, p.stderr[-1500:])
    r = json.loads(lines[-1])
    details = json.dumps(r, ensure_ascii=False)  # pytest sözlüğü kısaltmasın; CI tam ölçümü saklasın.
    assert r["tam"] and (r["w"], r["h"]) == (w, h), details
    assert not r["bar"] and not r["tasan"], details
    assert not r["metin_tasan"], details
    assert "Pencere" in r["dugme"], details
