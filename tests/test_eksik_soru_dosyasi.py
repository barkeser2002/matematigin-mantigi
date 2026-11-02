"""U2: soru dosyası açılışta klasörde YOK ama gerçek soruları başka yerde duruyor: önceki sürümün yedeği (<ad>.bak; öğretmen
dosyayı kaldırdı ya da taşıdı) ya da macOS 13 ve öncesinde iCloud'un bu Mac'e indirmediği dosyanın yer tutucusu
('.<ad>.icloud'). Eskiden açılış yerine örnek şablonu sessizce yazıyor (paketli uygulamada gömülü şablonu kopyalıyor),
dosya 'okundu' sayılıyordu: editörün ilk Kaydet'i yedeği örnek sorularla eziyordu, gerçek sorular kayboluyordu."""
import argparse
import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox

from matematigin_mantigi import app as app_mod
from matematigin_mantigi import paths
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question
from matematigin_mantigi.core.question_loader import backup_path, load_backup, load_questions, write_questions
from matematigin_mantigi.ui import question_editor as qe
from matematigin_mantigi.ui.question_editor import QuestionEditorDialog
from matematigin_mantigi.ui.theme import FontFamilies

FAM = FontFamilies("Arial", "Arial", False)
REAL = [Question(f"G{i}", "gerçek", 8, f"Öğretmenin gerçek sorusu {i}", ("i1",), "c", (), None) for i in range(1, 6)]
REAL_TEXTS = [q.soru for q in REAL]


@pytest.fixture(autouse=True)
def no_modal_blocks(monkeypatch):
    """Açılış uyarısı ve editörün sorusu gerçek modal açmaz (offscreen'de exec() sonsuza dek bekler): uyarılar
    `warnings`'e, sorular `asked`'e düşer; soru 'Kaydetmeden dön' ile yanıtlanır (hiçbir şey yazılmaz)."""
    warnings, asked = [], []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(
        lambda _p, title, text, *a, **k: warnings.append(text)))

    def exec_(box):
        asked.append(box.text())
        next(b for b in box.buttons() if b.text() == qe.KEEP_EDITING).click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", exec_)
    return warnings, asked


def _real_with_backup(path: Path) -> bytes:
    """Dosya ve yedeği gerçek sorularla; sonra dosya klasörden kalkar (yedek kalır). Yedeğin baytlarını döndürür."""
    write_questions(path, REAL)
    write_questions(path, REAL)
    path.unlink()
    return backup_path(path).read_bytes()


def _save_in_editor(win, monkeypatch) -> list:
    """Pencerenin editörünü açar (modal exec yerine) ve Kaydet'e basar; Kaydet'in yaydığı listeler döner."""
    saved = []

    def run(dlg):
        dlg.saved.connect(saved.append)
        dlg.show()
        dlg.save_button.click()
        if dlg.isVisible():
            dlg.reject()
        return dlg.result()
    monkeypatch.setattr(QuestionEditorDialog, "exec", run)
    win.open_editor()
    return saved


@pytest.mark.parametrize("trace", ["yedek", "icloud", "ikisi"])
def test_missing_question_file_is_not_replaced_by_samples(tmp_path, no_modal_blocks, trace):
    """Dosya yok ama yedeği ya da iCloud yer tutucusu var: örnek şablon YAZILMAZ, uyarı ne olduğunu ve ne yapılacağını
    söyler, uygulama örnek sorularla açılır ve sorular dosyadan okunmamış sayılır (editör yedeği yüklemeyi önerir)."""
    warnings, _asked = no_modal_blocks
    p = tmp_path / "sorular.xlsx"
    bak = _real_with_backup(p) if trace in ("yedek", "ikisi") else None
    if trace in ("icloud", "ikisi"):
        paths.icloud_placeholder(p).write_bytes(b"bplist00 yer tutucu")
    assert app_mod.load_questions_or_samples(p) == (list(SAMPLE_QUESTIONS), False)
    assert not p.exists()
    assert bak is None or backup_path(p).read_bytes() == bak
    assert len(warnings) == 1 and warnings[0].startswith("Soru dosyası bulunamadı: sorular.xlsx"), warnings
    text = warnings[0]
    assert "Örnek sorularla" in text, text
    if bak is not None:
        assert "Önceki sürümün yedeği var: sorular.xlsx.bak (adını sorular.xlsx" in text, text
    if trace != "yedek":
        assert "iCloud" in text, text


