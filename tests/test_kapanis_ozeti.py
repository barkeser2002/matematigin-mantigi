"""'Durdur ve çık' kapanışı uçtan uca: gerçek app.main ayrı süreçte (Qt'nin otomatik çıkışı ve sürecin gerçekten bitip
bitmediği süreç içinde görünmez). Gerçek modal pencereler (kapanış sorusu, kayıt sonucu) betikteki bir yanıtlayıcıyla
tıklanır; ayarlar geçici INI dosyasında (Windows kayıt defterine / macOS plist'ine dokunulmaz)."""
import json
import os
import subprocess
import sys

import pytest

CHILD = r'''
import errno, json, os, sys, threading
from pathlib import Path
from PyQt6 import sip
from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox
from matematigin_mantigi import app as app_mod
from matematigin_mantigi.core.recorder import NullRecorder
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.error_notice import POLL_MS
from matematigin_mantigi.ui.main_window import STOP_AND_QUIT

MODE = sys.argv[1]
# Süreç asılı kalırsa (pencere kapandı ama Qt'nin kuyruktaki çıkışı iptal edildi) kısmi çıktıyla kendini bitirir.
watchdog = threading.Timer(30, lambda: (print("ZAMAN_ASIMI", flush=True), os._exit(3)))
watchdog.daemon = True
watchdog.start()
real_build = app_mod.build_window
answered = set()
stray = []


def out(*a):
    print(*a, flush=True)


def notice_boxes():
    """Görünür uyarı kutuları (modal olmayan QMessageBox)."""
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()
            and not w.isModal()]


def later(cond, then, tries=200):
    if cond() or tries <= 0:
        then()
    else:
        QTimer.singleShot(25, lambda: later(cond, then, tries - 1))


def answer_modals():
    """Gerçek modal pencereleri yanıtlar: kapanış sorusunda 'Durdur ve çık', ötekilerde Tamam. Tamam birkaç yoklama
    aralığı sonra basılır: modal açıkken yoklama uyarı kutusunu açabilecekse açsın (eskiden kutu modalın çocuğu
    olup onunla siliniyordu). 'hata' senaryosunda özet açıkken yeni bir uyarı gelir (özetin çocuğu olarak görünür,
    özetle silinir; kapanan pencerenin altında yeniden açılmamalı)."""
    m = QApplication.activeModalWidget()
    if isinstance(m, QMessageBox) and m.isVisible() and sip.unwrapinstance(m) not in answered:
        answered.add(sip.unwrapinstance(m))
        out("MODAL " + json.dumps(m.text()))
        stop = [b for b in m.buttons() if b.text() == STOP_AND_QUIT]
        if stop:
            QTimer.singleShot(50, stop[0].click)
            return
        if MODE == "hata":
            QTimer.singleShot(0, late_boom)
        ok = m.buttons()[0]

        def click():
            out("MODAL_KAPANIRKEN_GORUNEN_KUTU", len(notice_boxes()))
            ok.click()
        QTimer.singleShot(3 * POLL_MS, click)


def late_boom():
    raise ValueError("özet açıkken gelen yapay hata")


class Rec(NullRecorder):
    """Kapanışı _StopWorker'da koşan sahte kaydedici; sonuç alanları (kendi metinleri) senaryodan."""
    stop_is_quick = False
    error = audio_error = None

    def __init__(self):
        super().__init__()
        self.release = threading.Event()

    def stop(self):
        super().stop()                          # kayıt bitti (IDLE), sonuç henüz pencereye ulaşmadı
        self.release.wait(20)
        if MODE == "hata":
            self.error = "yapay kapanış hatası, ham dosyalar silinmedi"
        self.audio_error = "Mikrofon kayıt sırasında kesildi (yapay)"
        return Path("rec") / "kayit_yapay.mp4"


def build(args, fam, settings=None):
    win = real_build(args, fam, AppSettings(QSettings("ayarlar.ini", QSettings.Format.IniFormat)))
    win.recorder = rec = Rec()
    store = win.session_store
    modals = QTimer(QApplication.instance()); modals.setInterval(20); modals.timeout.connect(answer_modals)
    modals.start()
    QApplication.instance().aboutToQuit.connect(lambda: out("CIKISTA_GORUNEN_KUTU", len(notice_boxes())))

    def boom():
        raise OSError("kayıt sırasında yapay yuva hatası")

    def snapshot_fails():                       # gerçek yuva: soru değişirken tahta PNG'si yazılamıyor (disk dolu)
        win.canvas.is_empty = lambda: False
        def full(*a, **k):
            raise OSError(errno.ENOSPC, "No space left on device", "oturum")
        store.save_snapshot = full
        win.flow.next_question()

    def start():
        if MODE == "yetim":                     # kapanış yolunun bilmediği, görünür başka bir üst düzey pencere
            stray.append(QLabel("başıboş pencere"))
            stray[0].show()
        win.toggle_recording(True)
        QTimer.singleShot(0, boom)
        QTimer.singleShot(0, snapshot_fails)
        later(lambda: "2 uyarı" in win.toolbar.alert_label.text(), close)

    def close():
        out("SERIT " + win.toolbar.alert_label.text())
        win.close()                             # kapanış sorusu (gerçek modal) -> 'Durdur ve çık'
        if MODE != "hata":                      # kayıt bitti ama sonuç pencereye ulaşmadan yoklama kutuyu açtı
            later(lambda: bool(notice_boxes()), rec.release.set)
        else:
            rec.release.set()

    later(lambda: win.isVisible(), start)
    return win


app_mod.build_window = build
code = app_mod.main(["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx", "--duzen", "duzen.json"])
out("EXEC", code)
sys.exit(code)
'''


