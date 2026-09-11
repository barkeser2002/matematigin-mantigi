"""✎ Soru editörü: soruları görsel olarak oluştur/düzenle/sil, görsel seç, Excel'e kaydet."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator, QPixmap
from PyQt6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout,
                             QWidget)

from matematigin_mantigi.core.models import OPTION_LETTERS, Question
from matematigin_mantigi.core.question_loader import save_question_image, write_questions
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies


def _display_id(raw: str, row: int) -> str:
    """Listede gösterilecek kimlik: S07 gibi iki+ haneli kalıpları korur, S1 -> S01 gibi
    tek haneli sayıları iki haneye tamamlar, hiç sayı yoksa satır sırasına göre S01, S02… üretir."""
    if re.fullmatch(r"[A-Za-z]*\d{2,}", raw):
        return raw
    m = re.fullmatch(r"([A-Za-z]*)(\d+)", raw)
    if m:
        pre, num = m.groups()
        return f"{pre}{int(num):02d}"
    return f"S{row + 1:02d}"


def _card(title: str, fam: FontFamilies) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setStyleSheet(f"QFrame {{ background: {theme.PANEL}; border-radius: 6px; }}")
    col = QVBoxLayout(f); col.setContentsMargins(18, 14, 18, 16); col.setSpacing(8)
    t = QLabel(title); t.setFont(theme.font(fam, 12, 600, spacing_pct=110)); t.setStyleSheet(f"color: {theme.MUTED};")
    col.addWidget(t)
    return f, col


class QuestionEditorDialog(QDialog):
    """Soru dosyasının (xlsx) görsel düzenleyicisi. Kaydet, write_questions ile yazar ve saved yayar."""

    saved = pyqtSignal(object)      # list[Question]

    def __init__(self, questions: Sequence[Question], questions_path: Path, fam: FontFamilies, parent=None):
        super().__init__(parent)
        self.fam = fam
        self.questions_path = Path(questions_path)
        self.images_dir = self.questions_path.parent / "sorular_gorsel"
        self.questions: list[Question] = list(questions)
        self._current = -1
        self._suppress = False
        self._image_value: str | None = None

        self.setWindowTitle("Soru editörü")
        self.setMinimumWidth(760)
        root = QVBoxLayout(self); root.setContentsMargins(24, 20, 24, 20); root.setSpacing(14)
        title = QLabel("✎ Soru editörü"); title.setFont(theme.font(fam, 20, 600)); root.addWidget(title)

        body = QHBoxLayout(); body.setSpacing(16); root.addLayout(body, 1)
        body.addLayout(self._build_left(), 0)
        body.addWidget(self._build_right(), 1)

        # Alt düğmeler kaydırma alanının dışında; küçük ekranda (MacBook) Kaydet hep görünür.
        buttons = QHBoxLayout(); buttons.addStretch(1)
        self.cancel_button = QPushButton("Vazgeç"); self.cancel_button.setObjectName("pill")
        self.save_button = QPushButton("Kaydet"); self.save_button.setObjectName("accent")
        self.cancel_button.clicked.connect(self.reject); self.save_button.clicked.connect(self._save)
        buttons.addWidget(self.cancel_button); buttons.addWidget(self.save_button)
        root.addLayout(buttons)

        self._reload_list()
        if self.questions:
            self.list_widget.setCurrentRow(0)
        else:
            self.content.setEnabled(False)
        self._fit_to_screen()

    # --- yapı ---------------------------------------------------------------------
    def _build_left(self) -> QVBoxLayout:
        left = QVBoxLayout(); left.setSpacing(8)
        lab = QLabel("Sorular"); lab.setFont(theme.font(self.fam, 12, 600, spacing_pct=110))
        lab.setStyleSheet(f"color: {theme.MUTED};")
        left.addWidget(lab)
        self.list_widget = QListWidget(); self.list_widget.setMinimumWidth(220)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        left.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        self.add_button = QPushButton("Ekle"); self.add_button.setObjectName("pill")
        self.del_button = QPushButton("Sil"); self.del_button.setObjectName("pill")
        self.add_button.clicked.connect(self._add); self.del_button.clicked.connect(self._delete)
        row.addWidget(self.add_button); row.addWidget(self.del_button)
        left.addLayout(row)
        return left

    def _build_right(self) -> QScrollArea:
        self.content = QWidget(); col = QVBoxLayout(self.content)
        col.setContentsMargins(0, 0, 8, 0); col.setSpacing(14)

        base_card, bcol = _card("Temel bilgiler", self.fam)
        self.id_edit = QLineEdit(); self.konu_edit = QLineEdit()
        self.sinif_edit = QLineEdit(); self.sinif_edit.setValidator(QIntValidator(0, 99, self))
        self.sinif_edit.setPlaceholderText("boş bırakılabilir")
        self.id_edit.textEdited.connect(self._sync_label); self.konu_edit.textEdited.connect(self._sync_label)
        bcol.addLayout(self._field("Kimlik (id)", self.id_edit))
        bcol.addLayout(self._field("Konu", self.konu_edit))
        bcol.addLayout(self._field("Sınıf", self.sinif_edit))
        self.soru_edit = QPlainTextEdit(); self.soru_edit.setMinimumHeight(70)
        self.soru_edit.textChanged.connect(self._sync_label)
        bcol.addLayout(self._field("Soru metni", self.soru_edit))
        col.addWidget(base_card)

        opt_card, ocol = _card("Şıklar (A–D)", self.fam)
        self.option_edits: list[QLineEdit] = []
        for letter in OPTION_LETTERS:
            e = QLineEdit(); self.option_edits.append(e)
            ocol.addLayout(self._field(f"{letter} şıkkı", e))
        col.addWidget(opt_card)

        ans_card, acol = _card("Cevap ve ipuçları", self.fam)
        self.cevap_edit = QLineEdit()
        acol.addLayout(self._field("Cevap", self.cevap_edit))
        self.hint_edits: list[QLineEdit] = []
        for n in range(1, 5):
            e = QLineEdit(); self.hint_edits.append(e)
            acol.addLayout(self._field(f"İpucu {n}", e))
        col.addWidget(ans_card)

        img_card, icol = _card("Görsel", self.fam)
        row = QHBoxLayout()
        self.image_edit = QLineEdit(); self.image_edit.setReadOnly(True)
        self.image_edit.setPlaceholderText("Görsel seçilmedi")
        self.choose_image_button = QPushButton("Resim seç…"); self.choose_image_button.setObjectName("pill")
        self.clear_image_button = QPushButton("Kaldır"); self.clear_image_button.setObjectName("pill")
        self.choose_image_button.clicked.connect(self._pick_image)
        self.clear_image_button.clicked.connect(self._clear_image)
        row.addWidget(self.image_edit, 1); row.addWidget(self.choose_image_button); row.addWidget(self.clear_image_button)
        icol.addLayout(row)
        self.preview = QLabel("(görsel yok)"); self.preview.setStyleSheet(f"color: {theme.MUTED};")
        self.preview.setMinimumHeight(90)
        icol.addWidget(self.preview)
        col.addWidget(img_card)
        col.addStretch(1)

        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidget(self.content); self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.content.setStyleSheet("background: transparent;")
        return self.scroll

    def _field(self, label: str, widget: QWidget) -> QVBoxLayout:
        box = QVBoxLayout(); box.setSpacing(3)
        lab = QLabel(label); lab.setFont(theme.font(self.fam, 11, 500))
        box.addWidget(lab); box.addWidget(widget)
        return box

    def _fit_to_screen(self) -> None:
        screen = self.parent().screen() if self.parent() is not None else QApplication.primaryScreen()
        avail = screen.availableGeometry().height() if screen else 900
        self.resize(max(self.minimumWidth(), 820), min(720, avail - 60))

    # --- liste/form eşitleme ------------------------------------------------------
    def _format_label(self, raw_id: str, konu: str, soru: str, row: int) -> str:
        ident = _display_id(raw_id, row)
        detail = konu or (soru[:32] if soru else "(boş soru)")
        return f"{ident} · {detail}"

    def _label(self, q: Question, row: int) -> str:
        return self._format_label(q.id, q.konu, q.soru, row)

    def _reload_list(self) -> None:
        prev = self._suppress
        self._suppress = True
        self.list_widget.clear()
        for row, q in enumerate(self.questions):
            self.list_widget.addItem(self._label(q, row))
        self._suppress = prev

    def _sync_label(self, *_) -> None:
        i = self._current
        if 0 <= i < self.list_widget.count():
            label = self._format_label(self.id_edit.text().strip(), self.konu_edit.text().strip(),
                                        self.soru_edit.toPlainText().strip(), i)
            self.list_widget.item(i).setText(label)

    def _on_row_changed(self, row: int) -> None:
        if not self._suppress and self._current != row:
            self._commit_current()
        self._current = row
        if 0 <= row < len(self.questions):
            self.content.setEnabled(True)
            self._populate(self.questions[row])
        else:
            self.content.setEnabled(False)

    def _populate(self, q: Question) -> None:
        self.id_edit.setText(q.id)
        self.konu_edit.setText(q.konu)
        self.sinif_edit.setText("" if q.sinif is None else str(q.sinif))
        self.soru_edit.setPlainText(q.soru)
        opts = list(q.options) + [""] * (4 - len(q.options))
        for e, val in zip(self.option_edits, opts):
            e.setText(val)
        hints = list(q.hints) + [""] * (4 - len(q.hints))
        for e, val in zip(self.hint_edits, hints):
            e.setText(val)
        self.cevap_edit.setText(q.cevap)
        self._image_value = self._to_relative(q.image)
        self.image_edit.setText(self._image_value or "")
        self._update_preview()

    def _question_from_form(self) -> Question:
        raw = self.sinif_edit.text().strip()
        sinif = int(raw) if raw else None
        return Question(
            id=self.id_edit.text().strip(),
            konu=self.konu_edit.text().strip(),
            sinif=sinif,
            soru=self.soru_edit.toPlainText().strip(),
            hints=tuple(e.text().strip() for e in self.hint_edits),
            cevap=self.cevap_edit.text().strip(),
            options=tuple(e.text().strip() for e in self.option_edits),
            image=self._image_value or None,
        )

    def _commit_current(self) -> None:
        i = self._current
        if self._suppress or not (0 <= i < len(self.questions)):
            return
        self.questions[i] = self._question_from_form()

    # --- görsel -------------------------------------------------------------------
    def _to_relative(self, image: str | None) -> str | None:
        if not image:
            return None
        p = Path(image)
        if p.is_absolute():
            try:
                return p.relative_to(self.questions_path.parent).as_posix()
            except ValueError:
                return p.as_posix()
        return p.as_posix()

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Soru görseli", "", "Görsel (*.png *.jpg *.jpeg)")
        if not path:
            return
        self._image_value = save_question_image(Path(path), self.images_dir)
        self.image_edit.setText(self._image_value)
        self._update_preview()

    def _clear_image(self) -> None:
        self._image_value = None
        self.image_edit.clear()
        self._update_preview()

    def _update_preview(self) -> None:
        pm = QPixmap()
        if self._image_value:
            abs_path = self.questions_path.parent / self._image_value
            if abs_path.exists():
                pm = QPixmap(str(abs_path))
        if pm.isNull():
            self.preview.setPixmap(QPixmap()); self.preview.setText("(görsel yok)")
        else:
            self.preview.setText("")
            self.preview.setPixmap(pm.scaled(160, 120, Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))

    # --- ekle/sil -----------------------------------------------------------------
    def _new_id(self) -> str:
        used = {q.id for q in self.questions}
        n = len(self.questions) + 1
        while f"S{n:02d}" in used:
            n += 1
        return f"S{n:02d}"

    def _add(self) -> None:
        self._commit_current()
        self.questions.append(Question(self._new_id(), "", None, "", (), "", (), None))
        self._reload_list()
        self.list_widget.setCurrentRow(len(self.questions) - 1)

    def _delete(self) -> None:
        row = self.list_widget.currentRow()
        if not (0 <= row < len(self.questions)):
            return
        del self.questions[row]
        self._current = -1                # kaydırılan modele eski formu yazma
        self._reload_list()
        if self.questions:
            self.list_widget.setCurrentRow(min(row, len(self.questions) - 1))
        else:
            self.content.setEnabled(False)

    # --- kaydet -------------------------------------------------------------------
    def value(self) -> list[Question]:
        self._commit_current()
        return list(self.questions)

    def _save(self) -> None:
        self._commit_current()
        for i, q in enumerate(self.questions):
            if not q.soru.strip():
                QMessageBox.warning(self, "Eksik soru", f"{i + 1}. sıradaki sorunun metni boş; lütfen doldurun.")
                self.list_widget.setCurrentRow(i)
                return
        write_questions(self.questions_path, self.questions)
        self.saved.emit(list(self.questions))
        self.accept()
