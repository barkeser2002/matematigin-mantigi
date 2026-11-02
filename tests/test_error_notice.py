import threading

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from matematigin_mantigi.ui import error_notice
from matematigin_mantigi.ui.error_notice import ErrorNotice, place_outside


def _visible_boxes():
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]


def _notice(qtbot):
    anchor = QWidget(); qtbot.addWidget(anchor); anchor.resize(800, 450); anchor.show()
    notice = ErrorNotice()
    notice.set_anchor(anchor)
    return notice, anchor


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
    assert _visible_boxes() == [notice.box] and notice.box.windowTitle() == "Düzen kaydedilemedi"
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
    """Kayda giren sahneyle en az çakışan yer: sahnesiz ikinci ekran varsa orası; tek ekranda tam ekran sahne
    neredeyse her yeri kapladığı için araç çubuğu (sol) tarafındaki alt köşe; pencereli sahnede hiç değmeyen yer."""
    size = QSize(360, 140)
    screen = QRect(0, 0, 1920, 1080)
    full_stage = QRect(88, 25, 1832, 1030)                  # 1920x1080 tam ekran: sahne araç çubuğunun sağında
    box = QRect(place_outside(size, full_stage, [screen], screen), size)
    assert screen.contains(box) and box.left() < full_stage.left() and box.bottom() > screen.center().y()

    second = QRect(1920, 0, 1440, 900)
    box = QRect(place_outside(size, full_stage, [screen, second], screen), size)
    assert second.contains(box) and not box.intersects(full_stage)

    windowed = QRect(400, 220, 1280, 720)
    box = QRect(place_outside(size, windowed, [screen], screen), size)
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
