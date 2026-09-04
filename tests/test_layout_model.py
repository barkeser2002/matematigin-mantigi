import json

from matematigin_mantigi.core import layout_model as lm


def test_default_layout_is_whiteboard_zones():
    assert lm.ZONE_KEYS == ("soru", "ipucu", "webcam")
    assert lm.DEFAULT_LAYOUT["soru"] == lm.PanelGeom(0, 0, 6, 4)
    assert lm.DEFAULT_LAYOUT["ipucu"] == lm.PanelGeom(6, 0, 6, 4)
    assert lm.DEFAULT_LAYOUT["webcam"] == lm.PanelGeom(9, 7, 3, 3)
    assert "cizim" not in lm.DEFAULT_LAYOUT


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
    b = lm.pixel_rect(lm.DEFAULT_LAYOUT["ipucu"], w, h, gap)
    assert b[0] - (a[0] + a[2]) == gap          # soru ile ipucu arasındaki yatay boşluk
    assert b[0] + b[2] == w                     # sağ kenara yapışık
    c = lm.pixel_rect(lm.DEFAULT_LAYOUT["webcam"], w, h, gap)
    assert c[0] + c[2] == w and c[1] + c[3] == h   # sağ alt köşe


def test_snap_moves_to_nearest_cell():
    w, h, gap = 1200, 1000, 14
    cw, ch = lm.cell_size(w, h, gap)
    px, py = cw + gap, ch + gap                      # hücre aralığı (cell pitch)
    g = lm.snap_rect(int(px * 0.4), int(py * 2.6), int(px * 3.2 - gap), int(py * 2.4 - gap), w, h, gap)
    assert g == lm.PanelGeom(0, 3, 3, 2)


def test_json_round_trip_and_bad_input():
    text = lm.to_json(lm.DEFAULT_LAYOUT)
    assert json.loads(text)["webcam"] == {"col": 9, "row": 7, "col_span": 3, "row_span": 3}
    assert lm.from_json(text) == lm.DEFAULT_LAYOUT
    assert lm.from_json("not json") == lm.DEFAULT_LAYOUT
    partial = lm.from_json('{"soru": {"col": 2, "row": 2, "col_span": 4, "row_span": 4},'
                           ' "cizim": {"col": 0, "row": 3, "col_span": 7, "row_span": 7}, "x": 1}')
    assert partial["soru"] == lm.PanelGeom(2, 2, 4, 4) and partial["ipucu"] == lm.DEFAULT_LAYOUT["ipucu"]
    assert "x" not in partial and "cizim" not in partial          # eski anahtar yok sayılır


def test_load_save_layout(tmp_path):
    p = tmp_path / "duzen.json"
    assert lm.load_layout(p) == lm.DEFAULT_LAYOUT          # missing file -> defaults
    custom = dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 8, 2, 2))
    lm.save_layout(p, custom)
    assert lm.load_layout(p) == custom
