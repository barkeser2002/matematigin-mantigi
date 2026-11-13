"""Tanıma örneği toplama penceresi (offscreen): menü girişi, Kaydet/Sonraki/Sil, ilerleme, ZIP, kayıt kapısı."""
import json

import numpy as np
import pytest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication

from matematigin_mantigi import paths
from matematigin_mantigi.core import ornek_toplama as ot
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar
from matematigin_mantigi.ui.ornek_toplama_window import OrnekToplamaPenceresi

FAM = FontFamilies("Arial", "Arial", False)


@pytest.fixture
def koku(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    return tmp_path / "tanima-ornekleri"


@pytest.fixture
def pencere(qtbot, koku):
    w = OrnekToplamaPenceresi(FAM, koku)
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


def _ciz(qtbot, w, noktalar):
    c = w.canvas
    qtbot.mousePress(c, Qt.MouseButton.LeftButton, pos=QPoint(*noktalar[0]))
    for p in noktalar[1:]:
        qtbot.mouseMove(c, QPoint(*p))
    qtbot.mouseRelease(c, Qt.MouseButton.LeftButton, pos=QPoint(*noktalar[-1]))


def test_window_title_and_big_symbol(pencere):
    assert pencere.windowTitle() == "Tanıma örneği topla"
    assert pencere.current_symbol() == "0"
    assert pencere.symbol_label.text() == "0"


def test_toolbar_has_sample_entry_that_emits(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    assert "Tanıma" in tb.sample_button.text()
    with qtbot.waitSignal(tb.sampleRequested, timeout=1000):
        qtbot.mouseClick(tb.sample_button, Qt.MouseButton.LeftButton)


def test_mouse_strokes_are_recorded_with_points_and_time(pencere, qtbot):
    _ciz(qtbot, pencere, [(40, 40), (60, 80), (80, 120)])
    assert pencere.canvas.has_ink()
    cizgi = pencere.canvas.strokes()
    assert len(cizgi) == 1 and len(cizgi[0]) >= 3
    assert set(cizgi[0][0]) == {"x", "y", "basinc", "zaman"}


def test_kaydet_writes_sample_and_updates_progress(pencere, qtbot, koku):
    _ciz(qtbot, pencere, [(40, 40), (60, 80), (80, 120)])
    assert pencere.save_button.isEnabled()
    assert pencere.save_current() is True
    assert ot.ornek_sayilari(koku)["0"] == 1
    assert list((koku / "0").glob("0_*.png")) and list((koku / "0").glob("0_*.json"))
    assert not pencere.canvas.has_ink()
    assert "1 / 30" in pencere.progress_label.text()
    assert "1 / 570" in pencere.total_label.text()


def test_kaydet_without_ink_saves_nothing(pencere, koku):
    assert pencere.save_current() is False
    assert ot.ornek_sayilari(koku)["0"] == 0
    assert "çiz" in pencere.notice_label.text().lower()


def test_sil_clears_unsaved_ink_and_writes_nothing(pencere, qtbot, koku):
    _ciz(qtbot, pencere, [(40, 40), (60, 80)])
    pencere.clear_current()
    assert not pencere.canvas.has_ink()
    assert sum(ot.ornek_sayilari(koku).values()) == 0


def test_sonraki_moves_to_next_symbol_when_nothing_unsaved(pencere, qtbot):
    pencere.next_symbol()
    assert pencere.current_symbol() == "1"
    assert pencere.symbol_label.text() == "1"
    assert "0 / 30" in pencere.progress_label.text()


def test_sonraki_is_blocked_by_unsaved_ink(pencere, qtbot):
    _ciz(qtbot, pencere, [(40, 40), (60, 80)])
    pencere.next_symbol()
    assert pencere.current_symbol() == "0"             # kaydedilmemiş çizim ilerlemeyi engeller
    assert "Kaydet" in pencere.notice_label.text() or "Sil" in pencere.notice_label.text()
    pencere.clear_current()
    pencere.next_symbol()
    assert pencere.current_symbol() == "1"


def test_sonraki_wraps_after_last_symbol(pencere):
    for _ in range(len(ot.SEMBOLLER)):
        pencere.next_symbol()
    assert pencere.current_symbol() == "0"


def test_progress_counts_existing_samples_from_folder(qtbot, koku):
    c = [[{"x": 1.0, "y": 1.0, "basinc": 1.0, "zaman": 0.0}, {"x": 9.0, "y": 9.0, "basinc": 1.0, "zaman": 0.1}]]
    for _ in range(4):
        ot.ornek_kaydet(koku, "1", c, np.full((100, 100), 255, np.uint8), zaman="T")
    w = OrnekToplamaPenceresi(FAM, koku)
    qtbot.addWidget(w)
    w.next_symbol()
    assert w.current_symbol() == "1"
    assert "4 / 30" in w.progress_label.text()
    assert "4 / 570" in w.total_label.text()


def test_export_zip_asks_for_file_and_writes_archive(pencere, qtbot, koku, tmp_path, monkeypatch):
    _ciz(qtbot, pencere, [(40, 40), (60, 80)])
    pencere.save_current()
    hedef = tmp_path / "disa.zip"
    monkeypatch.setattr("matematigin_mantigi.ui.ornek_toplama_window.QFileDialog.getSaveFileName",
                        lambda *a, **k: (str(hedef), "ZIP (*.zip)"))
    pencere.export_zip()
    assert hedef.exists()
    assert len(ot.ornekleri_oku(hedef)) == 1


def test_export_zip_cancel_writes_nothing(pencere, tmp_path, monkeypatch):
    monkeypatch.setattr("matematigin_mantigi.ui.ornek_toplama_window.QFileDialog.getSaveFileName",
                        lambda *a, **k: ("", ""))
    pencere.export_zip()
    assert not list(tmp_path.glob("*.zip"))


def test_main_window_opens_sample_window_after_recording_check(window, qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    window.toolbar.sample_button.click()
    qtbot.waitUntil(lambda: getattr(window, "_sample_window", None) is not None, timeout=3000)
    assert window._sample_window.windowTitle() == "Tanıma örneği topla"
    assert window._sample_window.koku == tmp_path / "tanima-ornekleri"
    window._sample_window.close()
