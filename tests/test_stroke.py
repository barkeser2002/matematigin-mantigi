import pytest

from matematigin_mantigi.core import stroke


@pytest.mark.parametrize("base,p,expected", [(4, 0.0, 2.4), (4, 1.0, 7.2), (4, 0.5, 4.8), (8, 0.25, 7.2)])
def test_pressure_width(base, p, expected):
    assert stroke.pressure_width(base, p) == pytest.approx(expected)


def test_pressure_is_clamped():
    assert stroke.pressure_width(4, -1.0) == pytest.approx(2.4)
    assert stroke.pressure_width(4, 3.0) == pytest.approx(7.2)


def test_eraser_and_cursor_diameters():
    assert [stroke.eraser_diameter(b) for b in (2, 4, 8)] == [20, 34, 68]
    assert [stroke.pen_cursor_diameter(b) for b in (2, 4, 8)] == [14, 18, 26]
    assert stroke.eraser_diameter(100) == 80 and stroke.pen_cursor_diameter(100) == 40
