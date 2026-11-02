import pytest
from PyQt6.QtCore import QPointF, QSize, Qt
from PyQt6.QtGui import QColor

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, HintMaskMode, QuestionStatus, Tool
from matematigin_mantigi.ui.main_window import RECORD_FAILED


@pytest.fixture(autouse=True)
def close_question_never_blocks(monkeypatch):
    """pytest-qt pencereyi teardown'da kapatır; kayıt açık kalmışsa kapanış sorusu gerçek modal açar ve offscreen'de
    exec() sonsuza dek bekler: hatalı kod (mutasyon, gerileme) kırmızı yerine DONAR. Soruyu kendisi yanıtlamayan
    testte soru açılırsa kayıt eşzamanlı durdurulur (arka plan kapanışının QThread'i pencereyle silinmesin), 'Durdur
    ve çık' seçilir ve test teardown'da hatayla biter. Soruyu bekleyen testler _answer_close_question ile bunun
    üstüne yazar. Statik QMessageBox pencereleri (warning, information...) ve başka kutuların exec'i (kapanış özeti)
    de aynı nedenle gerçek modal açmaz: test kendisi yakalamıyorsa çağrı kaydedilir ve test teardown'da hatayla
    biter."""
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.ui.main_window import STOP_AND_QUIT
    unexpected, statics = [], []

    def exec_(box):
        if box.text() != "Kayıt sürüyor, durdurulup çıkılsın mı?":
            statics.append(("exec", box.windowTitle(), box.text()))
            return QMessageBox.StandardButton.Ok
        unexpected.append(box.text())
        try:
            box.parent().recorder.stop()
        except Exception:  # noqa: BLE001 - temizlik; test zaten hatayla biter
            pass
        next(b for b in box.buttons() if b.text() == STOP_AND_QUIT).click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", exec_)
    for name in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *a, _name=name, **k: (statics.append((_name, *a[1:3])), QMessageBox.StandardButton.Ok)[1]))
    yield
    _release_windows_left_open()
    assert not unexpected, "kayıt açık kalmış pencere kapatıldı (kapanış sorusu yanıtlanmadı)"
    assert not statics, f"test yakalamadığı bir modal pencere açtı: {statics}"


def _release_windows_left_open(timeout_ms: int = 30000) -> None:
    """pytest-qt teardown'da pencereyi close() ve deleteLater eder. Başarısız bir test pencereyi kapanmayı yok sayan
    hâlde bırakmışsa (kayıt arka planda kaydediliyor ya da test kapanış sorusuna 'Kayda devam et' dedirtmiş) pencere
    çalışan iş parçacıklarıyla (kaydı kaydeden _StopWorker, kamera işçisi) sonraki testin olay döngüsünde silinir, Qt
    süreci düşürür ('QThread: Destroyed while thread is still running', Fatal Python error: Aborted) ve paketin geri
    kalanı hiç koşmaz (macOS CI). Teardown'da kayıt işçisi sınırlı beklenir, sonucu bu testte işlenir; pencere hâlâ
    açıksa kayıt durdurulur ve kamera kapatılır: bir testin hatası yalnız o testi kırmızı yapar."""
    from PyQt6.QtWidgets import QApplication
    from matematigin_mantigi.core.recorder import RecorderState
    from matematigin_mantigi.ui.main_window import MainWindow, _StopWorker
    for w in QApplication.topLevelWidgets():
        if not isinstance(w, MainWindow):
            continue
        workers = [t for t in w.findChildren(_StopWorker) if t.isRunning()]
        for worker in workers:
            worker.wait(timeout_ms)
        if workers:
            QApplication.processEvents()                                # kuyruktaki sonuç (_on_record_stopped)
        if w.isVisible():                                               # kapanma yok sayıldı: pencere açık kaldı
            try:
                if w.recorder.state is RecorderState.RECORDING:
                    w.recorder.stop()
            except Exception:  # noqa: BLE001 - temizlik; test zaten hatayla biter
                pass
            w.webcam_panel.shutdown()


def test_window_shell(window):
    assert window.windowTitle() == "Matematiğin Mantığı"
    assert window.toolbar.width() == 88
    wa = window.work_area
    stage = wa.stage_rect()
    x, y, w, h, _ = wa.recording_rect()
    assert wa.width() == window.width() - 88 and wa.height() == window.height()       # araç çubuğu dışta
    assert (w, h) == (stage.width(), stage.height()) and abs(w / h - 16 / 9) < 0.01   # kayıt 16:9 sahne
    assert (stage.left(), stage.top()) == ((wa.width() - w) // 2, (wa.height() - h) // 2)   # ortalı
    assert window.canvas is window.work_area.board and window.canvas.geometry() == window.work_area.inner_rect()
    assert window.work_area.name_label.text() == "Koray Varol" and window.work_area.frame_visible
    assert window.question_zone.number_label.text() == "1."
    assert window.question_zone.text_label.text().startswith("3x + 5")
    assert len(window.hint_zone.cards) == 3
    assert window.work_area.status_label.text().startswith("Araç: Kalem")


def test_tool_switch_updates_cursor_and_status(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.ERASER
    assert window.canvas.cursor().pixmap().size() == QSize(36, 36)
    assert "Araç: Silgi" in window.work_area.status_label.text()
    qtbot.mouseClick(window.toolbar.width_buttons[8], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().pixmap().size() == QSize(70, 70)          # silgi alanı büyüdü
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.PEN], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().pixmap().size() == QSize(36, 36)          # kurşun kalem ikonu
    assert window.settings.width == 8 and window.settings.tool == Tool.PEN


def test_tool_cursor_also_applies_over_zones(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toolbar.width_buttons[12], Qt.MouseButton.LeftButton)
    for zone in (window.question_zone, window.hint_zone, window.webcam_panel):
        assert zone.cursor().pixmap().size() == QSize(82, 82)
    assert window.hint_zone.cards[0].cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_color_selects_pen_and_persists(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.LASER], Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.toolbar.swatches["#c8322b"], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.PEN and window.canvas.color.name() == "#c8322b"
    assert window.settings.color == "#c8322b" and window.toolbar.tool_buttons[Tool.PEN].isChecked()


def test_question_flow_saves_snapshot_and_clears(window, qtbot):
    c = window.canvas
    c.begin_stroke(QPointF(50, 50), 0.6); c.extend_stroke(QPointF(200, 200), 0.6); c.end_stroke()
    qtbot.mouseClick(window.toolbar.work_button, Qt.MouseButton.LeftButton)
    assert window.toolbar.work_button.text() == "Soruyu tamamla ✓"
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)
    files = sorted(p.name for p in window.session_store.session_dir.glob("*.png"))
    assert files == ["S1_01.png"]
    assert c.is_empty() and window.flow.index == 1
    assert window.flow.status(0) == QuestionStatus.DONE
    assert window.toolbar.progress_label.text() == "1/3 tamamlandı · S2"
    assert window.question_zone.number_label.text() == "2."
    assert window.question_zone.text_label.text() == SAMPLE_QUESTIONS[1].soru
    assert len(window.hint_zone.cards) == 3


def test_prev_button_goes_back(window, qtbot):
    qtbot.mouseClick(window.toolbar.prev_button, Qt.MouseButton.LeftButton)
    assert window.flow.index == 2 and window.question_zone.number_label.text() == "3."


def test_next_without_drawing_writes_nothing(window, qtbot):
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)
    assert not window.session_store.session_dir.exists()


@pytest.mark.parametrize("failure", ["klasor", "png"])
def test_snapshot_failure_on_question_change_is_reported_and_lesson_continues(window, qtbot, tmp_path, monkeypatch,
                                                                              failure):
    """pen#1/app#2: soru değişirken tahta PNG'si yazılamazsa (oturum klasörü yerine dosya / silinmiş klasör, dolu
    disk) save_snapshot OSError fırlatıyor, yuva uygulamayı süren kayıtla birlikte düşürüyordu. Artık modal
    olmayan uyarı (kancaya kadar gitmez); sonraki soruya geçilir, tahta temizlenir, ders sürer."""
    from PyQt6.QtGui import QImage
    posted = _capture_notices(monkeypatch)
    if failure == "klasor":
        (tmp_path / "engel").write_text("dosya", encoding="utf-8")
        window.session_store.session_dir = tmp_path / "engel" / "oturum"
    else:
        monkeypatch.setattr(QImage, "save", lambda *a, **k: False)
    c = window.canvas
    c.begin_stroke(QPointF(50, 50), 0.6); c.extend_stroke(QPointF(200, 200), 0.6); c.end_stroke()
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)
    assert window.flow.index == 1 and c.is_empty()
    assert window.question_zone.number_label.text() == "2."
    assert posted and posted[0][0] == "Tahta görüntüsü kaydedilemedi" and "S1" in posted[0][1]


def test_hint_reveal_and_mask_mode(window, qtbot):
    hz = window.hint_zone
    qtbot.mouseClick(hz.cards[2], Qt.MouseButton.LeftButton)
    assert hz.cards[2].revealed and not hz.cards[0].revealed
    qtbot.mouseClick(hz.next_button, Qt.MouseButton.LeftButton)
    assert hz.counter_label.text() == "2 / 3"
    qtbot.mouseClick(hz.redact_button, Qt.MouseButton.LeftButton)
    assert window.settings.hint_mask == HintMaskMode.REDACT
    qtbot.mouseClick(window.toolbar.next_button, Qt.MouseButton.LeftButton)   # S2
    assert not any(c.revealed for c in hz.cards)


def test_question_hide_show(window, qtbot):
    qtbot.mouseClick(window.question_zone.hide_link, Qt.MouseButton.LeftButton)
    assert not window.question_zone.shown and not window.flow.is_question_shown()
    qtbot.mouseClick(window.question_zone.show_button, Qt.MouseButton.LeftButton)
    assert window.question_zone.shown


def test_pen_draws_over_hint_card_and_click_tool_reveals(window, qtbot):
    from PyQt6.QtTest import QTest
    win = window.windowHandle()
    card = window.hint_zone.cards[0]
    center = card.mapTo(window, card.rect().center())
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    QTest.mouseMove(win, center + QPointF(40, 20).toPoint())
    QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center + QPointF(40, 20).toPoint())
    assert not window.canvas.is_empty() and not card.revealed             # kalem: kartın üstüne çizdi
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.CLICK], Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.CLICK and window.canvas.cursor().shape() == Qt.CursorShape.ArrowCursor
    window.canvas.clear()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    assert card.revealed and window.canvas.is_empty()                       # tıkla: kart açıldı, çizim yok


def test_click_tool_tablet_press_over_hint_card_is_not_swallowed(window, qtbot):
    """XP-Pen bug: Tıkla modunda kalemle karta dokununca Zone.tabletEvent olayı yutmamalı.
    Not: Qt'nin gerçek cihazda kabul edilmemiş kalem olayını fare tıklamasına çevirmesi (senkron
    QApplication.sendEvent ile üretilen, spontane olmayan olaylarda) offscreen test platformunda
    tetiklenmiyor (doğrulandı); bu yüzden aynı konuma gönderilen gerçek fare tıklamasıyla asıl
    kullanıcı sonucunu (kart açılır) da doğruluyoruz."""
    from PyQt6.QtCore import QEvent
    from PyQt6.QtTest import QTest
    from test_canvas import tablet
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.CLICK], Qt.MouseButton.LeftButton)
    card = window.hint_zone.cards[0]
    zpos = card.mapTo(window.hint_zone, card.rect().center())
    assert not tablet(window.hint_zone, QEvent.Type.TabletPress, zpos.x(), zpos.y(), 0.8)
    assert not tablet(window.hint_zone, QEvent.Type.TabletRelease, zpos.x(), zpos.y(), 0.0)
    assert window.canvas.is_empty()                                          # kalem olayı tahtaya çizim olarak gitmedi
    win = window.windowHandle()
    wpos = card.mapTo(window, card.rect().center())
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, wpos)
    assert card.revealed and window.canvas.is_empty()                       # gerçek cihazda kalem de kartı açar


def test_pen_tool_tablet_draws_over_hint_card_and_does_not_reveal(window, qtbot):
    from PyQt6.QtCore import QEvent
    from test_canvas import tablet
    card = window.hint_zone.cards[0]
    zpos = card.mapTo(window.hint_zone, card.rect().center())
    assert tablet(window.hint_zone, QEvent.Type.TabletPress, zpos.x(), zpos.y(), 0.8)
    assert tablet(window.hint_zone, QEvent.Type.TabletMove, zpos.x() + 15, zpos.y() + 8, 0.8)
    assert tablet(window.hint_zone, QEvent.Type.TabletRelease, zpos.x() + 15, zpos.y() + 8, 0.0)
    assert not window.canvas.is_empty() and not card.revealed


def test_click_tool_tablet_press_on_empty_board_is_not_swallowed(window, qtbot):
    """DrawingCanvas.tabletEvent kendi başına da (bir Zone üzerinden değil, tahtanın boş bir
    yerine doğrudan dokunulduğunda) Tool.CLICK iken olayı kabul etmemeli."""
    from PyQt6.QtCore import QEvent
    from test_canvas import tablet
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.CLICK], Qt.MouseButton.LeftButton)
    x, y = 60, window.canvas.height() - 60                # herhangi bir bölgenin altında olmayan boş köşe
    assert not tablet(window.canvas, QEvent.Type.TabletPress, x, y, 0.8)
    assert not tablet(window.canvas, QEvent.Type.TabletRelease, x, y, 0.0)
    assert window.canvas.is_empty()


