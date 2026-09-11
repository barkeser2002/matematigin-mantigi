import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from matematigin_mantigi.core.models import Question, SAMPLE_QUESTIONS
from matematigin_mantigi.core.question_loader import load_questions, save_question_image
from matematigin_mantigi.ui.question_editor import QuestionEditorDialog, _display_id
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)


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
