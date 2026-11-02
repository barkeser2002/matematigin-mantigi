import errno
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import openpyxl
import pytest
from PyQt6.QtCore import QLocale, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from matematigin_mantigi.core.models import Question, SAMPLE_QUESTIONS
from matematigin_mantigi.core.question_loader import load_questions, save_question_image, write_questions
from matematigin_mantigi.ui import question_editor as qe
from matematigin_mantigi.ui.question_editor import QuestionEditorDialog, _display_id
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


@pytest.fixture(autouse=True)
def no_modal_box_blocks(monkeypatch):
    """Yanlış davranışta (gerileme, mutasyon) açılan gerçek modal kutu offscreen'de exec()'te sonsuza dek bekler: test
    kırmızı yerine DONAR. Kutu beklemeyen testte açılırsa kaydedilir, 'Kaydetmeden dön' seçilmiş sayılır ve test sonda
    düşer. Kutuyu bekleyen testler _capture_warnings / _answer ile bunun üstüne yazar."""
    unexpected = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda _p, title, text, *a, **k: unexpected.append(text)))
    monkeypatch.setattr(QMessageBox, "exec", lambda box: unexpected.append(box.text()) or 0)
    yield
    assert not unexpected, f"beklenmeyen kutu: {unexpected}"


def _dialog(qtbot, tmp_path, questions=None):
    path = tmp_path / "sorular_sablon.xlsx"
    d = QuestionEditorDialog(list(questions or SAMPLE_QUESTIONS), path, FAM)
    qtbot.addWidget(d)
    d.show()
    return d, path


def test_list_populates_and_selection_fills_form(qtbot, tmp_path):
    d, _ = _dialog(qtbot, tmp_path)
    assert d.list_widget.count() == 3
    assert d.list_widget.item(0).text() == "S01 · Denklemler"
    assert d.id_edit.text() == "S1" and d.konu_edit.text() == "Denklemler"
    assert d.soru_edit.toPlainText() == SAMPLE_QUESTIONS[0].soru
    assert [e.text() for e in d.option_edits] == ["3", "4", "5", "6"]
    d.list_widget.setCurrentRow(1)
    assert d.id_edit.text() == "S2" and d.konu_edit.text() == "Geometri"
    assert d.sinif_edit.text() == "6"


def test_edit_and_save_round_trips(qtbot, tmp_path):
    d, path = _dialog(qtbot, tmp_path)
    d.soru_edit.setPlainText("Yeni soru?")
    for e, val in zip(d.option_edits, ("W", "X", "Y", "Z")):
        e.setText(val)
    d.cevap_edit.setText("Z")
    d.save_button.click()
    loaded = load_questions(path)
    assert [q.id for q in loaded] == ["S1", "S2", "S3"]
    assert loaded[0].soru == "Yeni soru?"
    assert loaded[0].options == ("W", "X", "Y", "Z") and loaded[0].cevap == "Z"
    assert loaded[1].soru == SAMPLE_QUESTIONS[1].soru        # dokunulmayan satır korunur


def test_add_and_delete_rows(qtbot, tmp_path):
    d, _ = _dialog(qtbot, tmp_path)
    d.add_button.click()
    assert d.list_widget.count() == 4 and len(d.questions) == 4
    assert d.list_widget.currentRow() == 3 and d.content.isEnabled()
    d.list_widget.setCurrentRow(1)
    d.del_button.click()
    assert d.list_widget.count() == 3 and len(d.questions) == 3
    assert [q.id for q in d.questions] == ["S1", "S3", "S04"]


@pytest.fixture
def turkish_locale():
    """Öğretmenin Mac'i Türkçe bölge ayarında: '.' binlik ayırıcı. Varsayılan yerel ayar global durum,
    test sonunda geri yüklenir."""
    prev = QLocale()
    QLocale.setDefault(QLocale(QLocale.Language.Turkish, QLocale.Country.Turkey))
    yield
    QLocale.setDefault(prev)


@pytest.mark.parametrize("typed, expected", [("7.", 7), ("+", None), ("12", 12)])
def test_sinif_typed_ordinal_does_not_crash_save(qtbot, tmp_path, turkish_locale, typed, expected):
    """q#1: Türkçe sıra sayısı yazımı '7.' (ya da tek '+') Sınıf'a yazılıp Kaydet'e basılınca int() yuvada
    patlıyor, PyQt6 süreci (süren kayıtla birlikte) kapatıyordu. Alan yalnız rakam kabul etmeli."""
    d, path = _dialog(qtbot, tmp_path)
    d.sinif_edit.clear()
    qtbot.keyClicks(d.sinif_edit, typed)
    assert d.sinif_edit.text().isdigit() or d.sinif_edit.text() == ""
    d.save_button.click()
    assert load_questions(path)[0].sinif == expected