def test_record_badge_is_transparent_to_mouse(window):
    assert window.badge.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_record_badge_stays_transparent_after_edit_mode_round_trip(window, qtbot):
    """WorkArea.set_edit_mode eskiden badge_slot'un WA_TransparentForMouseEvents bayrağını `on`'a
    bağlıyordu; düzen moduna girip çıkınca (Düzen düğmesi / L kısayolu / Bitti) bu, rozetin kurucuda
    kalıcı olarak ayarlanan şeffaflığını False'a döndürüp orijinal hatayı geri getiriyordu."""
    assert window.badge.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    qtbot.mouseClick(window.toolbar.layout_button, Qt.MouseButton.LeftButton)
    assert window.work_area.edit_mode
    assert window.badge.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    window.work_area.done_button.click()
    assert not window.work_area.edit_mode
    assert window.badge.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


def test_shape_button_cycles_and_draws(window, qtbot):
    from matematigin_mantigi.core.models import Shape
    btn = window.toolbar.tool_buttons[Tool.SHAPE]
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert window.canvas.tool == Tool.SHAPE and window.canvas.shape == Shape.RECT and btn.glyph == "▭"
    assert "Şekil (Dikdörtgen)" in window.work_area.status_label.text()
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)                  # seçiliyken tekrar: elips
    assert window.canvas.shape == Shape.ELLIPSE and btn.glyph == "○"
    c = window.canvas
    c.begin_stroke(QPointF(300, 300), 0.5); c.extend_stroke(QPointF(500, 420), 0.5); c.end_stroke()
    assert not c.is_empty()
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.PEN], Qt.MouseButton.LeftButton)
    assert window.canvas.shape == Shape.ELLIPSE                        # seçim hatırlanır


def test_text_tool_through_window(window, qtbot):
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.TEXT], Qt.MouseButton.LeftButton)
    assert window.canvas.cursor().shape() == Qt.CursorShape.IBeamCursor
    window.canvas.begin_stroke(QPointF(300, 400), 0.5)
    assert window.canvas.text_edit.isVisible()
    qtbot.keyClicks(window.canvas.text_edit, "Cevap: N ve H")      # N/H harfleri kısayol olarak çalışmamalı
    assert window.flow.index == 0 and window.flow.is_question_shown()
    qtbot.keyClick(window.canvas.text_edit, Qt.Key.Key_Return)
    assert not window.canvas.is_empty() and window.toolbar.undo_button.isEnabled()
    assert window.canvas.text_edit.isHidden()
    window.canvas.begin_stroke(QPointF(300, 500), 0.5)
    qtbot.keyClicks(window.canvas.text_edit, "iptal")
    qtbot.keyClick(window.canvas.text_edit, Qt.Key.Key_Escape)
    assert window.canvas.text_edit.isHidden() and window.canvas._stroke_count == 1


def test_ink_is_visible_on_top_of_hint_card(window, qtbot):
    card = window.hint_zone.cards[1]
    center = card.mapTo(window.work_area, card.rect().center())
    bpos = QPointF(window.work_area.board.mapFrom(window.work_area, center))
    c = window.canvas; c.set_color(QColor("#2456b8")); c.set_base_width(12)
    c.begin_stroke(bpos + QPointF(-40, 0), 1.0); c.extend_stroke(bpos + QPointF(40, 0), 1.0); c.end_stroke()
    img = window.work_area.grab().toImage()
    assert img.pixelColor(center.x(), center.y()).name() == "#2456b8"     # kartın üstünde mürekkep görünür


def test_drawing_over_question_zone_reaches_board(window, qtbot):
    z = window.question_zone
    qtbot.mousePress(z, Qt.MouseButton.LeftButton, pos=z.rect().center())
    qtbot.mouseMove(z, z.rect().center() + QPointF(60, 40).toPoint())
    qtbot.mouseRelease(z, Qt.MouseButton.LeftButton, pos=z.rect().center() + QPointF(60, 40).toPoint())
    assert not window.canvas.is_empty()


def test_recording_stub_and_badge(window, qtbot):
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert window.recorder.is_recording and window.badge.active
    assert window.badge.isHidden()                                     # rozet varsayılan kapalı: kayda girmesin
    stage = window.work_area.stage_rect()                              # kayda giren dikdörtgen: 16:9 sahne
    assert (window.recorder.last_rect.width, window.recorder.last_rect.height) == (stage.width(), stage.height())
    assert abs(stage.width() / stage.height() - 16 / 9) < 0.01 and window.recorder.fps == 60
    assert window.toolbar.record_label.text() == "DURDUR · 00:00"
    window.badge.tick(); window.badge.tick()
    assert window.badge.text().startswith("KAYIT · 00:02 · ") and window.toolbar.record_label.text() == "DURDUR · 00:02"
    assert "1440" in window.badge.text()                              # 2K çıktı
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert not window.recorder.is_recording and window.badge.isHidden()
    assert window.toolbar.record_label.text() == "KAYIT"


def test_badge_can_be_shown_on_board_from_settings(window, qtbot):
    window.settings.set_visible("badge", True); window.apply_ui_settings()
    window.toggle_recording(True)
    assert not window.badge.isHidden()
    window.toggle_recording(False)


def test_recorder_error_reverts_button(window, qtbot, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import RecorderError
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[2])))

    def boom(rect, fps=60):
        raise RecorderError("ffmpeg bulunamadı")
    monkeypatch.setattr(window.recorder, "start", boom)
    qtbot.mouseClick(window.toolbar.record_button, Qt.MouseButton.LeftButton)
    assert not window.recorder.is_recording and not window.toolbar.record_button.isChecked()
    assert shown and shown[0].startswith("Kayıt başlamadı") and "ffmpeg bulunamadı" in shown[0], shown


def test_real_recorder_through_window(window, qtbot, tmp_path):
    import time
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    import pytest
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    frame = __import__("numpy").full((120, 160, 4), 255, __import__("numpy").uint8)
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=10, grabber=lambda r: frame, out_height=0)
    window.toggle_recording(True)
    assert window.recorder.is_recording
    time.sleep(0.5)
    window.toggle_recording(False)
    assert not window.toolbar.record_button.isEnabled()          # kapanış ayrı iş parçacığında
    qtbot.waitUntil(lambda: window.toolbar.record_button.isEnabled(), timeout=15000)
    assert window.recorder.last_path.exists() and "Kayıt kaydedildi" in window.work_area.status_label.text()


def test_real_recorder_with_audio_muxes_and_cleans_up(window, qtbot, tmp_path):
    """Pencere üzerinden ses+video: mikrofon (sahte) alınır, mux edilir, ara dosyalar silinir, süre gerçek."""
    import time
    import numpy as np
    import pytest
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    from tests.test_recorder import FakeAudioCapture, synthetic_grabber
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    window.settings.audio_device = "Sahte Mikrofon"          # apply_ui_settings bunu kaydediciye taşır
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                        out_height=0, audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture)
    window.toggle_recording(True)
    assert window.recorder.is_recording
    time.sleep(1.2)
    window.toggle_recording(False)
    assert not window.toolbar.record_button.isEnabled()      # mux ayrı iş parçacığında, arayüz donmaz
    qtbot.waitUntil(lambda: window.toolbar.record_button.isEnabled(), timeout=20000)
    path = window.recorder.last_path
    assert path.exists() and window.recorder.error is None and window.recorder.audio_error is None
    assert window.recorder.audio_result is not None and window.recorder.audio_result.samples > 40000
    assert window.recorder.av_offset_ms is not None          # ses-video başlangıç farkı ölçüldü
    assert not list(path.parent.glob("*.wav")) and not list(path.parent.glob("*.video.mp4"))   # ara dosyalar silindi
    import cv2
    cap = cv2.VideoCapture(str(path)); frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
    assert frames > 10


def test_microphone_cut_warning_reaches_the_notice_box_not_the_board(window, qtbot, tmp_path, monkeypatch):
    """Mikrofon kayıt sırasında kesilince (gerçek AudioCapture, sahte sounddevice, gerçek ffmpeg) kayıt videonun
    tam uzunluğunda kaydedilir; ses uyarısı uyarı kutusuna gider, dosyanın yeriyle. Eskiden yalnız durum satırına
    ('… · UYARI: Mikrofon kayıt sırasında kesildi') yazılıyordu: durum satırı sahnede, sonraki kayda girer ve uyarı
    yeri değildir (Temel ilke). Video sağlam olduğu için 'Kayıt hatası' penceresi açılmaz."""
    import pytest
    from matematigin_mantigi.core import audio_capture as ac
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    from tests.test_audio_capture import FakeSoundDevice
    from tests.test_recorder import stepping_clock, synthetic_grabber, wait_until
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    shown = _capture_modals(monkeypatch)
    posted = _capture_notices(monkeypatch)
    sd = FakeSoundDevice(blocks=15)                                       # 0,3 sn ses, sonra mikrofon susar
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    window.settings.audio_device = "USB Mikrofon"
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                              out_height=0, audio_device="USB Mikrofon", clock=stepping_clock())
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    wait_until(lambda: rec.frames_written >= 3 * rec.fps and sd.fed.is_set())   # 3 sn video (ayardaki fps)
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=20000)
    assert rec.audio_error and "Mikrofon kayıt sırasında kesildi" in rec.audio_error, rec.audio_error
    text = window.work_area.status_label.text()
    assert text.startswith(f"Kayıt kaydedildi: {rec.last_path}") and rec.audio_error not in text, text
    assert len(posted) == 1 and rec.audio_error in posted[0][1] and str(rec.last_path) in posted[0][1], posted
    assert shown == [] and rec.last_path.exists() and not list(rec.last_path.parent.glob("*.video.mp4"))


def test_microphone_warning_of_each_saved_recording_is_shown_outside_the_board(window, monkeypatch):
    """P2: başarılı kaydın ses uyarısı durum satırında değil uyarı kutusunda (kayıt bitti: açık yerde). Her kaydın
    uyarısı ayrı anahtarla gelir: aynı anahtarla oturumun ikinci kaydının uyarısı hiç gösterilmezdi."""
    from pathlib import Path
    from matematigin_mantigi.core.recorder import NullRecorder

    class MicCut(NullRecorder):                       # anında durur; sonuç alanları bu testin kendi metni
        audio_error = None
        count = 0

        def stop(self):
            super().stop()
            MicCut.count += 1
            self.audio_error = f"Mikrofon kayıt sırasında kesildi (yapay {MicCut.count})"
            return Path("oturum") / f"kayit_{MicCut.count}.mp4"
    shown = _capture_modals(monkeypatch)
    posted = _capture_notices(monkeypatch)
    window.recorder = MicCut()
    for _ in range(2):
        window.toggle_recording(True)
        window.toggle_recording(False)
    status = window.work_area.status_label.text()
    assert "kayit_2.mp4" in status and "Mikrofon" not in status and "UYARI" not in status, status
    assert shown == [] and len(posted) == 2 and posted[0][2] != posted[1][2], posted
    for i, (_title, text, _key) in enumerate(posted, start=1):
        assert f"Mikrofon kayıt sırasında kesildi (yapay {i})" in text and f"kayit_{i}.mp4" in text, text


def test_record_error_window_also_tells_what_happened_to_the_sound(window, qtbot, monkeypatch):
    """P2: ffmpeg kayıt ortasında ölünce (mikrofonlu kayıt) 'Kayıt hatası' penceresi yalnız 'ffmpeg borusu kapandı:
    ayrıntı yok' diyordu; kaydedicinin ses uyarısı (ses ayrı dosyada, birleştirilemedi) atılıyordu. Pencere ikisini
    birlikte söyler. P6: metin başlıksız da anlaşılır (Qt macOS'ta QMessageBox başlığını göstermez)."""
    from matematigin_mantigi.core.recorder import NullRecorder

    class PipeDied(NullRecorder):                     # kapanış _StopWorker'da; kendi metinleri (kaydedicininki değil)
        stop_is_quick = False
        error = audio_error = None

        def stop(self):
            super().stop()
            self.error = "yapay boru hatası: ayrıntı yok"
            self.audio_error = "Ses birleştirilemedi: yapay sebep; ses ayrı dosyada duruyor"
            return None
    shown = _capture_modals(monkeypatch)
    window.recorder = PipeDied()
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=10000)
    assert len(shown) == 1, shown
    text = shown[0][1]
    assert text.startswith(RECORD_FAILED) and "yapay boru hatası: ayrıntı yok" in text, text
    assert "Ses birleştirilemedi: yapay sebep; ses ayrı dosyada duruyor" in text, text


