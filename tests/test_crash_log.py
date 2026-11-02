import os
import re
import subprocess
import sys
import textwrap
import threading

import pytest
from PyQt6.QtCore import QThread

from matematigin_mantigi.core import crash_log

# Gerçek giriş noktası (app.main) ayrı süreçte: varsayılan kancayla PyQt6 yuvadaki yakalanmamış istisnada qFatal
# ile süreci öldürür; bunu ancak gerçek bir süreç gösterir (pytest-qt kendi kancasını kurduğu için süreç içinde
# görünmez). Pencere gerçek build_window'dan gelir; yalnız bir zamanlayıcı yuvası bilerek patlar.
_E2E = textwrap.dedent('''
    import sys
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from matematigin_mantigi import app as app_mod

    real_build = app_mod.build_window

    def build(args, fam, settings=None):
        win = real_build(args, fam, settings)
        def boom():
            raise OSError("yapay yuva hatası")
        def report():
            boxes = [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]
            print("AYAKTA", len(boxes), [b.isModal() for b in boxes], flush=True)
            win.close()
            QApplication.instance().quit()
        QTimer.singleShot(100, boom)
        QTimer.singleShot(1500, report)
        return win

    app_mod.build_window = build
    sys.exit(app_mod.main(["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx", "--duzen", "duzen.json"]))
''')

# Aynı senaryo süren bir kayıtla: gerçek ffmpeg kaydedicisi (sentetik ekran karesiyle) istisnadan önce başlar,
# istisnadan sonra durdurulur; son MP4 oluşmalı ve istisnadan sonra da kare yazılmış olmalı.
_E2E_REC = textwrap.dedent('''
    import sys
    from pathlib import Path
    import numpy as np
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from matematigin_mantigi import app as app_mod
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, record_rect_for

    real_build = app_mod.build_window
    frame = np.full((120, 160, 4), 255, np.uint8)

    def build(args, fam, settings=None):
        win = real_build(args, fam, settings)
        rec = MssFfmpegRecorder(lambda: Path("rec"), fps=10, grabber=lambda r: frame, out_height=0)
        at_boom = []
        def boom():
            at_boom.append(rec.frames_written)
            raise OSError("kayıt sırasında yapay yuva hatası")
        def stop():
            path = rec.stop()
            print("KAYIT", path is not None and path.exists(), at_boom[0], rec.frames_written, flush=True)
            win.close()
            QApplication.instance().quit()
        QTimer.singleShot(100, lambda: rec.start(record_rect_for(win.work_area.recording_rect()), fps=10))
        QTimer.singleShot(700, boom)
        QTimer.singleShot(1700, stop)
        return win

    app_mod.build_window = build
    sys.exit(app_mod.main(["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx", "--duzen", "duzen.json"]))
''')


def _run(tmp_path, source: str) -> subprocess.CompletedProcess:
    script = tmp_path / "calistir.py"
    script.write_text(source, encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    return subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env, capture_output=True, text=True,
                          timeout=120)


def test_app_survives_unhandled_slot_exception_and_logs_it(tmp_path):
    """app#2: sys.excepthook yoktu; herhangi bir yuvadaki istisna PyQt6'nın qFatal'ıyla uygulamayı ders ortasında
    öldürüyor, süren kayıt birleştirilmeden kalıyordu. Artık hata veri klasöründeki hatalar.log'a zaman damgası
    ve traceback'le yazılır, uygulama çalışmaya devam eder."""
    r = _run(tmp_path, _E2E)
    assert r.returncode == 0, f"süreç düştü ({r.returncode}):\n{r.stderr[-2000:]}"
    assert "AYAKTA 1 [False]" in r.stdout          # tek uyarı kutusu açıldı ve modal değil (ders sürer)
    log = (tmp_path / "hatalar.log").read_text(encoding="utf-8")       # dev modunda veri klasörü = çalışma dizini
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", log)
    assert "Traceback (most recent call last)" in log and "OSError: yapay yuva hatası" in log
    assert "in boom" in log


def test_recording_continues_through_unhandled_slot_exception(tmp_path):
    """Ders ortasındaki istisna kaydı da kaybettirmez: kayıt istisnadan sonra kare yazmayı sürdürür ve durdurulunca
    son MP4 oluşur (önceden süreç ölüyor, birleştirilmemiş ara dosyalar kalıyordu)."""
    from matematigin_mantigi.core.recorder import find_ffmpeg
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    r = _run(tmp_path, _E2E_REC)
    assert r.returncode == 0, f"süreç düştü ({r.returncode}):\n{r.stderr[-2000:]}"
    m = re.search(r"KAYIT (\w+) (\d+) (\d+)", r.stdout)
    assert m and m.group(1) == "True", r.stdout
    assert int(m.group(3)) > int(m.group(2)) > 0           # istisnadan sonra da kare yazıldı
    assert "kayıt sırasında yapay yuva hatası" in (tmp_path / "hatalar.log").read_text(encoding="utf-8")


