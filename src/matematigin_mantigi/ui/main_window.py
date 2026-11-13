"""Ana pencere: beyaz tahta + bölgeleri kurar ve sinyalleri bağlar. İş mantığı core/ içindedir."""
from __future__ import annotations

from dataclasses import replace
from math import ceil
from time import monotonic
import numpy as np
from pathlib import Path
from typing import Callable, Sequence

from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QToolTip, QWidget

from matematigin_mantigi import paths
from matematigin_mantigi.core import crash_log
from matematigin_mantigi.core.autostart import Autostart, AutostartError
from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import (SHAPE_META, TOOL_META, PenSettings, Question, QuestionStatus, Tool,
                                             next_shape)
from matematigin_mantigi.core.question_flow import QuestionFlow
from matematigin_mantigi.core.recorder import (DISK_HINT, Recorder, RecorderError, RecorderState, MicrophoneStartError, MssFfmpegRecorder, exception_text,
                                               record_rect_for)
from matematigin_mantigi.core.camera_recorder import CameraRecorder
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings, SessionState
from matematigin_mantigi.ui.camera_worker import FrameSource
from matematigin_mantigi.ui.cursors import cursor_for
from matematigin_mantigi.ui.hint_zone import HintZone
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
from matematigin_mantigi.ui.question_editor import QuestionEditorDialog
from matematigin_mantigi.ui.question_zone import QuestionZone
from matematigin_mantigi.ui.record_badge import RecordBadge
from matematigin_mantigi.ui.settings_dialog import SettingsDialog, SettingsValues
from matematigin_mantigi.ui import error_notice, theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.webcam_panel import WebcamPanel, CameraView
from matematigin_mantigi.ui.dual_screen import layout_supported, resolve_screen_key, screen_key
from matematigin_mantigi.ui.work_area import WorkArea


class _StopWorker(QThread):
    """recorder.stop() birkaç saniye sürebilir (ffmpeg kapanışı + ses birleştirme); arayüzü dondurmasın."""
    done = pyqtSignal(object)

    def __init__(self, recorder, parent=None, *, camera=None):
        super().__init__(parent)
        self.recorder = recorder
        self.camera = camera
        self.exc: str | None = None

    def run(self) -> None:
        path = None
        try:
            path = self.recorder.stop()
        except Exception as err:  # noqa: BLE001 - sonuç pencereye 'Kayıt hatası' olarak gider
            self.exc = str(err) or repr(err)         # mesajsız istisna (OSError()) da sessiz kalmasın
            crash_log.log_handled(err, "kayıt kapanışı")
        if self.camera is not None:
            try:
                self.camera.screen_started = getattr(self.recorder, "video_t0", None)
                self.camera.finish(getattr(self.recorder, "audio_result", None))
            except Exception as err:  # noqa: BLE001 - ana kaydın sonucu mutlaka teslim edilir
                self.camera._warn(f"Kamera kaydı tamamlanamadı: {err}")
        self.done.emit(path)


WEBCAM_HIDE_TIMEOUT_MS = 400   # apply_ui_settings'in "webcam" görünürlüğü kapatma yolu: closeEvent'in
                               # varsayılanından (2000ms) çok daha kısa -- bkz. apply_ui_settings ve
                               # WebcamPanel.shutdown docstring'i.
SAVING_KEY = "kayit-kaydediliyor"        # araç çubuğu uyarı şeridinde bu kaynağın anahtarı
SAVING_ALERT = "Kayıt kaydediliyor…"   # kapanış (ffmpeg + ses birleştirme) sürerken araç çubuğundaki uyarı
CLOSING_ALERT = "Kayıt kaydediliyor… bitince pencere kapanacak"     # pencere kapatılmak istendi, kayıt bekleniyor
# Kapanış beklenirken editör/ayarlar düğmesine basılınca düğmenin yanında görünen kısa neden.
CLOSING_NO_DIALOG = "Kayıt kaydediliyor; bitince pencere kapanacak. Bu pencere şimdi açılmaz."
STOP_AND_QUIT, KEEP_RECORDING = "Durdur ve çık", "Kayda devam et"   # kayıt sürerken kapatma sorusunun düğmeleri
# Kayıt pencerelerinin metni kendi başına anlaşılır olmalı: Qt macOS'ta QMessageBox başlığını göstermez.
START_FAILED = "Kayıt başlamadı."
RECORD_FAILED = "Kayıt düzgün tamamlanamadı."
# Kapanış özetinin ayrıntı düğmesi: Qt'nin kendi etiketi çevirisiz İngilizce ('Show Details...').
DETAILS_SHOW, DETAILS_HIDE = "Ayrıntılar", "Ayrıntıları gizle"


def _sound_text(audio_err: str) -> str:
    return f"Kaydın sesinde sorun var: {audio_err}"


def _video_text(video_warn: str) -> str:
    """Kaydedicinin görüntü uyarısı (video_warning: kodlayıcı kayda yetişemedi) kendi önekiyle: ses uyarısı değil."""
    return f"Kaydın görüntüsünde sorun var: {video_warn}"


def _record_error_text(err: str, audio_err: str | None, video_warn: str | None = None) -> str:
    """Kayıt hatası penceresinin metni: kaydedicinin hatası ve (atılmadan) ses ve görüntü uyarıları."""
    text = f"{RECORD_FAILED}\n{err}"
    if audio_err and audio_err not in err:
        text += f"\n\n{_sound_text(audio_err)}"
    if video_warn and video_warn not in err:
        text += f"\n\n{_video_text(video_warn)}"
    return text


def _turkish_details_button(box: QMessageBox) -> None:
    """setDetailedText'in eklediği düğmeye Türkçe etiket. Qt etiketi her tıklamada kendisi değiştirir; bu bağlantı
    Qt'ninkinden sonra kurulduğu için ondan sonra çalışır. Genişlik Qt'nin İngilizce etiketlerinden hesaplanıyor: Türkçe
    etiket kesilmesin."""
    for button in box.buttons():
        if box.buttonRole(button) != QMessageBox.ButtonRole.ActionRole:
            continue
        shown = [False]                         # ayrıntı başta kapalı

        def relabel(_checked=False, button=button, shown=shown):
            shown[0] = not shown[0]
            button.setText(DETAILS_HIDE if shown[0] else DETAILS_SHOW)
        button.setText(DETAILS_SHOW)
        button.clicked.connect(relabel)
        button.setMinimumWidth(max(button.sizeHint().width(),
                                   button.fontMetrics().horizontalAdvance(DETAILS_HIDE) + 32))


STARTUP_SCREEN_WAIT_MS = 10000     # --baslangic: ekran sürücüleri geç hazır olabilir; kayıtlı ekran bu süre aranır
STARTUP_SCREEN_POLL_MS = 500
SESSION_NOTICE_MS = 10000          # oturum geri yükleme uyarısı araç çubuğunda bu kadar kalır (sahneye girmez)
SESSION_NOTICE_KEY = "oturum"
BOARD_RESTORE_MAX_ASPECT_DIFF = 0.12    # kayıtlı tahta görüntüsü ile pencere oranı bundan fazla ayrışırsa yüklenmez
BOARD_RESTORE_MAX_BYTES = 64 * 1024 * 1024