def _text(x) -> str:
    return x.decode("utf-8", "replace") if isinstance(x, bytes) else (x or "")


def _run(tmp_path, mode: str):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    try:
        p = subprocess.run([sys.executable, "-c", CHILD, mode], cwd=tmp_path, env=env, capture_output=True,
                           text=True, timeout=90)
    except subprocess.TimeoutExpired as e:          # iç bekçi de takılırsa: kısmi çıktıyla kırmızı
        pytest.fail(f"süreç çıkmadı:\n{_text(e.stdout)}\n{_text(e.stderr)[-2000:]}")
        raise
    lines = p.stdout.splitlines()
    assert "ZAMAN_ASIMI" not in lines and p.returncode == 0, (p.returncode, p.stdout, p.stderr[-2000:])
    assert "EXEC 0" in lines and "CIKISTA_GORUNEN_KUTU 0" in lines, lines
    return lines


@pytest.mark.parametrize("mode", ["basari", "hata"])
def test_stop_and_quit_shows_one_summary_and_the_process_exits(tmp_path, mode):
    """P1 uçtan uca (gerçek app.main): kayıt sırasında iki uyarı birikir (yuvada istisna ve 'Tahta görüntüsü
    kaydedilemedi'), öğretmen pencereyi kapatıp 'Durdur ve çık' der. Kayıt başarıyla bittiyse eskiden pencere kapanıyor,
    uyarılar ve mikrofon uyarısı hiç görünmüyordu (kutu da gizli pencerenin çocuğu olarak ekranda kalıyordu); hatayla
    bittiyse 'Kayıt hatası'nın çocuğu olarak silinen kutu gizli ana pencerenin altında yeniden açılıyor, Qt'nin
    kuyruktaki çıkışını siliyordu: pencere kapanıyor, SÜREÇ ÇIKMIYORDU (Windows'ta görünmez arka plan süreci). Şimdi
    kapanış sorusundan sonra TEK pencere: sonuç, ses uyarısı ve iki uyarı; sonra süreç 0 ile çıkar, arkada kutu kalmaz.
    Özet açıkken gelen uyarı ('hata') özetin üstünde görünür, kapanan pencerenin altında yeniden açılmaz. Uyarılar
    hatalar.log'da da durur."""
    lines = _run(tmp_path, mode)
    modals = [json.loads(line[len("MODAL "):]) for line in lines if line.startswith("MODAL ")]
    assert len(modals) == 2 and modals[0] == "Kayıt sürüyor, durdurulup çıkılsın mı?", modals
    summary = modals[1]
    for part in ("kayıt sırasında yapay yuva hatası", "Tahta görüntüsü kaydedilemedi",
                 "Mikrofon kayıt sırasında kesildi (yapay)"):
        assert part in summary, summary
    assert ("yapay kapanış hatası, ham dosyalar silinmedi" if mode == "hata" else "kayit_yapay.mp4") in summary, summary
    late = 1 if mode == "hata" else 0             # özet açıkken gelen uyarı özetin üstünde görüldü
    assert f"MODAL_KAPANIRKEN_GORUNEN_KUTU {late}" in lines, lines
    log = (tmp_path / "hatalar.log").read_text(encoding="utf-8")
    assert "Tahta görüntüsü kaydedilemedi" in log and "kayıt sırasında yapay yuva hatası" in log, log
    assert mode != "hata" or "özet açıkken gelen yapay hata" in log, log


def test_closing_the_main_window_ends_the_process_even_if_another_window_is_left_open(tmp_path):
    """Ana pencere kapanınca süreç biter. Qt'nin kendi kuralı ('son pencere kapanınca çık') görünür başka bir üst düzey
    pencere oldukça bekler: kapanış yolunun bilmediği bir pencere (P1'deki uyarı kutusu gibi) pencere kapandıktan sonra
    süreci açık tutuyordu; ekran dışında ya da gizli pencerenin altında kalınca bu, görünmez arka plan süreci demek.
    app.main ana pencerenin kapanışında süreci açıkça bitirir; sonuç ve uyarılar yine kapanmadan önce gösterilir."""
    lines = _run(tmp_path, "yetim")
    modals = [json.loads(line[len("MODAL "):]) for line in lines if line.startswith("MODAL ")]
    assert len(modals) == 2 and "kayit_yapay.mp4" in modals[1], modals
