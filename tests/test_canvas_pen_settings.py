from PyQt6.QtCore import QPointF

from matematigin_mantigi.core.models import PenSettings
from matematigin_mantigi.ui.canvas import DrawingCanvas


def make(qtbot, settings):
    canvas = DrawingCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(300, 200)
    canvas.show()
    qtbot.waitExposed(canvas)
    canvas.set_pen_settings(settings)
    return canvas


def draw(canvas, pressure):
    canvas.begin_stroke(QPointF(40, 100), pressure)
    canvas.extend_stroke(QPointF(240, 100), pressure)
    canvas.end_stroke()


def thickness(canvas):
    return sum(canvas.strokes_image().pixelColor(140, y).alpha() > 100 for y in range(70, 130))


def test_pressure_limits_and_curve_change_rendered_width(qtbot):
    thin = make(qtbot, PenSettings(min_width=2, max_width=20, smoothing=0))
    thick = make(qtbot, PenSettings(min_width=2, max_width=20, smoothing=0))
    soft = make(qtbot, PenSettings(min_width=2, max_width=20, pressure_curve=0, smoothing=0))
    hard = make(qtbot, PenSettings(min_width=2, max_width=20, pressure_curve=100, smoothing=0))
    draw(thin, 0); draw(thick, 1); draw(soft, .5); draw(hard, .5)
    assert thickness(thin) == 2
    assert thickness(thick) == 20
    assert thickness(soft) > thickness(hard)


def test_smoothing_reduces_jitter_and_finishes_at_pointer(qtbot):
    raw = make(qtbot, PenSettings(min_width=2, max_width=2, smoothing=0))
    smooth = make(qtbot, PenSettings(min_width=2, max_width=2, smoothing=80))
    for canvas in (raw, smooth):
        canvas.begin_stroke(QPointF(40, 100), .5)
        for x, y in [(60, 100), (80, 110), (100, 100), (120, 100), (160, 100)]:
            canvas.extend_stroke(QPointF(x, y), .5)
        canvas.end_stroke()
    assert raw.strokes_image().pixelColor(80, 110).alpha() > 100
    assert smooth.strokes_image().pixelColor(80, 110).alpha() == 0
    assert smooth.strokes_image().pixelColor(160, 100).alpha() > 100


def test_round_nib_has_rounded_caps_and_undo(qtbot):
    canvas = make(qtbot, PenSettings(min_width=20, max_width=20, smoothing=0))
    draw(canvas, .5)
    image = canvas.strokes_image()
    assert image.pixelColor(32, 100).alpha() > 100
    assert image.pixelColor(32, 92).alpha() < 30
    canvas.undo()
    assert canvas.strokes_image().pixelColor(140, 100).alpha() == 0


def test_felt_flat_cap_opacity_and_half_pressure(qtbot):
    from matematigin_mantigi.core.models import Nib
    settings = PenSettings(nib=Nib.FELT, min_width=4, max_width=20, smoothing=0)
    low = make(qtbot, settings)
    high = make(qtbot, settings)
    draw(low, 0); draw(high, 1)
    assert low.strokes_image().pixelColor(140, 100).alpha() in range(215, 219)
    assert low.strokes_image().pixelColor(35, 100).alpha() == 0
    assert 0 < thickness(high) - thickness(low) <= 10


def test_chalk_has_opaque_ink_and_transparent_grain(qtbot):
    from matematigin_mantigi.core.models import Nib
    canvas = make(qtbot, PenSettings(nib=Nib.CHALK, min_width=20, max_width=20, smoothing=0))
    draw(canvas, .5)
    image = canvas.strokes_image()
    alphas = [image.pixelColor(x, y).alpha() for x in range(60, 220) for y in range(96, 104)]
    assert 255 in alphas and 0 in alphas


def test_window_applies_saved_and_updated_pen_settings(window):
    from dataclasses import replace
    assert window.canvas._pen_settings == window.settings.pen()
    new = replace(window.settings.pen(), min_width=8, max_width=8)
    window._apply_pen_settings(new)
    assert window.canvas._pen_settings == new
    assert window.settings.pen() == new


def test_toolbar_width_changes_stroke_even_at_full_pressure(qtbot):
    thin = make(qtbot, PenSettings(min_width=2, max_width=12, smoothing=0))
    thick = make(qtbot, PenSettings(min_width=2, max_width=12, smoothing=0))
    thin.set_base_width(4); thick.set_base_width(8)
    draw(thin, 1); draw(thick, 1)
    assert thickness(thin) == 12
    assert thickness(thick) == 24
