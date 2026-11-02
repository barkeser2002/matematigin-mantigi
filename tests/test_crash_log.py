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
    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from matematigin_mantigi import app as app_mod
    from matematigin_mantigi.core.settings import AppSettings

    real_build = app_mod.build_window

    def build(args, fam, settings=None):
        # Ayarlar geçici ini dosyasında: Windows kayıt defterine / macOS plist'ine dokunulmaz.
        win = real_build(args, fam, AppSettings(QSettings("ayarlar.ini", QSettings.Format.IniFormat)))
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
    ARGS = ["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx", "--duzen", "duzen.json"]
    sys.exit(app_mod.main(ARGS))
''')

# Aynı senaryo süren bir kayıtla: gerçek ffmpeg kaydedicisi (sentetik ekran karesiyle) istisnadan önce başlar,
# istisnadan sonra durdurulur; son MP4 oluşmalı ve istisnadan sonra da kare yazılmış olmalı.
_E2E_REC = textwrap.dedent('''
    import sys
    from pathlib import Path
    import numpy as np
    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QApplication
    from matematigin_mantigi import app as app_mod
    from matematigin_mantigi.core.settings import AppSettings
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, record_rect_for

    real_build = app_mod.build_window
    frame = np.full((120, 160, 4), 255, np.uint8)

    def build(args, fam, settings=None):
        # Ayarlar geçici ini dosyasında: Windows kayıt defterine / macOS plist'ine dokunulmaz.
        win = real_build(args, fam, AppSettings(QSettings("ayarlar.ini", QSettings.Format.IniFormat)))
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
    ARGS = ["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx", "--duzen", "duzen.json"]
    sys.exit(app_mod.main(ARGS))
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


def test_half_written_question_file_still_opens_the_app_with_samples(tmp_path):
    """#17 / B-2 uçtan uca: yazımı yarıda kalmış soru dosyası (inceleme s03: 5575 -> 2289 bayt) açılışta KeyError
    veriyordu; app.py yalnız QuestionTemplateError'ı yakaladığı için uygulama bir daha hiç açılmıyordu (çıkış 1,
    pencere yok). Artık uyarı dosya adını ve sebebi söyler, pencere örnek sorularla açılır, ayrıntı hatalar.log'da."""
    from matematigin_mantigi.core.models import SAMPLE_QUESTIONS
    from matematigin_mantigi.core.question_loader import write_questions
    xlsx = write_questions(tmp_path / "sorular.xlsx", SAMPLE_QUESTIONS)
    xlsx.write_bytes(xlsx.read_bytes()[:2289])
    r = _run(tmp_path, textwrap.dedent('''
        import sys
        from PyQt6.QtCore import QSettings, QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from matematigin_mantigi import app as app_mod
        from matematigin_mantigi.core.settings import AppSettings

        QMessageBox.warning = staticmethod(lambda _p, title, text, *a, **k: print("UYARI", title, "|",
                                           text.replace(chr(10), " / "), flush=True))
        real_build = app_mod.build_window

        def build(args, fam, settings=None):
            win = real_build(args, fam, AppSettings(QSettings("ayarlar.ini", QSettings.Format.IniFormat)))
            def report():
                print("PENCERE", win.isVisible(), [q.id for q in win.flow.questions], flush=True)
                win.close()
                QApplication.instance().quit()
            QTimer.singleShot(300, report)
            return win

        app_mod.build_window = build
        sys.exit(app_mod.main(["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx",
                               "--duzen", "duzen.json"]))
    '''))
    assert r.returncode == 0, f"uygulama açılmadı ({r.returncode}):\n{r.stderr[-2000:]}"
    assert "PENCERE True ['S1', 'S2', 'S3']" in r.stdout
    warning = next(ln for ln in r.stdout.splitlines() if ln.startswith("UYARI"))
    assert "sorular.xlsx" in warning and "Sebep:" in warning and "Örnek sorularla" in warning
    assert "dosya bozuk ya da yazımı yarıda kalmış" in warning, warning
    assert "yakalanan hata (soru dosyası" in (tmp_path / "hatalar.log").read_text(encoding="utf-8")


