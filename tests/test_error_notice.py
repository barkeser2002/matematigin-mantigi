import json
import os
import subprocess
import sys
import textwrap
import threading

from PyQt6 import sip
from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from matematigin_mantigi.ui import error_notice
from matematigin_mantigi.ui.error_notice import POLL_MS, ErrorNotice, place_outside


def _visible_boxes():
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]


def _notice(qtbot):
    anchor = QWidget(); qtbot.addWidget(anchor); anchor.resize(800, 450); anchor.show()
    notice = ErrorNotice()
    notice.set_anchor(anchor)
    return notice, anchor


def _route(notice):
    """Kayıt yolunu sahte bir kayıt durumuna ve şeride bağlar: rec[0] kayıt sürüyor mu; alerts şeride yazılanlar
    (None: şerit bu kaynağın uyarısını kaldırdı)."""
    rec, alerts = [False], []
    notice.set_recording_route(lambda: rec[0], alerts.append)
    return rec, alerts


def _box_shown(notice):
    return notice.box is not None and not sip.isdeleted(notice.box) and notice.box.isVisible()


def test_post_shows_a_single_non_modal_box_without_a_window_storm(qtbot):
    """Aynı hata art arda yüzlerce kez gelse de tek, modal olmayan bir kutu: ders ve kayıt sürer, pencere yağmuru
    olmaz. Farklı bir hata aynı kutunun metnini değiştirir; kapatılan bir uyarı aynı hatayla yeniden açılmaz."""
    notice, _ = _notice(qtbot)
    for _ in range(200):
        notice.post("Beklenmeyen hata", "aynı hata", "k1")
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible(), timeout=2000)
    qtbot.addWidget(notice.box)
    assert _visible_boxes() == [notice.box]
    assert not notice.box.isModal() and notice.box.windowModality() == Qt.WindowModality.NonModal
    assert notice.box.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)    # kalemden odağı çalmaz
    notice.post("Düzen kaydedilemedi", "farklı hata", "k2")
    qtbot.waitUntil(lambda: notice.box.text() == "farklı hata", timeout=2000)
    assert _visible_boxes() == [notice.box]
    if sys.platform != "darwin":                 # Qt macOS'ta QMessageBox başlığını yok sayar; metin kendi başına yeter
        assert notice.box.windowTitle() == "Düzen kaydedilemedi"
    notice.box.button(QMessageBox.StandardButton.Ok).click()
    notice.post("Beklenmeyen hata", "aynı hata", "k1")
    qtbot.wait(50)
    assert _visible_boxes() == []


def test_post_from_a_worker_thread_opens_the_box_in_the_gui_thread(qtbot):
    """Kanca kamera/kayıt iş parçacığından da çağrılır; kutu yine GUI iş parçacığında kurulmalı."""
    notice, _ = _notice(qtbot)
    t = threading.Thread(target=lambda: notice.post("Beklenmeyen hata", "iş parçacığından", "k"))
    t.start(); t.join()
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible(), timeout=2000)
    qtbot.addWidget(notice.box)
    assert notice.box.thread() is QApplication.instance().thread()


def test_module_post_without_install_does_not_raise(capsys):
    """Kurulmamışken (QApplication öncesi, testler) uyarı yalnız stderr'e gider, istisna fırlatmaz."""
    prev = error_notice._instance
    error_notice._instance = None
    try:
        error_notice.post("Başlık", "metin")
    finally:
        error_notice._instance = prev
    assert "metin" in capsys.readouterr().err