def test_startup_error_is_logged_and_exits_cleanly(tmp_path):
    """Açılışta (olay döngüsünden önce) patlayan hata da günlüğe düşer; uyarı kuyruğu çıkışta süreci çökertmez
    (Python'un normal hata çıkışı 1, abort/segfault değil)."""
    r = _run(tmp_path, textwrap.dedent('''
        import sys
        from matematigin_mantigi import app as app_mod
        def build(args, fam, settings=None):
            raise RuntimeError("açılışta yapay hata")
        app_mod.build_window = build
        sys.exit(app_mod.main(["matematigin-mantigi"]))
    '''))
    assert r.returncode == 1, r.stderr[-2000:]
    assert "RuntimeError: açılışta yapay hata" in (tmp_path / "hatalar.log").read_text(encoding="utf-8")


# --- süreç içi: kancanın kendi sözleşmesi -------------------------------------------------------------------
@pytest.fixture
def installed(tmp_path):
    """Kancayı tmp_path'teki günlükle geçici kurar. sys/threading kancaları global durum: test sonunda (pytest-qt'nin
    kendi yakalama kancası dahil) eski hâline döner."""
    prev = (sys.excepthook, threading.excepthook)
    notes = []
    log = crash_log.install(tmp_path / "hatalar.log", notify=lambda title, text, key: notes.append((title, text)))
    yield log, notes
    crash_log.uninstall(log)
    sys.excepthook, threading.excepthook = prev


def _exc_info(msg: str = "yapay"):
    try:
        raise OSError(msg)                     # her çağrıda aynı satır: aynı kod yolu, aynı hata
    except OSError:
        return sys.exc_info()


def test_repeated_error_is_logged_once_then_only_counted(installed):
    """Saniyede onlarca kez patlayan bir yuva (ör. çizim olayı) günlüğü ve ekranı doldurmasın: aynı hata (tür +
    kod yolu; mesajı değişse de) bir kez tam yazılır, sonra yalnız 10., 100. … tekrarında tek satır; uyarı bir kez."""
    log, notes = installed
    for i in range(250):
        sys.excepthook(*_exc_info(f"yapay {i}"))
    text = log.path.read_text(encoding="utf-8")
    assert text.count("Traceback (most recent call last)") == 1
    assert "aynı hata 10. kez" in text and "aynı hata 100. kez" in text and "aynı hata 11. kez" not in text
    assert len(notes) == 1 and notes[0][0] == "Beklenmeyen hata" and "OSError: yapay 0" in notes[0][1]
    try:
        raise ValueError("başka bir hata")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    assert len(notes) == 2 and "ValueError: başka bir hata" in log.path.read_text(encoding="utf-8")


def test_unwritable_log_does_not_raise_and_still_warns(tmp_path, installed):
    """Günlük yazılamazsa (klasör yerine dosya, izin, dolu disk) kanca yine istisna fırlatmaz, uyarı yine gelir."""
    log, notes = installed
    (tmp_path / "engel").write_text("dosya", encoding="utf-8")
    log.path = tmp_path / "engel" / "hatalar.log"
    sys.excepthook(*_exc_info())
    assert len(notes) == 1 and "yazılamadı" in notes[0][1]


def test_hook_survives_failing_notify_and_unprintable_exception(installed):
    """Kancanın kendisi patlamamalı: uyarı geri çağırması ve istisnanın str()'si hata verse bile günlük yazılır."""
    log, notes = installed

    class Bozuk(Exception):
        def __str__(self):
            raise RuntimeError("str() de bozuk")

    def bad_notify(*_a):
        raise RuntimeError("uyarı gösterilemedi")
    log.notify = bad_notify
    try:
        raise Bozuk()
    except Bozuk:
        sys.excepthook(*sys.exc_info())          # istisna fırlatmamalı
    assert "Bozuk" in log.path.read_text(encoding="utf-8")


def test_qthread_run_exception_is_logged_and_warns(qtbot, installed):
    """QThread.run içinden kaçan istisna da (kamera, kayıt kapanışı iş parçacıkları) kancaya gelir; kanca iş
    parçacığından çağrılır."""
    log, notes = installed

    class Bozuk(QThread):
        def run(self):
            raise ValueError("iş parçacığında yapay hata")
    t = Bozuk()
    with qtbot.waitSignal(t.finished, timeout=3000):
        t.start()
    assert "ValueError: iş parçacığında yapay hata" in log.path.read_text(encoding="utf-8")
    assert len(notes) == 1


def test_python_thread_exception_is_logged(installed):
    """threading.Thread (ör. ses yazıcısı) istisnası da aynı günlüğe, iş parçacığı adıyla düşer."""
    log, notes = installed

    def boom():
        raise ZeroDivisionError("yapay")
    t = threading.Thread(target=boom, name="ses-yazici")
    t.start(); t.join()
    text = log.path.read_text(encoding="utf-8")
    assert "ZeroDivisionError: yapay" in text and "ses-yazici" in text
    assert len(notes) == 1


def test_keyboard_interrupt_is_not_reported_as_error(installed, capsys):
    """Geliştirme terminalindeki Ctrl+C bir uygulama hatası değil: günlüğe ve uyarıya girmez."""
    log, notes = installed
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert not log.path.exists() and notes == []


def test_uninstall_restores_previous_hooks(tmp_path):
    prev = (sys.excepthook, threading.excepthook)
    log = crash_log.install(tmp_path / "hatalar.log")
    try:
        assert sys.excepthook == log.excepthook and threading.excepthook == log.threading_hook
    finally:
        crash_log.uninstall(log)
    assert (sys.excepthook, threading.excepthook) == prev