def _screen_pixels(widget, width: int):
    """Ekranda (offscreen: pencerelerin son çizilmiş hâli) widget'ın sol üstünden başlayan `width` genişliğindeki
    bant: kaydedicinin ilk karesinde ne göründüğü. Bant sabit genişlikte: yazı uzayıp kısalsa da aynı yer ölçülür."""
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QApplication
    tl = widget.mapToGlobal(QPoint(0, 0))
    return QApplication.primaryScreen().grabWindow(0, tl.x(), tl.y(), width, widget.height()).toImage()


def test_saved_recording_path_is_off_the_board_before_the_next_recording_starts(window, monkeypatch):
    """P3: başarılı kayıttan sonra durum satırına 'Kayıt kaydedildi: <tam yol>' yazılıyordu; durum satırı sahnede ve
    kayda girer: sonraki kayıt başlarken satır böyle kaldığı için dosya yolu (kullanıcı adı) yeni videoya giriyordu.
    Kayıt başlamadan satır olağan metnine döner ve ekrana çizilir: kaydedici ilk kareyi start() içinde, GUI'de
    yakalar (yalnız setText ekrandaki eski yazıyı ilk karede bırakırdı)."""
    from pathlib import Path
    from matematigin_mantigi.core.recorder import NullRecorder
    status = window.work_area.status_label

    class Rec(NullRecorder):                          # start(): kaydedicinin ilk kareyi yakaladığı an
        at_start: list = []

        def start(self, rect, fps=60):
            Rec.at_start.append((status.text(), _screen_pixels(status, 900)))
            super().start(rect, fps)

        def stop(self):
            super().stop()
            return Path("/Users/ogretmen/Documents/Matematiğin Mantığı/oturum/kayit_1.mp4")
    window.recorder = Rec()
    window.toggle_recording(True)
    window.toggle_recording(False)
    assert "kayit_1.mp4" in status.text()                             # kayıttan sonra öğretmen dosyanın yerini görür
    window.repaint()                                                  # (ekranda da yazıyor)
    window.toggle_recording(True)
    window.toggle_recording(False)
    (first_text, first_px), (second_text, second_px) = Rec.at_start
    assert second_text == first_text and "ogretmen" not in second_text, Rec.at_start
    assert second_px == first_px                                      # ilk karede de yol yok: olağan satır çizili


def test_notice_box_open_when_recording_starts_is_not_in_the_first_frame(window, qtbot, tmp_path, monkeypatch):
    """P4: kayıttan önce açık kalan uyarı kutusu kaydın ilk karelerine giriyordu (k001-k005; kutu hatalar.log'un tam
    yolunu, yani kullanıcı adını taşır): kaydedici ilk kareyi start() içinde, GUI'de yakalar; kutu ise ancak kayıt
    rozetinin ilk tikinde, start() döndükten sonra gizleniyordu. Kutu start()'tan önce gizlenir, uyarı şeride geçer;
    kayıt bitince geri gelir."""
    import pytest
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    from matematigin_mantigi.ui import error_notice
    from tests.test_recorder import stepping_clock, synthetic_grabber
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    shown = _capture_modals(monkeypatch)
    _wired_notice(window, monkeypatch)
    error_notice.post("Düzen kaydedilemedi", "duzen.json yazılamadı: erişim izni yok.", key="duzen")
    qtbot.waitUntil(lambda: bool(_visible_message_boxes()), timeout=2000)
    first_frame: list = []

    def grabber(rect):
        if not first_frame:                           # ilk çağrı start() içinde, GUI iş parçacığında
            first_frame.append(len(_visible_message_boxes()))
        return synthetic_grabber(rect)
    window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=10, grabber=grabber, out_height=0,
                                        clock=stepping_clock())
    window.toggle_recording(True)
    strip = window.toolbar.alert_label.text()
    window.toggle_recording(False)
    qtbot.waitUntil(lambda: window.toolbar.record_button.isEnabled(), timeout=15000)
    assert first_frame == [0] and strip == "⚠ Düzen kaydedilemedi — ayrıntı kayıt bitince", (first_frame, strip)
    qtbot.waitUntil(lambda: bool(_visible_message_boxes()), timeout=2000)        # kayıt bitti: kutu geri geldi
    assert "duzen.json yazılamadı" in _visible_message_boxes()[0].text() and shown == []


def _magenta_share(image) -> float:
    """Görüntüde macenta (testte kutu bu renge boyanır) piksellerin oranı."""
    import numpy as np
    from PyQt6.QtGui import QImage
    img = image.convertToFormat(QImage.Format.Format_RGB32)
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    px = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width(), :3]
    return float(((px[..., 0] > 200) & (px[..., 1] < 60) & (px[..., 2] > 200)).mean()) if px.size else 0.0


def _magenta_notice_box(window, qtbot, monkeypatch):
    """Pencereye bağlı gerçek uyarı kutusu, kayıttan önce açık; ekranda ayırt edilsin diye macenta. (kutu, yeri)."""
    from matematigin_mantigi.ui import error_notice
    notice = _wired_notice(window, monkeypatch)
    error_notice.post("Beklenmeyen hata", "Ayrıntı: /Users/ogretmen.adi/Documents/Matematiğin Mantığı/hatalar.log",
                      key="k1")
    qtbot.waitUntil(lambda: bool(_visible_message_boxes()), timeout=2000)
    box = _visible_message_boxes()[0]
    box.setStyleSheet("QMessageBox, QMessageBox * { background: #ff00ff; color: #ff00ff; border: none; }")
    qtbot.wait(100)                                   # macenta kutu ekrana çizilsin
    return notice, box.geometry()


def test_box_hidden_for_recording_is_off_the_screen_when_the_first_frame_is_grabbed(window, qtbot, monkeypatch):
    """U6: prepare_recording kutuyu start()'tan önce gizliyordu; ama gizlenen pencere olay döngüsü dönene dek ekranda
    (exposed) kalıyor, ekran yakalayıcısı onu çizmeye devam ediyordu: kutu (hatalar.log'un yolu, yani kullanıcı adı)
    gerçek kaydın ilk ~3 karesindeydi (inceleme v02, k001-k003). Qt düzeyindeki görünürlük bunu göstermez: ilk kare
    (start() içinde, GUI'de) ekrandan piksel düzeyinde alınır, macenta kutu orada çizili olmamalı. Kutu gizlenince
    dönen olay turunda yoklama ve sıradaki yeni uyarı kutuyu geri getirmez (şeride gider); kayıt bitince ikisi kutuda."""
    from PyQt6.QtGui import QGuiApplication
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.ui import error_notice
    shown = _capture_modals(monkeypatch)
    notice, area = _magenta_notice_box(window, qtbot, monkeypatch)

    def on_screen() -> float:
        return _magenta_share(QGuiApplication.primaryScreen().grabWindow(
            0, area.x(), area.y(), area.width(), area.height()).toImage())
    assert on_screen() > 0.5                          # ölçü çalışıyor: açık kutu ekranda macenta

    class Rec(NullRecorder):
        first_frame = None

        def start(self, rect, fps=60):                # gerçek kaydedici ilk kareyi burada, GUI'de yakalar
            Rec.first_frame = (on_screen(), len(_visible_message_boxes()))
            super().start(rect, fps)
    window.recorder = Rec()
    notice._poll_timer.setInterval(0)                 # yoklama her olay turunda: kutuyu geri getirecekse getirsin
    error_notice.post("Tahta görüntüsü kaydedilemedi", "S1 sorusunun resmi yazılamadı.", key="k2")      # sırada
    window.toggle_recording(True)
    notice._poll_timer.setInterval(error_notice.POLL_MS)
    strip = window.toolbar.alert_label.text()
    qtbot.wait(3 * error_notice.POLL_MS)
    during = (len(_visible_message_boxes()), on_screen())                       # kayıt sürerken de yok
    window.toggle_recording(False)
    assert Rec.first_frame == (0.0, 0) and strip == "⚠ 2 uyarı — ayrıntı kayıt bitince", (Rec.first_frame, strip)
    assert during == (0, 0.0), during
    qtbot.waitUntil(lambda: bool(_visible_message_boxes()), timeout=2000)        # kayıt bitti: ikisi kutuda
    text = _visible_message_boxes()[0].text()
    assert "hatalar.log" in text and "S1 sorusunun resmi" in text and shown == [], (text, shown)


def test_box_hidden_for_a_recording_that_does_not_start_comes_back(window, qtbot, monkeypatch):
    """U6: kayıt başlamazsa (başlatma hatası) start()'tan önce gizlenen kutu geri gelir, şerit temizlenir: uyarı
    kaybolmaz."""
    from matematigin_mantigi.core.recorder import NullRecorder, RecorderError

    class Failing(NullRecorder):
        def start(self, rect, fps=60):
            raise RecorderError("ffmpeg bulunamadı (yapay)")
    shown = _capture_modals(monkeypatch)
    _magenta_notice_box(window, qtbot, monkeypatch)
    window.recorder = Failing()
    window.toggle_recording(True)
    assert len(shown) == 1 and "Kayıt başlamadı" in shown[0][1], shown
    qtbot.waitUntil(lambda: bool(_visible_message_boxes()), timeout=2000)
    assert "hatalar.log" in _visible_message_boxes()[0].text() and not window.toolbar.alert_label.isVisible()


# --- #2: kayıt kaydedilirken yeni kayıt yok; uyarı araç çubuğunda (denetim app#1, e2e#2) -----------------------

def test_r_while_previous_recording_is_saving_starts_nothing_and_warns_in_toolbar(window, qtbot, tmp_path,
                                                                                  monkeypatch):
    """Durdurma arka planda sürerken kayıt düğmesi kilitliydi ama R değildi: yeni kayıt başlıyor, ilk dersin
    kapanışı yeni kaydın alanlarını devralıyor, araç çubuğu kayıt sürerken 'kayıt yok' gösteriyordu. Şimdi
    kaydedilirken R hiçbir şey başlatmaz; uyarı araç çubuğundadır (tahtadaki durum satırı kayda girer, uyarı
    taşımaz) ve kayıt kapanınca kalkar. Gerçek ffmpeg; uzun birleştirme olayla bekletilir (sleep yok)."""
    import pytest
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState, find_ffmpeg
    from tests.test_recorder import FakeAudioCapture, SlowMux, stepping_clock, synthetic_grabber, wait_until
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    mux = SlowMux(monkeypatch)
    window.settings.audio_device = "Sahte Mikrofon"
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                              out_height=0, audio_device="Sahte Mikrofon",
                                              audio_factory=FakeAudioCapture, clock=stepping_clock())
    tb, status = window.toolbar, window.work_area.status_label
    qtbot.keyClick(window, Qt.Key.Key_R)                                 # 1. ders
    assert rec.is_recording
    first = rec.last_path
    wait_until(lambda: rec.frames_written >= 10)
    qtbot.keyClick(window, Qt.Key.Key_R)                                 # durdur: kapanış arka planda
    try:
        assert mux.entered.wait(20)                                      # ilk ders birleştiriliyor
        assert not tb.record_button.isEnabled()
        qtbot.keyClick(window, Qt.Key.Key_R)                             # kaydedilirken yine R
        assert rec.state is RecorderState.FINALIZING and rec.last_path == first and not window.badge.active
        assert not tb.record_button.isChecked() and tb.record_label.text() == "KAYIT"
        assert tb.alert_label.isVisible() and tb.alert_label.text() == "Kayıt kaydediliyor…"
        assert "kaydediliyor" not in status.text() and "kapatılıyor" not in status.text()
        assert shown == []                                               # modal pencere de açılmadı
    finally:
        mux.release()
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=20000)
    assert tb.alert_label.isHidden() and shown == []                     # kayıt kapandı: uyarı kalktı, hata yok
    assert first.exists() and not list(first.parent.glob("*.video.mp4")) and not list(first.parent.glob("*.wav"))
    qtbot.keyClick(window, Qt.Key.Key_R)                                 # artık yeni kayıt başlar
    assert rec.state is RecorderState.RECORDING and rec.last_path != first and tb.record_button.isChecked()
    wait_until(lambda: rec.frames_written >= 3)
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=20000)
    assert rec.last_path.exists() and shown == []


def test_stopping_shows_the_saving_strip_until_the_recording_is_saved(window, qtbot, tmp_path, monkeypatch):
    """Normal durdurmada (R) kapanış sürerken araç çubuğunda 'Kayıt kaydediliyor…' görünür, düğme kilitli; kayıt
    bitince şerit kalkar. (Önceki test şeridi ancak kaydedilirken ikinci R'den sonra görüyordu: durdurmanın kendisi
    şeridi göstermese de geçiyordu.)"""
    import pytest
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    from matematigin_mantigi.ui.main_window import SAVING_ALERT
    from tests.test_recorder import FakeAudioCapture, SlowMux, stepping_clock, synthetic_grabber, wait_until
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    mux = SlowMux(monkeypatch)
    window.settings.audio_device = "Sahte Mikrofon"
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                              out_height=0, audio_device="Sahte Mikrofon",
                                              audio_factory=FakeAudioCapture, clock=stepping_clock())
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    wait_until(lambda: rec.frames_written >= 10)
    assert tb.alert_label.isHidden()                                     # kayıt sürerken şerit yok
    qtbot.keyClick(window, Qt.Key.Key_R)                                 # durdur: kapanış arka planda
    try:
        assert mux.entered.wait(20)
        assert tb.alert_label.isVisible() and tb.alert_label.text() == SAVING_ALERT
        assert not tb.record_button.isEnabled()
    finally:
        mux.release()
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=20000)
    assert tb.alert_label.isHidden() and shown == [] and rec.last_path.exists()