def test_place_outside_prefers_another_screen_then_the_toolbar_side():
    """Kayda giren sahneyle en az çakışan yer: sahnesiz ikinci ekran varsa orası; pencereli sahnede hiç değmeyen yer.
    Tek ekranda tam ekran sahne neredeyse her yeri kaplar: kutu araç çubuğu (sol) tarafında, ama araç çubuğunun
    altını (uyarı şeridi + kayıt düğmesi) örtmeden üstte durur. Eski beklenti sol alttı: kutu kayıt düğmesini ve
    şeridi örtüyordu (B-1)."""
    size = QSize(360, 140)
    screen = QRect(0, 0, 1920, 1080)
    full_stage = QRect(88, 25, 1832, 1030)                  # 1920x1080 tam ekran: sahne araç çubuğunun sağında
    toolbar_bottom = QRect(0, 940, 88, 140)                 # şerit + kayıt düğmesi + 'KAYIT' yazısı
    box = QRect(place_outside(size, full_stage, [screen], screen, toolbar_bottom), size)
    assert screen.contains(box) and box.left() < full_stage.left() and not box.intersects(toolbar_bottom)

    second = QRect(1920, 0, 1440, 900)
    box = QRect(place_outside(size, full_stage, [screen, second], screen, toolbar_bottom), size)
    assert second.contains(box) and not box.intersects(full_stage)

    windowed = QRect(400, 220, 1280, 720)
    box = QRect(place_outside(size, windowed, [screen], screen, QRect(400, 800, 88, 140)), size)
    assert screen.contains(box) and not box.intersects(windowed)


def test_box_lands_fully_on_screen_with_the_app_stylesheet(qtbot):
    """QMessageBox son boyutunu ancak gösterilirken kesinleştirir. Gösterilmeden önceki tahminle konan kutu,
    uygulamanın stil sayfasıyla büyüyünce ekranın altından taşıyor, Tamam düğmesi kesiliyordu (1920x1080 tam ekran
    görsel kontrolünde 28 px)."""
    from matematigin_mantigi.ui import theme
    fam = theme.FontFamilies("Arial", "Arial", False)
    notice, anchor = _notice(qtbot)
    anchor.setStyleSheet(theme.build_stylesheet(fam))
    notice.post("Beklenmeyen hata", "Bir hata oluştu ama uygulama çalışmaya devam ediyor; süren bir kayıt varsa "
                "durdurulmadı.\n\nOSError: yapay yuva hatası\n\nAyrıntı: /Users/ogretmen/Documents/Matematiğin "
                "Mantığı/hatalar.log", "k")
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible(), timeout=2000)
    qtbot.addWidget(notice.box)
    assert notice.box.screen().availableGeometry().contains(notice.box.frameGeometry())


def test_box_opens_over_an_open_modal_dialog_so_it_stays_clickable(qtbot):
    """Soru editörü gibi uygulama modal bir pencere açıkken gelen uyarı o pencerenin çocuğu olur; ana pencerenin
    çocuğu olsaydı modal pencere kapanana kadar tıklanamazdı."""
    from PyQt6.QtWidgets import QDialog
    notice, anchor = _notice(qtbot)
    dlg = QDialog(anchor); dlg.setModal(True); dlg.show()
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is dlg, timeout=2000)
    notice.post("Beklenmeyen hata", "editör açıkken", "k")
    qtbot.waitUntil(lambda: notice.box is not None and notice.box.isVisible(), timeout=2000)
    qtbot.addWidget(notice.box)
    assert notice.box.parent() is dlg and not notice.box.isModal()
    dlg.close()