def ink_from_snapshot(image: QImage, size: QSize, dpr: float = 1.0) -> QImage:
    """Beyaz zeminli tahta PNG'sinden şeffaf mürekkep katmanı (ARGB32 premultiplied) üretir: 'renkten alfaya'.
    Alfa = 255 - min(R,G,B); premultiplied renk = kanal + alfa - 255. Beyaz üstüne tek kat mürekkep için kayıpsızdır
    (kalem, silgi sonrası beyaz, tebeşir kenarları); yarı saydam üst üste katmanlar tek kata iner."""
    rgb = image.convertToFormat(QImage.Format.Format_RGB32).scaled(
        size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    w, h = rgb.width(), rgb.height()
    raw = np.frombuffer(rgb.constBits().asstring(rgb.sizeInBytes()), np.uint8)
    pixels = raw.reshape(h, rgb.bytesPerLine())[:, :w * 4].reshape(h, w, 4).astype(np.int16)   # B G R x
    alpha = 255 - pixels[:, :, :3].min(axis=2)
    out = np.empty((h, w, 4), np.uint8)
    out[:, :, :3] = np.clip(pixels[:, :, :3] + alpha[:, :, None] - 255, 0, 255)
    out[:, :, 3] = alpha
    result = QImage(out.tobytes(), w, h, w * 4, QImage.Format.Format_ARGB32_Premultiplied).copy()
    result.setDevicePixelRatio(dpr)
    return result


class _Preview(CameraView):
    SMOOTH_SCALING = False             # büyük yardımcı görüntüde ucuz yakın komşu ölçekleme
    MAX_PAINT_FPS = 30
    closed = pyqtSignal()
    fullscreenKey = pyqtSignal()        # F11 / Esc ana pencereye iletilir: önizleme etkinken ana pencerenin
    escapeKey = pyqtSignal()            # WindowShortcut'ları çalışmaz, tam ekrandan çıkış kilitlenirdi

    def __init__(self, parent=None):
        super().__init__(parent)
        QShortcut(QKeySequence("F11"), self, activated=self.fullscreenKey.emit)
        QShortcut(QKeySequence("Escape"), self, activated=self.escapeKey.emit)
        self.close_button = QPushButton("Kapat", self)
        self.close_button.setObjectName("preview_close")
        self.close_button.clicked.connect(self.close)
        self.close_button.adjustSize()
        # Yalnız yeni kare gelince çiz; bekleyen tek istek daima en yeni kareyi kullanır.
        # Her kareye sabit 33 ms eklemek 30 fps kaynağı 15 fps'ye böler: önceki
        # istekten kalan süreyi bekleyerek yaklaşık 30 Hz tavanını koru.
        self._last_paint_request = 0.0
        self._paint_timer = QTimer(self)
        self._paint_timer.setSingleShot(True)
        self._paint_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._paint_timer.timeout.connect(self._paint_latest_frame)

    def _request_frame_update(self) -> None:
        if not self._paint_timer.isActive():
            remaining = 1 / self.MAX_PAINT_FPS - (monotonic() - self._last_paint_request)
            self._paint_timer.start(max(0, ceil(remaining * 1000)))

    def _paint_latest_frame(self) -> None:
        self._last_paint_request = monotonic()
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._paint_timer.stop()
        super().set_placeholder(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.close_button.move(max(0, self.width() - self.close_button.width() - 8), 8)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, fam: FontFamilies, questions: Sequence[Question], settings: AppSettings,
                 recorder: Recorder, session_store: SessionStore,
                 camera_source_factory: Callable[[int], FrameSource] | None, layout_path: Path, parent=None,
                 *, questions_path: "Path | None" = None, questions_from_file: bool = True,
                 session_state: "SessionState | None" = None, startup: bool = False,
                 autostart: "Autostart | None" = None):
        """camera_source_factory: kamera indeksinden kaynak üretir; None ise kamera açılmaz.
        questions_path: soru dosyası (xlsx); verilmezse soru editörü açılmaz.
        questions_from_file: sorular o dosyadan mı okundu. False: açılışta okunamadı, tahtada örnek sorular var; editör
        onları dosyanın (ya da yedeğinin) gerçek sorularının üzerine yazmaz (Q1).
        session_state: önceki oturumun kapanışta kaydedilen durumu (son soru, tahta görüntüsü); None ise geri
        yüklenmez. startup: bilgisayar açılışında başlatıldı (--baslangic): kayıtlı ekran geç hazır olabilir, bir
        süre aranır. Hiçbir durumda kayıt kendiliğinden başlamaz."""
        super().__init__(parent)
        self.autostart = autostart or Autostart()
        self._session_ready = False                     # kurulum bitene dek oturum durumu yazılmaz (eskiyi ezmesin)
        # Soru/pencere olayları ayarları güncellemeden önce açılıştaki tercihi al. İlk açılışta tahta ekranı
        # seçimi eskisi gibi tam ekran açılır; kayıtlı pencere modu yalnız geri yüklemede korunur.
        self._initial_fullscreen = settings.session_state.fullscreen if settings.has_session_state else True
        self._pending_board: tuple[str, str] | None = None
        self._startup_screen_wait_left = STARTUP_SCREEN_WAIT_MS if startup else 0
        self._startup_screen_timer = QTimer(self)
        self._startup_screen_timer.setSingleShot(True)
        self._startup_screen_timer.setInterval(STARTUP_SCREEN_POLL_MS)
        self._startup_screen_timer.timeout.connect(self._restore_screen_preferences)
        self._board_restore_scheduled = False
        self._preview = None
        self._preview_board = None
        self._preview_screen = None
        self._screen_preferences_restored = False
        self.camera_source_factory = camera_source_factory
        self._camera_recorder: CameraRecorder | None = None
        self._camera_warning: str | None = None
        self._camera_timer = QTimer(self)
        self._camera_timer.setInterval(200)
        self._camera_timer.timeout.connect(self._check_camera_recording)
        self._stop_worker: _StopWorker | None = None    # kayıt kapanışı arka planda sürüyor (sonucu henüz gelmedi)
        self._record_rect = None
        self._record_starting = False
        self._geometry_interrupted = False
        self._reporting_record_result = False
        self._close_after_save = False                  # pencere kapatılmak istendi: kayıt bitince kapanacak
        self.base_fam = fam                       # paketle gelen aile; Ayarlar'daki dosya bunun üstüne biner
        self.fam, self.settings, self.recorder, self.session_store = fam, settings, recorder, session_store
        # apply_ui_settings artık her göz düğmesi tıklamasında da çalıştığı için (Görev 6) burada
        # önbelleğe alınmış son uygulanan yazı tipi dosyası/logo -- QFontDatabase.addApplicationFont ve
        # logo pixmap'ini yeniden yüklemek yalnız gerçekten DEĞİŞTİKLERİNDE yapılır (bkz. apply_ui_settings).
        self._applied_font_file: str | None = None
        self._applied_font_family: str | None = None
        self._applied_logo: tuple[str, int] | None = None
        self.layout_path = Path(layout_path)
        self.questions_path = Path(questions_path) if questions_path else None
        self.questions_from_file = questions_from_file
        self.setWindowTitle("Matematiğin Mantığı")

        central = QWidget(); row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
        self.toolbar = ToolBar(fam)
        self.work_area = WorkArea(fam)
        self.work_area.installEventFilter(self)
        self._geometry_timer = QTimer(self)
        self._geometry_timer.setInterval(200)
        self._geometry_timer.timeout.connect(self._check_record_geometry)
        app = QApplication.instance()
        app.screenAdded.connect(self._screen_topology_changed)
        app.screenRemoved.connect(self._screen_topology_changed)
        self.canvas = self.work_area.board
        self.canvas.set_pen_settings(settings.pen())
        self.question_zone = QuestionZone(fam)
        self.hint_zone = HintZone(fam)
        # Yeşil perde ayarı Ayarlar penceresinden; varsayılan kaldırılmış.
        cam_index = settings.camera_index
        factory = (lambda: camera_source_factory(cam_index)) if camera_source_factory else (lambda: _NoCamera())
        self.webcam_panel = WebcamPanel(fam, factory, settings.chroma, chroma_enabled=settings.chroma_enabled,
                                        open_retries=15 if camera_source_factory is not None else 0)
        for key, zone in (("soru", self.question_zone), ("ipucu", self.hint_zone), ("webcam", self.webcam_panel)):
            self.work_area.add_zone(key, zone)
        self.work_area.set_layout(lm.load_layout(self.layout_path))
        self.badge = RecordBadge(fam, self.work_area)
        self.work_area.badge_slot = self.badge
        row.addWidget(self.toolbar); row.addWidget(self.work_area, 1)
        self.setCentralWidget(central)

        self.flow = QuestionFlow(questions, self)
        self._last_snapshot = None
        self._autosave_failed = False
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30000)
        self._autosave_timer.timeout.connect(self._autosave_board)
        self._autosave_timer.start()
        self._wire()
        self._shortcuts()
        self._restore_settings()
        self.apply_ui_settings()
        self.toolbar.editor_button.setEnabled(self.questions_path is not None)
        self._wire_session()
        if session_state is not None:
            self._restore_session_question(session_state)
        if questions:
            self._on_question_changed(self.flow.index)
        self._session_ready = True
        # Webcam'in başlatılması artık apply_ui_settings()'in (yukarıda, _restore_settings'ten hemen sonra
        # çağrıldı) "webcam" görünürlük anahtarına bağlı işi -- burada koşulsuz tekrar başlatmak, kapalı
        # kaydedilmiş bir webcam'i yeniden başlatıp Görev 6'nın önlemeye çalıştığı boşa CPU'yu geri getirirdi.

    # --- wiring -------------------------------------------------------------------
    def _wire(self) -> None:
        tb, c, flow = self.toolbar, self.canvas, self.flow
        tb.toolSelected.connect(self._on_tool)
        tb.colorSelected.connect(self._on_color)
        tb.widthSelected.connect(self._on_width)
        tb.undoRequested.connect(c.undo)
        tb.clearRequested.connect(c.clear)
        tb.workToggled.connect(flow.toggle_work)
        tb.prevRequested.connect(flow.prev_question)
        tb.nextRequested.connect(flow.next_question)
        tb.recordToggled.connect(self.toggle_recording)
        tb.penSettingsRequested.connect(self.open_pen_settings)
        tb.settingsRequested.connect(self.open_settings)
        tb.fullscreenRequested.connect(self._toggle_fullscreen)
        tb.editorRequested.connect(self.open_editor)
        tb.layoutEditToggled.connect(self.work_area.set_edit_mode)
        self.work_area.editModeChanged.connect(tb.set_layout_edit)
        self.work_area.layoutChanged.connect(self._save_layout)
        self.work_area.visibilityToggled.connect(self._on_visibility_toggled)
        self.work_area.fontScaleChanged.connect(self._on_font_scale_changed)
        self.badge.ticked.connect(tb.set_recording_time)     # süre araç çubuğunda sayar (kayda girmez)
        self.badge.ticked.connect(self._check_recorder)

        c.historyChanged.connect(lambda can_undo, _e: tb.set_undo_enabled(can_undo))
        c.pressureChanged.connect(lambda p: self._status(f"XP-Pen · {p:.2f}"))
        c.inputSourceChanged.connect(lambda src: self._status("XP-Pen" if src == "tablet" else "fare"))

        flow.before_question_change = self._on_question_leaving
        flow.questionChanged.connect(self._on_question_changed)
        flow.statusChanged.connect(self._on_status_changed)
        flow.progressChanged.connect(lambda _d, _t: self._refresh_progress())
        flow.questionVisibilityChanged.connect(self.question_zone.set_shown)
        flow.hintChanged.connect(lambda i, _n: self.hint_zone.set_focus(i))
        flow.hintRevealChanged.connect(
            lambda q, h, on: self.hint_zone.set_revealed(h, on) if q == flow.index else None)

        qz, hz = self.question_zone, self.hint_zone
        qz.showRequested.connect(flow.show_question)
        qz.hideRequested.connect(flow.hide_question)
        hz.prevRequested.connect(flow.hint_prev)
        hz.nextRequested.connect(flow.hint_next)
        hz.revealToggled.connect(flow.toggle_reveal)
        hz.maskModeChanged.connect(self._on_mask_mode)

    def _typing(self) -> bool:
        """Yazı aracının kutusu açıkken tek tuşlu kısayollar kutuya bırakılır."""
        return self.canvas.text_edit.isVisible()

    def _shortcuts(self) -> None:
        def sc(keys: str, fn, while_typing: bool = False) -> None:
            def run():
                if self._typing() and not while_typing:
                    return
                fn()
            QShortcut(QKeySequence(keys), self, activated=run)
        for i, tool in enumerate(Tool, start=1):
            sc(str(i), lambda t=tool: (self._on_tool(t), self.toolbar.set_tool(t)))
        sc("Ctrl+Z", self.canvas.undo)
        sc("Ctrl+Shift+X", self.canvas.clear)
        sc("N", self.flow.next_question)
        sc("P", self.flow.prev_question)
        sc("Space", self.flow.toggle_work)
        sc("R", lambda: self.toggle_recording(self.recorder.state is not RecorderState.RECORDING))
        sc("H", lambda: self.flow.show_question() if not self.flow.is_question_shown() else self.flow.hide_question())
        sc("Left", self.flow.hint_prev)
        sc("Right", self.flow.hint_next)
        sc("Return", self._return_key, while_typing=True)
        sc("L", lambda: self.work_area.set_edit_mode(not self.work_area.edit_mode))
        sc("F11", self._toggle_fullscreen)
        sc("Escape", self._escape, while_typing=True)

    def _return_key(self) -> None:
        if self._typing():
            self.canvas.commit_text()         # yazı kutusu açıkken Enter yazıyı işler
        else:
            self.flow.toggle_reveal()

    def _toggle_fullscreen(self) -> None:
        if self.recorder.state is RecorderState.RECORDING:
            self.toolbar.set_alert("window-lock", "Kayıt sürerken pencere değiştirilemez")
            return
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _escape(self) -> None:
        if self._typing():
            self.canvas.cancel_text()
        elif self.work_area.edit_mode:
            self.work_area.set_edit_mode(False)
        elif self.isFullScreen():
            if self.recorder.state is RecorderState.RECORDING:
                self.toolbar.set_alert("window-lock", "Kayıt sürerken pencere değiştirilemez")
            else:
                self.showNormal()

    def _restore_settings(self) -> None:
        s = self.settings
        self.canvas.set_tool(s.tool); self.canvas.set_color(QColor(s.color)); self.canvas.set_base_width(s.width)
        self.toolbar.set_tool(s.tool); self.toolbar.set_color(s.color); self.toolbar.set_width(s.width)
        self.hint_zone.set_mask_mode(s.hint_mask)
        self.question_zone.set_reading_ms(s.pen().reading_ms)
        self.work_area.set_click_mode(s.tool == Tool.CLICK)
        self.refresh_cursor()
        self._status("XP-Pen")

    # --- handlers -----------------------------------------------------------------
    def _on_tool(self, t: Tool) -> None:
        if t == Tool.SHAPE and self.canvas.tool == Tool.SHAPE:      # Şekil'e tekrar basış: sıradaki şekil
            self.canvas.set_shape(next_shape(self.canvas.shape))
        self.canvas.set_tool(t); self.settings.tool = t
        self.toolbar.set_shape_glyph(SHAPE_META[self.canvas.shape][1])
        self.work_area.set_click_mode(t == Tool.CLICK)
        self.refresh_cursor(); self._status("XP-Pen")

    def _on_color(self, hx: str) -> None:
        self.canvas.set_color(QColor(hx)); self.settings.color = hx
        if self.canvas.tool != Tool.PEN:              # renk seçimi kalemi seçer
            self._on_tool(Tool.PEN); self.toolbar.set_tool(Tool.PEN)
        self.refresh_cursor()

    def _on_width(self, w: int) -> None:
        self.canvas.set_base_width(w); self.settings.width = w
        self.refresh_cursor(); self._status("XP-Pen")

    def refresh_cursor(self) -> None:
        self.work_area.set_tool_cursor(cursor_for(self.canvas.tool, self.canvas.color, self.canvas.base_width,
                                                  self.canvas.devicePixelRatioF()))

    def _status(self, pressure_text: str) -> None:
        tool = TOOL_META[self.canvas.tool][0]
        if self.canvas.tool == Tool.SHAPE:
            tool = f"Şekil ({SHAPE_META[self.canvas.shape][0]})"
        self.work_area.set_status(f"Araç: {tool} · Kalınlık: {self.canvas.base_width} px · Basınç: {pressure_text}")

    def _save_board(self, i: int, *, automatic: bool = False) -> bool:
        if self.canvas.has_snapshot_content():
            qid = self.flow.questions[i].id
            try:
                image = self.canvas.snapshot_image()
                if self._last_snapshot is not None and self._last_snapshot[0] == qid and self._last_snapshot[1] == image:
                    try:
                        valid = self._snapshot_matches(self._last_snapshot[2], image)
                    except OSError:
                        valid = False
                    if valid:
                        self._autosave_failed = False
                        return True
                path = self.session_store.save_snapshot(qid, image)
                if not self._snapshot_matches(path, image):
                    raise OSError(f"Kaydedilen PNG doğrulanamadı: {path}")
                self._last_snapshot = (qid, image, path)
                self._autosave_failed = False
                self._remember_session(board_image=str(path), board_question_id=qid)
            except Exception as err:  # Görüntü oluşturma da kayıt gibi başarısız olabilir.
                # Kayıt sürerken uyarı sahne dışında kalır; çağıran tahtayı korur.
                detail = error_notice.describe_os_error(err) if isinstance(err, OSError) else str(err)
                if not automatic or not self._autosave_failed:
                    error_notice.post("Tahta görüntüsü kaydedilemedi",
                                  f"{qid} sorusunun tahta resmi kaydedilemedi: {detail}."
                                  f"\nKlasör: {self.session_store.session_dir}\nDers ve süren kayıt devam ediyor.",
                                  key="tahta-goruntusu", repeat=True)
                self._autosave_failed = True
                return False
        return True

    @staticmethod
    def _snapshot_matches(path: Path, image: QImage) -> bool:
        saved = QImage.fromData(path.read_bytes(), "PNG")
        if saved.isNull():
            return False
        fmt = QImage.Format.Format_ARGB32
        return saved.convertToFormat(fmt) == image.convertToFormat(fmt)

    def _autosave_board(self) -> None:
        if self.settings.pen().autosave and self.flow.questions:
            self._save_board(self.flow.index, automatic=True)

    def _on_question_leaving(self, i: int) -> bool:
        if not self._save_board(i):
            return False
        self.canvas.reset_board()
        self._last_snapshot = None
        return True

    def _save_layout(self, layout) -> None:
        """Düzen değişince duzen.json'a yazar; yazılamazsa uygulama düşmez, uyarı verilir."""
        try:
            lm.save_layout(self.layout_path, layout)
        except OSError as err:
            error_notice.post("Düzen kaydedilemedi",
                              f"{self.layout_path.name} yazılamadı: {error_notice.describe_os_error(err)}.\n"
                              "Bölgelerin yeni yeri bu oturumda geçerli; uygulama yeniden açılınca eski düzen gelir.",
                              key="duzen")

    def _on_question_changed(self, i: int) -> None:
        if not self.flow.questions:
            return
        q = self.flow.questions[i]
        self._remember_question()
        self.question_zone.set_question(q, i + 1, animate=True)
        self.hint_zone.set_hints(q.id, q.hints)
        for h in range(len(q.hints)):
            self.hint_zone.set_revealed(h, self.flow.is_revealed(h))
        self._refresh_progress()

    def _on_status_changed(self, i: int, s: QuestionStatus) -> None:
        self._refresh_progress()

    def _refresh_progress(self) -> None:
        self.toolbar.set_progress(self.flow.progress_label())
        self.toolbar.set_work_label(self.flow.work_label())

    def _on_mask_mode(self, m) -> None:
        self.settings.hint_mask = m

    def _on_visibility_toggled(self, key: str, on: bool) -> None:
        """Düzen modundaki göz düğmesine tıklandığında (work_area.visibilityToggled): ayara yaz, sonra
        tüm görünürlükleri tek eşleme noktasından (apply_ui_settings) yeniden uygula."""
        self.settings.set_visible(key, on)
        self.apply_ui_settings()

    def _on_font_scale_changed(self, v: float) -> None:
        """Düzen çubuğundaki yazı boyutu kaydırıcısı (work_area.fontScaleChanged): ayara yaz, sonra
        tahtayı tek eşleme noktasından (apply_ui_settings) yeniden uygula -- _on_visibility_toggled
        ile aynı kalıp (Görev 7)."""
        self.settings.font_scale = v
        self.apply_ui_settings()

    def eventFilter(self, watched, event):
        if watched is getattr(self, "work_area", None) and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            self._observe_record_geometry()
            QTimer.singleShot(0, self._check_record_geometry)
        return super().eventFilter(watched, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._observe_record_geometry()
        QTimer.singleShot(0, self._check_record_geometry)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._observe_record_geometry()
        QTimer.singleShot(0, self._check_record_geometry)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.toolbar.set_fullscreen(self.isFullScreen())
            self._remember_window()
            self._observe_record_geometry()
            QTimer.singleShot(0, self._check_record_geometry)

    def _observe_record_geometry(self):
        if getattr(self, "_preview", None) is not None and not self._preview_valid():
            self._disable_preview("Ekran veya pencere konumu değişti; önizleme kapatıldı.", interrupt=True)
        # Yalnız tespit: Qt geometri olayının içinde modal pencere açmak yeniden girişe yol açar.
        if (getattr(self, "_record_rect", None) is not None
                and (self._record_starting or self.recorder.state is RecorderState.RECORDING)
                and not self._record_saving()
                and (self.isMinimized() or record_rect_for(self.work_area.recording_rect()) != self._record_rect)):
            self._geometry_interrupted = True
            self.toolbar.set_alert("geometry", "Çekim alanı değişti; kayıt durduruluyor")

    def _screen_topology_changed(self, *_args):
        if self._preview is not None:
            self._disable_preview("Ekran düzeni değişti; kamera önizlemesi kapatıldı.", interrupt=True)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._screen_preferences_restored:
            self._screen_preferences_restored = True
            QTimer.singleShot(0, self._restore_screen_preferences)
            if self._pending_board is not None and not self._board_restore_scheduled:
                self._board_restore_scheduled = True
                QTimer.singleShot(0, self._restore_board_image)

    def _restore_screen_preferences(self):
        screens = QApplication.screens()
        board_key, preview_key = self.settings.board_screen_key, self.settings.preview_screen_key
        board = resolve_screen_key(screens, board_key)
        target = resolve_screen_key(screens, preview_key)
        if ((board_key and board is None) or (preview_key and target is None)) and self._startup_screen_wait_left > 0 \
                and self.recorder.state is RecorderState.IDLE and not self._record_saving():
            # Bilgisayar açılışı: ekran/tablet sürücüleri geç hazır olabilir. UI'yı bloklamadan kısa aralıklarla
            # yeniden dene; süre dolunca mevcut ekranda kal (aşağıdaki yol).
            self._startup_screen_wait_left -= STARTUP_SCREEN_POLL_MS
            self._startup_screen_timer.start()
            return
        self._startup_screen_wait_left = 0
        if board_key and board is None:
            target = None
        self._configure_screens(board, target, restoring=True)

    def _preview_closed(self):
        self.settings.preview_screen_key = None
        self._disable_preview("Kamera önizlemesi kapatıldı.", interrupt=True)

    def _disable_preview(self, message="", *, interrupt=False):
        preview, self._preview = self._preview, None
        self._preview_board = self._preview_screen = None
        if preview is not None:
            try:
                self.webcam_panel.frameReady.disconnect(preview.set_frame)
                self.webcam_panel.placeholderChanged.disconnect(preview.set_placeholder)
            except (TypeError, RuntimeError):
                pass
            preview.hide()
            preview.deleteLater()
            if not self.settings.visible("webcam"):
                self.webcam_panel.shutdown(WEBCAM_HIDE_TIMEOUT_MS)
        if message:
            self.toolbar.set_alert("preview", message)
        if interrupt and (self._record_starting or self.recorder.state is RecorderState.RECORDING):
            self._geometry_interrupted = True
            self.toolbar.set_alert("geometry", "Ekran düzeni değişti; kayıt durduruluyor")
            QTimer.singleShot(0, self._check_record_geometry)
        if self.recorder.state is not RecorderState.RECORDING and not self._record_starting:
            self._geometry_timer.stop()

    def _preview_valid(self):
        if self._preview is None:
            return True
        try:
            screens = QApplication.screens()
            board, target = self._preview_board, self._preview_screen
            area = QRect(self.work_area.mapToGlobal(QPoint(0, 0)), self.work_area.size())
            return (layout_supported(screens, board, target)
                    and self.screen() is board and board.geometry().contains(area)
                    and target.geometry().contains(self._preview.frameGeometry())
                    and not self._preview.frameGeometry().intersects(area)
                    and not self.isMinimized() and self._preview.isVisible())
        except RuntimeError:
            return False

    def _configure_screens(self, board, target, *, restoring=False):
        if self.recorder.state is RecorderState.RECORDING or self._record_saving():
            self.toolbar.set_alert("preview", "Kayıt sırasında ekran seçimi değiştirilemez.")
            return
        self._disable_preview()
        screens = QApplication.screens()
        if board is not None:
            if board not in screens:
                self.toolbar.set_alert("preview", "Seçilen tahta ekranı bulunamadı.")
                return
            if self.windowHandle():
                self.windowHandle().setScreen(board)
            if not restoring or self._initial_fullscreen:
                self.move(board.availableGeometry().topLeft())
                self.showFullScreen()
            else:
                self.showNormal()
                avail = board.availableGeometry()
                if not avail.contains(self.frameGeometry()):
                    # Başka/kayıp ekrandaki veya taşan pencereyi ortala; çerçeveye de yer bırak.
                    # Hedef ekrana zaten sığan kayıtlı geometriyi değiştirme.
                    rect = QRect(0, 0, min(self.width(), avail.width() * 9 // 10),
                                 min(self.height(), avail.height() * 9 // 10))
                    rect.moveCenter(avail.center())
                    self.setGeometry(rect)
        board = board or self.screen()
        if target is None:
            self.toolbar.set_alert("preview", None)
            return
        if not layout_supported(screens, board, target):
            self.toolbar.set_alert("preview", "Önizleme açılamadı: ekranlar ayrı ve aynı ölçekte olmalı; karma DPI desteklenmez.")
            return
        preview = _Preview(None)
        preview.setWindowTitle("Kamera önizleme")
        preview.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        preview.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._preview, self._preview_board, self._preview_screen = preview, board, target
        preview.closed.connect(self._preview_closed)
        preview.fullscreenKey.connect(self._toggle_fullscreen)
        preview.escapeKey.connect(self._escape)
        self.webcam_panel.frameReady.connect(preview.set_frame)
        self.webcam_panel.placeholderChanged.connect(preview.set_placeholder)
        if self.webcam_panel.view._frame is not None:
            preview.set_frame(self.webcam_panel.view._frame)
        else:
            preview.set_placeholder(self.webcam_panel.view.placeholder_text)
        g = target.availableGeometry()
        preview.setGeometry(g.x() + g.width() // 4, g.y() + g.height() // 4, g.width() // 2, g.height() // 2)
        preview.show()
        if not self._preview_valid():
            self._disable_preview("Önizleme konumu doğrulanamadı; kapatıldı.")
            return
        if self.camera_source_factory is not None:
            self.webcam_panel.start()
        self.toolbar.set_alert("preview", "Kamera önizlemesi açık. Kaydı kontrol edin; kayıt dışı kalacağı garanti edilmez.")
        self._geometry_timer.start()

    def _check_record_geometry(self):
        if self._preview is not None and not self._preview_valid():
            self._disable_preview("Ekran veya önizleme konumu değişti; önizleme kapatıldı.", interrupt=True)
        self._observe_record_geometry()
        if (self._geometry_interrupted and not self._record_starting
                and self.recorder.state is RecorderState.RECORDING
                and not self._record_saving()):
            self.toggle_recording(False)

    def _record_saving(self) -> bool:
        """Önceki kayıt hâlâ kaydediliyor (kaydedici FINALIZING) ya da durdurma sonucu pencereye henüz ulaşmadı
        (_StopWorker'ın done'ı _on_record_stopped'ta işlenmedi). Bu sürede ne yeni kayıt ne ikinci durdurma."""
        return self.recorder.state is RecorderState.FINALIZING or self._stop_worker is not None

    def _show_saving_alert(self) -> None:
        """Araç çubuğunda 'Kayıt kaydediliyor…' (durum satırına değil: o tahtada, kayda girer); pencere kapatılmak
        istendiyse bitince kapanacağını da söyler."""
        self.toolbar.set_alert(SAVING_KEY, CLOSING_ALERT if self._close_after_save else SAVING_ALERT)

    # Kapanış kabul edildi (pencere kapanıyor; kamera ve ayarlar kapandı): app.main süreci bitirir.
    closed = pyqtSignal()
    # Kayıt başlamak üzere: kaydedici ilk kareyi start() içinde, hemen yakalar. app.py uyarı kutusunu gizler.
    recordingAboutToStart = pyqtSignal()

    def _prepare_first_frame(self) -> None:
        """Kayıt başlamadan hemen önce kayda girmemesi gerekenler ekrandan kalkar (P3, P4). Sahnedeki durum satırı
        önceki kaydın sonucunu (dosyanın tam yolu, yani kullanıcı adı) taşıyabilir: olağan metnine döner ve HEMEN
        çizilir (yalnız setText eski yazıyı ilk karede bırakırdı; kısalan yazının eski yeri de çizilir). Açık uyarı
        kutusu recordingAboutToStart ile gizlenir (eskiden rozetin ilk tikinde, start() döndükten sonra)."""
        status = self.work_area.status_label
        before = status.geometry()
        self._status("XP-Pen")
        self.work_area.repaint(before.united(status.geometry()))
        self.recordingAboutToStart.emit()

    def _validate_record_start(self) -> None:
        """Modal döngüleri ve ilk kare hazırlığı sırasında alan değişmiş olabilir."""
        self._observe_record_geometry()
        if (self._geometry_interrupted or self.isMinimized() or not self.isVisible()
                or (self._preview is not None and not self._preview_valid())):
            raise RecorderError("Pencere veya çekim alanı değişti; kayıt başlatılmadı.")

    def _settle_record_confirmation(self) -> None:
        # Modal kapandıktan sonra ekranın yeniden çizilmesini işle; bu turda gelen
        # geometri/kapanış olayları kaydedici ilk kareyi almadan denetlenir.
        from PyQt6.QtCore import QEventLoop
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self._validate_record_start()

    def toggle_recording(self, on: bool) -> None:
        if self._record_starting:
            return
        if self._record_saving():               # düğme kilitli; R de kapanan kaydın yollarına karışmasın (#2)
            self._show_saving_alert()
            return
        fps = self.settings.record_fps
        state = self.recorder.state
        if on and state is RecorderState.IDLE:
            silent_reason = None
            if isinstance(self.recorder, MssFfmpegRecorder) and not self.settings.audio_device:
                silent_reason = "Mikrofon seçilmedi."
            if self.settings.audio_device:
                from matematigin_mantigi.core.audio_capture import resolve_input_device
                if resolve_input_device(self.settings.audio_device) is None:
                    silent_reason = "Seçilen mikrofon bulunamadı veya kimliği belirsiz."
            if self._preview is not None and not self._preview_valid():
                self._disable_preview("Önizleme konumu doğrulanamadı; kayıt başlamadı.")
                self._record_start_failed(RecorderError("Ekran düzeni doğrulanamadı."))
                return
            if self.isMinimized():
                self._record_start_failed(RecorderError("Pencere simge durumundayken kayıt başlatılamaz."))
                return
            rect = record_rect_for(self.work_area.recording_rect())
            self._record_rect = rect
            self._geometry_interrupted = False
            self._record_starting = True
            try:
                def confirm_silent(reason):
                    return QMessageBox.question(self, "Mikrofon", f"{reason}\nSes olmadan kayıt başlatılsın mı?",
                                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

                if silent_reason and not confirm_silent(silent_reason):
                    self._record_rect = None
                    self._geometry_interrupted = False
                    self.toolbar.set_alert("geometry", None)
                    self.toolbar.set_recording(False)
                    return
                if silent_reason:
                    self._settle_record_confirmation()
                self._validate_record_start()
                self._prepare_first_frame()
                self._validate_record_start()
                self.toolbar.set_alert("geometry", None)
                if silent_reason:
                    device = self.recorder.audio_device
                    try:
                        self.recorder.audio_device = None
                        self.recorder.start(rect, fps=fps)
                    finally:
                        self.recorder.audio_device = device
                else:
                    try:
                        if isinstance(self.recorder, MssFfmpegRecorder):
                            self.recorder.start(rect, fps=fps, require_audio=True)
                        else:
                            self.recorder.start(rect, fps=fps)
                    except MicrophoneStartError as err:
                        if not confirm_silent(str(err)):
                            self._record_rect = None
                            self._geometry_interrupted = False
                            self.toolbar.set_alert("geometry", None)
                            self.toolbar.set_recording(False)
                            return
                        self._settle_record_confirmation()
                        self._prepare_first_frame()
                        self._validate_record_start()
                        self.toolbar.set_alert("geometry", None)
                        device = self.recorder.audio_device
                        try:
                            self.recorder.audio_device = None
                            self.recorder.start(rect, fps=fps)
                        finally:
                            self.recorder.audio_device = device
            except Exception as err:  # noqa: BLE001 - hiçbir başlatma hatası yuvadan kaçıp düğmeyi 'kayıtta' bırakmasın
                self._record_rect = None
                self._geometry_interrupted = False
                self.toolbar.set_alert("geometry", None)
                self._record_start_failed(err)
                return
            finally:
                self._record_starting = False
            self._start_camera_recording()
            self._geometry_timer.start()
            h = self.settings.record_height or rect.height
            self.badge.set_format(round(rect.width * h / rect.height), h, fps)
            self.badge.start()
            self.work_area.relayout()
            QTimer.singleShot(0, self._check_record_geometry)
        elif not on and state is RecorderState.RECORDING:
            self.badge.stop()
            self.work_area.relayout()
            if getattr(self.recorder, "stop_is_quick", False):
                self._on_record_stopped(self.recorder.stop())
            else:
                self._start_stop_worker()
                return
        recording = self.recorder.state is RecorderState.RECORDING
        self.toolbar.set_recording(recording)
        if recording:
            self.toolbar.set_recording_time(self.badge.seconds)

    def _start_camera_recording(self) -> None:
        self._camera_recorder = None
        self._camera_warning = None
        self.toolbar.set_alert("camera-file", None)
        panel = self.webcam_panel
        if not (self.settings.record_camera and self.settings.visible("webcam")
                and panel.has_camera and panel.worker.isRunning()):
            return
        path = getattr(self.recorder, "last_path", None)
        started = getattr(self.recorder, "video_t0", None)
        if path is None:
            self._camera_warning = "Ayrı kamera kaydı başlamadı: ekran kaydının yolu yok."
            self.toolbar.set_alert("camera-file", "Kamera dosyası başlamadı; ana kayıt sürüyor")
            return
        try:
            self._camera_recorder = CameraRecorder(path, started)
            panel.worker.raw_recorder = self._camera_recorder
            self._camera_timer.start()
        except Exception as err:  # noqa: BLE001
            self._camera_warning = f"Ayrı kamera kaydı başlamadı: {err}"
            crash_log.log_handled(err, "ayrı kamera kaydı başlatma")
            self.toolbar.set_alert("camera-file", "Kamera dosyası başlamadı; ana kayıt sürüyor")

    def _check_camera_recording(self) -> None:
        camera = self._camera_recorder
        if camera is not None:
            camera.check_stall()
        if camera is not None and camera.warning:
            self._camera_warning = camera.warning
            self.toolbar.set_alert("camera-file", "Kamera dosyasında sorun var; ana kayıt sürüyor")

    def _start_stop_worker(self) -> None:
        """Kapanışı (recorder.stop: ffmpeg + ses birleştirme) arka planda başlatır; sonuç _on_record_stopped'a gelir.
        O ana dek düğme ve R kilitli. Kaydedici zaten kapanıyorsa (FINALIZING) işçinin stop()'u bitişi bekler."""
        self.toolbar.set_recording(False)
        self.toolbar.record_button.setEnabled(False)
        self._show_saving_alert()
        if self._camera_recorder is not None:
            self.webcam_panel.worker.raw_recorder = None
            self._camera_recorder.request_stop()
        self._stop_worker = _StopWorker(self.recorder, self, camera=self._camera_recorder)
        self._stop_worker.done.connect(self._on_record_stopped)
        self._stop_worker.start()

    def _record_start_failed(self, err: Exception) -> None:
        """Kayıt başlamadı: araç çubuğu 'kayıt yok'a döner, sebep pencerede (her denemede), ayrıntı hatalar.log'da.
        OSError (disk, izin) ve beklenmeyen hata da buraya gelir: yuvadan kaçıp düğmeyi 'kayıtta' bırakmasın. Metin
        başlıksız da anlaşılır: Qt macOS'ta QMessageBox başlığını göstermez ('Beklenmeyen hata: …' tek başına
        neyin olmadığını söylemiyordu)."""
        self.toolbar.set_recording(False)
        crash_log.log_handled(err, "kayıt başlatma")
        if isinstance(err, RecorderError):
            reason = str(err)
        elif isinstance(err, OSError):
            reason = f"Kayıt dosyası yazılamadı: {err}\n{DISK_HINT}"
        else:
            reason = f"Beklenmeyen hata: {exception_text(err)}"
        QMessageBox.warning(self, "Kayıt başlatılamadı", f"{START_FAILED}\n{reason}")

    def _on_record_stopped(self, path) -> None:
        worker, exc = self._stop_worker, None
        if worker is not None:
            worker.wait()                    # done run()'ın son adımı: iş parçacığı bitsin, öyle bırakılsın
            exc = worker.exc
            worker.deleteLater()             # bitmiş iş parçacığı nesnesi pencerede birikmesin
        self._camera_timer.stop()
        self._check_camera_recording()
        self.toolbar.set_alert("camera-file", None)
        self._stop_worker = None             # kapanış bitti: düğme ve R yeniden kayıt başlatabilir
        self.toolbar.set_alert(SAVING_KEY, None)
        self.toolbar.record_button.setEnabled(True)
        self.toolbar.set_recording(False)
        self._record_rect = None
        if self._preview is None:
            self._geometry_timer.stop()
        self.toolbar.set_alert("window-lock", None)
        self.toolbar.set_alert("geometry", None)
        self.work_area.set_aspect_lock(self.settings.aspect_lock)
        interrupted, self._geometry_interrupted = self._geometry_interrupted, False
        closing, self._close_after_save = self._close_after_save, False
        # Başka bir modal pencere açıksa (ör. 'Durdur ve çık'tan önce açılmış soru editörü) pencere kapanmaz: kapanınca
        # süreç biter, o pencerenin exec döngüsü de biter, içindeki kaydedilmemiş iş sorulmadan kaybolurdu (U3).
        blocker = self._open_dialog_title() if closing else None
        self._reporting_record_result = True
        try:
            if interrupted:
                QMessageBox.warning(self, "Kayıt durduruldu", "Çekim alanı değiştiği için kayıt durduruldu. Değişiklik ile durdurma arasında yanlış alan kaydedilmiş olabilir; kayıt sonucunu kontrol edin.")
            if closing:
                self._show_closing_summary(path, exc, blocker)
            else:
                self._report_record_result(path, exc)
        finally:
            self._reporting_record_result = False
            if closing and blocker is None:  # pencere kapatılmak istenmişti: kayıt bitti, sonuç ve uyarılar gösterildi
                self.close()

    def _open_dialog_title(self) -> str | None:
        """Açık bir modal pencere varsa başlığı (başlıksızsa boş metin); yoksa None."""
        dialog = QApplication.activeModalWidget()
        return None if dialog is None else dialog.windowTitle()

    def _refuse_while_closing(self, button: QWidget) -> bool:
        """Pencere kayıt kaydedilince kendisi kapanacak ('Durdur ve çık'): soru editörü, Ayarlar ve kalem ayarları
        açılmaz. Açılsaydı pencere kapanınca exec döngüsüyle birlikte biter, içindeki kaydedilmemiş iş (editörde
        yazılan sorular) sorulmadan kaybolurdu (U3). Neden tıklanan düğmenin yanında kısa ipucuyla söylenir (şeritte
        zaten 'bitince pencere kapanacak' yazıyor); modal kutu açılmaz."""
        if not self._close_after_save:
            return False
        try:
            QToolTip.showText(button.mapToGlobal(button.rect().center()), CLOSING_NO_DIALOG, button, button.rect(),
                              4000)
        except Exception:  # noqa: BLE001 - ipucu gösterilemezse de pencere açılmaz
            pass
        return True

    def _record_problems(self, exc: str | None) -> tuple[str | None, str | None, str | None]:
        """(hata, ses uyarısı, görüntü uyarısı). Önce kaydedicinin anlamlı hatası (sebep, dosyaların yeri); işçinin ham
        istisna metni yalnız yedek. Görüntü uyarısı (kodlayıcı kayda yetişemedi) kaydedicinin ayrı alanında
        (video_warning): eskiden audio_error'daydı ve 'Kaydın sesinde sorun var' diye gösteriliyordu (U7). Alanı
        olmayan kaydedicide None."""
        video_warn = getattr(self.recorder, "video_warning", None)
        if self._camera_warning:
            video_warn = "\n".join(filter(None, (video_warn, "Ayrı kamera kaydı: " + self._camera_warning)))
        return (getattr(self.recorder, "error", None) or exc, getattr(self.recorder, "audio_error", None), video_warn)

    def _record_details(self) -> list[str]:
        cap = getattr(self.recorder, "capture_fps", 0.0)
        parts = [f"yakalama ~{cap:.0f} kare/sn"] if cap else []
        off = getattr(self.recorder, "av_offset_ms", None)
        if off is not None:
            parts.append(f"ses hizası {off:+.0f} ms telafi edildi")
        res = getattr(self.recorder, "audio_result", None)
        if res is not None and (res.overflows or res.dropped_blocks):
            parts.append(f"ses taşması {res.overflows + res.dropped_blocks}")
        return parts

    def _show_closing_summary(self, path, exc: str | None, blocked_by: str | None = None) -> None:
        """'Durdur ve çık': pencere kendisi kapanmadan önce TEK pencerede kaydın sonucu (dosya ya da hata, ses uyarısı)
        ve görülmemiş bütün uyarılar (kayıt sırasında biriken, Tamam'a basılmamış); o an kayıt yok. Eskiden başarıda
        sonuç durum satırına yazılıp pencere hemen kapanıyor, uyarılar hiç görünmüyordu; hatada uyarı kutusu 'Kayıt
        hatası'nın çocuğu olup onunla siliniyor, gizlenen pencerenin altında yeniden açılıp Qt'nin otomatik çıkışını
        iptal ediyordu (pencere kapanır, süreç çıkmazdı). Uyarılar kutudan alınır: pencere kapanırken açılmazlar.
        Uyarıların ayrıntısı kaydırılabilir ayrıntı bölümünde, ana metinde yalnız sayıları: hepsi ana metinde olunca
        özet MacBook Air'de 1138 px boyla ekrandan taşıyor, Tamam ekranın dışında kalıyordu (U4). blocked_by: pencere
        kapanmıyor, şu başlıklı modal pencere hâlâ açık (U3; başlıksızsa boş metin): özet bunu da söyler."""
        err, audio_err, video_warn = self._record_problems(exc)
        parts: list[str] = []
        if err:
            parts.append(_record_error_text(err, audio_err, video_warn))
        else:
            if path is not None:
                details = self._record_details()
                parts.append(f"Kayıt kaydedildi: {path}" + ("\n" + " · ".join(details) if details else ""))
            if audio_err:
                parts.append(_sound_text(audio_err))
            if video_warn:
                parts.append(_video_text(video_warn))
        notices = error_notice.take_all()
        if notices:
            parts.append(f"{len(notices)} uyarı var: ayrıntısı aşağıda ('{DETAILS_SHOW}' düğmesi) ve hatalar.log'da.")
        if blocked_by is not None:
            which = f"'{blocked_by}' penceresi" if blocked_by else "Başka bir pencere"
            parts.append(f"Pencere kapanmadı: {which} hâlâ açık; kapansaydı içindeki kaydedilmemiş değişiklikler "
                         "kaybolurdu. Onu kapattıktan sonra uygulamayı yeniden kapatın.")
        if not parts:
            return
        warn = bool(err or audio_err or video_warn or notices or blocked_by is not None)
        box = QMessageBox(QMessageBox.Icon.Warning if warn else QMessageBox.Icon.Information,
                          "Kayıt sonucu" if warn else "Kayıt kaydedildi", "\n\n".join(parts),
                          QMessageBox.StandardButton.Ok, self)
        if notices:
            box.setDetailedText(error_notice.summary_text(notices))
            _turkish_details_button(box)
        box.exec()
        box.deleteLater()

    def _report_record_result(self, path, exc: str | None) -> None:
        """Hata pencerede (o an kayıt yok), ses ve görüntü uyarılarıyla birlikte. Başarı durum satırında; başarılı
        kaydın ses uyarısı (mikrofon kesildi) ve görüntü uyarısı (kodlayıcı kayda yetişemedi) uyarı kutusunda, her biri
        kendi başlığı, öneki ve anahtarıyla: durum satırı sahnede, sonraki kayda girer ve uyarı taşımaz (Temel ilke).
        Eskiden hata varken ses uyarısı atılıyordu (ffmpeg kayıt ortasında ölünce yalnız 'ffmpeg borusu kapandı'
        görünüyordu); başarıda da yalnız durum satırındaydı."""
        err, audio_err, video_warn = self._record_problems(exc)
        if err:
            QMessageBox.warning(self, "Kayıt hatası", _record_error_text(err, audio_err, video_warn))
            return
        if path is not None:
            details = self._record_details()
            self.work_area.set_status(f"Kayıt kaydedildi: {Path(path).name}" + (" · " + " · ".join(details) if details else ""))
        # Her kaydın uyarısı kendi anahtarıyla: aynı anahtar oturumda bir kez gösterilir.
        where = f"Kayıt kaydedildi: {path}\n" if path is not None else ""
        if audio_err:
            error_notice.post("Kayıtta ses sorunu", f"{where}{_sound_text(audio_err)}",
                              key=f"kayit-sesi:{path if path is not None else audio_err}")
        if video_warn:
            error_notice.post("Kayıtta görüntü sorunu", f"{where}{_video_text(video_warn)}",
                              key=f"kayit-goruntu:{path if path is not None else video_warn}")

    def _check_recorder(self, _seconds: int) -> None:
        """Yazıcı borusu koptuysa (ffmpeg çöktü) kaydı hemen kapat ve kullanıcıya söyle."""
        if getattr(self.recorder, "failed", False) and self.recorder.state is RecorderState.RECORDING:
            self.toggle_recording(False)

    def open_pen_settings(self) -> None:
        if self._refuse_while_closing(self.toolbar.pen_settings_button):
            return
        dlg = PenSettingsDialog(self.settings.pen(), self.canvas.color, self.canvas.base_width, self.fam, self)
        dlg.applied.connect(self._apply_pen_settings)
        dlg.exec()

    def _apply_pen_settings(self, p: PenSettings) -> None:
        self.settings.set_pen(p)
        self.canvas.set_pen_settings(p)
        self.question_zone.set_reading_ms(p.reading_ms)

    def _confirm_recorded_dialog(self) -> bool:
        if self.recorder.state is not RecorderState.RECORDING:
            return True
        allowed = QMessageBox.question(
            self, "Kayıt sürüyor",
            "Bu pencere kayda girer (editör cevapları gösterir). Yine de açılsın mı?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes
        # Sorunun modal olay döngüsünde kapanış başlatılmış olabilir.
        return allowed and not self._close_after_save

    def open_settings(self) -> None:
        if self._refuse_while_closing(self.toolbar.settings_button) or not self._confirm_recorded_dialog():
            return
        dlg = SettingsDialog(self.settings, self.fam, self, autostart=self.autostart)
        dlg.applied.connect(self.apply_settings_values)
        dlg.exec()

    def open_editor(self) -> None:
        if self._refuse_while_closing(self.toolbar.editor_button):
            return
        if self.questions_path is None:
            QMessageBox.information(self, "Soru editörü", "Soru dosyası tanımlı değil.")
            return
        if not self._confirm_recorded_dialog():
            return
        dlg = QuestionEditorDialog(self.flow.questions, self.questions_path, self.fam, self,
                                   from_file=self.questions_from_file,
                                   before_save=lambda: not self.flow.questions or self._save_board(self.flow.index))
        dlg.saved.connect(lambda questions: self.reload_questions(questions, board_saved=True))
        # Kaydet dosyaya yazdı: tahtadaki sorular artık dosyanınkiler (pencere örnek sorularla açılmış olsa da).
        dlg.saved.connect(lambda _questions: setattr(self, "questions_from_file", True))
        dlg.exec()

    def reload_questions(self, questions, *, board_saved=False) -> None:
        """Editörden gelen yeni listeyi uygular; akış başa döner, arayüz yeniden restart olmadan tazelenir."""
        if self.flow.questions and not board_saved:
            if not self._on_question_leaving(self.flow.index):
                error_notice.post("Sorular yenilenemedi", "Tahta kaydedilemediği için yeni soru listesi tahtaya uygulanmadı. "
                                  "Mevcut tahta korunuyor; disk sorununu giderip soruları yeniden yükleyin.",
                                  key="soru-yenileme")
                return

        else:
            self.canvas.reset_board()
            self._last_snapshot = None
        self.flow.set_questions(list(questions))
        if self.flow.questions:
            self._on_question_changed(self.flow.index)
        self._refresh_progress()

    def apply_settings_values(self, v: SettingsValues) -> None:
        s = self.settings
        self._startup_screen_wait_left = 0               # kullanıcı ekranları kendisi seçti: açılış bekleyişi biter
        self._startup_screen_timer.stop()
        if v.autostart is not None:
            self._apply_autostart(v.autostart)
        s.font_file = v.font_file
        s.set_pen(replace(s.pen(), reading_ms=v.reading_ms))
        s.auto_key = v.auto_key
        s.chroma_enabled = v.chroma_enabled
        s.presenter_name = v.presenter_name
        s.logo_file = v.logo_file
        s.logo_size = v.logo_size
        s.record_fps, s.record_height, s.audio_device = v.record_fps, v.record_height, v.audio_device
        s.record_folder = v.record_folder
        s.record_camera = v.record_camera
        s.aspect_lock = v.aspect_lock
        s.frame_style = v.frame_style
        if v.camera_index != s.camera_index:
            s.camera_index = v.camera_index
            if self.camera_source_factory is not None:
                idx = v.camera_index
                self.webcam_panel.set_source_factory(lambda: self.camera_source_factory(idx))
        for key, on in v.visible.items():
            s.set_visible(key, on)
        self.apply_ui_settings()
        board_missing = isinstance(v.board_screen, (tuple, list))
        preview_missing = isinstance(v.preview_screen, (tuple, list))
        if self.recorder.state is not RecorderState.RECORDING and not self._record_saving():
            s.board_screen_key = v.board_screen if board_missing else screen_key(v.board_screen)
            s.preview_screen_key = v.preview_screen if preview_missing else screen_key(v.preview_screen)
        self._configure_screens(None if board_missing else v.board_screen,
                                None if board_missing or preview_missing else v.preview_screen)

    def apply_ui_settings(self) -> None:
        """Ayarlardaki yazı tipi, yazma hızı, otomatik perde tonu ve görünürlükleri arayüze uygular."""
        s = self.settings
        # Yazı tipi dosyasını yalnız GERÇEKTEN değiştiyse yeniden yükle: apply_ui_settings artık her göz
        # düğmesi tıklamasında da çalışıyor (Görev 6), ama theme.load_font_file her çağrıda
        # QFontDatabase.addApplicationFont'u tekrar tekrar çağırır -- bu aynı dosya için TEKİLLEŞTİRMEZ,
        # her çağrı süreç ömrü boyunca kalıcı yeni bir kayıt biriktirir (bkz. review notları).
        if s.font_file != self._applied_font_file:
            self._applied_font_file = s.font_file
            self._applied_font_family = theme.load_font_file(s.font_file) if s.font_file else None
        self.fam = replace(self.base_fam, sans=self._applied_font_family) if self._applied_font_family else self.base_fam
        # Tahta yazı boyutu kaydırıcısı (Görev 7): yalnız TAHTA (work_area + bölgeler + webcam + rozet)
        # ölçekli aileyi görür. self.fam kendisi ÖLÇEKSİZ kalır -- diyaloglar (open_pen_settings,
        # open_settings, open_editor) ve araç çubuğu (self.toolbar, __init__'te self.fam ile kurulur ve
        # bir daha güncellenmez) büyümesin diye.
        board_fam = replace(self.fam, scale=s.font_scale)
        self.question_zone.set_families(board_fam)
        self.hint_zone.set_families(board_fam)
        self.webcam_panel.set_families(board_fam)
        # Rozet, work_area.set_families'TEN ÖNCE boyutlanmalı (review): set_families kendi relayout()'unu
        # HER çağrıda koşulsuz çalıştırır (set_aspect_lock/set_frame_visible/set_presenter_name gibi
        # BAŞKA çağrıların relayout()'una yaslanmadan) -- bu yüzden rozetin doğru (taşmayan, sağa hizalı)
        # konumu BURADAN, tesadüfen değil yapısal olarak garanti edilir. Sıra tersine çevrilirse (rozet
        # set_families'TEN SONRA boyutlansa) o anki relayout() rozetin ESKİ genişliğini görür ve rozet
        # yalnızca aşağıdaki üç çağrının (hepsi bugün koşulsuz) tesadüfen sonradan gelen relayout()'una
        # kalırdı -- bkz. test_badge_stays_right_anchored_after_font_scale_change_with_real_content.
        self.badge.set_families(board_fam)
        self.work_area.set_families(board_fam)
        self.work_area.set_font_scale(s.font_scale)
        self.question_zone.set_reading_ms(s.pen().reading_ms)
        self.webcam_panel.set_auto_key(s.auto_key)
        self.webcam_panel.set_chroma_enabled(s.chroma_enabled)
        self.hint_zone.set_controls_visible(s.visible("hint_controls"))
        self.hint_zone.set_heading_visible(s.visible("hint_heading"))
        self.hint_zone.setVisible(s.visible("hint_zone"))
        self.work_area.set_item_visible("hint_zone", s.visible("hint_zone"))
        self.work_area.status_label.setVisible(s.visible("status"))
        self.work_area.set_item_visible("status", s.visible("status"))
        self.webcam_panel.overlay_label.setVisible(s.visible("cam_label"))
        # brand'in setVisible'ı BURADA YOK (nihai inceleme, madde 4): marka plakasının görünürlüğünü
        # yalnız _apply_chrome yazar (set_item_visible onu tetikler) -- etkin çerçeve stili markayı kendi
        # bandına çizdiğinde plaka gizli kalmalı. Buradaki ikinci yazıcı zaten bir satır sonra eziliyordu.
        # NOT: "status" (yukarıda) ve "logo" (aşağıda) için aynı satırlar ÖLÜ DEĞİL -- _apply_chrome onlara
        # dokunmaz, gerçek widget görünürlüğünü hâlâ burası uygular.
        self.work_area.set_item_visible("brand", s.visible("brand"))
        self.question_zone.set_hide_link_enabled(s.visible("hide_link"))
        self.question_zone.set_number_visible(s.visible("question_number"))
        self.question_zone.setVisible(s.visible("question_zone"))
        self.work_area.set_item_visible("question_zone", s.visible("question_zone"))
        if self.recorder.state is not RecorderState.RECORDING and not self._record_saving():
            self.work_area.set_aspect_lock(s.aspect_lock)
        self.work_area.set_frame_visible(s.visible("frame"))
        self.work_area.set_frame_style(s.frame_style)
        self.work_area.set_item_visible("frame_titles", s.visible("frame_titles"))
        # presenter: metin (set_presenter_name) ve görünürlük (set_item_visible) artık AYRI -- göz düğmesi
        # ile Ayarlar'daki ad kutusu birbirini ezmesin diye (bkz. work_area.set_presenter_name docstring'i).
        self.work_area.set_presenter_name(s.presenter_name)
        self.work_area.set_item_visible("presenter", s.visible("presenter"))
        # Logo pixmap'i de aynı nedenle (font gibi) yalnız dosya/boyut değiştiyse yeniden yüklenir --
        # set_logo() QPixmap(path) + ölçekleme yapar, göz düğmesi tıklamalarında boşuna tekrarlanmasın.
        logo_key = (s.logo_file, s.logo_size)
        if logo_key != self._applied_logo:
            self._applied_logo = logo_key
            self.work_area.set_logo(s.logo_file, s.logo_size)
        self.work_area.logo_label.setVisible(s.visible("logo"))
        self.work_area.set_item_visible("logo", s.visible("logo"))
        self.badge.show_on_board = s.visible("badge")
        if self.badge.active:
            self.badge.setVisible(self.badge.show_on_board)
        self.work_area.set_item_visible("badge", s.visible("badge"))
        # webcam: görünürlük + yaşam döngüsü. Kapatılınca CameraWorker durur (chroma-key artık görünmeyen
        # bir widget için boşa kare işlemez); açılınca yalnız gerçek bir kamera kaynağı VARSA yeniden başlar
        # (main_window.py __init__'teki "camera_source_factory is not None" kalıbıyla aynı koruma).
        webcam_on = s.visible("webcam")
        self.webcam_panel.setVisible(webcam_on)
        self.work_area.set_item_visible("webcam", webcam_on)
        if webcam_on or self._preview is not None:
            if self.camera_source_factory is not None:
                self.webcam_panel.start()
        else:
            # Kısa üst sınır: bu yol rutin bir düzenleme eylemiyle (göz düğmesi) her tetiklenebilir --
            # closeEvent'teki varsayılan (2000ms) burada kamera sürücüsü takılırsa arayüzü iki saniye
            # dondururdu. İş parçacığı normalde ~33ms'de durur; üst sınır yalnız arızaya karşı emniyet.
            self.webcam_panel.shutdown(WEBCAM_HIDE_TIMEOUT_MS)
        for attr, val in (("fps", s.record_fps), ("out_height", s.record_height), ("audio_device", s.audio_device or None)):
            if hasattr(self.recorder, attr):
                setattr(self.recorder, attr, val)

    # --- oturum durumu (kapanıp açılınca kaldığı yerden devam) -----------------------
    def _wire_session(self) -> None:
        # Tahta boşaldı (Temizle, geri al, soru geçişi): kayıtlı tahta görüntüsü artık geçerli değil.
        self.canvas.historyChanged.connect(self._on_history_for_session)

    def _on_history_for_session(self, _can_undo: bool, empty: bool) -> None:
        if empty:
            self._remember_session(board_image="", board_question_id="")

    def _remember_session(self, **changes) -> None:
        """Oturum durumunu günceller; yalnız değişince yazılır (diske sürekli yazma yok)."""
        if not getattr(self, "_session_ready", False):
            return
        try:
            current = self.settings.session_state
            state = replace(current, **changes)
            if state != current:
                self.settings.session_state = state
        except Exception as err:  # noqa: BLE001 - oturum belleği hiçbir zaman dersi durdurmaz
            crash_log.log_handled(err, "oturum durumu")

    def _remember_question(self, *, keep_board: bool = False) -> None:
        # Sorular dosyadan okunamadıysa (örnek sorular) gerçek soru konumunun üzerine yazılmaz.
        if not self.questions_from_file or not self.flow.questions:
            return
        default = paths.default_template_path()
        self._remember_session(
            questions_file=str(self.questions_path) if self.questions_path and self.questions_path != default else "",
            question_id=self.flow.current.id, question_index=self.flow.index,
            **({} if keep_board else {"board_image": "", "board_question_id": ""}))

    def _remember_window(self) -> None:
        if not getattr(self, "_session_ready", False):
            return
        changes: dict = {"fullscreen": self.isFullScreen()}
        if not self.isMinimized():
            rect = self.normalGeometry() if (self.isFullScreen() or self.isMaximized()) else self.geometry()
            if rect.width() >= 200 and rect.height() >= 150:
                changes["geometry"] = (rect.x(), rect.y(), rect.width(), rect.height())
        self._remember_session(**changes)

    def _remember_on_close(self) -> None:
        self._remember_window()
        self._remember_question(keep_board=True)
        if not self.canvas.has_snapshot_content():
            self._remember_session(board_image="", board_question_id="")

    def _restore_session_question(self, state: SessionState) -> None:
        """Son soruya (kimliğiyle) döner; tahta görüntüsü pencere gösterilince yüklenir. Kimlik yoksa (dosya
        değişmiş) ilk soruda kalır; durumlar (bitti/işleniyor) değişmez."""
        questions = self.flow.questions
        if not questions or not state.question_id:
            return
        saved = state.question_index
        if 0 <= saved < len(questions) and questions[saved].id == state.question_id:
            index = saved
        else:
            index = next((i for i, q in enumerate(questions) if q.id == state.question_id), None)
        if index is None:
            return
        if index != self.flow.index:
            self.flow.select(index)
        if state.board_image and state.board_question_id == state.question_id:
            self._pending_board = (state.board_image, state.board_question_id)

    def restore_window_state(self, state: SessionState) -> None:
        """Önceki pencere geometrisini (ekranlardan birinde yeterince görünüyorsa) ve tam ekranı geri getirir.
        Gösterilmeden önce çağrılır. Ekran artık yoksa varsayılan boyutta kalır."""
        rect = self._fitting_geometry(state.geometry)
        if rect is not None:
            self.setGeometry(rect)
        if state.fullscreen:
            self.setWindowState(self.windowState() | Qt.WindowState.WindowFullScreen)

    @staticmethod
    def _fitting_geometry(geometry) -> "QRect | None":
        if not geometry:
            return None
        x, y, w, h = geometry
        wanted = QRect(x, y, w, h)
        best, best_area = None, 0
        for screen in QApplication.screens():
            avail = screen.availableGeometry()
            inter = wanted.intersected(avail)
            area = max(0, inter.width()) * max(0, inter.height())
            if area > best_area:
                best, best_area = avail, area
        # Pencere ekrandan büyükse (ekran küçüldü) ekrana sığdırılır; yoksa yarısı görünür olmalı.
        if best is None or best_area < 0.5 * min(w * h, best.width() * best.height()):
            return None                                   # ekran artık yok / pencere büyük ölçüde dışarıda
        w, h = min(w, best.width()), min(h, best.height())
        x = max(best.left(), min(x, best.right() - w + 1))
        y = max(best.top(), min(y, best.bottom() - h + 1))
        return QRect(x, y, w, h)

    def show_session_notice(self, text: str) -> None:
        """Kısa uyarı araç çubuğunun şeridinde (sahneye ve kayda girmez); birkaç saniye sonra kalkar."""
        self.toolbar.set_alert(SESSION_NOTICE_KEY, text)
        timer = getattr(self, "_session_notice_timer", None)
        if timer is None:                                  # pencerenin çocuğu: pencere silinince zamanlayıcı da gider
            timer = self._session_notice_timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._clear_session_notice)
        timer.start(SESSION_NOTICE_MS)

    def _clear_session_notice(self) -> None:
        self.toolbar.set_alert(SESSION_NOTICE_KEY, None)

    def _restore_board_image(self) -> None:
        """Önceki oturumda o sorunun son tahta PNG'sini (varsa, sağlamsa ve soru aynıysa) tuvale geri koyar.
        Kullanıcı bu arada çizdiyse dokunmaz. Pencere oranı çok değiştiyse çizim bozulacağı için yüklenmez."""
        pending, self._pending_board = self._pending_board, None
        if pending is None or not self.flow.questions:
            return
        path, qid = pending
        try:
            if self.flow.current.id != qid or self.canvas.has_snapshot_content():
                return
            file = Path(path)
            if not file.is_file() or file.stat().st_size > BOARD_RESTORE_MAX_BYTES:
                return
            image = QImage.fromData(file.read_bytes(), "PNG")
            layer = self.canvas._strokes
            if image.isNull() or layer.isNull():
                return
            have, want = image.width() / max(1, image.height()), layer.width() / max(1, layer.height())
            if abs(have - want) / want > BOARD_RESTORE_MAX_ASPECT_DIFF:
                self.show_session_notice("Önceki tahta çizimi, pencere oranı değiştiği için geri yüklenmedi.")
                return
            c = self.canvas
            c._strokes = ink_from_snapshot(image, layer.size(), layer.devicePixelRatio())    # tuval API'si yok: tek nokta
            c._stroke_count = 1
            c.update()
            c.historyChanged.emit(False, False)
        except Exception as err:  # noqa: BLE001 - bozuk/okunamayan görüntü açılışı düşürmez
            crash_log.log_handled(err, "tahta görüntüsü geri yükleme")

    def _apply_autostart(self, on: bool) -> None:
        try:
            self.autostart.set_enabled(on)
        except AutostartError as err:
            error_notice.post("Bilgisayar açılınca başlatma", f"{err}", key="acilista-baslat")

    def closeEvent(self, e):
        """Pencere kapatma (pencere düğmesi, close(), QApplication.quit; macOS'ta ⌘Q da pencerelere bu olayı gönderir).
        Kayıt sürerken önce sorulur. Kayıt kaydedilirken pencere kapanmaz: olay yok sayılır, kapanış arka planda
        biter, sonuç ve görülmemiş uyarılar tek pencerede gösterilir ve pencere kendisi kapanır (_on_record_stopped).
        Çalışan _StopWorker hiçbir koşulda yok edilmez: Qt süreci 'QThread: Destroyed while thread is still running'
        ile düşürür, kayıt birleşmeden kalırdı. Gerçek kapanışta kamera ve ayarlar, kaydı durdurmak patlasa da her
        koşulda kapanır; ardından `closed` yayılır (app.main süreci bitirir)."""
        if self._reporting_record_result or self._record_starting:
            if self._record_starting:
                self._geometry_interrupted = True
            e.ignore()  # Modal olay döngüsünde sonuç tamamlanmadan pencere kapanamaz.
            return
        if self.recorder.state is RecorderState.RECORDING and not self._record_saving():
            if not self._confirm_stop_and_quit():
                e.ignore()
                return
            try:
                self.toggle_recording(False)         # yavaş kaydedici: arka planda _StopWorker; hızlısı hemen durur
            except Exception as err:  # noqa: BLE001 - kapanış sürer; hata söylenir ve günlüğe yazılır
                self._report_close_error(err)
        if self._record_saving():
            self._close_after_save = True
            if self._stop_worker is None:            # kapanışı başkası başlatmış (FINALIZING): bitişini bekleyen işçi
                self._start_stop_worker()
            self._show_saving_alert()
            e.ignore()
            return
        if self.flow.questions and not self._save_board(self.flow.index):
            e.ignore()
            return
        self._remember_on_close()
        self._disable_preview()
        try:
            # Varsayılan (2000ms) üst sınır: pencere zaten kapanıyor, birkaç saniyelik gecikme kabul edilebilir
            # (apply_ui_settings'in görünürlük yolu bunun yerine kısa WEBCAM_HIDE_TIMEOUT_MS'yi kullanır).
            self.webcam_panel.shutdown()
        finally:
            self.settings.sync()
        super().closeEvent(e)
        self.closed.emit()

    def _confirm_stop_and_quit(self) -> bool:
        """Kayıt sürerken kapatma sorusu. Varsayılan ve Esc 'Kayda devam et': yanlışlıkla basılan ⌘Q dersi kesmesin."""
        box = QMessageBox(QMessageBox.Icon.Question, "Kayıt sürüyor", "Kayıt sürüyor, durdurulup çıkılsın mı?",
                          parent=self)
        box.setInformativeText("Kayıt arka planda kaydedilir; bitince pencere kendisi kapanır.")
        stop = box.addButton(STOP_AND_QUIT, QMessageBox.ButtonRole.AcceptRole)
        keep = box.addButton(KEEP_RECORDING, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(keep)
        box.setEscapeButton(keep)
        box.exec()
        stopped = box.clickedButton() is stop
        box.deleteLater()
        return stopped

    def _report_close_error(self, err: Exception) -> None:
        crash_log.log_handled(err, "pencere kapanışı")
        QMessageBox.warning(self, "Kayıt hatası", f"Kayıt kapatılamadı: {exception_text(err)}")


class _NoCamera:
    def open(self) -> bool: return False
    def read(self): return None
    def release(self) -> None: pass