# Q1 uçtan uca: soru dosyası açılışta okunamaz (yarım satır), uygulama örnek sorularla açılır; pencere açıkken öğretmen
# dosyayı Excel'de düzeltir. Editör iki tur gerçek modal exec ile açılır, her turda Kaydet'e iki kez basılır.
_SAMPLES_THEN_FIXED = textwrap.dedent('''
    import hashlib, json, sys
    from pathlib import Path
    import openpyxl
    from PyQt6.QtCore import QSettings, QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from matematigin_mantigi import app as app_mod
    from matematigin_mantigi.core.models import Question
    from matematigin_mantigi.core.question_loader import backup_path, load_backup, load_questions, write_questions
    from matematigin_mantigi.core.settings import AppSettings
    from matematigin_mantigi.ui import question_editor as qe

    p = Path("sorular.xlsx")
    real = [Question(f"G{i}", "gerçek", 8, f"Öğretmenin gerçek sorusu {i}", ("i1",), "c", (), None)
            for i in range(1, 6)]
    write_questions(p, real)
    wb = openpyxl.load_workbook(p); wb.active.append(["G6", "yarım satır"]); wb.save(p)     # açılışta okunamaz
    backup_path(p).unlink(missing_ok=True)
    answer = qe.RELOAD_FROM_FILE if sys.argv[1] == "yukle" else qe.KEEP_EDITING
    res = {"uyarilar": [], "sorular": [], "turlar": []}
    QMessageBox.warning = staticmethod(lambda _p, title, text, *a, **k: res["uyarilar"].append(text.splitlines()[0]))

    def ask(box):                                   # editörün sorusu (gerçek QMessageBox, exec yerine yanıt)
        res["sorular"].append(box.text().splitlines()[0])
        next(b for b in box.buttons() if b.text() == answer).click()
        return 0
    QMessageBox.exec = ask

    def texts(load):
        try:
            return [q.soru for q in load(p)]
        except Exception as err:
            return type(err).__name__

    real_build = app_mod.build_window

    def build(args, fam, settings=None):
        win = real_build(args, fam, AppSettings(QSettings("ayarlar.ini", QSettings.Format.IniFormat)))
        res["acilis"] = [q.id for q in win.flow.questions]

        def fixed_in_excel():
            write_questions(p, real)                # öğretmen satırı Excel'de düzeltip kaydetti (Excel .bak yazmaz)
            backup_path(p).unlink()
            res["duzeltilen"] = hashlib.sha256(p.read_bytes()).hexdigest()
            QTimer.singleShot(0, lambda: editor_round(1))

        def editor_round(n):
            def press_save_twice():
                dlg = QApplication.activeModalWidget()
                if not isinstance(dlg, qe.QuestionEditorDialog):
                    QTimer.singleShot(20, press_save_twice)
                    return
                for _ in range(2):
                    if dlg.isVisible():
                        dlg.save_button.click()
                if dlg.isVisible():
                    dlg.reject()
            QTimer.singleShot(0, press_save_twice)
            win.open_editor()                       # gerçek modal exec
            res["turlar"].append({"dosya": texts(load_questions),
                                  "yedek": texts(load_backup) if backup_path(p).exists() else None,
                                  "ayni": hashlib.sha256(p.read_bytes()).hexdigest() == res["duzeltilen"],
                                  "tahta": [q.id for q in win.flow.questions]})
            if n == 1:
                QTimer.singleShot(0, lambda: editor_round(2))
            else:
                res["artik"] = sorted(x.name for x in Path(".").iterdir() if x.name.endswith(".tmp"))
                print("SONUC " + json.dumps(res, ensure_ascii=False), flush=True)
                win.close()
                QApplication.instance().quit()
        QTimer.singleShot(200, fixed_in_excel)
        return win

    app_mod.build_window = build
    sys.exit(app_mod.main(["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx",
                           "--duzen", "duzen.json"]))
''')