def test_r_before_the_stop_result_reaches_the_window_starts_nothing(window, qtbot, tmp_path, monkeypatch):
    """Kaydedici IDLE'a döndükten sonra da, durdurma sonucu pencereye ulaşana (_on_record_stopped) dek yeni kayıt
    yok: yoksa geç gelen sonuç yeni kaydın araç çubuğunu 'kayıt yok'a çevirir ve onun hata alanlarını okur."""
    import threading
    import pytest
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState, find_ffmpeg
    from tests.test_recorder import stepping_clock, synthetic_grabber, wait_until
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=10, grabber=synthetic_grabber,
                                              out_height=0, clock=stepping_clock())
    held, go = threading.Event(), threading.Event()
    real_stop = rec.stop

    def stop_then_hold():
        path = real_stop()                     # kaydedici bitirdi (IDLE) ...
        held.set()
        assert go.wait(20)                     # ... ama sonuç henüz pencereye gönderilmedi
        return path
    monkeypatch.setattr(rec, "stop", stop_then_hold)
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    first = rec.last_path
    wait_until(lambda: rec.frames_written >= 3)
    qtbot.keyClick(window, Qt.Key.Key_R)
    try:
        assert held.wait(20) and rec.state is RecorderState.IDLE
        qtbot.keyClick(window, Qt.Key.Key_R)
        assert rec.state is RecorderState.IDLE and rec.last_path == first          # yeni kayıt başlamadı
        assert tb.alert_label.isVisible() and not tb.record_button.isEnabled()
    finally:
        go.set()
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=20000)
    assert tb.alert_label.isHidden() and not tb.record_button.isChecked() and first.exists()


def test_exception_while_saving_is_shown_and_window_does_not_stay_locked(window, qtbot, tmp_path, monkeypatch):
    """Kapanışın bir adımı patlarsa (ör. Windows'ta kullanımdaki dosyanın yeniden adlandırılması) hata gösterilir ve
    arayüz 'kaydediliyor'da takılı kalmaz: şerit kalkar, düğme açılır, sonraki R yeni kayıt başlatır. Pencere önce
    kaydedicinin anlamlı hatasını gösterir (sebep + kayıt klasörü), ham istisna metnini değil; istisna günlüğe gider."""
    from pathlib import Path
    import pytest
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState, find_ffmpeg
    from tests.test_recorder import capture_logged, stepping_clock, synthetic_grabber, wait_until
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    logged = capture_logged(monkeypatch)

    class NoMic:
        def __init__(self, device): pass
        def start(self, path): raise RuntimeError("aygıt yok")
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=10, grabber=synthetic_grabber,
                                              out_height=0, audio_device="Yok", audio_factory=NoMic,
                                              clock=stepping_clock())
    real_replace = Path.replace

    def busy(self, target):
        if self.name.endswith(".video.mp4"):
            raise PermissionError(13, "dosya kullanımda", str(self))
        return real_replace(self, target)
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    wait_until(lambda: rec.frames_written >= 3)
    monkeypatch.setattr(Path, "replace", busy)                 # mikrofonsuz kayıt: .video.mp4 -> .mp4 patlar
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=20000)
    assert shown and shown[0][1].startswith(RECORD_FAILED) and "dosya kullanımda" in shown[0][1], shown
    assert rec.error in shown[0][1] and f"Kayıt klasörü: {tmp_path / 'rec'}" in rec.error, shown
    assert (PermissionError, "kayıt kapanışı") in [(type(e), where) for e, where in logged]
    assert tb.alert_label.isHidden() and rec.state is RecorderState.IDLE
    monkeypatch.setattr(Path, "replace", real_replace)
    qtbot.keyClick(window, Qt.Key.Key_R)                        # kilitli kalmadı: yeni kayıt başlar
    assert rec.state is RecorderState.RECORDING and tb.record_button.isChecked()
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=20000)
    assert rec.last_path.exists() and len(shown) == 1


def test_record_start_oserror_is_shown_and_toolbar_returns_to_idle(window, qtbot, monkeypatch):
    """Başlatmadaki OSError (disk dolu, izin yok, macOS'ta Belgeler izni) eskiden yalnız RecorderError yakalandığı
    için yuvadan kaçıyordu; PyQt6 yuvadaki yakalanmamış hatada uygulamayı kapatır. Şimdi anlamlı mesaj gösterilir,
    araç çubuğu 'kayıt yok'a döner; düğme ve R aynı yoldan. Ayrıntı hatalar.log'a da düşer."""
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import RecorderState
    from tests.test_recorder import capture_logged
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    logged = capture_logged(monkeypatch)

    def disk_full(rect, fps=60):
        raise OSError(28, "No space left on device", "/Users/ogretmen/Documents/oturum")
    monkeypatch.setattr(window.recorder, "start", disk_full)
    tb = window.toolbar
    qtbot.mouseClick(tb.record_button, Qt.MouseButton.LeftButton)
    assert shown and shown[0][1].startswith("Kayıt başlamadı"), shown        # başlıksız da anlaşılır (macOS)
    assert "Kayıt dosyası yazılamadı" in shown[0][1] and "No space left on device" in shown[0][1]
    assert window.recorder.state is RecorderState.IDLE and not window.badge.active
    assert not tb.record_button.isChecked() and tb.record_label.text() == "KAYIT"
    qtbot.keyClick(window, Qt.Key.Key_R)
    assert len(shown) == 2 and not tb.record_button.isChecked()
    assert [(type(e), where) for e, where in logged] == [(OSError, "kayıt başlatma")] * 2


def test_unexpected_record_start_error_is_shown_logged_and_toolbar_returns_to_idle(window, qtbot, monkeypatch):
    """Beklenmeyen (RecorderError/OSError dışı) başlatma hatası yuvadan kaçıyordu: düğme 'kayıtta' kalıyor, yalnız
    genel hata kutusu ve aynı hata için bir kez geliyordu (sonraki denemeler sessiz). Son çare: her denemede 'Kayıt
    başlatılamadı' penceresi, araç çubuğu 'KAYIT'a döner, ayrıntı hatalar.log'a gider."""
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_recorder import capture_logged
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    logged = capture_logged(monkeypatch)

    def boom(rect, fps=60):
        raise RuntimeError("can't start new thread")
    monkeypatch.setattr(window.recorder, "start", boom)
    tb = window.toolbar
    qtbot.mouseClick(tb.record_button, Qt.MouseButton.LeftButton)
    assert [text for _title, text in shown] == [
        "Kayıt başlamadı.\nBeklenmeyen hata: RuntimeError: can't start new thread"]      # başlıksız da anlaşılır
    assert not tb.record_button.isChecked() and tb.record_label.text() == "KAYIT" and not window.badge.active
    qtbot.keyClick(window, Qt.Key.Key_R)                                  # R aynı yoldan; ikinci deneme de sessiz değil
    assert len(shown) == 2 and not tb.record_button.isChecked()
    assert [(type(e), where) for e, where in logged] == [(RuntimeError, "kayıt başlatma")] * 2


def test_stop_error_without_message_is_still_shown_and_logged(window, qtbot, monkeypatch):
    """Kapanış mesajsız bir istisnayla patlarsa (OSError()) _StopWorker.exc boş kalıyor, arayüz hiçbir şey
    göstermiyordu ve hata hiçbir yere yazılmıyordu. Şimdi pencerede istisnanın kendisi görünür, hatalar.log'a düşer."""
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import NullRecorder
    from tests.test_recorder import capture_logged

    class FailingStop(NullRecorder):                                  # kapanış ayrı iş parçacığında koşar
        stop_is_quick = False

        def stop(self):
            super().stop()
            raise OSError()
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    logged = capture_logged(monkeypatch)
    window.recorder = FailingStop()
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.keyClick(window, Qt.Key.Key_R)
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=10000)
    assert [text for _title, text in shown] == [f"{RECORD_FAILED}\nOSError()"]
    assert [(type(e), where) for e, where in logged] == [(OSError, "kayıt kapanışı")]


def test_ffmpeg_dying_at_start_shows_why_and_where_the_sound_is(window, qtbot, tmp_path, monkeypatch):
    """Mikrofonlu kayıtta ffmpeg başta ölünce (kodlayıcı açılamadı, disk dolu) pencere ham 'No such file or
    directory' metnini gösteriyordu. Şimdi kaydedicinin hatası: ffmpeg'in sebebi ve silinmeyen ses dosyasının yeri."""
    import sys
    import pytest
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder
    from tests.test_recorder import FakeAudioCapture, fake_ffmpeg, stepping_clock, synthetic_grabber, wait_until
    if sys.platform == "win32":
        pytest.skip("sahte ffmpeg bir kabuk betiği")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    exe = fake_ffmpeg(tmp_path, "echo 'Error while opening encoder: No space left on device' >&2; exit 1")
    window.settings.audio_device = "Sahte Mikrofon"
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                              out_height=0, ffmpeg_exe=str(exe), audio_device="Sahte Mikrofon",
                                              audio_factory=FakeAudioCapture, clock=stepping_clock())
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    wait_until(lambda: rec.failed)
    window.badge.tick()                                                 # _check_recorder kaydı kapatır
    qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=10000)
    assert len(shown) == 1 and shown[0][1].startswith(RECORD_FAILED), shown
    text = shown[0][1]
    assert "No space left on device" in text and str(rec.last_path.with_suffix(".wav")) in text, text
    assert "No such file" not in text and rec.last_path.with_suffix(".wav").exists()


def test_writer_failure_stops_recording_on_next_badge_tick(window):
    """ffmpeg borusu koparsa (kaydedici failed) saniyelik rozet tikinde kayıt kapatılır (_check_recorder)."""
    window.toggle_recording(True)
    assert window.recorder.is_recording
    window.recorder.failed = True
    window.badge.tick()
    assert not window.recorder.is_recording and not window.toolbar.record_button.isChecked()


def test_layout_edit_persists_to_file(window, qtbot, tmp_path):
    qtbot.mouseClick(window.toolbar.layout_button, Qt.MouseButton.LeftButton)
    assert window.work_area.edit_mode
    window.work_area.reset_layout()
    assert (tmp_path / "duzen.json").exists()
    assert lm.load_layout(tmp_path / "duzen.json") == lm.DEFAULT_LAYOUT
    window.work_area.done_button.click()
    assert not window.work_area.edit_mode and not window.toolbar.layout_button.isChecked()


def _capture_notices(monkeypatch) -> list:
    from matematigin_mantigi.ui import error_notice
    posted = []
    monkeypatch.setattr(error_notice, "post", lambda title, text, key=None: posted.append((title, text, key)))
    return posted


def test_layout_save_failure_is_reported_and_editing_continues(window, qtbot, tmp_path, monkeypatch):
    """app#2: düzen değişince duzen.json yazılamazsa (izin, salt okunur disk, klasör yerine dosya) layoutChanged
    lambda'sındaki save_layout OSError fırlatıyor, yuva uygulamayı süren kayıtla birlikte düşürüyordu. Artık modal
    olmayan uyarı (kancaya kadar gitmez); yeni düzen bu oturumda geçerli kalır, düzenleme sürer."""
    posted = _capture_notices(monkeypatch)
    (tmp_path / "engel").write_text("dosya", encoding="utf-8")
    window.layout_path = tmp_path / "engel" / "duzen.json"
    qtbot.mouseClick(window.toolbar.layout_button, Qt.MouseButton.LeftButton)
    window.work_area.reset_layout()
    window.work_area.reset_layout()                         # tekrar: aynı uyarı anahtarı (pencere yağmuru yok)
    assert [p[0] for p in posted] == ["Düzen kaydedilemedi"] * 2 and posted[0][2] == posted[1][2]
    assert "duzen.json" in posted[0][1]
    window.work_area.done_button.click()
    assert not window.work_area.edit_mode


def test_restores_settings_on_start(qtbot, tmp_path, ini_settings, dead_camera):
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    ini_settings.tool = Tool.LASER; ini_settings.color = "#1f8a4c"; ini_settings.width = 2
    ini_settings.hint_mask = HintMaskMode.REDACT; ini_settings.chroma_enabled = False
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda index: dead_camera, tmp_path / "d.json")
    qtbot.addWidget(win)
    assert win.canvas.tool == Tool.LASER and win.canvas.color.name() == "#1f8a4c" and win.canvas.base_width == 2
    assert win.toolbar.tool_buttons[Tool.LASER].isChecked() and win.toolbar.width_buttons[2].isChecked()
    assert win.hint_zone.mask_mode == HintMaskMode.REDACT
    assert win.webcam_panel.chroma_enabled is False           # Ayarlar'daki perde anahtarı geri gelir
    assert win.question_zone.reading_ms == 0 and not win.question_zone.is_animating


