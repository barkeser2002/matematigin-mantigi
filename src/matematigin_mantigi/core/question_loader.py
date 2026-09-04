"""Excel şablonu: sütun doğrulama, örnek şablon üretme, soru yükleme."""
from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question

REQUIRED_COLUMNS = ("id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3", "cevap")


class QuestionTemplateError(ValueError):
    pass


def write_template(path: Path, with_samples: bool = True) -> Path:
    path = Path(path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sorular"
    ws.append(list(REQUIRED_COLUMNS))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    if with_samples:
        for q in SAMPLE_QUESTIONS:
            hints = list(q.hints) + [""] * (3 - len(q.hints))
            ws.append([q.id, q.konu, q.sinif, q.soru, *hints[:3], q.cevap])
    for col, width in zip("ABCDEFGH", (8, 16, 8, 60, 40, 40, 40, 16)):
        ws.column_dimensions[col].width = width
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


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
    idx = {c: header.index(c) for c in REQUIRED_COLUMNS}

    questions: list[Question] = []
    for row_no, row in enumerate(rows, start=2):
        cells = list(row) + [None] * (len(header) - len(row))
        if all(_text(c) == "" for c in cells):
            continue
        soru = _text(cells[idx["soru"]])
        if not soru:
            raise QuestionTemplateError(f"Satır {row_no}: 'soru' boş")
        qid = _text(cells[idx["id"]]) or f"S{len(questions) + 1}"
        sinif_raw = _text(cells[idx["sinif"]])
        try:
            sinif: int | None = int(float(sinif_raw)) if sinif_raw else None
        except ValueError:
            sinif = None
        hints = tuple(h for h in (_text(cells[idx[k]]) for k in ("ipucu1", "ipucu2", "ipucu3")) if h)
        questions.append(Question(qid, _text(cells[idx["konu"]]), sinif, soru, hints, _text(cells[idx["cevap"]])))
    wb.close()
    if not questions:
        raise QuestionTemplateError("Şablonda hiç soru yok")
    return questions