def test_sinif_ordinal_then_row_change_keeps_number(qtbot, tmp_path, turkish_locale):
    """Aynı çökme başka satıra geçerken de (_on_row_changed -> _commit_current) oluyordu."""
    d, _ = _dialog(qtbot, tmp_path)
    d.sinif_edit.clear()
    qtbot.keyClicks(d.sinif_edit, "7.")
    d.list_widget.setCurrentRow(1)
    assert d.questions[0].sinif == 7


def test_sinif_parse_tolerates_non_digits_set_programmatically(qtbot, tmp_path):
    """setText doğrulayıcıyı atlar; form okuması yine de çökmemeli (rakam dışı karakterler atılır)."""
    d, _ = _dialog(qtbot, tmp_path)
    d.sinif_edit.setText("7.")
    assert d._question_from_form().sinif == 7
    d.sinif_edit.setText("+")
    assert d._question_from_form().sinif is None


def test_empty_soru_blocks_save(qtbot, tmp_path, monkeypatch):
    d, path = _dialog(qtbot, tmp_path)
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a[1])))
    d.add_button.click()            # metni boş yeni satır seçili
    d.save_button.click()
    assert shown and shown[0] == "Eksik soru"
    assert not path.exists()         # boş soru varken yazılmaz


def test_image_pick_copies_and_round_trips(qtbot, tmp_path, monkeypatch):
    png = tmp_path / "resim.png"
    img = QImage(10, 10, QImage.Format.Format_RGB32); img.fill(Qt.GlobalColor.red); img.save(str(png))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(png), "")))
    d, path = _dialog(qtbot, tmp_path)
    d.list_widget.setCurrentRow(0)
    d.choose_image_button.click()
    assert d.image_edit.text() == "sorular_gorsel/resim.png"
    assert (tmp_path / "sorular_gorsel" / "resim.png").exists()
    d.save_button.click()
    loaded = load_questions(path)
    assert loaded[0].image == str(tmp_path / "sorular_gorsel" / "resim.png")


def test_saved_signal_fires_with_edited_list(qtbot, tmp_path):
    d, _ = _dialog(qtbot, tmp_path)
    with qtbot.waitSignal(d.saved) as sig:
        d.save_button.click()
    assert isinstance(sig.args[0], list) and [q.id for q in sig.args[0]] == ["S1", "S2", "S3"]


@pytest.mark.parametrize("raw, row, expected", [
    ("S1", 0, "S01"),
    ("S07", 6, "S07"),
    ("", 2, "S03"),
    ("X9", 0, "X09"),
    ("S123", 0, "S123"),      # 3+ haneli id aynen kalır, kısaltılmaz/yeniden doldurulmaz
    ("SORU-A", 4, "S05"),     # tamamen sayısız/uyumsuz id -> satır sırasına göre üretilir
])
def test_display_id_table(raw, row, expected):
    assert _display_id(raw, row) == expected


def test_label_shows_konu_when_present(qtbot, tmp_path):
    d, _ = _dialog(qtbot, tmp_path)
    assert d.list_widget.item(0).text() == "S01 · Denklemler"


def test_label_falls_back_to_soru_start_when_konu_empty(qtbot, tmp_path):
    q = Question("S1", "", 7, "Bu sorunun konusu boş bırakıldı ama metni uzun", (), "", ())
    d, _ = _dialog(qtbot, tmp_path, questions=[q])
    label = d.list_widget.item(0).text()
    assert label == "S01 · " + q.soru[:32]
    assert label != "S01"                 # çıplak id'ye çökmemeli


def test_label_shows_placeholder_when_konu_and_soru_empty(qtbot, tmp_path):
    q = Question("S1", "", None, "", (), "", ())
    d, _ = _dialog(qtbot, tmp_path, questions=[q])
    assert d.list_widget.item(0).text() == "S01 · (boş soru)"


def test_sync_label_matches_reload_label_format(qtbot, tmp_path):
    """Satır düzenlenirken (_sync_label) ve liste yeniden yüklenirken (_reload_list, _label
    üzerinden) üretilen etiketler bire bir aynı olmalı; farklıysa alan düzenlenince biçim değişir."""
    d, _ = _dialog(qtbot, tmp_path)
    d.list_widget.setCurrentRow(0)
    d.konu_edit.setText("")
    d.konu_edit.textEdited.emit("")
    live_label = d.list_widget.item(0).text()
    reloaded_q = d._question_from_form()
    reload_label = d._label(reloaded_q, 0)
    assert live_label == reload_label


