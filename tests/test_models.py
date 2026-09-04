from matematigin_mantigi.core.models import (PALETTE, SAMPLE_QUESTIONS, TOOL_META, WIDTHS,
                                             PenSettings, Question, Tool)
from matematigin_mantigi import app


def test_palette_and_widths_match_mockup():
    assert PALETTE == ("#1c1b19", "#c8322b", "#2456b8", "#1f8a4c")
    assert WIDTHS == (2, 4, 8)


def test_every_tool_has_label_and_glyph():
    assert set(TOOL_META) == set(Tool)
    assert TOOL_META[Tool.PEN] == ("Kalem", "✎")


def test_sample_questions_have_three_hints():
    assert len(SAMPLE_QUESTIONS) == 3
    assert all(isinstance(q, Question) and len(q.hints) == 3 for q in SAMPLE_QUESTIONS)


def test_pen_settings_defaults():
    p = PenSettings()
    assert (p.pressure_curve, p.smoothing, p.min_width, p.max_width) == (50, 35, 1, 12)
    assert p.template_matching is False and p.reading_ms == 150


def test_question_optional_fields_default():
    q = Question("S1", "k", None, "soru?", ("h",), "c")
    assert q.options == () and q.image is None
    assert SAMPLE_QUESTIONS[0].options == ("3", "4", "5", "6")


def test_parse_args_defaults():
    ns = app.parse_args(["prog"])
    assert ns.sorular is None and ns.kamera is None and ns.kamera_yok is False


def test_build_window_offscreen(qtbot, tmp_path, ini_settings, monkeypatch):
    from matematigin_mantigi.ui.theme import FontFamilies
    monkeypatch.chdir(tmp_path)
    win = app.build_window(app.parse_args(["prog", "--kamera-yok"]), FontFamilies("Arial", "Arial", False), ini_settings)
    qtbot.addWidget(win)
    assert win.windowTitle() == "Matematiğin Mantığı"
    assert (tmp_path / "sorular_sablon.xlsx").exists()