def test_settings_camera_change_restarts_worker_and_logo(window, qtbot, tmp_path, monkeypatch):
    from PyQt6.QtGui import QImage
    from matematigin_mantigi.ui import settings_dialog as sd
    img = QImage(80, 80, QImage.Format.Format_RGB32); img.fill(Qt.GlobalColor.blue)
    logo = tmp_path / "logo.png"; img.save(str(logo))
    old_worker = window.webcam_panel.worker
    seen = []
    window.camera_source_factory = lambda index: (seen.append(index), window.camera_source_factory_dead)[1]
    window.camera_source_factory_dead = old_worker._source

    def fake_exec(self):
        self.logo_path_edit.setText(str(logo))
        self.camera_combo.addItem("Kamera 2", 2); self.camera_combo.setCurrentIndex(self.camera_combo.count() - 1)
        self._apply()
        return 1
    monkeypatch.setattr(sd.SettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.settings_button, Qt.MouseButton.LeftButton)
    assert window.settings.camera_index == 2 and seen == [2]
    assert window.webcam_panel.worker is not old_worker
    assert window.work_area.logo_is_file and window.settings.logo_file == str(logo)


def test_reload_questions_updates_flow_and_zone(window):
    from matematigin_mantigi.core.models import Question
    new = [Question("Z1", "Yeni konu", 5, "Yepyeni soru?", ("ip",), "cevap", ("a", "b", "c", "d"), None),
           Question("Z2", "Konu2", None, "İkinci?", (), "x", (), None)]
    window.reload_questions(new)
    assert [q.id for q in window.flow.questions] == ["Z1", "Z2"] and window.flow.index == 0
    assert window.question_zone.number_label.text() == "1."
    assert window.question_zone.text_label.text() == "Yepyeni soru?"
    assert len(window.hint_zone.cards) == 1


def test_reload_empty_list_does_not_crash(window):
    window.reload_questions([])
    assert window.flow.questions == () and window.flow.index == 0


def test_editor_button_disabled_and_open_is_guarded_without_path(window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    calls = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: calls.append(a)))
    assert not window.toolbar.editor_button.isEnabled()          # fixture questions_path yok
    window.open_editor()
    assert calls                                                 # bilgi kutusu gösterildi, başka iş yok


def test_window_with_questions_path_enables_editor(qtbot, tmp_path, ini_settings, dead_camera):
    from matematigin_mantigi.core.models import PenSettings, Question
    from matematigin_mantigi.core.question_loader import write_questions
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    path = write_questions(tmp_path / "sorular.xlsx", list(SAMPLE_QUESTIONS))
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda index: dead_camera,
                     tmp_path / "d.json", questions_path=path)
    qtbot.addWidget(win)
    assert win.questions_path == path and win.toolbar.editor_button.isEnabled()
    win.reload_questions([Question("Z1", "K", 5, "Yeni?", ("i",), "c", ("a", "b", "c", "d"), None)])
    assert [q.id for q in win.flow.questions] == ["Z1"] and win.flow.index == 0
    assert win.question_zone.text_label.text() == "Yeni?"


def test_close_is_clean(window):
    window.close()


def test_keyboard_shortcuts(window, qtbot):
    qtbot.keyClick(window, Qt.Key.Key_2)
    assert window.canvas.tool == Tool.ERASER and window.toolbar.tool_buttons[Tool.ERASER].isChecked()
    qtbot.keyClick(window, Qt.Key.Key_N)
    assert window.flow.index == 1
    qtbot.keyClick(window, Qt.Key.Key_P)
    assert window.flow.index == 0
    qtbot.keyClick(window, Qt.Key.Key_Right)
    assert window.hint_zone.counter_label.text() == "2 / 3"
    qtbot.keyClick(window, Qt.Key.Key_Return)
    assert window.hint_zone.cards[1].revealed
    qtbot.keyClick(window, Qt.Key.Key_R)
    assert window.recorder.is_recording
    qtbot.keyClick(window, Qt.Key.Key_R)
    assert not window.recorder.is_recording
    qtbot.keyClick(window, Qt.Key.Key_L)
    assert window.work_area.edit_mode
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert not window.work_area.edit_mode


def test_pen_settings_round_trip_through_window(window, qtbot, monkeypatch):
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.ui import pen_settings as ps

    def fake_exec(self):
        self.smoothing_slider.setValue(80)
        self._apply()
        return 1
    monkeypatch.setattr(ps.PenSettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.pen_settings_button, Qt.MouseButton.LeftButton)
    assert window.settings.pen() == PenSettings(smoothing=80, reading_ms=0)     # hız korunur (fixture: 0)


def test_settings_dialog_toggles_aspect_lock(window, qtbot, monkeypatch):
    from matematigin_mantigi.ui import settings_dialog as sd
    wa = window.work_area
    assert window.settings.aspect_lock is True and wa.stage_rect() != wa.rect()

    def fake_exec(self):
        self.aspect_lock_check.setChecked(False)
        self._apply()
        return 1
    monkeypatch.setattr(sd.SettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.settings_button, Qt.MouseButton.LeftButton)
    assert window.settings.aspect_lock is False and wa.aspect_lock is False
    assert wa.stage_rect() == wa.rect()                                # bant yok: tahta tüm alanı kaplar
    x, y, w, h, _ = wa.recording_rect()
    assert (w, h) == (wa.width(), wa.height())


def test_settings_dialog_applies_speed_visibility_and_auto_key(window, qtbot, monkeypatch):
    from matematigin_mantigi.ui import settings_dialog as sd

    def fake_exec(self):
        self.reading_slider.setValue(90)
        self.auto_key_check.setChecked(False)
        self.visibility_checks["status"].setChecked(False)
        self.visibility_checks["cam_label"].setChecked(False)
        self.visibility_checks["hint_controls"].setChecked(False)
        self.visibility_checks["brand"].setChecked(False)
        self.visibility_checks["question_number"].setChecked(False)
        self.visibility_checks["frame"].setChecked(False)
        self.presenter_edit.setText("Barış Keser")
        self.chroma_check.setChecked(False)
        self._apply()
        return 1
    monkeypatch.setattr(sd.SettingsDialog, "exec", fake_exec)
    qtbot.mouseClick(window.toolbar.settings_button, Qt.MouseButton.LeftButton)
    s = window.settings
    assert s.chroma_enabled is False and window.webcam_panel.chroma_enabled is False
    assert s.presenter_name == "Barış Keser" and window.work_area.name_label.text() == "Barış Keser"
    stage = window.work_area.stage_rect()                              # çerçeve kapalı: tahta = sahne
    assert not window.work_area.frame_visible and window.canvas.geometry() == stage
    assert stage != window.work_area.rect() and abs(stage.width() / stage.height() - 16 / 9) < 0.01
    assert s.pen().reading_ms == 90 and window.question_zone.reading_ms == 90
    assert s.auto_key is False and s.visible("status") is False
    assert window.work_area.status_label.isHidden() and window.webcam_panel.overlay_label.isHidden()
    assert window.hint_zone.blur_button.isHidden() and window.work_area.brand.isHidden()
    assert window.question_zone.number_label.isHidden()
    assert not window.hint_zone.title_label.isHidden()                 # dokunulmayan öğe açık kalır


def test_visibility_and_font_restored_on_start(qtbot, tmp_path, ini_settings, dead_camera):
    import pytest
    from matematigin_mantigi import paths
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    caveat = next(iter(paths.FONTS_DIR.glob("Caveat*.ttf")), None)
    if caveat is None:
        pytest.skip("bundled fonts not downloaded")
    ini_settings.set_pen(PenSettings(reading_ms=0))
    ini_settings.set_visible("brand", False); ini_settings.set_visible("hide_link", False)
    ini_settings.font_file = str(caveat)
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda index: dead_camera, tmp_path / "d.json")
    qtbot.addWidget(win); win.show()
    assert win.work_area.brand.isHidden() and win.question_zone.hide_link.isHidden()
    assert win.question_zone.text_label.font().family() == "Caveat"
    assert win.hint_zone.cards[0].text_label.font().family() == "Caveat"


# --- Görev 6: düzenle modunda göz düğmeleri + tam panel gizleme ------------------------------------------

def test_question_zone_and_hint_zone_panels_can_be_hidden_and_restored(window):
    window.settings.set_visible("hint_zone", False)
    window.apply_ui_settings()
    assert window.hint_zone.isHidden()
    window.settings.set_visible("hint_zone", True)
    window.apply_ui_settings()
    assert not window.hint_zone.isHidden()

    window.settings.set_visible("question_zone", False)
    window.apply_ui_settings()
    assert window.question_zone.isHidden()
    window.settings.set_visible("question_zone", True)
    window.apply_ui_settings()
    assert not window.question_zone.isHidden()


def test_presenter_visibility_and_name_do_not_stomp_each_other_through_window(window):
    """Eski kod set_presenter_name("") geçerek gizliyordu -- bu ad METNİNİ de kalıcı olarak siliyordu.
    Yeni kodda ad hiç dokunulmadan yalnız görünürlük kapanmalı: apply_ui_settings tekrar çağrıldığında
    (ör. başka bir ayar değişince) ad hâlâ name_label.text()'te durmalı."""
    s, wa = window.settings, window.work_area
    s.presenter_name = "Barış Keser"
    window.apply_ui_settings()
    assert not wa.name_label.isHidden() and wa.name_label.text() == "Barış Keser"

    s.set_visible("presenter", False)
    window.apply_ui_settings()
    assert wa.name_label.isHidden()
    assert wa.name_label.text() == "Barış Keser"             # ESKİ kod burada metni "" yapardı

    s.set_visible("presenter", True)
    window.apply_ui_settings()
    assert not wa.name_label.isHidden() and wa.name_label.text() == "Barış Keser"

    s.presenter_name = ""                                      # açık görünürlük + boş ad -> yine gizli
    window.apply_ui_settings()
    assert wa.name_label.isHidden()


def test_webcam_hidden_stops_camera_thread_and_shown_restarts_it(qtbot, tmp_path, ini_settings, fake_camera):
    """Webcam paneli gizlenince CameraWorker iş parçacığı gerçekten durmalı (görünmeyen bir widget için
    boşa chroma-key yapmasın); gösterilince yeniden başlamalı. Sahte (gerçekten kare üreten) kamera
    kullanılıyor ki iş parçacığının fiilen çalışıp durduğu doğrulanabilsin."""
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), lambda index: fake_camera, tmp_path / "d.json")
    qtbot.addWidget(win)
    qtbot.waitUntil(lambda: win.webcam_panel.has_camera, timeout=2000)   # __init__ zaten start() etti
    assert win.webcam_panel.worker.isRunning()

    win.settings.set_visible("webcam", False)
    win.apply_ui_settings()
    assert win.webcam_panel.isHidden()
    qtbot.waitUntil(lambda: win.webcam_panel.worker.isFinished(), timeout=3000)   # iş parçacığı GERÇEKTEN durdu

    win.settings.set_visible("webcam", True)
    win.apply_ui_settings()
    assert not win.webcam_panel.isHidden()
    qtbot.waitUntil(lambda: win.webcam_panel.worker.isRunning(), timeout=2000)    # yeniden başladı


def test_webcam_start_never_called_without_camera_source_factory(qtbot, tmp_path, ini_settings, monkeypatch):
    """camera_source_factory None ise (main_window.py __init__'teki kalıp) apply_ui_settings de start()'ı
    hiç çağırmamalı -- ne kuruluşta ne de görünürlük ileri geri değiştirilirken."""
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    from matematigin_mantigi.ui.webcam_panel import WebcamPanel
    calls = []
    monkeypatch.setattr(WebcamPanel, "start", lambda self: calls.append(True))
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o"), None, tmp_path / "d.json")
    qtbot.addWidget(win)
    assert win.camera_source_factory is None and calls == []
    win.settings.set_visible("webcam", False); win.apply_ui_settings()
    assert win.webcam_panel.isHidden()                  # görünürlük hâlâ uygulanıyor (start olmasa da)
    win.settings.set_visible("webcam", True); win.apply_ui_settings()
    assert not win.webcam_panel.isHidden()
    assert calls == []                                  # ama start() hiçbir aşamada çağrılmadı (factory yok)


def test_eye_button_click_writes_setting_through_main_window_and_persists_on_restart(qtbot, tmp_path,
                                                                                      ini_settings, dead_camera):
    """Göz düğmesine tıklama WorkArea.visibilityToggled yayar; MainWindow._on_visibility_toggled ayara
    yazar ve apply_ui_settings'i tetikler. Aynı ayar nesnesiyle kurulan İKİNCİ bir pencere (yeniden
    başlatmayı taklit eder) durumu korumalı."""
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o1"), lambda index: dead_camera, tmp_path / "d1.json")
    qtbot.addWidget(win); win.show(); qtbot.waitExposed(win)
    win.work_area.set_edit_mode(True)
    btn = win.work_area._eye_buttons["brand"]
    assert btn.isChecked() and win.settings.visible("brand") is True

    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert not btn.isChecked()
    assert win.settings.visible("brand") is False           # MainWindow üzerinden ayara yazıldı
    assert win.work_area.brand.isHidden()                   # apply_ui_settings gerçek widget'ı da gizledi

    win2 = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                      NullRecorder(), SessionStore(tmp_path / "o2"), lambda index: dead_camera, tmp_path / "d2.json")
    qtbot.addWidget(win2)
    assert win2.settings.visible("brand") is False          # aynı ayar nesnesi: yeniden kurulunca da korunuyor
    assert win2.work_area.brand.isHidden()