def test_format_label_strips_whitespace_regardless_of_source(qtbot, tmp_path):
    """_format_label boşluğu kendi içinde temizlemeli; aksi halde henüz temizlenmemiş bir veri
    kaynağından (ör. yeni bir içe aktarıcı) gelen boşluklu id/konu/soru, _label (liste yüklenirken)
    ile _sync_label (alan düzenlenirken canlı) arasında farklı biçimler üretir — brief'in uyardığı
    tam senaryo ("satır düzenlenince etiket biçimi değişir").

    Boşluklu soru 2. satırda (index 1) tutuluyor: yapıcı yalnız 0. satırı seçip formu doldurduğu
    için (bu da soru_edit.textChanged üzerinden _sync_label'ı dolaylı tetikler), 1. satırın etiketi
    _reload_list -> _label'ın ürettiği hâliyle dokunulmadan kalır; sonra o satıra "geçilmiş" gibi
    formu doldurup _sync_label'ın ürettiğiyle karşılaştırıyoruz."""
    clean = Question("S1", "Denklemler", 7, "orijinal soru", (), "", ())
    messy = Question("  S5  ", "  Cebir  ", None, "  2x = 8 ise x kaçtır?  ", (), "", ())
    d, _ = _dialog(qtbot, tmp_path, questions=[clean, messy])
    reload_label = d.list_widget.item(1).text()          # _reload_list -> _label(messy, 1), henüz dokunulmadı

    d._current = 1
    d.id_edit.setText(messy.id)
    d.konu_edit.setText(messy.konu)
    d.soru_edit.setPlainText(messy.soru)                  # textChanged -> _sync_label otomatik tetiklenir
    live_label = d.list_widget.item(1).text()

    assert reload_label == live_label == "S05 · Cebir"


def test_new_id_is_zero_padded_and_avoids_collisions(qtbot, tmp_path):
    d, _ = _dialog(qtbot, tmp_path)
    assert d._new_id() == "S04"
    d.questions.append(Question("S04", "", None, "x", (), "", ()))
    assert d._new_id() == "S05"


def test_save_question_image_disambiguates(tmp_path):
    a = tmp_path / "a.png"; a.write_bytes(b"AAA")
    b = tmp_path / "b.png"; b.write_bytes(b"BBB")
    images = tmp_path / "sorular_gorsel"
    rel1 = save_question_image(a, images)
    assert rel1 == "sorular_gorsel/a.png"
    # aynı içerik yeniden: kopya çoğaltılmaz
    assert save_question_image(a, images) == "sorular_gorsel/a.png"
    # farklı içerik, aynı ad: '_1' eki
    (tmp_path / "sub").mkdir(); c = tmp_path / "sub" / "a.png"; c.write_bytes(b"CCC")
    rel3 = save_question_image(c, images)
    assert rel3 == "sorular_gorsel/a_1.png"
    assert (images / "a.png").read_bytes() == b"AAA" and (images / "a_1.png").read_bytes() == b"CCC"


# --- Kaydet hataları ve yapıştırılan kontrol karakterleri (#3) -----------------------------------------------
def _capture_warnings(monkeypatch) -> list:
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda _parent, title, text, *a, **k: shown.append(
        (title, text))))
    return shown


def test_save_while_file_is_open_in_excel_keeps_dialog_and_edits(qtbot, tmp_path, monkeypatch):
    """e2e#6/q#2: Windows'ta xlsx Excel'de açıkken wb.save PermissionError fırlatıyor, yakalanmadığı için uygulama
    (süren kayıtla) düşüyor ve editördeki her düzenleme kayboluyordu. Artık Türkçe mesaj, pencere açık kalır;
    Excel kapatılınca yeniden Kaydet düzenlemeleri yazar."""
    import openpyxl
    shown = _capture_warnings(monkeypatch)
    real_save = openpyxl.Workbook.save

    def locked(self, filename):
        raise PermissionError(13, "Permission denied", str(filename))
    monkeypatch.setattr(openpyxl.Workbook, "save", locked)
    d, path = _dialog(qtbot, tmp_path)
    saved = []
    d.saved.connect(saved.append)
    d.soru_edit.setPlainText("Excel açıkken düzenlendi?")
    d.save_button.click()
    assert shown and shown[0][0] == "Kaydedilemedi" and "Excel" in shown[0][1]
    assert d.isVisible() and d.result() != d.DialogCode.Accepted and saved == []
    edited = "Excel açıkken düzenlendi?"
    assert d.soru_edit.toPlainText() == edited and d.questions[0].soru == edited
    assert not path.exists()

    monkeypatch.setattr(openpyxl.Workbook, "save", real_save)         # Excel kapatıldı
    d.save_button.click()
    assert load_questions(path)[0].soru == "Excel açıkken düzenlendi?"
    assert saved and d.result() == d.DialogCode.Accepted


