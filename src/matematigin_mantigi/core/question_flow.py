"""Soru akışı: sıra, durumlar, soru gizleme, ipucu gezinme ve açma durumu."""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import QObject, pyqtSignal

from matematigin_mantigi.core.models import Question, QuestionStatus


class QuestionFlow(QObject):
    questionLeaving = pyqtSignal(int)
    questionChanged = pyqtSignal(int)
    statusChanged = pyqtSignal(int, object)
    progressChanged = pyqtSignal(int, int)
    questionVisibilityChanged = pyqtSignal(bool)
    hintChanged = pyqtSignal(int, int)
    hintRevealChanged = pyqtSignal(int, int, bool)

    def __init__(self, questions: Sequence[Question], parent: QObject | None = None):
        super().__init__(parent)
        self._questions: tuple[Question, ...] = tuple(questions)
        self._index = 0
        self._status = [QuestionStatus.WAITING for _ in self._questions]
        self._shown = True
        self._hint_index = 0
        self._revealed: set[tuple[int, int]] = set()

    # --- read ------------------------------------------------------------------
    @property
    def questions(self) -> tuple[Question, ...]:
        return self._questions

    @property
    def index(self) -> int:
        return self._index

    @property
    def current(self) -> Question:
        return self._questions[self._index]

    def status(self, i: int | None = None) -> QuestionStatus:
        i = self._index if i is None else i
        return self._status[i] if 0 <= i < len(self._status) else QuestionStatus.WAITING

    def done_count(self) -> int:
        return sum(1 for s in self._status if s == QuestionStatus.DONE)

    def is_question_shown(self) -> bool:
        return self._shown

    def hint_index(self) -> int:
        return self._hint_index

    def hint_count(self) -> int:
        return len(self.current.hints) if self._questions else 0

    def is_revealed(self, hint: int | None = None) -> bool:
        hint = self._hint_index if hint is None else hint
        return (self._index, hint) in self._revealed

    def work_label(self) -> str:
        return "Soruyu tamamla ✓" if self.status() == QuestionStatus.WORKING else "Soruyu işle"

    def progress_label(self) -> str:
        total = len(self._questions)
        base = f"{self.done_count()}/{total} tamamlandı"
        return f"{base} · {self.current.id}" if total else base

    # --- mutate ----------------------------------------------------------------
    def _set_status(self, i: int, s: QuestionStatus) -> None:
        if self._status[i] != s:
            self._status[i] = s
            self.statusChanged.emit(i, s)
            self.progressChanged.emit(self.done_count(), len(self._questions))

    def set_questions(self, questions: Sequence[Question]) -> None:
        """Soru listesini tümüyle değiştirir; sıra başa döner, durumlar ve ipucu durumu sıfırlanır.
        Arayüz tazelemesini çağıran taraf yapar (MainWindow._on_question_changed)."""
        self._questions = tuple(questions)
        self._index = 0
        self._status = [QuestionStatus.WAITING for _ in self._questions]
        self._hint_index = 0
        self._revealed = set()

    def select(self, i: int) -> None:
        if not self._questions or not 0 <= i < len(self._questions):
            return
        if i != self._index:
            self.questionLeaving.emit(self._index)
        self._index = i
        self._hint_index = 0
        self.questionChanged.emit(i)
        self.progressChanged.emit(self.done_count(), len(self._questions))
        self.hintChanged.emit(0, self.hint_count())

    def toggle_work(self) -> None:
        if not self._questions:
            return
        s = self.status()
        self._set_status(self._index, QuestionStatus.DONE if s == QuestionStatus.WORKING
                         else QuestionStatus.WORKING)

    def next_question(self) -> None:
        if not self._questions:
            return
        if self.status() == QuestionStatus.WORKING:
            self._set_status(self._index, QuestionStatus.DONE)
        self.select((self._index + 1) % len(self._questions))

    def prev_question(self) -> None:
        """Önceki sayfaya döner; durumları değiştirmez."""
        if not self._questions:
            return
        self.select((self._index - 1) % len(self._questions))

    def show_question(self) -> None:
        if not self._shown:
            self._shown = True
            self.questionVisibilityChanged.emit(True)

    def hide_question(self) -> None:
        if self._shown:
            self._shown = False
            self.questionVisibilityChanged.emit(False)

    def set_hint_index(self, i: int) -> None:
        n = self.hint_count()
        i = max(0, min(n - 1, i)) if n else 0
        if i != self._hint_index:
            self._hint_index = i
            self.hintChanged.emit(i, n)

    def hint_prev(self) -> None:
        self.set_hint_index(self._hint_index - 1)

    def hint_next(self) -> None:
        self.set_hint_index(self._hint_index + 1)

    def toggle_reveal(self, hint: int | None = None) -> None:
        if not self.hint_count():
            return
        hint = self._hint_index if hint is None else hint
        key = (self._index, hint)
        if key in self._revealed:
            self._revealed.discard(key)
        else:
            self._revealed.add(key)
        self.hintRevealChanged.emit(self._index, hint, key in self._revealed)