def test_webcam_shutdown_uses_short_timeout_on_visibility_path_but_default_on_close(window, monkeypatch):
    """IMPORTANT (review): apply_ui_settings'in görünürlük yolu artık rutin bir düzenleme eylemiyle (göz
    düğmesi) her tetiklenebilir, bu yüzden kısa bir üst sınır (WEBCAM_HIDE_TIMEOUT_MS) geçmeli; closeEvent
    pencere zaten kapanırken çalıştığından hâlâ eski varsayılanı (parametresiz -- 2000ms) kullanmalı.

    Not: sahte kameramız yok (fixture `dead_camera` kullanır, açılışı hep başarısız olur, open_retries=15
    ile 2sn aralıkla yeniden dener) -- shutdown'ı SAF bir sahte ile değiştirmek (çağrıyı kaydedip GERÇEK
    uygulamayı hiç çalıştırmamak) closeEvent'in de artık iş parçacığını asla durdurmaması demek olurdu;
    böyle bir pencere qtbot teardown'ında ~30sn'ye kadar arka planda yeniden denemeye devam eder ve bu,
    aynı süreçte SONRA çalışan başka bir kamera testini tıkayabilir (bunu review sırasında elle doğruladım).
    Bu yüzden sahte, çağrıyı kaydettikten SONRA gerçek shutdown'ı da çağırır -- iş parçacığı hep gerçekten durur."""
    from matematigin_mantigi.ui import main_window as mw
    calls = []
    real_shutdown = window.webcam_panel.shutdown

    def spy_shutdown(*a, **k):
        calls.append(a)
        return real_shutdown(*a, **k)
    monkeypatch.setattr(window.webcam_panel, "shutdown", spy_shutdown)

    window.settings.set_visible("webcam", False)
    window.apply_ui_settings()
    assert calls == [(mw.WEBCAM_HIDE_TIMEOUT_MS,)]

    calls.clear()
    window.close()
    assert calls == [()]                      # closeEvent argümansız çağırır (kendi varsayılanı, 2000ms)


def test_apply_ui_settings_skips_reload_when_font_and_logo_unchanged_but_reloads_on_change(window, monkeypatch,
                                                                                            tmp_path):
    """IMPORTANT (review): apply_ui_settings artık her göz düğmesi tıklamasında da çalışıyor. Yazı tipi
    dosyası (QFontDatabase.addApplicationFont tekilleştirmez, her çağrı kalıcı bir kayıt biriktirir) ve
    logo pixmap'i (QPixmap yükleme + ölçekleme) bu yüzden yalnız GERÇEKTEN değiştiklerinde yeniden
    yüklenmeli -- ayarlar aynı kalırken tekrarlanan apply_ui_settings çağrılarında değil."""
    from matematigin_mantigi.ui import main_window as mw
    font_calls: list = []
    logo_calls: list = []
    monkeypatch.setattr(mw.theme, "load_font_file", lambda p: (font_calls.append(p), "FakeFamily")[1])
    monkeypatch.setattr(window.work_area, "set_logo", lambda *a, **k: logo_calls.append(a))

    font_path = str(tmp_path / "a.ttf")
    logo_path = str(tmp_path / "logo.png")
    window.settings.font_file = font_path
    window.settings.logo_file = logo_path
    window.apply_ui_settings()
    window.apply_ui_settings()
    window.apply_ui_settings()
    assert font_calls == [font_path]                              # üç çağrıya rağmen yalnız bir kez
    assert logo_calls == [(logo_path, window.settings.logo_size)]
    assert window.fam.sans == "FakeFamily"                        # önbellek self.fam'ı hâlâ doğru üretiyor

    window.settings.font_file = str(tmp_path / "b.ttf")           # gerçekten değişti: yeniden yüklenmeli
    window.apply_ui_settings()
    assert font_calls == [font_path, str(tmp_path / "b.ttf")]
    assert len(logo_calls) == 1                                   # logo değişmedi: hâlâ yalnız bir kez


# --- Görev 7: düzenle modunda yazı boyutu kaydırıcısı ---------------------------------------------------

def test_font_scale_grows_board_text_but_not_toolbar_or_dialogs(window):
    """settings.font_scale + apply_ui_settings tahtadaki yazıları (ipucu başlığı, soru metni/seçenekleri,
    work_area'nın kendi etiketleri, webcam overlay'i, kayıt rozeti) büyütmeli -- ama araç çubuğu VE
    diyaloglara giden self.fam ölçeksiz kalmalı (bkz. görev 7 brief'i: 'ölçeklenmeyecek (tahta dışı)')."""
    win = window
    base_title_px = win.hint_zone.title_label.font().pixelSize()
    base_option_px = win.question_zone.option_labels[0].font().pixelSize()
    base_status_px = win.work_area.status_label.font().pixelSize()
    base_overlay_px = win.webcam_panel.overlay_label.font().pixelSize()
    base_toolbar_px = win.toolbar.progress_label.font().pixelSize()

    win.settings.font_scale = 1.5
    win.apply_ui_settings()

    assert win.hint_zone.title_label.font().pixelSize() == round(base_title_px * 1.5)
    assert win.question_zone.text_label.font().pixelSize() == round(30 * 1.5)
    assert win.question_zone.option_labels[0].font().pixelSize() == round(base_option_px * 1.5)
    assert win.work_area.status_label.font().pixelSize() == round(base_status_px * 1.5)
    assert win.webcam_panel.overlay_label.font().pixelSize() == round(base_overlay_px * 1.5)
    assert win.badge.label.font().pixelSize() == round(11 * 1.5)

    assert win.toolbar.progress_label.font().pixelSize() == base_toolbar_px    # araç çubuğu büyümedi
    assert win.fam.scale == 1.0                                               # diyaloglara giden aile ölçeksiz


def test_font_scale_slider_writes_setting_and_persists_on_restart(qtbot, tmp_path, ini_settings, dead_camera):
    """Kaydırıcı fontScaleChanged yayar; MainWindow._on_font_scale_changed ayara yazar (apply_ui_settings
    ile tahtaya uygular). Aynı ayar nesnesiyle kurulan İKİNCİ bir pencere (yeniden başlatmayı taklit eder)
    hem kaydırıcının konumunu hem tahtadaki boyutu korumalı (bkz. eye-button eşdeğeri: Görev 6'nın
    test_eye_button_click_writes_setting_through_main_window_and_persists_on_restart'ı)."""
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    from matematigin_mantigi.ui.theme import FontFamilies
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                     NullRecorder(), SessionStore(tmp_path / "o1"), lambda index: dead_camera, tmp_path / "d1.json")
    qtbot.addWidget(win); win.show(); qtbot.waitExposed(win)

    win.work_area.font_scale_slider.setValue(130)
    assert win.settings.font_scale == 1.3                          # MainWindow üzerinden ayara yazıldı
    assert win.hint_zone.title_label.font().pixelSize() == round(20 * 1.3)

    win2 = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), ini_settings,
                      NullRecorder(), SessionStore(tmp_path / "o2"), lambda index: dead_camera, tmp_path / "d2.json")
    qtbot.addWidget(win2)
    assert win2.settings.font_scale == 1.3
    assert win2.work_area.font_scale_slider.value() == 130          # kaydırıcı da yeniden kurulunca korunuyor
    assert win2.hint_zone.title_label.font().pixelSize() == round(20 * 1.3)


def test_badge_stays_right_anchored_after_font_scale_change_with_real_content(window, monkeypatch):
    """IMPORTANT (review): badge.set_families() (main_window.py) rozeti adjustSize() ile büyütür ama
    KENDİSİ yeniden konumlamaz. Bu bugün doğru sonuç verir ama TESADÜFEN: apply_ui_settings'in rozeti
    büyüttükten SONRA çağırdığı set_aspect_lock/set_frame_visible/set_presenter_name (üçü de koşulsuz,
    üçü de kendi relayout()'unu çalıştırır) rozeti kazara doğru yere taşır. Gerçek garanti artık
    apply_ui_settings'in rozeti work_area.set_families'TEN ÖNCE boyutlaması: set_families kendi
    relayout()'unu HER ZAMAN koşulsuz çağırır, üç "kaza"ya ihtiyaç duymaz.

    Bu üçünü kasıtlı olarak SUSTURUYORUZ (relayout() çağrısını at, durumu yine güncelle) ki test bugünkü
    tesadüfi kurtarıcılara değil, YAPISAL garantiye bağlı kalsın -- ileride biri bu üçüne Görev 6/7'nin
    font_file/logo önbelleği gibi bir "değiştiyse çalış" koruması eklerse (bkz. review'ın bıraktığı not:
    bu üçü rozeti SAVUNAN tesadüfi ağlar), koruma eklenince bu üçü artık relayout() çağırmaz hâle gelir --
    tam olarak bu testin SUSTURDUĞU şey -- ve rozet konumu yine YAPISAL garantiye (set_families sırası)
    bağlı kalmaya devam etmeli. Kırmızı-yeşil doğrulaması (susturma + sıra kasıtlı tersine çevrilerek,
    bkz. task-7-report.md "Fix report") review'ın kendi ölçümüyle birebir örtüşen bir sonuç üretti:
    genişlik 441 -> 693 px, boşluk 12 -> -240 (252 px taşma).

    Rozete GERÇEK İÇERİK vermek şart: boş etiketin adjustSize()'ı ölçekle neredeyse hiç değişmez, sorunu
    gizler."""
    win = window
    win.badge.set_format(1920, 1080, 60)      # gerçek içerik: "KAYIT · 00:00 · 1920×1080 · 60 fps"
    win.work_area.relayout()                  # toggle_recording'in set_format sonrası yaptığı gibi

    # Üç tesadüfi ağı, durumu yine uygulayarak ama relayout()'suz bırak -- yalnız set_families'in KENDİ
    # relayout()'u rozeti kurtarabilsin.
    monkeypatch.setattr(win.work_area, "set_aspect_lock", lambda on: setattr(win.work_area, "aspect_lock", on))
    monkeypatch.setattr(win.work_area, "set_frame_visible", lambda on: setattr(win.work_area, "frame_visible", on))
    monkeypatch.setattr(win.work_area, "set_presenter_name", lambda text: None)

    inner = win.work_area.inner_rect()
    before_w = win.work_area.badge_slot.width()
    assert win.work_area.badge_slot.x() == inner.right() - before_w - 12    # başlangıçta sağa hizalı

    win.settings.font_scale = 1.6
    win.apply_ui_settings()

    after_w = win.work_area.badge_slot.width()
    assert after_w > before_w                                              # rozet gerçekten büyüdü
    assert win.work_area.badge_slot.x() == inner.right() - after_w - 12    # ve hâlâ sağa hizalı (taşmadı)


# --- kayıt sürerken / kaydedilirken pencere kapatma (bağımsız inceleme F2, F7) ------------------------------

STOP_AND_QUIT, KEEP_RECORDING = "Durdur ve çık", "Kayda devam et"


def _answer_close_question(monkeypatch, button: str, on_other=None) -> list:
    """Kapanış sorusunu (QMessageBox.exec) `button` yazılı düğmeyle yanıtlar; sorulan metinleri döndürür. Başlık
    bakılmaz: Qt macOS'ta QMessageBox başlığını yok sayar (setWindowTitle boş kalır), kullanıcı yalnız metni görür.
    O düğmesi olmayan başka bir kutu (kapanış özeti) on_other(kutu) verilmişse ona gider ve Tamam'la kapanır;
    verilmemişse test düşer (StopIteration)."""
    from PyQt6.QtWidgets import QMessageBox
    asked: list = []

    def exec_(box):
        choice = [b for b in box.buttons() if b.text() == button]
        if not choice and on_other is not None:
            on_other(box)
            return QMessageBox.StandardButton.Ok
        asked.append(box.text())
        next(iter(choice)).click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", exec_)
    return asked


def _box_text(box) -> str:
    """Kutunun kullanıcıya gösterdiği metin: ana metin ve (varsa) ayrıntı bölümü."""
    return box.text() + (f"\n\n{box.detailedText()}" if box.detailedText() else "")


def _answer_with_summary(monkeypatch, button: str | None = None) -> tuple[list, list]:
    """Kapanış sorusu `button` (varsayılan 'Durdur ve çık') ile yanıtlanır; kapanış özeti (QMessageBox.exec) ve statik
    pencereler (warning, information) gerçek modal açmadan (başlık, metin + ayrıntı) olarak toplanır.
    (sorulanlar, gösterilenler) döner."""
    shown: list = []
    asked = _answer_close_question(monkeypatch, button or STOP_AND_QUIT,
                                   on_other=lambda box: shown.append((box.windowTitle(), _box_text(box))))
    from PyQt6.QtWidgets import QMessageBox
    for name in ("warning", "information"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: shown.append(a[1:3])))
    return asked, shown