def test_save_other_os_error_shows_reason_and_keeps_dialog(qtbot, tmp_path, monkeypatch):
    import errno
    import openpyxl
    shown = _capture_warnings(monkeypatch)

    def full(self, filename):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(openpyxl.Workbook, "save", full)
    d, _ = _dialog(qtbot, tmp_path)
    d.save_button.click()
    assert shown and shown[0][0] == "Kaydedilemedi" and "diskte yer kalmadı" in shown[0][1]
    assert d.isVisible() and d.result() != d.DialogCode.Accepted


def test_pasted_control_characters_are_cleaned_and_save_succeeds(qtbot, tmp_path):
    """q#2: PDF/Word'den kopyalanan metindeki kontrol karakterleri (\\x03, \\x0b …) alanlarda kalıyor, openpyxl
    IllegalCharacterError fırlatıyor ve uygulama düşüyordu. Kontrol karakterleri atılır; Word/PowerPoint'in satır
    sonu olarak kullandığı dikey sekme satır sonu olur; sekme ve satır sonu korunur."""
    from PyQt6.QtWidgets import QApplication
    d, path = _dialog(qtbot, tmp_path)
    clip = QApplication.clipboard()
    clip.setText("PDF'den kopya\x03 metin\x0bikinci satır\tsekme")
    d.soru_edit.clear(); d.soru_edit.paste()
    assert "\x03" in d.soru_edit.toPlainText()                 # yapıştırma karakteri alanda bırakıyor
    clip.setText("ipucu\x02 bir\x1f")
    d.hint_edits[0].clear(); d.hint_edits[0].paste()
    d.konu_edit.setText("Kon\x00u")
    d.save_button.click()
    q = load_questions(path)[0]
    assert q.soru == "PDF'den kopya metin\nikinci satır\tsekme"
    assert q.hints[0] == "ipucu bir" and q.konu == "Konu"


def test_image_copy_error_shows_message_and_keeps_previous_image(qtbot, tmp_path, monkeypatch):
    """Görsel sorular_gorsel'e kopyalanamazsa (izin, dolu disk) yuva patlamaz; mesaj gösterilir, eski görsel kalır."""
    import shutil
    png = tmp_path / "resim.png"
    img = QImage(10, 10, QImage.Format.Format_RGB32); img.fill(Qt.GlobalColor.red); img.save(str(png))
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(png), "")))

    def denied(*_a, **_k):
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(shutil, "copyfile", denied)
    shown = _capture_warnings(monkeypatch)
    d, _ = _dialog(qtbot, tmp_path)
    before = d.image_edit.text()
    d.choose_image_button.click()
    assert shown and shown[0][0] == "Görsel eklenemedi" and "erişim izni yok" in shown[0][1]
    assert d.image_edit.text() == before and d.isVisible()


# --- Kaydet yarıda kalırsa dosya bozulmaz, mesaj bunu doğru söyler (B-2) --------------------------------------
def _existing(tmp_path) -> tuple:
    path = tmp_path / "sorular_sablon.xlsx"
    write_questions(path, SAMPLE_QUESTIONS)
    return path, path.read_bytes()


def test_save_failing_mid_write_keeps_the_file_and_says_so(qtbot, tmp_path, monkeypatch):
    """B-2: Kaydet yazımın ortasında hata alınca (dolu disk) dosya yarım kalıyor, uyarı bunu söylemiyordu; Vazgeç'ten
    sonra uygulama bir daha açılmıyordu. Artık dosya eski hâliyle kalır ve mesaj bunu söyler."""
    path, before = _existing(tmp_path)
    shown = _capture_warnings(monkeypatch)

    def half_written(self, filename):
        Path(filename).write_bytes(b"PK\x03\x04 yarim")
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(openpyxl.Workbook, "save", half_written)
    d, _ = _dialog(qtbot, tmp_path)
    d.soru_edit.setPlainText("Yarıda kalan kayıt")
    d.save_button.click()
    assert shown and shown[0][0] == "Kaydedilemedi" and "diskte yer kalmadı" in shown[0][1]
    assert "değişmedi" in shown[0][1] and d.isVisible()
    assert path.read_bytes() == before and len(load_questions(path)) == 3