@pytest.mark.parametrize("answer", ["yukle", "donme"])
def test_app_opened_with_samples_never_saves_them_over_the_fixed_question_file(tmp_path, answer):
    """Q1 uçtan uca (inceleme v07): örnek sorularla açılan uygulamada dosya sonradan düzelince editörün Kaydet'i 3
    örnek soruyu gerçek dosyanın üzerine uyarısız yazıyor, ikinci turda yedek de örneklerle değişiyordu. Artık editör
    dosyadaki soruları yüklemeyi önerir: öğretmen yüklerse dosya ve yedek gerçek sorularla kalır, tahta onları gösterir
    ve ikinci turda soru sorulmaz; yüklemezse hiçbir şey yazılmaz (dosya bayt bayt aynı, yedek oluşmaz)."""
    script = tmp_path / "calistir.py"
    script.write_text(_SAMPLES_THEN_FIXED, encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    r = subprocess.run([sys.executable, str(script), answer], cwd=tmp_path, env=env, capture_output=True, text=True,
                       timeout=120)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("SONUC ")), None)
    assert r.returncode == 0 and line is not None, f"çıkış {r.returncode}:\n{r.stdout}\n{r.stderr[-2000:]}"
    import json
    res = json.loads(line[len("SONUC "):])
    real = [f"Öğretmenin gerçek sorusu {i}" for i in range(1, 6)]
    assert res["acilis"] == ["S1", "S2", "S3"] and res["uyarilar"] == ["Soru dosyası okunamadı: sorular.xlsx"], res
    if answer == "yukle":
        assert len(res["sorular"]) == 1 and "sorular.xlsx" in res["sorular"][0], res
        for tur in res["turlar"]:
            assert tur["dosya"] == real and tur["yedek"] == real, res
            assert tur["tahta"] == [f"G{i}" for i in range(1, 6)], res
    else:
        assert len(res["sorular"]) == 4, res
        for tur in res["turlar"]:
            assert tur == {"dosya": real, "yedek": None, "ayni": True, "tahta": ["S1", "S2", "S3"]}, res
    assert res["artik"] == [], res


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


def test_hook_lets_go_of_the_failed_paint_frame(qtbot, installed):
    """B-7: PyQt6 kurulu kancayı PyErr_Print() üzerinden çağırır; o da kancadan önce sys.last_exc/last_type/
    last_value/last_traceback'i bu istisnaya ayarlar. Kanca bunları bırakmazsa paintEvent'in çerçevesi ve içindeki
    etkin QPainter bir sonraki istisnaya dek yaşıyor, her çizimde 'QBackingStore::endPaint() called with active
    painter' basılıyordu. Gerçek bir paintEvent istisnası: kancadan sonra çerçevedeki nesne de serbest kalmalı."""
    import gc
    import weakref
    from PyQt6.QtGui import QPainter
    from PyQt6.QtWidgets import QWidget
    log, _notes = installed
    alive = []

    class Marker:
        pass

    class Bomb(QWidget):
        armed = True

        def paintEvent(self, _e):
            painter = QPainter(self)
            marker = Marker()
            alive.append(weakref.ref(marker))
            if Bomb.armed:
                Bomb.armed = False                         # geçici: yalnız bir kez patlar
                raise RuntimeError("geçici çizim hatası")
            painter.end()

    w = Bomb()
    qtbot.addWidget(w)
    w.resize(60, 40)
    w.show()
    qtbot.waitUntil(lambda: "geçici çizim hatası" in (log.path.read_text(encoding="utf-8")
                                                       if log.path.exists() else ""), timeout=3000)
    gc.collect()
    assert getattr(sys, "last_value", None) is None and getattr(sys, "last_traceback", None) is None
    assert getattr(sys, "last_exc", None) is None
    assert alive and alive[0]() is None                     # patlayan çerçevenin nesneleri (QPainter dahil) bırakıldı


def test_hook_leaves_unrelated_last_exception_alone(installed):
    """Kanca yalnız kendi istisnasının sys.last_* kaydını bırakır: doğrudan çağrıldığında (PyErr_Print'siz) başka bir
    istisnanın hata ayıklama kaydına dokunmaz."""
    try:
        raise LookupError("önceki, ilgisiz hata")
    except LookupError as e:
        unrelated = e
    prev = {n: getattr(sys, n, _ABSENT) for n in ("last_exc", "last_type", "last_value", "last_traceback")}
    sys.last_value, sys.last_type, sys.last_traceback = unrelated, LookupError, unrelated.__traceback__
    try:
        sys.excepthook(*_exc_info())
        assert sys.last_value is unrelated
    finally:
        for n, v in prev.items():
            if v is _ABSENT:
                if hasattr(sys, n):
                    delattr(sys, n)
            else:
                setattr(sys, n, v)


_ABSENT = object()


def test_uninstall_restores_previous_hooks(tmp_path):
    prev = (sys.excepthook, threading.excepthook)
    log = crash_log.install(tmp_path / "hatalar.log")
    try:
        assert sys.excepthook == log.excepthook and threading.excepthook == log.threading_hook
    finally:
        crash_log.uninstall(log)
    assert (sys.excepthook, threading.excepthook) == prev
