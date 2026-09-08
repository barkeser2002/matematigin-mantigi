"""Ana pencere: beyaz tahta + bölgeleri kurar ve sinyalleri bağlar. İş mantığı core/ içindedir."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable, Sequence

from PyQt6.QtGui import QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import (SHAPE_META, TOOL_META, PenSettings, Question, QuestionStatus, Tool,
                                             next_shape)
from matematigin_mantigi.core.question_flow import QuestionFlow
from matematigin_mantigi.core.recorder import Recorder, record_rect_for
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.camera_worker import FrameSource
from matematigin_mantigi.ui.cursors import cursor_for
from matematigin_mantigi.ui.hint_zone import HintZone
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
from matematigin_mantigi.ui.question_zone import QuestionZone
from matematigin_mantigi.ui.record_badge import RecordBadge
from matematigin_mantigi.ui.settings_dialog import SettingsDialog, SettingsValues
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.webcam_panel import WebcamPanel
from matematigin_mantigi.ui.work_area import WorkArea


class MainWindow(QMainWindow):
    def __init__(self, fam: FontFamilies, questions: Sequence[Question], settings: AppSettings,
                 recorder: Recorder, session_store: SessionStore,
                 camera_source_factory: Callable[[int], FrameSource] | None, layout_path: Path, parent=None):
        """camera_source_factory: kamera indeksinden kaynak üretir; None ise kamera açılmaz."""
        super().__init__(parent)
        self.camera_source_factory = camera_source_factory
        self.base_fam = fam                       # paketle gelen aile; Ayarlar'daki dosya bunun üstüne biner
        self.fam, self.settings, self.recorder, self.session_store = fam, settings, recorder, session_store
        self.layout_path = Path(layout_path)
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
        self.webcam_panel = WebcamPanel(fam, factory, settings.chroma, chroma_enabled=settings.chroma_enabled)
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
        if questions:
            self._on_question_changed(self.flow.index)
        if camera_source_factory is not None:
            self.webcam_panel.start()

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
        tb.layoutEditToggled.connect(self.work_area.set_edit_mode)
        self.work_area.editModeChanged.connect(tb.set_layout_edit)
        self.work_area.layoutChanged.connect(lambda lay: lm.save_layout(self.layout_path, lay))

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
        sc("R", lambda: self.toggle_recording(not self.recorder.is_recording))
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
            self.session_store.save_snapshot(self.flow.questions[i].id, self.canvas.snapshot_image())
        self.canvas.clear()

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

    def toggle_recording(self, on: bool) -> None:
        if on and not self.recorder.is_recording:
            rect = record_rect_for(self.work_area.recording_rect())
            self.recorder.start(rect, fps=60)
            self.badge.set_format(rect.width, rect.height, 60)
            self.badge.start()
            self.work_area.relayout()
        elif not on and self.recorder.is_recording:
            self.recorder.stop()
            self.badge.stop()
            self.work_area.relayout()
        self.toolbar.set_recording(self.recorder.is_recording)

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

    def apply_settings_values(self, v: SettingsValues) -> None:
        s = self.settings
        s.font_file = v.font_file
        s.set_pen(replace(s.pen(), reading_ms=v.reading_ms))
        s.auto_key = v.auto_key
        s.chroma_enabled = v.chroma_enabled
        s.presenter_name = v.presenter_name
        s.logo_file = v.logo_file
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
        family = theme.load_font_file(s.font_file) if s.font_file else None
        self.fam = replace(self.base_fam, sans=family) if family else self.base_fam
        self.question_zone.set_families(self.fam)
        self.hint_zone.set_families(self.fam)
        self.question_zone.set_reading_ms(s.pen().reading_ms)
        self.webcam_panel.set_auto_key(s.auto_key)
        self.webcam_panel.set_chroma_enabled(s.chroma_enabled)
        self.hint_zone.set_controls_visible(s.visible("hint_controls"))
        self.hint_zone.set_heading_visible(s.visible("hint_heading"))
        self.work_area.status_label.setVisible(s.visible("status"))
        self.webcam_panel.overlay_label.setVisible(s.visible("cam_label"))
        self.work_area.brand.setVisible(s.visible("brand"))
        self.question_zone.set_hide_link_enabled(s.visible("hide_link"))
        self.question_zone.set_number_visible(s.visible("question_number"))
        self.work_area.set_frame_visible(s.visible("frame"))
        self.work_area.set_presenter_name(s.presenter_name if s.visible("presenter") else "")
        self.work_area.set_logo(s.logo_file)
        self.work_area.logo_label.setVisible(s.visible("logo"))

    def closeEvent(self, e):
        self.webcam_panel.shutdown()
        self.settings.sync()
        super().closeEvent(e)


class _NoCamera:
    def open(self) -> bool: return False
    def read(self): return None
    def release(self) -> None: pass