def test_save_refused_while_open_in_excel_keeps_the_file(qtbot, tmp_path, monkeypatch):
    """Windows'ta dosya Excel'de açıkken yeni sürüm yerine konamaz (os.replace PermissionError): dosya değişmez, mesaj
    Excel'i kapatıp yeniden Kaydet'i söyler ve dosyanın değişmediğini bildirir."""
    real_replace = os.replace
    path, before = _existing(tmp_path)

    def locked(src, dst, *a, **k):
        if os.fspath(dst) == os.fspath(path):
            raise PermissionError(13, "The process cannot access the file", os.fspath(dst))
        return real_replace(src, dst, *a, **k)
    monkeypatch.setattr(os, "replace", locked)
    shown = _capture_warnings(monkeypatch)
    d, _ = _dialog(qtbot, tmp_path)
    d.soru_edit.setPlainText("Excel açıkken")
    d.save_button.click()
    assert shown and shown[0][0] == "Kaydedilemedi" and "Excel" in shown[0][1] and "değişmedi" in shown[0][1]
    assert path.read_bytes() == before and d.isVisible()


@pytest.mark.parametrize("err", [zipfile.BadZipFile("bozuk zip"), KeyError("xl/workbook.xml"),
                                 ValueError("geçersiz hücre değeri")], ids=["BadZipFile", "KeyError", "ValueError"])
def test_unexpected_save_error_shows_a_message_and_keeps_the_dialog(qtbot, tmp_path, monkeypatch, err):
    """Kaydet yalnız OSError'ı yakalıyordu: çalışma kitabından gelen BadZipFile, KeyError ya da ValueError yuvadan
    kaçıp genel hata kutusuna düşüyor, düzenlemeler pencereyle kayboluyordu. Hepsi mesajla, pencere açık kalır."""
    from matematigin_mantigi.ui import question_editor

    def boom(*_a, **_k):
        raise err
    monkeypatch.setattr(question_editor, "write_questions", boom)
    shown = _capture_warnings(monkeypatch)
    d, _ = _dialog(qtbot, tmp_path)
    saved = []
    d.saved.connect(saved.append)
    d.save_button.click()
    assert shown and shown[0][0] == "Kaydedilemedi" and "değişmedi" in shown[0][1]
    assert d.isVisible() and saved == []


# --- okunamayan soru dosyasının üzerine yazılmaz (#4) ---------------------------------------------------------
@pytest.mark.parametrize("kind", ["yarim", "sutun"])
def test_save_does_not_overwrite_an_unreadable_question_file(qtbot, tmp_path, monkeypatch, kind):
    """#4: açılışta okunamayan soru dosyası (uygulama örnek sorularla açılır) editörde Kaydet'le örnek soruların
    altında kalıyordu; öğretmenin gerçek soruları o dosyada olabilir (yazımı yarıda kalmış xlsx, sütunları farklı
    kendi çizelgesi). Kaydet o dosyanın üzerine yazmaz, sebebi ve ne yapılacağını söyler, pencere açık kalır;
    öğretmen dosyayı düzeltip ya da kaldırıp yeniden Kaydet'e basınca yazılır."""
    path = tmp_path / "sorular_sablon.xlsx"
    if kind == "yarim":
        write_questions(path, SAMPLE_QUESTIONS)
        path.write_bytes(path.read_bytes()[:2289])
    else:
        wb = openpyxl.Workbook()
        wb.active.append(["id", "soru", "ogretmen_notu"]); wb.active.append(["S1", "Gerçek soru", "not"])
        wb.save(path)
    before = path.read_bytes()
    shown = _capture_warnings(monkeypatch)
    d, _ = _dialog(qtbot, tmp_path)
    saved = []
    d.saved.connect(saved.append)
    d.save_button.click()
    assert shown and shown[0][0] == "Kaydedilmedi" and "sorular_sablon.xlsx okunamıyor" in shown[0][1]
    assert path.read_bytes() == before and d.isVisible() and saved == []
    path.rename(tmp_path / "eski_sorular.xlsx")                      # öğretmen dosyayı klasörden kaldırdı
    d.save_button.click()
    assert saved and [q.id for q in load_questions(path)] == ["S1", "S2", "S3"]