# --- kayıt sürerken: kutu yok, şerit var; kayıt bitince kutu (B-1) -------------------------------------------
def test_while_recording_the_notice_goes_to_the_strip_and_waits_until_recording_ends(qtbot):
    """B-1: kayıt sürerken açılan kutu kayda giriyordu (1920x1080 tam ekranda %74'ü sahnede, kayıt düğmesi ve şerit
    örtülü, hatalar.log'un tam yolu yani kullanıcı adı videoda). Kayıt sürerken kutu açılmaz: araç çubuğunun şeridine
    kısa satır gider; kayıt bitince şerit temizlenir ve bekleyen uyarılar tek kutuda gösterilir. Yoklama zamanlayıcısı
    yalnız iş varken çalışır."""
    notice, _ = _notice(qtbot)
    rec, alerts = _route(notice)
    assert not notice._poll_timer.isActive()
    rec[0] = True
    notice.post("Beklenmeyen hata", "Ayrıntı: /Users/ogretmen/Documents/Matematiğin Mantığı/hatalar.log", "k1")
    qtbot.waitUntil(lambda: alerts == ["⚠ Beklenmeyen hata — ayrıntı kayıt bitince"], timeout=2000)
    notice.post("Düzen kaydedilemedi", "duzen.json yazılamadı", "k2")
    notice.post("Beklenmeyen hata", "aynı hata yeniden", "k1")             # aynı anahtar: bekleyen tek uyarı kalır
    qtbot.waitUntil(lambda: len(alerts) == 2, timeout=2000)
    qtbot.wait(3 * POLL_MS)                                                # kayıt sürdükçe hiçbir yoldan kutu yok
    assert _visible_boxes() == [] and alerts[-1] == "⚠ 2 uyarı — ayrıntı kayıt bitince"
    assert notice._poll_timer.isActive()
    rec[0] = False                                                         # kayıt bitti (kaydedildi)
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    assert alerts[-1] is None and _visible_boxes() == [notice.box]
    text = notice.box.text()
    assert "hatalar.log" in text and "duzen.json yazılamadı" in text and "aynı hata yeniden" not in text
    assert text.index("Beklenmeyen hata") < text.index("Düzen kaydedilemedi")      # geliş sırasıyla
    notice.box.button(QMessageBox.StandardButton.Ok).click()
    qtbot.waitUntil(lambda: not notice._poll_timer.isActive(), timeout=2000)       # iş kalmadı: yoklama durur


def test_box_open_when_recording_starts_is_hidden_and_comes_back_after(qtbot):
    """Öğretmen kutuyu kapatmadan kaydı başlatırsa kutu kayda girmesin: gizlenir, şeride geçer; kayıt bitince aynı
    uyarı yeniden gösterilir (Tamam'a basılmadığı için görülmüş sayılmaz)."""
    notice, _ = _notice(qtbot)
    rec, alerts = _route(notice)
    notice.post("Beklenmeyen hata", "kayıttan önce gelen", "k1")
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    rec[0] = True
    qtbot.waitUntil(lambda: _visible_boxes() == [], timeout=2000)
    assert alerts == ["⚠ Beklenmeyen hata — ayrıntı kayıt bitince"]
    rec[0] = False
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    assert notice.box.text() == "kayıttan önce gelen" and alerts[-1] is None


def test_growing_box_is_moved_back_onto_the_screen(qtbot):
    """B-3: görünür kutuya daha uzun ikinci uyarı gelince kutu yerinde büyüyordu: alt köşeye konan kutunun alt kenarı
    ve Tamam düğmesi ekranın altından taşıyordu (1920x1080 tam ekranda 88 px). Görünürken de gerçek boyutla
    yeniden konumlanır."""
    notice, _ = _notice(qtbot)
    notice.post("Düzen kaydedilemedi", "kısa", "k1")
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    long_text = "\n".join(f"{i}. satır: kutuyu büyüten uzun uyarı metni" for i in range(16))
    notice.post("Beklenmeyen hata", long_text, "k2")
    qtbot.waitUntil(lambda: notice.box.text() == long_text, timeout=2000)
    assert notice.box.screen().availableGeometry().contains(notice.box.frameGeometry())


