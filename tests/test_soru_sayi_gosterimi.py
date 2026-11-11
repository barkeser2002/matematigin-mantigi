"""Excel değer hücrelerinin Türkçe gösterimi; dosya ve yedek salt okunur kalır."""
from datetime import date, datetime, time, timedelta

import openpyxl
from openpyxl.utils import get_column_letter
import pytest

from matematigin_mantigi.core.question_loader import (ALL_COLUMNS, QuestionTemplateError,
                                                      backup_path, load_backup, load_questions)


VALUE_COLUMNS = ("soru", "ipucu1", "ipucu2", "ipucu3", "ipucu4", "cevap", "a", "b", "c", "d")


def _workbook(tmp_path, column, value, number_format="General"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(ALL_COLUMNS))
    ws.append(["S1", "Konu", 7, "Soru?"])
    cell = ws.cell(2, ALL_COLUMNS.index(column) + 1, value)
    cell.number_format = number_format
    path = tmp_path / "sorular.xlsx"
    wb.save(path)
    wb.close()
    return path


def _value(question, column):
    if column.startswith("ipucu"):
        return question.hints[0]
    if column in ("a", "b", "c", "d"):
        return question.options[0]
    return getattr(question, column)


@pytest.mark.parametrize("column", VALUE_COLUMNS)
@pytest.mark.parametrize("value, expected", [(2.5, "2,5"), (-0.125, "-0,125"), (3.0, "3"), (0, "0")])
def test_numeric_value_cells_use_turkish_decimal(tmp_path, column, value, expected):
    path = _workbook(tmp_path, column, value)
    assert _value(load_questions(path)[0], column) == expected


@pytest.mark.parametrize("column", VALUE_COLUMNS)
@pytest.mark.parametrize("value, number_format, expected", [
    (0.5, "0%", "%50"), (0.125, "0.0%", "%12,5"),
    (0.29, "0%", "%29"), (-0.075, "0.0%", "%-7,5"), (0, "0%", "%0"),
    (2.5, '0.0"%"', "2,5"), (2.5, r"0.0\%", "2,5"),
])
def test_percentage_cells_use_percent_prefix(tmp_path, column, value, number_format, expected):
    path = _workbook(tmp_path, column, value, number_format)
    assert _value(load_questions(path)[0], column) == expected


@pytest.mark.parametrize("column", VALUE_COLUMNS)
@pytest.mark.parametrize("value, number_format", [
    (date(2026, 2, 1), "yyyy-mm-dd"), (datetime(2026, 2, 1, 9, 30), "yyyy-mm-dd hh:mm"),
    (time(9, 30), "hh:mm"), (timedelta(hours=30), "[h]:mm:ss"), (46054, "d/m/yyyy"),
])
@pytest.mark.parametrize("loader", [load_questions, load_backup])
def test_date_cells_are_rejected_without_changing_file_or_backup(tmp_path, column, value, number_format, loader):
    path = _workbook(tmp_path, column, value, number_format)
    before = path.read_bytes()
    bak = backup_path(path)
    bak.write_bytes(before)
    with pytest.raises(QuestionTemplateError) as error:
        loader(path)
    message = str(error.value)
    coordinate = f"{get_column_letter(ALL_COLUMNS.index(column) + 1)}2"
    assert "Satır 2" in message and column in message and coordinate in message
    assert "hücreyi Metin yapın" in message
    assert path.read_bytes() == before and bak.read_bytes() == before
    # Hata sonrasında Windows'ta da dosya tutamağı açık kalmamalı.
    for original in (path, bak):
        moved = original.with_name(original.name + ".tasindi")
        original.rename(moved)
        moved.rename(original)


@pytest.mark.parametrize("column", VALUE_COLUMNS)
@pytest.mark.parametrize("text", ["2.5", "%50", "1/2", "2026-02-01", "  2,5\nMetin  "])
def test_text_cells_remain_verbatim_even_with_numeric_or_date_format(tmp_path, column, text):
    path = _workbook(tmp_path, column, text, "yyyy-mm-dd")
    assert _value(load_questions(path)[0], column) == text


def test_identifier_and_grade_keep_existing_conversion(tmp_path):
    path = _workbook(tmp_path, "id", 2.5, "0%")
    wb = openpyxl.load_workbook(path)
    wb.active["C2"] = 7.5
    wb.active["C2"].number_format = "0%"
    wb.save(path)
    wb.close()
    question = load_questions(path)[0]
    assert question.id == "2.5" and question.sinif == 7