def test_save_fills_an_empty_template(qtbot, tmp_path, monkeypatch):
    """Boş şablon (başlık satırı var, soru yok) okunamayan dosya sayılmaz: editör soruları ona yazar."""
    from matematigin_mantigi.core.question_loader import write_template
    path = write_template(tmp_path / "sorular_sablon.xlsx", with_samples=False)
    shown = _capture_warnings(monkeypatch)             # yanlış ret gerçek modal kutu açıp testi kilitlemesin
    d, _ = _dialog(qtbot, tmp_path)
    d.save_button.click()
    assert shown == [] and len(load_questions(path)) == 3


# --- örnek sorularla açılmış uygulama gerçek soruları ezmez (Q1) --------------------------------------------------
REAL = [Question(f"G{i}", "gerçek", 8, f"Öğretmenin gerçek sorusu {i}", ("i1",), "c", (), None) for i in range(1, 6)]
REAL_TEXTS = [q.soru for q in REAL]


def _answer(monkeypatch, label: str) -> list:
    """Editörün sorusunu (QMessageBox.exec) label yazılı düğmeyle yanıtlar; sorulan metinler listede birikir."""
    asked = []

    def exec_(box):
        asked.append(box.text())
        next(b for b in box.buttons() if b.text() == label).click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", exec_)
    return asked


def _samples_dialog(qtbot, path: Path):
    """Uygulama soru dosyasını açılışta okuyamamış: pencerede örnek sorular."""
    d = QuestionEditorDialog(list(SAMPLE_QUESTIONS), path, FAM, from_file=False)
    qtbot.addWidget(d)
    d.show()
    return d


def _texts(path: Path) -> list[str]:
    return [q.soru for q in load_questions(path)]


def _bak_texts(path: Path) -> list[str]:
    from matematigin_mantigi.core.question_loader import load_backup
    return [q.soru for q in load_backup(path)]


def test_samples_are_not_saved_over_a_question_file_that_became_readable(qtbot, tmp_path, monkeypatch):
    """Q1: açılışta okunamayan soru dosyası (yarım satır, iCloud'da inmemiş, eşitleme kilidi) uygulama açıkken düzelince
    editör 3 örnek soruyu gerçek dosyanın üzerine uyarısız yazıyor, ikinci Kaydet yedeği de örneklerle değiştiriyordu:
    gerçek sorular hiçbir yerde kalmıyordu. Artık yazılmaz; dosyadaki soruları yüklemek önerilir, öğretmen istemezse
    dosya da yedek de değişmez."""
    from matematigin_mantigi.core.question_loader import backup_path
    path = write_questions(tmp_path / "sorular_sablon.xlsx", REAL)
    before = path.read_bytes()
    asked = _answer(monkeypatch, qe.KEEP_EDITING)
    d = _samples_dialog(qtbot, path)
    saved = []
    d.saved.connect(saved.append)
    d.save_button.click()
    d.save_button.click()
    assert len(asked) == 2 and "sorular_sablon.xlsx" in asked[0] and "5 soru" in asked[0], asked
    assert path.read_bytes() == before and not backup_path(path).exists()
    assert saved == [] and d.isVisible() and [q.id for q in d.questions] == ["S1", "S2", "S3"]


def test_reloading_the_fixed_file_then_saving_keeps_the_real_questions(qtbot, tmp_path, monkeypatch):
    """Q1: 'Dosyadan yeniden yükle' dosyadaki soruları pencereye getirir (hiçbir şey yazılmaz); sonraki Kaydet onları
    yazar: dosya da yedek de gerçek sorularla kalır."""
    path = write_questions(tmp_path / "sorular_sablon.xlsx", REAL)
    asked = _answer(monkeypatch, qe.RELOAD_FROM_FILE)
    d = _samples_dialog(qtbot, path)
    saved = []
    d.saved.connect(saved.append)
    before = path.read_bytes()
    d.save_button.click()
    assert len(asked) == 1 and saved == [] and d.isVisible() and path.read_bytes() == before
    assert [d.list_widget.item(i).text() for i in range(d.list_widget.count())] == [
        f"G0{i} · gerçek" for i in range(1, 6)]
    assert d.soru_edit.toPlainText() == REAL_TEXTS[0]
    d.soru_edit.setPlainText("Öğretmenin gerçek sorusu 1 (düzenlendi)")
    d.save_button.click()
    assert len(asked) == 1 and saved
    assert _texts(path) == ["Öğretmenin gerçek sorusu 1 (düzenlendi)"] + REAL_TEXTS[1:]
    assert _bak_texts(path) == REAL_TEXTS