def test_box_destroyed_with_its_temporary_modal_parent_is_shown_again(qtbot):
    """B-4: modal bir pencere açıkken gelen uyarının kutusu onun çocuğu olur (tıklanabilsin). Pencere statik
    QMessageBox.warning() ise (\"Kaydedilemedi\", \"Kayıt hatası\") kapanınca kutuyu da siler; anahtar gösterildi
    sayıldığı için aynı uyarı bir daha hiç gelmiyordu. Tamam'a basılmadan yok olan kutu ana pencere altında yeniden
    açılır; Tamam'a basılmış uyarı ise geri gelmez."""
    notice, anchor = _notice(qtbot)

    def open_modal():
        modal = QMessageBox(QMessageBox.Icon.Warning, "Kaydedilemedi", "…", QMessageBox.StandardButton.Ok, anchor)
        modal.setModal(True); modal.show()
        qtbot.waitUntil(lambda: QApplication.activeModalWidget() is modal, timeout=2000)
        return modal

    modal = open_modal()
    notice.post("Beklenmeyen hata", "modal açıkken gelen", "k1")
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    assert notice.box.parent() is modal
    sip.delete(modal)                          # statik warning() exec bitince kutuyu böyle siler
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    assert notice.box.parent() is anchor and notice.box.text() == "modal açıkken gelen"
    notice.box.button(QMessageBox.StandardButton.Ok).click()

    modal = open_modal()
    notice.post("Beklenmeyen hata", "görülen uyarı", "k2")
    qtbot.waitUntil(lambda: _box_shown(notice) and notice.box.text() == "görülen uyarı", timeout=2000)
    notice.box.button(QMessageBox.StandardButton.Ok).click()                 # öğretmen gördü
    sip.delete(modal)
    qtbot.wait(100)
    assert _visible_boxes() == []


# --- kapanış: gizli/kapanmış ana pencerenin altında pencere açılmaz; uyarılar hatalar.log'da (P1) --------------
def test_no_box_opens_under_a_hidden_main_window_and_the_box_closes_with_it(qtbot):
    """Ana pencere kapanınca görünen kutu da kapanır; ana pencere gizliyken gelen uyarı pencere açmaz (gizli pencerenin
    çocuğu olarak gösterilen kutu Qt'nin otomatik çıkışını kuyruktan siliyordu: pencere kapanıyor, süreç çıkmıyordu).
    Yoklama da durur. Pencere yeniden gösterilirse (ör. kapanış iptal) Tamam'a basılmamış uyarılar geri gelir."""
    notice, anchor = _notice(qtbot)
    rec, alerts = _route(notice)
    notice.post("Beklenmeyen hata", "kapanıştan önce görünen", "k1")
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    anchor.close()
    assert _visible_boxes() == []
    notice.post("Düzen kaydedilemedi", "pencere kapalıyken gelen", "k2")
    for _ in range(3):
        QApplication.processEvents()
    assert _visible_boxes() == [] and not notice._poll_timer.isActive()
    anchor.show()
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    text = notice.box.text()
    assert "kapanıştan önce görünen" in text and "pencere kapalıyken gelen" in text, text


def test_box_lost_with_a_modal_is_not_shown_again_under_a_closed_main_window(qtbot):
    """'Kayıt hatası' modalının çocuğu olan kutu modalla silinir; ardından pencere kapanırsa kutu gizli pencerenin
    altında yeniden açılmaz (açılıyordu: Qt'nin kuyruktaki çıkışı silinip süreç görünmez kalıyordu, v04)."""
    notice, anchor = _notice(qtbot)
    modal = QMessageBox(QMessageBox.Icon.Warning, "", "Kayıt hatası", QMessageBox.StandardButton.Ok, anchor)
    modal.setModal(True); modal.show()
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is modal, timeout=2000)
    notice.post("Beklenmeyen hata", "modalın çocuğu", "k1")
    qtbot.waitUntil(lambda: _box_shown(notice) and notice.box.parent() is modal, timeout=2000)
    sip.delete(modal)                          # statik warning() exec bitince kutuyu da siler ...
    anchor.close()                             # ... ve pencere hemen kapanır (_close_after_save)
    for _ in range(5):
        QApplication.processEvents()
    assert _visible_boxes() == []