def _spy_shutdown(window, monkeypatch) -> tuple[list, list]:
    """Kamera kapatma (gerçeği de çağrılır) ve ayar yazma çağrıları."""
    shut, synced = [], []
    real_shutdown, real_sync = window.webcam_panel.shutdown, window.settings.sync
    monkeypatch.setattr(window.webcam_panel, "shutdown", lambda *a: (shut.append(a), real_shutdown(*a)))
    monkeypatch.setattr(window.settings, "sync", lambda: (synced.append(1), real_sync()))
    return shut, synced


def _capture_modals(monkeypatch) -> list:
    """Statik QMessageBox.warning/information çağrıları (başlık, metin); gerçek modal açılmaz (offscreen'de donardı).
    Testler başlığa bakmaz: Qt macOS'ta QMessageBox başlığını göstermez, kullanıcıya gereken her şey metinde."""
    from PyQt6.QtWidgets import QMessageBox
    shown: list = []
    for name in ("warning", "information"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: shown.append(a[1:3])))
    return shown


def _wired_notice(window, monkeypatch):
    """Gerçek uyarı kutusu: uygulamadaki gibi pencereye bağlı (app._wire_notice), modül düzeyindeki post()'un hedefi."""
    from matematigin_mantigi import app as app_mod
    from matematigin_mantigi.ui import error_notice
    notice = error_notice.ErrorNotice()
    monkeypatch.setattr(error_notice, "_instance", notice)
    app_mod._wire_notice(notice, window)
    return notice


def _visible_message_boxes() -> list:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()]


def test_closing_while_recording_asks_and_keep_recording_cancels_the_close(window, qtbot, monkeypatch):
    """Kayıt sürerken pencere kapatılınca kayıt sessizce durdurulup (uzun derste dakikalarca donarak) kapanıyordu.
    Şimdi önce sorulur: 'Kayda devam et' kapanmayı iptal eder, kayıt ve pencere sürer."""
    from matematigin_mantigi.core.recorder import RecorderState
    asked = _answer_close_question(monkeypatch, KEEP_RECORDING)
    shut, synced = _spy_shutdown(window, monkeypatch)
    window.toggle_recording(True)
    assert window.close() is False
    assert asked == ["Kayıt sürüyor, durdurulup çıkılsın mı?"]
    assert window.isVisible() and window.recorder.state is RecorderState.RECORDING and window.badge.active
    assert window.toolbar.record_button.isChecked() and shut == [] and synced == []
    window.toggle_recording(False)                                    # (teardown'da soru açılmasın)


def test_closing_while_recording_saves_in_background_then_the_window_closes_itself(window, qtbot, tmp_path,
                                                                                  monkeypatch):
    """'Durdur ve çık': kayıt arka planda kaydedilir (pencere donmaz), kapanma olayı yok sayılır, araç çubuğu
    beklendiğini söyler; tekrar kapatma soru sormadan bekler. Kayıt bitince sonuç (dosyanın yeri) pencere açıkken
    gösterilir, sonra pencere kendisi kapanır; kamera ve ayarlar ancak o zaman kapanır. Eskiden kapanış GUI iş
    parçacığında senkron koşuyordu; sonra da sonuç durum satırına yazılıp pencereyle birlikte kayboluyordu."""
    import pytest
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState, find_ffmpeg
    from matematigin_mantigi.ui.main_window import CLOSING_ALERT
    from tests.test_recorder import FakeAudioCapture, SlowMux, stepping_clock, synthetic_grabber, wait_until
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    shown = []                                                        # (metin, pencere açık mı, kamera kapandı mı)
    asked = _answer_close_question(monkeypatch, STOP_AND_QUIT, on_other=lambda box: shown.append(
        (_box_text(box), window.isVisible(), bool(shut))))
    shut, synced = _spy_shutdown(window, monkeypatch)
    mux = SlowMux(monkeypatch)
    window.settings.audio_device = "Sahte Mikrofon"
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                              out_height=0, audio_device="Sahte Mikrofon",
                                              audio_factory=FakeAudioCapture, clock=stepping_clock())
    tb = window.toolbar
    qtbot.keyClick(window, Qt.Key.Key_R)
    wait_until(lambda: rec.frames_written >= 10)
    try:
        assert window.close() is False                                # kapanma olayı yok sayıldı
        assert asked == ["Kayıt sürüyor, durdurulup çıkılsın mı?"]
        assert mux.entered.wait(20)                                   # kayıt arka planda birleştiriliyor
        assert window.isVisible() and rec.state is RecorderState.FINALIZING
        assert tb.alert_label.isVisible() and tb.alert_label.text() == CLOSING_ALERT
        assert not tb.record_button.isEnabled() and shut == [] and synced == []
        assert window.close() is False and len(asked) == 1           # tekrar kapatma: soru yok, yine bekler
        qtbot.keyClick(window, Qt.Key.Key_R)                          # R yeni kayıt başlatmaz, bilgi korunur
        assert rec.state is RecorderState.FINALIZING and tb.alert_label.text() == CLOSING_ALERT
    finally:
        mux.release()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=20000)   # kayıt bitti: pencere kendisi kapandı
    assert shut == [()] and synced == [1] and rec.error is None, rec.error
    path = rec.last_path
    assert len(shown) == 1 and shown[0][0].startswith(f"Kayıt kaydedildi: {path}"), shown
    assert shown[0][1:] == (True, False), shown                       # sonuç pencere ve kamera kapanmadan önce
    assert path.exists() and not list(path.parent.glob("*.video.mp4")) and not list(path.parent.glob("*.wav"))


def test_closing_while_saving_waits_without_asking_and_closes_when_saved(window, qtbot, tmp_path, monkeypatch):
    """Kayıt zaten kaydedilirken (durdurma işçisi çalışıyor) kapatma soru sormaz: kapanma olayı yok sayılır, kayıt
    bitince sonuç gösterilir ve pencere kendisi kapanır. Eskiden 60 sn bekleyip çalışan _StopWorker'ı yok ediyordu
    ('QThread: Destroyed while thread is still running', süreç -6 ile düşüyor, ara dosyalar kalıyordu)."""
    import pytest
    from matematigin_mantigi.core.recorder import MssFfmpegRecorder, find_ffmpeg
    from matematigin_mantigi.ui.main_window import CLOSING_ALERT
    from tests.test_recorder import FakeAudioCapture, SlowMux, stepping_clock, synthetic_grabber, wait_until
    if find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    asked, shown = _answer_with_summary(monkeypatch)
    shut, synced = _spy_shutdown(window, monkeypatch)
    mux = SlowMux(monkeypatch)
    window.settings.audio_device = "Sahte Mikrofon"
    rec = window.recorder = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber,
                                              out_height=0, audio_device="Sahte Mikrofon",
                                              audio_factory=FakeAudioCapture, clock=stepping_clock())
    qtbot.keyClick(window, Qt.Key.Key_R)
    wait_until(lambda: rec.frames_written >= 10)
    qtbot.keyClick(window, Qt.Key.Key_R)                              # durdur: kapanış arka planda
    try:
        assert mux.entered.wait(20)
        assert window.close() is False and asked == []                # soru yok, kapanma bekliyor
        assert window.isVisible() and window.toolbar.alert_label.text() == CLOSING_ALERT and shut == []
    finally:
        mux.release()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=20000)
    assert shut == [()] and synced == [1] and rec.last_path.exists()
    assert len(shown) == 1 and shown[0][1].startswith(f"Kayıt kaydedildi: {rec.last_path}"), shown


def test_close_error_is_reported_and_camera_and_settings_still_shut_down(window, qtbot, monkeypatch):
    """Kapanışta kaydı durdurmak patlarsa kamera kapatma ve ayar yazma atlanıyordu: kamera iş parçacığı çalışırken
    süreç bitiyor ('QThread: Destroyed…', -6), hata kullanıcıya söylenmiyordu. Şimdi hata pencerede ve günlükte;
    kamera ve ayarlar her koşulda kapanır, pencere kapanır."""
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi.core.recorder import NullRecorder
    from tests.test_recorder import capture_logged

    class BrokenStop(NullRecorder):                                   # anında durur (stop_is_quick), ama patlar
        def stop(self):
            super().stop()
            raise OSError(13, "Permission denied", "kayit.mp4")
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1:3])))
    asked = _answer_close_question(monkeypatch, STOP_AND_QUIT)
    logged = capture_logged(monkeypatch)
    shut, synced = _spy_shutdown(window, monkeypatch)
    window.recorder = BrokenStop()
    window.toggle_recording(True)
    window.close()
    assert len(asked) == 1 and not window.isVisible()
    assert shut == [()] and synced == [1]
    assert [text for _title, text in shown] == [
        "Kayıt kapatılamadı: PermissionError: [Errno 13] Permission denied: 'kayit.mp4'"], shown
    assert [(type(e), where) for e, where in logged] == [(PermissionError, "pencere kapanışı")]


def test_window_closed_while_the_result_is_shown_does_not_close_a_second_time(window, qtbot, monkeypatch):
    """Kayıt bitince pencere kendisi kapanacakken sonuç penceresi (Kayıt hatası) açıkken pencere başka yoldan
    kapanırsa (QApplication.quit, close()) kapanış bir kez olur: kamera kapatma ve ayar yazma bir kez koşar.
    (_on_record_stopped sonradan yine close() çağırır; Qt kabul edilen kapanışta platform penceresini yok ettiği
    için o çağrı olay göndermez. Bu kilit, kapanış akışı değişirse ikinci kapanışı yakalar.)"""
    from matematigin_mantigi.core.recorder import NullRecorder

    class FailingBackgroundStop(NullRecorder):                        # kapanış _StopWorker'da, hatayla biter
        stop_is_quick = False
        error = "ffmpeg hata kodu 1: disk dolu"
    shown = []

    def summary(box):
        shown.append(box.text())
        window.close()                                                # sonuç penceresi açıkken çıkış
    _answer_close_question(monkeypatch, STOP_AND_QUIT, on_other=summary)
    shut, synced = _spy_shutdown(window, monkeypatch)
    window.recorder = FailingBackgroundStop()
    window.toggle_recording(True)
    assert window.close() is False                                    # kayıt arka planda kaydediliyor
    qtbot.waitUntil(lambda: bool(shown) and window._stop_worker is None, timeout=10000)
    qtbot.wait(50)
    assert len(shown) == 1 and "ffmpeg hata kodu 1: disk dolu" in shown[0] and not window.isVisible(), shown
    assert shut == [()] and synced == [1], (shut, synced)


def test_finished_stop_workers_do_not_pile_up_on_the_window(window, qtbot):
    """Her durdurma pencereye bir _StopWorker (QThread) çocuğu ekliyor, hiçbiri silinmiyordu. İş parçacığı bittikten
    sonra nesne de silinir (deleteLater)."""
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.ui.main_window import _StopWorker

    class BackgroundStop(NullRecorder):                               # kapanış _StopWorker'da koşar
        stop_is_quick = False
    window.recorder = BackgroundStop()
    tb = window.toolbar
    for _ in range(3):
        qtbot.keyClick(window, Qt.Key.Key_R)
        qtbot.keyClick(window, Qt.Key.Key_R)
        qtbot.waitUntil(lambda: tb.record_button.isEnabled(), timeout=10000)
    qtbot.waitUntil(lambda: not window.findChildren(_StopWorker), timeout=5000)


@pytest.mark.parametrize("outcome", ["kaydedildi", "hata"])
def test_stop_and_quit_shows_the_result_and_the_waiting_notices_in_one_window_then_closes(window, qtbot,
                                                                                          monkeypatch, outcome):
    """P1: 'Durdur ve çık'tan sonra kayıt başarıyla biterse pencere kapanıyor, mikrofon uyarısı ve kayıt sırasında
    biriken uyarılar ('Tahta görüntüsü kaydedilemedi') hiç görünmüyordu; hatayla biterse uyarı kutusu 'Kayıt hatası'
    penceresinin çocuğu olup onunla siliniyor, gizlenen ana pencerenin altında yeniden açılıyordu. Şimdi pencere
    kapanmadan önce TEK pencerede: kaydın sonucu (dosya ya da hata), ses uyarısı ve bütün bekleyen uyarılar. Sonra
    pencere kapanır; arkada kutu, şerit, yoklama kalmaz."""
    from pathlib import Path
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.ui import error_notice

    class BackgroundStop(NullRecorder):               # kapanış _StopWorker'da; sonuç alanları bu testin kendi metni
        stop_is_quick = False
        error = audio_error = None

        def stop(self):
            super().stop()
            if outcome == "hata":
                self.error = "yapay kapanış hatası, ham dosyalar silinmedi"
            self.audio_error = "Mikrofon kayıt sırasında kesildi (yapay)"
            return Path("oturum") / "kayit_yapay.mp4"
    notice = _wired_notice(window, monkeypatch)
    asked, shown = _answer_with_summary(monkeypatch)
    window.recorder = BackgroundStop()
    window.toggle_recording(True)
    error_notice.post("Tahta görüntüsü kaydedilemedi", "S1 sorusunun tahta resmi kaydedilemedi: diskte yer kalmadı.",
                      key="tahta-goruntusu")
    qtbot.waitUntil(lambda: "Tahta görüntüsü" in window.toolbar.alert_label.text(), timeout=2000)
    assert window.close() is False and len(asked) == 1                # kayıt arka planda kaydediliyor
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=10000)
    assert len(shown) == 1, shown                                     # tek özet penceresi
    text = shown[0][1]
    assert "S1 sorusunun tahta resmi kaydedilemedi" in text and "Mikrofon kayıt sırasında kesildi (yapay)" in text, text
    if outcome == "hata":
        assert "yapay kapanış hatası, ham dosyalar silinmedi" in text, text
    else:
        assert str(Path("oturum") / "kayit_yapay.mp4") in text, text
    qtbot.wait(3 * error_notice.POLL_MS)                              # kapanıştan sonra hiçbir yoldan kutu açılmaz
    assert _visible_message_boxes() == [] and not notice._poll_timer.isActive() and not notice._pending


