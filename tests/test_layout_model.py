import json

from matematigin_mantigi.core import layout_model as lm


def test_default_layout_matches_mockup():
    assert lm.DEFAULT_LAYOUT["soru"] == lm.PanelGeom(0, 0, 7, 3)
    assert lm.DEFAULT_LAYOUT["ipucu"] == lm.PanelGeom(7, 0, 5, 5)
    assert lm.DEFAULT_LAYOUT["cizim"] == lm.PanelGeom(0, 3, 7, 7)
    assert lm.DEFAULT_LAYOUT["webcam"] == lm.PanelGeom(7, 5, 5, 5)


def test_clamp_keeps_inside_grid_and_min_span():
    assert lm.clamp(lm.PanelGeom(11, 9, 1, 1)) == lm.PanelGeom(10, 8, 2, 2)
    assert lm.clamp(lm.PanelGeom(-3, -1, 20, 20)) == lm.PanelGeom(0, 0, 12, 10)
    assert lm.clamp(lm.PanelGeom(8, 2, 6, 3)) == lm.PanelGeom(6, 2, 6, 3)


def test_pixel_rect_and_snap_round_trip():
    w, h, gap = 1200, 1000, 14
    for key, g in lm.DEFAULT_LAYOUT.items():
        x, y, pw, ph = lm.pixel_rect(g, w, h, gap)
        assert lm.snap_rect(x, y, pw, ph, w, h, gap) == g, key


def test_pixel_rects_tile_the_area_without_overlap():
    w, h, gap = 1200, 1000, 14
    a = lm.pixel_rect(lm.DEFAULT_LAYOUT["soru"], w, h, gap)
    b = lm.pixel_rect(lm.DEFAULT_LAYOUT["cizim"], w, h, gap)
    assert b[1] - (a[1] + a[3]) == gap          # vertical gap between soru and cizim
    c = lm.pixel_rect(lm.DEFAULT_LAYOUT["ipucu"], w, h, gap)
    assert c[0] - (a[0] + a[2]) == gap          # horizontal gap between soru and ipucu
    assert c[0] + c[2] == w                     # right edge flush


def test_snap_moves_to_nearest_cell():
    w, h, gap = 1200, 1000, 14
    cw, ch = lm.cell_size(w, h, gap)
    px, py = cw + gap, ch + gap                      # hücre aralığı (cell pitch)
    g = lm.snap_rect(int(px * 0.4), int(py * 2.6), int(px * 3.2 - gap), int(py * 2.4 - gap), w, h, gap)
    assert g == lm.PanelGeom(0, 3, 3, 2)


def test_json_round_trip_and_bad_input():
    text = lm.to_json(lm.DEFAULT_LAYOUT)
    assert json.loads(text)["webcam"] == {"col": 7, "row": 5, "col_span": 5, "row_span": 5}
    assert lm.from_json(text) == lm.DEFAULT_LAYOUT
    assert lm.from_json("not json") == lm.DEFAULT_LAYOUT
    partial = lm.from_json('{"soru": {"col": 2, "row": 2, "col_span": 4, "row_span": 4}, "x": 1}')
    assert partial["soru"] == lm.PanelGeom(2, 2, 4, 4) and partial["cizim"] == lm.DEFAULT_LAYOUT["cizim"]
    assert "x" not in partial


def test_load_save_layout(tmp_path):
    p = tmp_path / "duzen.json"
    assert lm.load_layout(p) == lm.DEFAULT_LAYOUT          # missing file -> defaults
    custom = dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 8, 2, 2))
    lm.save_layout(p, custom)
    assert lm.load_layout(p) == custom