def test_take_all_hands_over_shown_and_waiting_notices_and_closes_the_box(qtbot):
    """Kapanış özeti için: Tamam'a basılmamış (görünen) ve kayıt sırasında biriken uyarıların hepsi geliş sırasıyla
    verilir ve bırakılır: kutu kapanır ve geri gelmez, şerit temizlenir, yoklama durur."""
    notice, _ = _notice(qtbot)
    rec, alerts = _route(notice)
    notice.post("Düzen kaydedilemedi", "görünen kutuda", "k1")
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    rec[0] = True
    notice.post("Tahta görüntüsü kaydedilemedi", "kayıt sırasında", "k2")
    qtbot.waitUntil(lambda: alerts[-1:] == ["⚠ 2 uyarı — ayrıntı kayıt bitince"], timeout=2000)
    rec[0] = False
    assert notice.take_all() == [("Düzen kaydedilemedi", "görünen kutuda"),
                                 ("Tahta görüntüsü kaydedilemedi", "kayıt sırasında")]
    assert alerts[-1] is None and _visible_boxes() == [] and not notice._poll_timer.isActive()
    qtbot.wait(3 * POLL_MS)
    assert _visible_boxes() == [] and notice.take_all() == []
    notice.post("Düzen kaydedilemedi", "görünen kutuda", "k1")          # özette gösterildi: yeniden gelmez
    qtbot.wait(50)
    assert _visible_boxes() == []


def test_posted_notices_are_written_to_the_error_log_without_flooding_it(tmp_path, monkeypatch):
    """Kullanıcıya gösterilen her uyarı başlığı ve metniyle hatalar.log'a da yazılır: kutu/özet okunmadan kapansa da
    sonradan ne olduğu görülür (eskiden 'Tahta görüntüsü kaydedilemedi' günlükte hiç yoktu). Günlük aynı türü oturumda
    bir kez yazar: her uyarı anahtarı kendi girdisini alır (tek türde ikinci uyarı hiç yazılmazdı), aynı uyarının
    tekrarı günlüğü doldurmaz."""
    from matematigin_mantigi.core import crash_log
    monkeypatch.setattr(crash_log, "_active", crash_log.CrashLog(tmp_path / "hatalar.log"))
    monkeypatch.setattr(error_notice, "_instance", None)               # kutu yok (stderr); günlük yine yazılır
    error_notice.post("Tahta görüntüsü kaydedilemedi", "S1 sorusunun tahta resmi kaydedilemedi: diskte yer kalmadı.",
                      key="tahta-goruntusu")
    for _ in range(5):
        error_notice.post("Düzen kaydedilemedi", "duzen.json yazılamadı: erişim izni yok.", key="duzen")
    text = (tmp_path / "hatalar.log").read_text(encoding="utf-8")
    assert "Tahta görüntüsü kaydedilemedi" in text and "S1 sorusunun tahta resmi kaydedilemedi" in text, text
    assert "Düzen kaydedilemedi" in text and text.count("duzen.json yazılamadı") == 1, text


def test_box_never_activates_or_raises_itself(qtbot, monkeypatch):
    """Kutu odağı çalmaz (kalem ve kısayollar tahtada kalır). Offscreen QPA gösterilen her pencereyi etkinleştirdiği
    için odak burada ölçülemez: kutuyu etkinleştiren ya da öne alan bir çağrı hiçbir yolda yapılmamalı (ilk gösterim,
    görünür kutunun metni değişirken, kayıttan sonra yeniden gösterilirken)."""
    calls = []
    monkeypatch.setattr(QMessageBox, "activateWindow", lambda self: calls.append("activateWindow"))
    monkeypatch.setattr(QMessageBox, "raise_", lambda self: calls.append("raise_"))
    notice, _ = _notice(qtbot)
    rec, _alerts = _route(notice)
    notice.post("Beklenmeyen hata", "ilk", "k1")
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    qtbot.addWidget(notice.box)
    notice.post("Düzen kaydedilemedi", "ikinci", "k2")
    qtbot.waitUntil(lambda: notice.box.text() == "ikinci", timeout=2000)
    rec[0] = True
    qtbot.waitUntil(lambda: _visible_boxes() == [], timeout=2000)
    rec[0] = False
    qtbot.waitUntil(lambda: _box_shown(notice), timeout=2000)
    assert calls == [] and notice.box.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)