def test_dialogs_do_not_open_while_the_window_waits_to_close(window, qtbot, tmp_path, monkeypatch):
    """U3: 'Durdur ve çık'tan sonra kayıt kaydedilirken açılan soru editörü (Ayarlar, kalem ayarları da) pencere
    kendisi kapanınca exec döngüsüyle birlikte bitiyordu: editörde yazılmış ama kaydedilmemiş sorular sorulmadan
    kayboluyordu (inceleme v30 editor). Kapanış beklenirken bu pencereler açılmaz; tıklanan düğmenin yanında kısa
    neden görünür (araç çubuğunun şeridinde zaten 'bitince pencere kapanacak' yazıyor)."""
    import threading
    from pathlib import Path
    from PyQt6.QtWidgets import QToolTip
    from matematigin_mantigi.core.question_loader import write_questions
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.ui import pen_settings as ps
    from matematigin_mantigi.ui import settings_dialog as sd
    from matematigin_mantigi.ui.main_window import CLOSING_ALERT
    from matematigin_mantigi.ui.question_editor import QuestionEditorDialog
    release = threading.Event()

    class HeldStop(NullRecorder):                     # kapanış _StopWorker'da; test bırakana dek sürer
        stop_is_quick = False

        def stop(self):
            super().stop()
            release.wait(20)
            return Path("oturum") / "kayit.mp4"
    opened, tips = [], []
    for cls in (QuestionEditorDialog, sd.SettingsDialog, ps.PenSettingsDialog):
        monkeypatch.setattr(cls, "exec", lambda self, name=cls.__name__: opened.append(name) or 0)
    # İpucu çağrısı kaydedilir: görünürlüğü platforma bağlı (macOS'ta solarak açılır, isVisible() hemen True olmaz).
    monkeypatch.setattr(QToolTip, "showText", staticmethod(lambda pos, text, w=None, *a: tips.append((text, w))))
    asked, shown = _answer_with_summary(monkeypatch)
    window.questions_path = write_questions(tmp_path / "sorular.xlsx", list(SAMPLE_QUESTIONS))
    window.toolbar.editor_button.setEnabled(True)     # fikstür penceresi soru dosyasız kuruldu (düğme kapalıydı)
    window.recorder = HeldStop()
    window.toggle_recording(True)
    tb = window.toolbar
    try:
        assert window.close() is False and tb.alert_label.text() == CLOSING_ALERT and len(asked) == 1
        for open_dialog, button in ((window.open_editor, tb.editor_button), (window.open_settings, tb.settings_button),
                                    (window.open_pen_settings, tb.pen_settings_button)):
            tips.clear()
            open_dialog()
            assert opened == [] and len(tips) == 1 and tips[0][1] is button, tips
            assert "bitince pencere kapanacak" in tips[0][0], tips
        qtbot.mouseClick(tb.editor_button, Qt.MouseButton.LeftButton)          # düğmeden de aynı yol
        assert opened == [] and window.isVisible() and len(tips) == 2
    finally:
        release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=10000)
    assert opened == [] and len(shown) == 1 and "kayit.mp4" in shown[0][1], shown


def test_window_stays_open_if_a_dialog_is_still_open_when_the_recording_is_saved(window, qtbot, monkeypatch):
    """U3: kapanış anında (kayıt kaydedildi, pencere kendisi kapanacak) başka bir modal pencere açıksa (ör. 'Durdur ve
    çık'tan önce açılmış soru editörü) pencere kapanmaz: kapansaydı süreç biter, o pencerenin exec döngüsü de biter,
    içindeki kaydedilmemiş iş sorulmadan kaybolurdu. Özet bunu ve açık pencerenin adını söyler; kamera ve ayarlar
    kapanmaz. O pencere kapatılınca uygulama yeniden kapatılabilir."""
    from PyQt6.QtWidgets import QApplication, QDialog
    from matematigin_mantigi.core.recorder import NullRecorder

    class BackgroundStop(NullRecorder):               # kapanış _StopWorker'da
        stop_is_quick = False
    asked, shown = _answer_with_summary(monkeypatch)
    shut, synced = _spy_shutdown(window, monkeypatch)
    window.recorder = BackgroundStop()
    window.toggle_recording(True)
    dlg = QDialog(window)
    dlg.setWindowTitle("Soru editörü")
    dlg.setModal(True)
    dlg.show()
    qtbot.waitUntil(lambda: QApplication.activeModalWidget() is dlg, timeout=2000)
    assert window.close() is False and len(asked) == 1                # 'Durdur ve çık': kayıt arka planda
    qtbot.waitUntil(lambda: window._stop_worker is None, timeout=10000)
    qtbot.wait(50)
    assert window.isVisible() and shut == [] and synced == [], (shut, synced)
    assert len(shown) == 1 and "Pencere kapanmadı" in shown[0][1] and "Soru editörü" in shown[0][1], shown
    assert not window.toolbar.alert_label.isVisible() and window.toolbar.record_button.isEnabled()
    dlg.close()
    assert window.close() is True and not window.isVisible() and shut == [()] and synced == [1]


CLOSE_CHILD = r'''
import os, subprocess, sys, threading, time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QSettings, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox
from matematigin_mantigi.core import crash_log
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, PenSettings
from matematigin_mantigi.core.recorder import MssFfmpegRecorder, NullRecorder
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.main_window import MainWindow
from matematigin_mantigi.ui.theme import FontFamilies
from tests.test_recorder import FakeAudioCapture, stepping_clock, synthetic_grabber

tmp, scenario = Path(sys.argv[1]), sys.argv[2]
watchdog = threading.Timer(60, lambda: (print("ZAMAN_ASIMI", flush=True), os._exit(3)))
watchdog.daemon = True                                # temiz çıkış onu beklemesin
watchdog.start()


def out(*a):
    print(*a, flush=True)


class Camera:                                         # sürekli kare veren kamera: kapanışta iş parçacığı çalışıyor
    def open(self): return True
    def read(self):
        time.sleep(0.02)
        return np.full((240, 320, 3), 90, np.uint8)
    def release(self): pass


class BrokenStop(NullRecorder):
    def stop(self):
        super().stop()
        raise OSError(13, "Permission denied", "kayit.mp4")


def answer(box):                                      # kapanış sorusu: "Durdur ve çık"; kapanış özeti: Tamam
    stop = [b for b in box.buttons() if b.text() == "Durdur ve çık"]
    if not stop:
        kind = "BILGI" if box.icon() == QMessageBox.Icon.Information else "UYARI"
        out(kind, (box.text() + " " + box.detailedText()).strip().replace("\n", " "))
        return QMessageBox.StandardButton.Ok
    out("SORU", box.text())
    stop[0].click()
    return 0


gate_in, gate_go = threading.Event(), threading.Event()
real_run = subprocess.run


def gated_run(args, *a, **k):                         # ses birleştirme, senaryo bırakana dek bekler
    if "-shortest" in args:
        gate_in.set()
        gate_go.wait(20)
    return real_run(args, *a, **k)


def poll(cond, then):
    QTimer.singleShot(20, lambda: then() if cond() else poll(cond, then))


def main() -> int:
    crash = crash_log.install(tmp / "hatalar.log")    # gerçek uygulamadaki gibi: yuvadaki hata süreci düşürmez
    app = QApplication(sys.argv[:1])
    QMessageBox.exec = answer
    QMessageBox.warning = staticmethod(lambda *a, **k: out("UYARI", str(a[2]).replace("\n", " ")))
    QMessageBox.information = staticmethod(lambda *a, **k: out("BILGI", str(a[2]).replace("\n", " ")))
    subprocess.run = gated_run
    settings = AppSettings(QSettings(str(tmp / "ayarlar.ini"), QSettings.Format.IniFormat))
    settings.set_pen(PenSettings(reading_ms=0))
    settings.audio_device = "Sahte"
    if scenario == "kapanis-hatasi":
        rec = BrokenStop()
    else:
        rec = MssFfmpegRecorder(lambda: tmp / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                                audio_device="Sahte", audio_factory=FakeAudioCapture, clock=stepping_clock())
    win = MainWindow(FontFamilies("Arial", "Arial", False), list(SAMPLE_QUESTIONS), settings, rec,
                     SessionStore(tmp / "oturum"), lambda index: Camera(), tmp / "duzen.json")
    win.resize(1280, 720)
    win.show()

    def quit_():                                      # ⌘Q (macOS uygulama menüsü) ve QApplication.quit aynı yol
        out("KAMERA", win.webcam_panel.worker.isRunning())
        QApplication.quit()
        if scenario != "kapanis-hatasi":
            poll(gate_in.is_set, saving)

    def saving():
        def report():
            out("KAYDEDILIRKEN", win.isVisible(), rec.state.value, win.toolbar.alert_label.text())
            gate_go.set()
        QTimer.singleShot(300, report)

    def recorded():
        if scenario == "kaydedilirken":
            win.toggle_recording(False)               # durdur: kapanış arka planda
        quit_()

    def start():
        win.toggle_recording(True)
        if scenario == "kapanis-hatasi":
            poll(lambda: win.webcam_panel.worker.isRunning(), quit_)
        else:
            poll(lambda: rec.frames_written >= 10 and win.webcam_panel.worker.isRunning(), recorded)

    QTimer.singleShot(0, start)
    code = app.exec()
    out("EXEC", code, win.isVisible(), win.webcam_panel.worker.isRunning())
    crash_log.uninstall(crash)
    return code


sys.exit(main())                                       # pencere main() yerelinde: dönünce bırakılır (app.main gibi)
'''


@pytest.mark.parametrize("scenario", ["kayit-surerken", "kaydedilirken", "kapanis-hatasi"])
def test_quitting_while_recording_or_saving_exits_cleanly(tmp_path, scenario):
    """Gerçek olay döngüsü, ayrı süreçte (Qt'nin 'QThread: Destroyed…' ile süreci düşürmesi süreç içinde görünmez).
    QApplication.quit (macOS'ta ⌘Q bu yoldan pencerelere kapanma olayı gönderir) kayıt sürerken ya da kaydedilirken:
    pencere kayıt bitene dek açık kalır, sonra kendisi kapanır; çıkış kodu 0, ara dosyalar birleşip silinmiş.
    Kapanışta kayıt durdurma patlasa da kamera iş parçacığı durur, hata söylenir ve günlüğe yazılır, süreç düşmez."""
    import os
    import subprocess
    import sys
    from pathlib import Path
    from matematigin_mantigi.core.recorder import find_ffmpeg
    if scenario != "kapanis-hatasi" and find_ffmpeg() is None:
        pytest.skip("ffmpeg yok")
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(tmp_path / "cfg"),
               PYTHONPATH=os.pathsep.join(p for p in (str(root), os.environ.get("PYTHONPATH", "")) if p))
    p = subprocess.run([sys.executable, "-c", CLOSE_CHILD, str(tmp_path), scenario], cwd=root, env=env,
                       capture_output=True, text=True, timeout=120)
    lines = p.stdout.splitlines()
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr[-2000:])
    assert "QThread: Destroyed" not in p.stderr and "ZAMAN_ASIMI" not in p.stdout, (p.stdout, p.stderr[-2000:])
    assert "KAMERA True" in lines and "EXEC 0 False False" in lines, lines      # kamera çalışıyordu; durdu
    asked = [line for line in lines if line.startswith("SORU")]
    assert asked == ([] if scenario == "kaydedilirken" else ["SORU Kayıt sürüyor, durdurulup çıkılsın mı?"]), lines
    if scenario == "kapanis-hatasi":
        assert [line for line in lines if line.startswith("UYARI")] == [
            "UYARI Kayıt kapatılamadı: PermissionError: [Errno 13] Permission denied: 'kayit.mp4'"]
        assert "pencere kapanışı" in (tmp_path / "hatalar.log").read_text(encoding="utf-8")
        return
    assert "KAYDEDILIRKEN True finalizing Kayıt kaydediliyor… bitince pencere kapanacak" in lines, lines
    assert not [line for line in lines if line.startswith("UYARI")], lines
    saved = [line for line in lines if line.startswith("BILGI")]          # sonuç, pencere kapanmadan önce gösterildi
    assert len(saved) == 1 and saved[0].startswith(f"BILGI Kayıt kaydedildi: {tmp_path / 'rec'}"), lines
    names = sorted(p.name for p in (tmp_path / "rec").iterdir())
    assert len(names) == 2 and names[0].endswith(".log") and names[1].endswith(".mp4"), names   # birleşti, silindi
