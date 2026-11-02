"""Ana pencere: beyaz tahta + bölgeleri kurar ve sinyalleri bağlar. İş mantığı core/ içindedir."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable, Sequence

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QWidget

from matematigin_mantigi.core import crash_log
from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import (SHAPE_META, TOOL_META, PenSettings, Question, QuestionStatus, Tool,
                                             next_shape)
from matematigin_mantigi.core.question_flow import QuestionFlow
from matematigin_mantigi.core.recorder import (DISK_HINT, Recorder, RecorderError, RecorderState, exception_text,
                                               record_rect_for)
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
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
from matematigin_mantigi.ui.webcam_panel import WebcamPanel
from matematigin_mantigi.ui.work_area import WorkArea


class _StopWorker(QThread):
    """recorder.stop() birkaç saniye sürebilir (ffmpeg kapanışı + ses birleştirme); arayüzü dondurmasın."""
    done = pyqtSignal(object)

    def __init__(self, recorder, parent=None):
        super().__init__(parent)
        self.recorder = recorder
        self.exc: str | None = None

    def run(self) -> None:
        path = None
        try:
            path = self.recorder.stop()
        except Exception as err:  # noqa: BLE001 - sonuç pencereye 'Kayıt hatası' olarak gider
            self.exc = str(err) or repr(err)         # mesajsız istisna (OSError()) da sessiz kalmasın
            crash_log.log_handled(err, "kayıt kapanışı")
        self.done.emit(path)


WEBCAM_HIDE_TIMEOUT_MS = 400   # apply_ui_settings'in "webcam" görünürlüğü kapatma yolu: closeEvent'in
                               # varsayılanından (2000ms) çok daha kısa -- bkz. apply_ui_settings ve
                               # WebcamPanel.shutdown docstring'i.
SAVING_KEY = "kayit-kaydediliyor"        # araç çubuğu uyarı şeridinde bu kaynağın anahtarı
SAVING_ALERT = "Kayıt kaydediliyor…"   # kapanış (ffmpeg + ses birleştirme) sürerken araç çubuğundaki uyarı


class MainWindow(QMainWindow):
    def __init__(self, fam: FontFamilies, questions: Sequence[Question], settings: AppSettings,
                 recorder: Recorder, session_store: SessionStore,
                 camera_source_factory: Callable[[int], FrameSource] | None, layout_path: Path, parent=None,
                 *, questions_path: "Path | None" = None):
        """camera_source_factory: kamera indeksinden kaynak üretir; None ise kamera açılmaz.
        questions_path: soru dosyası (xlsx); verilmezse soru editörü açılmaz."""
        super().__init__(parent)
        self.camera_source_factory = camera_source_factory
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
        self.setWindowTitle("Matematiğin Mantığı")

        central = QWidget(); row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
        self.toolbar = ToolBar(fam)
        self.work_area = WorkArea(fam)
        self.canvas = self.work_area.board
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
        self._wire()
        self._shortcuts()
        self._restore_settings()
        self.apply_ui_settings()
        self.toolbar.editor_button.setEnabled(self.questions_path is not None)
        if questions:
            self._on_question_changed(self.flow.index)
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

        flow.questionLeaving.connect(self._on_question_leaving)
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
        sc("F11", lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        sc("Escape", self._escape, while_typing=True)

    def _return_key(self) -> None:
        if self._typing():
            self.canvas.commit_text()         # yazı kutusu açıkken Enter yazıyı işler
        else:
            self.flow.toggle_reveal()

    def _escape(self) -> None:
        if self._typing():
            self.canvas.cancel_text()
        elif self.work_area.edit_mode:
            self.work_area.set_edit_mode(False)
        elif self.isFullScreen():
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

    def _on_question_leaving(self, i: int) -> None:
        if not self.canvas.is_empty():
            qid = self.flow.questions[i].id
            try:
                self.session_store.save_snapshot(qid, self.canvas.snapshot_image())
            except OSError as err:
                # Yuvadan kaçan hata uygulamayı (süren kayıtla) düşürüyordu; ders sürer, yalnız bu PNG eksik kalır.
                error_notice.post("Tahta görüntüsü kaydedilemedi",
                                  f"{qid} sorusunun tahta resmi kaydedilemedi: {error_notice.describe_os_error(err)}."
                                  f"\nKlasör: {self.session_store.session_dir}\nDers ve süren kayıt devam ediyor.",
                                  key="tahta-goruntusu")
        self.canvas.clear()

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

    def _record_saving(self) -> bool:
        """Önceki kayıt hâlâ kaydediliyor (kaydedici FINALIZING) ya da durdurma sonucu pencereye henüz ulaşmadı
        (_StopWorker'ın done'ı _on_record_stopped'ta işlenmedi). Bu sürede ne yeni kayıt ne ikinci durdurma."""
        return self.recorder.state is RecorderState.FINALIZING or getattr(self, "_stop_worker", None) is not None

    def toggle_recording(self, on: bool) -> None:
        if self._record_saving():               # düğme kilitli; R de kapanan kaydın yollarına karışmasın (#2)
            self.toolbar.set_alert(SAVING_KEY, SAVING_ALERT)
            return
        fps = self.settings.record_fps
        state = self.recorder.state
        if on and state is RecorderState.IDLE:
            rect = record_rect_for(self.work_area.recording_rect())
            try:
                self.recorder.start(rect, fps=fps)
            except Exception as err:  # noqa: BLE001 - hiçbir başlatma hatası yuvadan kaçıp düğmeyi 'kayıtta' bırakmasın
                self._record_start_failed(err)
                return
            h = self.settings.record_height or rect.height
            self.badge.set_format(round(rect.width * h / rect.height), h, fps)
            self.badge.start()
            self.work_area.relayout()
        elif not on and state is RecorderState.RECORDING:
            self.badge.stop()
            self.work_area.relayout()
            if getattr(self.recorder, "stop_is_quick", False):
                self._on_record_stopped(self.recorder.stop())
            else:
                self.toolbar.set_recording(False)
                self.toolbar.record_button.setEnabled(False)
                self.toolbar.set_alert(SAVING_KEY, SAVING_ALERT)      # durum satırına değil: o tahtada, kayda girer
                self._stop_worker = _StopWorker(self.recorder, self)
                self._stop_worker.done.connect(self._on_record_stopped)
                self._stop_worker.start()
                return
        recording = self.recorder.state is RecorderState.RECORDING
        self.toolbar.set_recording(recording)
        if recording:
            self.toolbar.set_recording_time(self.badge.seconds)

    def _record_start_failed(self, err: Exception) -> None:
        """Kayıt başlamadı: araç çubuğu 'kayıt yok'a döner, sebep pencerede (her denemede), ayrıntı hatalar.log'da.
        OSError (disk, izin) ve beklenmeyen hata da buraya gelir: yuvadan kaçıp düğmeyi 'kayıtta' bırakmasın."""
        self.toolbar.set_recording(False)
        crash_log.log_handled(err, "kayıt başlatma")
        if isinstance(err, RecorderError):
            text = str(err)
        elif isinstance(err, OSError):
            text = f"Kayıt dosyası yazılamadı: {err}\n{DISK_HINT}"
        else:
            text = f"Beklenmeyen hata: {exception_text(err)}"
        QMessageBox.warning(self, "Kayıt başlatılamadı", text)

    def _on_record_stopped(self, path) -> None:
        worker = getattr(self, "_stop_worker", None)
        if worker is not None:
            worker.wait()                    # done run()'ın son adımı: iş parçacığı bitsin, öyle bırakılsın
        self._stop_worker = None             # kapanış bitti: düğme ve R yeniden kayıt başlatabilir
        self.toolbar.set_alert(SAVING_KEY, None)
        self.toolbar.record_button.setEnabled(True)
        self.toolbar.set_recording(False)
        # Önce kaydedicinin anlamlı hatası (sebep, dosyaların yeri); işçinin ham istisna metni yalnız yedek.
        err = getattr(self.recorder, "error", None) or (worker.exc if worker is not None else None)
        audio_err = getattr(self.recorder, "audio_error", None)
        if err:
            QMessageBox.warning(self, "Kayıt hatası", err)
            return
        if path is None:
            return
        cap = getattr(self.recorder, "capture_fps", 0.0)
        parts = [f"yakalama ~{cap:.0f} kare/sn"] if cap else []
        off = getattr(self.recorder, "av_offset_ms", None)
        if off is not None:
            parts.append(f"ses hizası {off:+.0f} ms telafi edildi")
        res = getattr(self.recorder, "audio_result", None)
        if res is not None and (res.overflows or res.dropped_blocks):
            parts.append(f"ses taşması {res.overflows + res.dropped_blocks}")
        if audio_err:
            parts.append(f"UYARI: {audio_err}")
        self.work_area.set_status(f"Kayıt kaydedildi: {path}" + (" · " + " · ".join(parts) if parts else ""))

    def _check_recorder(self, _seconds: int) -> None:
        """Yazıcı borusu koptuysa (ffmpeg çöktü) kaydı hemen kapat ve kullanıcıya söyle."""
        if getattr(self.recorder, "failed", False) and self.recorder.state is RecorderState.RECORDING:
            self.toggle_recording(False)

    def open_pen_settings(self) -> None:
        dlg = PenSettingsDialog(self.settings.pen(), self.canvas.color, self.canvas.base_width, self.fam, self)
        dlg.applied.connect(self._apply_pen_settings)
        dlg.exec()

    def _apply_pen_settings(self, p: PenSettings) -> None:
        self.settings.set_pen(p)
        self.question_zone.set_reading_ms(p.reading_ms)

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.fam, self)
        dlg.applied.connect(self.apply_settings_values)
        dlg.exec()

    def open_editor(self) -> None:
        if self.questions_path is None:
            QMessageBox.information(self, "Soru editörü", "Soru dosyası tanımlı değil.")
            return
        dlg = QuestionEditorDialog(self.flow.questions, self.questions_path, self.fam, self)
        dlg.saved.connect(self.reload_questions)
        dlg.exec()

    def reload_questions(self, questions) -> None:
        """Editörden gelen yeni listeyi uygular; akış başa döner, arayüz yeniden restart olmadan tazelenir."""
        self.canvas.clear()
        self.flow.set_questions(list(questions))
        if self.flow.questions:
            self._on_question_changed(self.flow.index)
        self._refresh_progress()

    def apply_settings_values(self, v: SettingsValues) -> None:
        s = self.settings
        s.font_file = v.font_file
        s.set_pen(replace(s.pen(), reading_ms=v.reading_ms))
        s.auto_key = v.auto_key
        s.chroma_enabled = v.chroma_enabled
        s.presenter_name = v.presenter_name
        s.logo_file = v.logo_file
        s.logo_size = v.logo_size
        s.record_fps, s.record_height, s.audio_device = v.record_fps, v.record_height, v.audio_device
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
        if webcam_on:
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

    def closeEvent(self, e):
        if self.recorder.state is RecorderState.RECORDING:
            self.recorder.stop()                 # pencere kapanırken kayıt dosyası tamamlansın
        worker = getattr(self, "_stop_worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(60000)                   # arka planda ses birleştirme sürüyorsa bitmesini bekle
        # Varsayılan (2000ms) üst sınır: pencere zaten kapanıyor, birkaç saniyelik gecikme kabul edilebilir
        # (apply_ui_settings'in görünürlük yolu bunun yerine kısa WEBCAM_HIDE_TIMEOUT_MS'yi kullanır).
        self.webcam_panel.shutdown()
        self.settings.sync()
        super().closeEvent(e)


class _NoCamera:
    def open(self) -> bool: return False
    def read(self): return None
    def release(self) -> None: pass