# --- gerçek app.main: kayıt yolu ve yerleşim bağlaması --------------------------------------------------------
_FHD = [dict(name="S1", x=0, y=0, width=1920, height=1080, logicalDpi=96, logicalBaseDpi=96, dpr=1)]
_DUAL = _FHD + [dict(name="S2", x=1920, y=0, width=1440, height=900, logicalDpi=96, logicalBaseDpi=96, dpr=1)]

_APP_PRELUDE = textwrap.dedent('''
    import json, sys
    from PyQt6.QtCore import QPoint, QSettings, QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from matematigin_mantigi import app as app_mod
    from matematigin_mantigi.core.recorder import NullRecorder, RecorderState
    from matematigin_mantigi.core.settings import AppSettings
    from matematigin_mantigi.ui.error_notice import POLL_MS

    real_build = app_mod.build_window
    res = {}

    def boxes():
        return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]

    def rect(r):
        return [r.x(), r.y(), r.width(), r.height()]

    def later(cond, then, tries=100):
        """cond doğru olunca (en çok ~5 sn beklenir) then; olay döngüsü 50 ms adımlarla döner."""
        if cond() or tries <= 0:
            then()
        else:
            QTimer.singleShot(50, lambda: later(cond, then, tries - 1))

    def snapshot(win):
        b, strip, button = boxes(), win.toolbar.alert_label, win.toolbar.record_button
        tl = button.mapToGlobal(QPoint(0, 0))
        return {"kutu": len(b), "cerceve": rect(b[0].frameGeometry()) if b else None,
                "metin": b[0].text() if b else "", "serit": strip.text() if strip.isVisible() else None,
                "kayit_dugmesi": [tl.x(), tl.y(), button.width(), button.height()],
                "sahne": list(win.work_area.recording_rect()[:4]),
                "ekranlar": [rect(s.geometry()) for s in QApplication.screens()]}

    def done(win):
        print("SONUC " + json.dumps(res), flush=True)
        win.recorder.forced = None
        win.close()
        QApplication.instance().quit()

    class Rec(NullRecorder):
        """Kayıt gerçek toggle_recording yolundan başlar/durur; kaydın kaydedilme anı (FINALIZING) elle sürülür."""
        forced = None

        @property
        def state(self):
            return self.forced or NullRecorder.state.fget(self)

    def make(args, fam):
        # Ayarlar geçici ini dosyasında: Windows kayıt defterine / macOS plist'ine dokunulmaz.
        win = real_build(args, fam, AppSettings(QSettings("ayarlar.ini", QSettings.Format.IniFormat)))
        win.recorder = Rec()
        QTimer.singleShot(100, win.showFullScreen)
        return win

    def run(build):
        app_mod.build_window = build
        sys.exit(app_mod.main(["matematigin-mantigi", "--kamera-yok", "--sorular", "sorular.xlsx",
                               "--duzen", "duzen.json"]))
''')

_RECORDING_FULL_SCREEN = '''
def build(args, fam, settings=None):
    win = make(args, fam)
    rec, wait = win.recorder, 3 * POLL_MS

    def before_recording():
        raise ValueError("kayıttan önce yapay hata")

    def boom():
        raise OSError("kayıt sırasında yapay yuva hatası")

    def opened():
        QTimer.singleShot(0, before_recording)
        later(lambda: bool(boxes()), start)

    def start():
        res["once"] = snapshot(win)
        win.toggle_recording(True)
        res["baslar_baslamaz"] = snapshot(win)      # yoklamayı beklemeden: kaydın ilk karelerine girmesin
        QTimer.singleShot(0, boom)
        later(lambda: "2 uyarı" in win.toolbar.alert_label.text(), lambda: QTimer.singleShot(wait, recording))

    def recording():
        res["kayitta"] = snapshot(win)
        win.toggle_recording(False)                 # NullRecorder hemen durur; kaydedilme anı elle sürülür
        rec.forced = RecorderState.FINALIZING
        QTimer.singleShot(wait, finalizing)

    def finalizing():
        res["kaydedilirken"] = snapshot(win)
        rec.forced = None
        later(lambda: bool(boxes()), after)

    def after():
        res["sonra"] = snapshot(win)
        done(win)

    later(lambda: win.isFullScreen() and win.width() == 1920, opened)
    return win

run(build)
'''

