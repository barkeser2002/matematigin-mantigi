import pytest

pymupdf = pytest.importorskip("pymupdf")

from matematigin_mantigi.core.pdf_import import PdfImportError, extract_questions  # noqa: E402


def make_pdf(path, pages=1):
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=1920, height=1080)
        page.insert_text((95, 240), f"{n}.", fontsize=40)
        page.insert_text((165, 240), "Iki ile uc toplami kactir?", fontsize=36)
        page.insert_text((165, 380), "A) 3     B) 5     C) 7     D) 8", fontsize=30)
        page.insert_text((1045, 100), "AKILLI IPUCLARI", fontsize=34)
        page.insert_text((1047, 200), "Once sayilari yaz.", fontsize=22)
        page.insert_text((1047, 300), "Sonra topla.", fontsize=22)
        page.insert_text((1047, 400), "Sonucu kontrol et.", fontsize=22)
    doc.save(str(path))
    doc.close()


def test_extract_pages(tmp_path):
    pdf = tmp_path / "t.pdf"
    make_pdf(pdf, pages=2)
    qs = extract_questions(pdf, tmp_path / "img")
    assert [q.id for q in qs] == ["S01", "S02"]
    q = qs[0]
    assert q.soru == "Iki ile uc toplami kactir?"
    assert q.options == ("3", "5", "7", "8")
    assert q.hints == ("Once sayilari yaz.", "Sonra topla.", "Sonucu kontrol et.")
    assert q.image is None and q.cevap == "" and q.konu == ""


def test_missing_pdf(tmp_path):
    with pytest.raises(PdfImportError):
        extract_questions(tmp_path / "yok.pdf")
