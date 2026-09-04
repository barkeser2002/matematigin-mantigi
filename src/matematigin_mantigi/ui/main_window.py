"""Ana pencere: bileşenleri kurar ve sinyalleri bağlar. İş mantığı core/ içindedir."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.core.models import TOOL_META, Question, QuestionStatus, Tool
from matematigin_mantigi.core.question_flow import QuestionFlow
from matematigin_mantigi.core.recorder import Recorder, record_rect_for
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui.camera_worker import FrameSource
from matematigin_mantigi.ui.canvas_panel import CanvasPanel
from matematigin_mantigi.ui.cursors import cursor_for
from matematigin_mantigi.ui.hint_panel import HintPanel
from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
from matematigin_mantigi.ui.question_panel import QuestionPanel
from matematigin_mantigi.ui.record_badge import RecordBadge
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.webcam_panel import WebcamPanel
from matematigin_mantigi.ui.work_area import WorkArea


class MainWindow(QMainWindow):
    def __init__(self, fam: FontFamilies, questions: Sequence[Question], settings: AppSettings,
                 recorder: Recorder, session_store: SessionStore,
                 camera_source_factory: Callable[[], FrameSource] | None, layout_path: Path, parent=None):
        super().__init__(parent)
        self.fam, self.settings, self.recorder, self.session_store = fam, settings, recorder, session_store
        self.layout_path = Path(layout_path)
        self.setWindowTitle("Matematiğin Mantığı")

        central = QWidget(); row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0); row.setSpacing(0)
        self.toolbar = ToolBar(fam)
        self.work_area = WorkArea(fam)
        self.question_panel = QuestionPanel(fam)
        self.hint_panel = HintPanel(fam)
        self.canvas_panel = CanvasPanel(fam)
        self.canvas = self.canvas_panel.canvas
        self.webcam_panel = WebcamPanel(fam, camera_source_factory or (lambda: _NoCamera()),
                                        settings.chroma, settings.chroma_enabled)
        for key, panel in (("soru", self.question_panel), ("ipucu", self.hint_panel),
                           ("cizim", self.canvas_panel), ("webcam", self.webcam_panel)):
            self.work_area.add_panel(key, panel)
        self.work_area.set_layout(lm.load_layout(self.layout_path))
        self.badge = RecordBadge(fam, self.work_area)
        self.work_area.badge_slot = self.badge
        row.addWidget(self.toolbar); row.addWidget(self.work_area, 1)
        self.setCentralWidget(central)

        self.flow = QuestionFlow(questions, self)
        self._wire()
        self._restore_settings()
        self.question_panel.set_questions(questions)
        self._on_question_changed(self.flow.index if questions else 0)
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
        tb.nextRequested.connect(flow.next_question)
        tb.recordToggled.connect(self.toggle_recording)
        tb.penSettingsRequested.connect(self.open_pen_settings)
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
        flow.questionVisibilityChanged.connect(self.question_panel.set_shown)
        flow.hintChanged.connect(lambda i, _n: self.hint_panel.set_focus(i))
        flow.hintRevealChanged.connect(
            lambda q, h, on: self.hint_panel.set_revealed(h, on) if q == flow.index else None)

        qp, hp = self.question_panel, self.hint_panel
        qp.questionSelected.connect(flow.select)
        qp.showRequested.connect(flow.show_question)
        qp.hideRequested.connect(flow.hide_question)
        hp.prevRequested.connect(flow.hint_prev)
        hp.nextRequested.connect(flow.hint_next)
        hp.revealToggled.connect(flow.toggle_reveal)
        hp.maskModeChanged.connect(self._on_mask_mode)
        self.webcam_panel.chromaToggled.connect(self._on_chroma_toggled)

    def _restore_settings(self) -> None:
        s = self.settings
        self.canvas.set_tool(s.tool); self.canvas.set_color(QColor(s.color)); self.canvas.set_base_width(s.width)
        self.toolbar.set_tool(s.tool); self.toolbar.set_color(s.color); self.toolbar.set_width(s.width)
        self.hint_panel.set_mask_mode(s.hint_mask)
        self.refresh_cursor()
        self._status("XP-Pen")

    # --- handlers -----------------------------------------------------------------
    def _on_tool(self, t: Tool) -> None:
        self.canvas.set_tool(t); self.settings.tool = t
        self.refresh_cursor(); self._status("XP-Pen")

    def _on_color(self, hx: str) -> None:
        self.canvas.set_color(QColor(hx)); self.settings.color = hx
        if self.canvas.tool != Tool.PEN:              # mockup: renk seçimi kalemi seçer
            self._on_tool(Tool.PEN); self.toolbar.set_tool(Tool.PEN)
        self.refresh_cursor()

    def _on_width(self, w: int) -> None:
        self.canvas.set_base_width(w); self.settings.width = w
        self.refresh_cursor(); self._status("XP-Pen")

    def refresh_cursor(self) -> None:
        self.canvas.setCursor(cursor_for(self.canvas.tool, self.canvas.color, self.canvas.base_width,
                                         self.canvas.devicePixelRatioF()))

    def _status(self, pressure_text: str) -> None:
        self.canvas_panel.set_status(TOOL_META[self.canvas.tool][0], self.canvas.base_width, pressure_text)

    def _on_question_leaving(self, i: int) -> None:
        if not self.canvas.is_empty():
            self.session_store.save_snapshot(self.flow.questions[i].id, self.canvas.snapshot_image())
        self.canvas.clear()

    def _on_question_changed(self, i: int) -> None:
        if not self.flow.questions:
            return
        q = self.flow.questions[i]
        self.question_panel.set_current(i)
        self.hint_panel.set_hints(q.id, q.hints)
        for h in range(len(q.hints)):
            self.hint_panel.set_revealed(h, self.flow.is_revealed(h))
        self.canvas_panel.set_question_label(f"· {q.id} için çözüm alanı")
        self._refresh_progress()

    def _on_status_changed(self, i: int, s: QuestionStatus) -> None:
        self.question_panel.set_status(i, s)
        self._refresh_progress()

    def _refresh_progress(self) -> None:
        text = self.flow.progress_label()
        self.toolbar.set_progress(text); self.question_panel.set_progress(text)
        self.toolbar.set_work_label(self.flow.work_label())

    def _on_mask_mode(self, m) -> None:
        self.settings.hint_mask = m

    def _on_chroma_toggled(self, on: bool) -> None:
        self.settings.chroma_enabled = on

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
        self.toolbar.set_recording(self.recorder.is_recording)

    def open_pen_settings(self) -> None:
        dlg = PenSettingsDialog(self.settings.pen(), self.canvas.color, self.canvas.base_width, self.fam, self)
        dlg.applied.connect(self.settings.set_pen)
        dlg.exec()

    def closeEvent(self, e):
        self.webcam_panel.shutdown()
        self.settings.sync()
        super().closeEvent(e)


class _NoCamera:
    def open(self) -> bool: return False
    def read(self): return None
    def release(self) -> None: pass