_SECOND_SCREEN = '''
def build(args, fam, settings=None):
    win = make(args, fam)

    def boom():
        raise OSError("yapay yuva hatası")

    def start():
        QTimer.singleShot(0, boom)
        later(lambda: bool(boxes()), after)

    def after():
        res["sonra"] = snapshot(win)
        done(win)

    later(lambda: win.isFullScreen() and win.width() == 1920, start)
    return win

run(build)
'''


def _run_app(tmp_path, body: str, screens: list) -> dict:
    """Gerçek app.main ayrı süreçte, offscreen ekran yapılandırmasıyla (ekranlar.json; çalışma dizinine göreli yol).
    Betik ölçtüklerini 'SONUC <json>' satırıyla verir."""
    (tmp_path / "ekranlar.json").write_text(json.dumps({"screens": screens}), encoding="utf-8")
    script = tmp_path / "calistir.py"
    script.write_text(_APP_PRELUDE + textwrap.dedent(body), encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen:configfile=ekranlar.json", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    r = subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env, capture_output=True, text=True,
                       timeout=120)
    assert r.returncode == 0, f"süreç düştü ({r.returncode}):\n{r.stderr[-2000:]}"
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("SONUC ")), None)
    assert line is not None, r.stdout + r.stderr[-2000:]
    return json.loads(line[len("SONUC "):])


def test_app_routes_notices_to_the_toolbar_while_recording_full_screen(tmp_path):
    """B-1 uçtan uca (gerçek app.main, 1920x1080 tek ekran, tam ekran): kayıttan önce açılmış kutu kayıt başlar
    başlamaz (yoklamayı beklemeden, ilk karelere girmeden) gizlenir; kayıt sürerken yuvadaki hata kutu açmaz, araç
    çubuğunun şeridine kısa satır yazılır; kayıt kaydedilirken (FINALIZING) de. Kayıt bitince şerit temizlenir, kutu
    iki uyarıyla açılır ve kayıt düğmesini örtmez (eskiden sol altta, kayıt düğmesinin üstündeydi)."""
    res = _run_app(tmp_path, _RECORDING_FULL_SCREEN, _FHD)
    assert res["once"]["kutu"] == 1 and res["baslar_baslamaz"]["kutu"] == 0, res
    strip = "⚠ 2 uyarı — ayrıntı kayıt bitince"
    assert (res["kayitta"]["kutu"], res["kayitta"]["serit"]) == (0, strip), res["kayitta"]
    assert (res["kaydedilirken"]["kutu"], res["kaydedilirken"]["serit"]) == (0, strip), res["kaydedilirken"]
    after = res["sonra"]
    assert after["kutu"] == 1 and after["serit"] is None, after
    assert "kayıttan önce yapay hata" in after["metin"] and "kayıt sırasında yapay yuva hatası" in after["metin"]
    box, button, screen = QRect(*after["cerceve"]), QRect(*after["kayit_dugmesi"]), QRect(*after["ekranlar"][0])
    assert screen.contains(box) and not box.intersects(button), after


def test_app_puts_the_box_on_a_free_second_screen(tmp_path):
    """app.main kutuya kayda giren sahneyi bildirir: sahnesiz ikinci ekran varsa kutu orada açılır, sahneye hiç
    değmez (bu bağlama kaybolunca kutu tam ekran sahnenin üstüne düşüyordu ve hiçbir test bunu yakalamıyordu)."""
    res = _run_app(tmp_path, _SECOND_SCREEN, _DUAL)
    after = res["sonra"]
    box, stage, second = QRect(*after["cerceve"]), QRect(*after["sahne"]), QRect(*after["ekranlar"][1])
    assert after["kutu"] == 1 and second.contains(box) and not box.intersects(stage), after