def test_missing_question_file_without_traces_still_gets_the_sample_template(tmp_path, no_modal_blocks):
    """Yedek ve yer tutucu yoksa (ilk açılış) eskisi gibi örnek şablon yazılır ve dosyadan okunur, uyarı yok."""
    warnings, _asked = no_modal_blocks
    p = tmp_path / "sorular.xlsx"
    questions, from_file = app_mod.load_questions_or_samples(p)
    assert from_file is True and warnings == [] and [q.soru for q in load_questions(p)] == [q.soru for q in questions]


def _args(tmp_path, sorular=None) -> argparse.Namespace:
    argv = ["matematigin-mantigi", "--kamera-yok", "--duzen", str(tmp_path / "duzen.json")]
    if sorular is not None:
        argv += ["--sorular", str(sorular)]
    return app_mod.parse_args(argv)


@pytest.mark.parametrize("mode", ["gelistirme", "paketli"])
def test_window_opened_without_the_file_offers_the_backup_and_never_overwrites_it(qtbot, tmp_path, monkeypatch,
                                                                                 ini_settings, no_modal_blocks,
                                                                                 mode):
    """Uçtan uca (gerçek build_window, inceleme v20): klasörde yalnız <ad>.bak (gerçek sorular). Geliştirmede
    ensure_template örnekleri yazıyordu; paketli uygulamada ensure_user_data gömülü şablonu kopyalıyordu. Şimdi dosya
    oluşmaz, pencere örneklerle ama 'dosyadan okunmadı' olarak açılır; editörün Kaydet'i yedeği yüklemeyi sorar ve
    'Kaydetmeden dön'de hiçbir şey yazmaz: yedek bayt bayt aynı kalır."""
    warnings, asked = no_modal_blocks
    if mode == "paketli":
        bundle = tmp_path / "paket"
        bundle.mkdir()
        write_questions(bundle / paths.TEMPLATE_NAME, SAMPLE_QUESTIONS)       # .app içindeki örnek şablon
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
        monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "ev"))
        p = paths.default_template_path()
        p.parent.mkdir(parents=True)
        args = _args(tmp_path)
    else:
        p = tmp_path / "sorular.xlsx"
        args = _args(tmp_path, sorular=p)
    bak = _real_with_backup(p)
    win = app_mod.build_window(args, FAM, ini_settings)
    qtbot.addWidget(win)
    assert win.questions_path == p and win.questions_from_file is False and not p.exists()
    assert [q.soru for q in win.flow.questions] == [q.soru for q in SAMPLE_QUESTIONS]
    assert len(warnings) == 1 and f"{p.name}.bak" in warnings[0], warnings
    saved = _save_in_editor(win, monkeypatch)
    assert len(asked) == 1 and f"{p.name}.bak" in asked[0] and "5 soru" in asked[0], asked
    assert saved == [] and not p.exists() and backup_path(p).read_bytes() == bak
    assert [q.soru for q in load_backup(p)] == REAL_TEXTS


def test_editor_does_not_write_samples_next_to_an_icloud_placeholder(qtbot, tmp_path, no_modal_blocks):
    """Örnek sorularla açılmış editör, soru dosyası iCloud'da (yer tutucusu klasörde, asıl dosya inmemiş) ve yedek
    yokken Kaydet'te örnekleri o ada yazıyordu: iCloud'daki gerçek dosyayla çakışan yeni bir yerel dosya. Yazmaz,
    dosyanın inmesini beklemesini söyler; düzenlemeler pencerede kalır."""
    warnings, asked = no_modal_blocks
    p = tmp_path / "sorular.xlsx"
    paths.icloud_placeholder(p).write_bytes(b"bplist00 yer tutucu")
    d = QuestionEditorDialog(list(SAMPLE_QUESTIONS), p, FAM, from_file=False)
    qtbot.addWidget(d)
    d.show()
    saved = []
    d.saved.connect(saved.append)
    d.save_button.click()
    assert saved == [] and d.isVisible() and not p.exists() and asked == []
    assert len(warnings) == 1 and "iCloud" in warnings[0] and "sorular.xlsx" in warnings[0], warnings
    assert "Düzenlemeleriniz bu pencerede duruyor" in warnings[0], warnings
