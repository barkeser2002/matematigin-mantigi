import openpyxl
import pytest

from matematigin_mantigi.core.models import Question
from matematigin_mantigi.core.question_loader import (ALL_COLUMNS, REQUIRED_COLUMNS, QuestionTemplateError,
                                                      ensure_template, load_questions, write_questions,
                                                      write_template)


def test_write_then_load_round_trip(tmp_path):
    p = write_template(tmp_path / "sorular_sablon.xlsx")
    qs = load_questions(p)
    assert [q.id for q in qs] == ["S1", "S2", "S3"]
    assert qs[0].soru == "3x + 5 = 20 ise x kaçtır?" and qs[0].sinif == 7
    assert qs[2].hints == ("Paydaları eşitle: 6 ortak payda.", "2/3 = 4/6 olur; 4/6 + 1/6.", "Cevap: 5/6.")
    assert qs[0].options == ("3", "4", "5", "6") and qs[0].image is None
    wb = openpyxl.load_workbook(p)
    assert [c.value for c in wb.active[1]] == list(ALL_COLUMNS)
    assert wb.active["A1"].font.bold


def test_optional_columns_round_trip(tmp_path):
    q = Question("S9", "Konu", 8, "Soru?", ("h1", "h2", "h3", "h4"), "42", ("1", "2", "3", "4"), "img/s9.png")
    p = write_questions(tmp_path / "q.xlsx", [q])
    (tmp_path / "img").mkdir()
    loaded = load_questions(p)[0]
    assert loaded.hints == ("h1", "h2", "h3", "h4") and loaded.options == ("1", "2", "3", "4")
    assert loaded.image == str(tmp_path / "img" / "s9.png")         # xlsx klasörüne göre çözülür


def test_ensure_template_creates_once(tmp_path):
    p = tmp_path / "s.xlsx"
    assert not p.exists()
    ensure_template(p); mtime = p.stat().st_mtime
    ensure_template(p)
    assert p.stat().st_mtime == mtime


def test_missing_column_is_reported(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3"])   # cevap yok
    p = tmp_path / "bad.xlsx"; wb.save(p)
    with pytest.raises(QuestionTemplateError, match="cevap"):
        load_questions(p)


def test_required_only_header_still_loads(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S1", "Konu", "7", "Eski şablon sorusu", "a", "b", "c", "d"])
    p = tmp_path / "old.xlsx"; wb.save(p)
    q = load_questions(p)[0]
    assert q.options == () and q.image is None and q.hints == ("a", "b", "c")


def test_blank_rows_skipped_and_missing_hints_dropped(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S9", "Konu", "8", "Soru metni", "ipucu a", None, "", "42"])
    ws.append([None] * 8)
    ws.append(["S10", "Konu", None, "İkinci soru", None, None, None, "x"])
    p = tmp_path / "ok.xlsx"; wb.save(p)
    qs = load_questions(p)
    assert len(qs) == 2
    assert qs[0].hints == ("ipucu a",) and qs[0].sinif == 8
    assert qs[1].hints == () and qs[1].sinif is None


def test_missing_question_text_names_the_row(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S1", "Konu", "7", None, "a", "b", "c", "d"])
    p = tmp_path / "row.xlsx"; wb.save(p)
    with pytest.raises(QuestionTemplateError, match="2"):
        load_questions(p)


def test_empty_file_raises(tmp_path):
    p = write_template(tmp_path / "empty.xlsx", with_samples=False)
    with pytest.raises(QuestionTemplateError, match="hiç soru"):
        load_questions(p)