@pytest.mark.parametrize("state", ["yok", "bos"])
@pytest.mark.parametrize("answer", ["dön", "yedekten"])
def test_samples_are_not_saved_while_the_backup_holds_the_questions(qtbot, tmp_path, monkeypatch, state, answer):
    """Q1, yedek döngüsü: öğretmen okunamayan dosyayı klasörden kaldırdıysa (ya da boşalttıysa) örnek sorular yazılınca
    bir sonraki Kaydet önceki sürümün yedeğini (gerçek sorular) da örneklerle değiştirirdi. Yedekte sorular varken
    örnekler yazılmaz, yedekteki soruları yüklemek önerilir; yüklenince Kaydet onları soru dosyası olarak yazar."""
    from matematigin_mantigi.core.question_loader import backup_path, write_template
    path = tmp_path / "sorular_sablon.xlsx"
    write_questions(path, REAL)
    write_questions(path, REAL)                             # yedekte de gerçek sorular
    path.unlink()
    if state == "bos":
        write_template(path, with_samples=False)
    bak_before = backup_path(path).read_bytes()
    asked = _answer(monkeypatch, qe.KEEP_EDITING if answer == "dön" else qe.LOAD_BACKUP)
    d = _samples_dialog(qtbot, path)
    saved = []
    d.saved.connect(saved.append)
    d.save_button.click()
    assert len(asked) == 1 and "sorular_sablon.xlsx.bak" in asked[0] and "5 soru" in asked[0], asked
    assert saved == [] and d.isVisible() and backup_path(path).read_bytes() == bak_before
    assert path.exists() == (state == "bos")
    if answer == "yedekten":
        assert d.soru_edit.toPlainText() == REAL_TEXTS[0]
        d.save_button.click()
        assert saved and _texts(path) == REAL_TEXTS and len(asked) == 1
        if state == "yok":
            assert backup_path(path).read_bytes() == bak_before
    else:
        d.save_button.click()
        assert len(asked) == 2 and saved == [] and backup_path(path).read_bytes() == bak_before


@pytest.mark.parametrize("state", ["yok", "bos"])
def test_samples_fill_a_missing_or_empty_question_file(qtbot, tmp_path, monkeypatch, state):
    """Korunacak soru yoksa (dosya yok ya da boş şablon, yedek yok) örnek sorularla açılmış editör yazabilir."""
    from matematigin_mantigi.core.question_loader import write_template
    path = tmp_path / "sorular_sablon.xlsx"
    if state == "bos":
        write_template(path, with_samples=False)
    d = _samples_dialog(qtbot, path)
    saved = []
    d.saved.connect(saved.append)
    d.save_button.click()
    assert saved and [q.id for q in load_questions(path)] == ["S1", "S2", "S3"]


def test_samples_are_not_saved_over_a_file_that_cannot_be_read(qtbot, tmp_path, monkeypatch):
    """Örnek sorular tutan editör dosyayı okuyamıyorsa (kilit, izin, inmemiş iCloud dosyası) içinde gerçek sorular olup
    olmadığını bilemez: yazmaz, sebebi söyler."""
    path = write_questions(tmp_path / "sorular_sablon.xlsx", REAL)
    before = path.read_bytes()

    def locked(p):
        raise PermissionError(errno.EACCES, "Permission denied", str(p))
    monkeypatch.setattr(qe, "load_questions", locked)
    shown = _capture_warnings(monkeypatch)
    d = _samples_dialog(qtbot, path)
    d.save_button.click()
    assert len(shown) == 1 and shown[0][0] == "Kaydedilmedi" and "örnek sorular" in shown[0][1]
    assert "erişim izni yok" in shown[0][1] and "sorular_sablon.xlsx" in shown[0][1]
    assert path.read_bytes() == before and d.isVisible()


