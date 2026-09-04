"""Excel şablonu: sütun doğrulama, örnek şablon üretme, soru yükleme/yazma."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import openpyxl
from openpyxl.styles import Font

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question

REQUIRED_COLUMNS = ("id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3", "cevap")
OPTIONAL_COLUMNS = ("ipucu4", "a", "b", "c", "d", "gorsel")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
_WIDTHS = {"id": 8, "konu": 16, "sinif": 8, "soru": 60, "ipucu1": 40, "ipucu2": 40, "ipucu3": 40,
           "cevap": 16, "ipucu4": 40, "a": 14, "b": 14, "c": 14, "d": 14, "gorsel": 28}


class QuestionTemplateError(ValueError):
    pass


def write_questions(path: Path, questions: Sequence[Question]) -> Path:
    """Soruları tüm sütunlarla yazar. Görsel yolu xlsx klasörüne göre göreli ise öyle bırakılır."""
    path = Path(path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sorular"
    ws.append(list(ALL_COLUMNS))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for q in questions:
        hints = list(q.hints[:4]) + [""] * max(0, 4 - len(q.hints))
        opts = list(q.options[:4]) + [""] * max(0, 4 - len(q.options))
        ws.append([q.id, q.konu, q.sinif, q.soru, hints[0], hints[1], hints[2], q.cevap,
                   hints[3], *opts, q.image or ""])
    for i, col in enumerate(ALL_COLUMNS):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = _WIDTHS[col]
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def write_template(path: Path, with_samples: bool = True) -> Path:
    return write_questions(path, SAMPLE_QUESTIONS if with_samples else [])


def ensure_template(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        write_template(path)
    return path


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def load_questions(path: Path) -> list[Question]:
    path = Path(path)
    if not path.exists():
        raise QuestionTemplateError(f"Şablon bulunamadı: {path}")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [_text(c).lower() for c in (next(rows, None) or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise QuestionTemplateError("Eksik sütun(lar): " + ", ".join(missing))
    idx = {c: header.index(c) for c in ALL_COLUMNS if c in header}

    def cell(cells, key) -> str:
        return _text(cells[idx[key]]) if key in idx else ""

    questions: list[Question] = []
    for row_no, row in enumerate(rows, start=2):
        cells = list(row) + [None] * (len(header) - len(row))
        if all(_text(c) == "" for c in cells):
            continue
        soru = cell(cells, "soru")
        if not soru:
            raise QuestionTemplateError(f"Satır {row_no}: 'soru' boş")
        qid = cell(cells, "id") or f"S{len(questions) + 1}"
        sinif_raw = cell(cells, "sinif")
        try:
            sinif: int | None = int(float(sinif_raw)) if sinif_raw else None
        except ValueError:
            sinif = None
        hints = tuple(h for h in (cell(cells, k) for k in ("ipucu1", "ipucu2", "ipucu3", "ipucu4")) if h)
        options = tuple(o for o in (cell(cells, k) for k in ("a", "b", "c", "d")) if o)
        image_raw = cell(cells, "gorsel")
        image: str | None = None
        if image_raw:
            p = Path(image_raw)
            image = str(p if p.is_absolute() else (path.parent / p))
        questions.append(Question(qid, cell(cells, "konu"), sinif, soru, hints, cell(cells, "cevap"),
                                  options, image))
    wb.close()
    if not questions:
        raise QuestionTemplateError("Şablonda hiç soru yok")
    return questions