def test_window_opened_with_samples_keeps_the_editor_off_the_real_file(qtbot, tmp_path, monkeypatch, ini_settings,
                                                                      dead_camera):
    """Q1, pencere yolu: örnek sorularla açılan pencere bunu editöre söyler. Dosyadaki sorular yüklenip kaydedilince
    tahta onları gösterir ve pencere artık dosyadan okunmuş sayılır (sonraki açılışta soru sorulmaz)."""
    from matematigin_mantigi.core.models import PenSettings
    from matematigin_mantigi.core.recorder import NullRecorder
    from matematigin_mantigi.core.session_store import SessionStore
    from matematigin_mantigi.ui.main_window import MainWindow
    path = write_questions(tmp_path / "sorular_sablon.xlsx", REAL)
    ini_settings.set_pen(PenSettings(reading_ms=0))
    win = MainWindow(FAM, list(SAMPLE_QUESTIONS), ini_settings, NullRecorder(), SessionStore(tmp_path / "o"),
                     lambda index: dead_camera, tmp_path / "d.json", questions_path=path, questions_from_file=False)
    qtbot.addWidget(win)
    asked = _answer(monkeypatch, qe.RELOAD_FROM_FILE)
    rounds = []

    def run(dlg):                         # modal exec yerine: Kaydet (yükleme önerisi), Kaydet (yazım)
        rounds.append(dlg.from_file)
        dlg.show()
        dlg.save_button.click()
        if dlg.isVisible():
            dlg.save_button.click()
        if dlg.isVisible():
            dlg.reject()
        return dlg.result()
    monkeypatch.setattr(QuestionEditorDialog, "exec", run)
    win.open_editor()
    assert rounds == [False] and len(asked) == 1
    assert [q.soru for q in win.flow.questions] == REAL_TEXTS and win.questions_from_file
    assert _texts(path) == REAL_TEXTS and _bak_texts(path) == REAL_TEXTS
    win.open_editor()
    assert rounds == [False, True] and len(asked) == 1
    assert _texts(path) == REAL_TEXTS and _bak_texts(path) == REAL_TEXTS


# Kaydet'in gerçek hâli: yazımın ORTASINDA işletim sistemi hatası (RLIMIT_FSIZE, write() EFBIG). Ayrı süreçte.
_SAVE_DISK_FULL = '''
import json, random, resource, string, sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS
from matematigin_mantigi.core.question_loader import load_questions, write_questions
from matematigin_mantigi.ui.question_editor import QuestionEditorDialog
from matematigin_mantigi.ui.theme import FontFamilies

app = QApplication(sys.argv)
path = Path("sorular_sablon.xlsx")
write_questions(path, SAMPLE_QUESTIONS)
before = path.read_bytes()
shown = []
QMessageBox.warning = staticmethod(lambda _p, title, text, *a, **k: shown.append((title, text)))
d = QuestionEditorDialog(load_questions(path), path, FontFamilies("Arial", "Arial", False))
d.show()
rnd = random.Random(0)
d.soru_edit.setPlainText("Yeni düzenleme: " + "".join(rnd.choice(string.ascii_letters) for _ in range(6000)))
soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
resource.setrlimit(resource.RLIMIT_FSIZE, (len(before) + 1500, hard))     # yedek sığar, yeni dosya sığmaz
d.save_button.click()
resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
try:
    loaded = len(load_questions(path))
except Exception as err:
    loaded = type(err).__name__
res = {"uyari": shown, "acik": d.isVisible(), "ayni": path.read_bytes() == before, "yuklenen": loaded,
       "dosyalar": sorted(p.name for p in Path(".").iterdir())}
print("SONUC " + json.dumps(res, ensure_ascii=False), flush=True)
'''


@pytest.mark.skipif(sys.platform == "win32", reason="RLIMIT_FSIZE yalnız POSIX'te")
def test_disk_full_mid_save_keeps_the_question_file_loadable(tmp_path):
    """B-2 uçtan uca (inceleme s03): Kaydet yazımın ortasında EFBIG alınca soru dosyası yarım kalıyor (5575 -> 2289
    bayt) ve uygulama bir daha açılmıyordu. Artık dosya bayt bayt aynı ve yüklenebilir, geçici dosya kalmaz, mesaj
    dosyanın değişmediğini söyler, düzenlemeler pencerede durur."""
    script = tmp_path / "calistir.py"
    script.write_text(_SAVE_DISK_FULL, encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    r = subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env, capture_output=True, text=True,
                       timeout=120)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("SONUC ")), None)
    assert r.returncode == 0 and line is not None, f"çıkış {r.returncode}:\n{r.stdout}\n{r.stderr[-2000:]}"
    res = json.loads(line[len("SONUC "):])
    assert res["ayni"] and res["yuklenen"] == 3 and res["acik"], res
    assert len(res["uyari"]) == 1 and res["uyari"][0][0] == "Kaydedilemedi" and "değişmedi" in res["uyari"][0][1]
    assert res["dosyalar"] == ["calistir.py", "sorular_sablon.xlsx", "sorular_sablon.xlsx.bak"], res
