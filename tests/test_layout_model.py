import errno
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

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


def test_clamp_free_allows_smaller_span_than_clamp_but_stays_in_area():
    w, h, gap = 1200, 1000, 14
    tiny = lm.clamp_free(lm.PanelGeom(0, 0, 0.1, 0.1), w, h, gap)
    assert 0 < tiny.col_span < lm.MIN_SPAN and 0 < tiny.row_span < lm.MIN_SPAN   # clamp() bunu 2'ye yuvarlardı
    assert tiny.col >= 0 and tiny.row >= 0
    cw, ch = lm.cell_size(w, h, gap)
    px_w = tiny.col_span * (cw + gap) - gap                    # gerçek piksel taban genişliği
    px_h = tiny.row_span * (ch + gap) - gap
    assert px_w >= lm.MIN_FREE_W - 1e-6 and px_h >= lm.MIN_FREE_H - 1e-6   # 80x60 px taban korunuyor
    out = lm.clamp_free(lm.PanelGeom(20, 20, 5, 5), w, h, gap)
    assert out.col + out.col_span <= lm.GRID_COLS and out.row + out.row_span <= lm.GRID_ROWS
    assert out.col >= 0 and out.row >= 0                        # alanı terk etmiyor


def test_clamp_free_without_area_never_touches_span():
    """area_w/area_h/gap verilmezse (from_json, WorkArea.set_layout -- yükleme yolu) clamp_free piksel
    tabanını UYGULAMAZ: kaydedilmiş kesirli bir span, ne kadar küçük olursa olsun aynen korunur. Piksel
    tabanı yalnız onu yaratan sürüklemede (gerçek alan bilinirken, free_rect üzerinden) uygulanır --
    kalıcılık kaydedileni birebir geri vermeli, hangi pencerede yüklenirse yüklensin."""
    assert lm.clamp_free(lm.PanelGeom(0, 0, 0.01, 0.02)) == lm.PanelGeom(0, 0, 0.01, 0.02)
    assert lm.clamp_free(lm.PanelGeom(2, 1, 0.3, 0.25)) == lm.PanelGeom(2, 1, 0.3, 0.25)
    assert lm.clamp_free(lm.PanelGeom(9, 7, 0.447, 0.528)) == lm.PanelGeom(9, 7, 0.447, 0.528)  # 2560x1440'ta gerçek taban
    # yalnız sıfır/negatif span'e karşı bir koruma var -- bu, bir boyut TABANI değil
    guarded = lm.clamp_free(lm.PanelGeom(0, 0, 0, -5))
    assert guarded.col_span > 0 and guarded.row_span > 0
    # ızgara sınırları hâlâ geçerli (clamp ile aynı üst sınır/alan kuralı)
    out = lm.clamp_free(lm.PanelGeom(20, 20, 5, 5))
    assert out.col + out.col_span <= lm.GRID_COLS and out.row + out.row_span <= lm.GRID_ROWS
    assert out.col >= 0 and out.row >= 0


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


def test_free_rect_returns_fractional_unlike_snap_rect():
    w, h, gap = 1200, 1000, 14
    cw, ch = lm.cell_size(w, h, gap)
    x, y = int(cw * 1.4), int(ch * 2.6)
    pw, ph = int(cw * 3.3 - gap), int(ch * 2.2 - gap)
    free = lm.free_rect(x, y, pw, ph, w, h, gap)
    snapped = lm.snap_rect(x, y, pw, ph, w, h, gap)
    assert any(v != round(v) for v in (free.col, free.row, free.col_span, free.row_span))
    assert all(isinstance(v, int) for v in (snapped.col, snapped.row, snapped.col_span, snapped.row_span))


def test_json_round_trip_and_bad_input():
    text = lm.to_json(lm.DEFAULT_LAYOUT)
    assert json.loads(text)["webcam"] == {"col": 9, "row": 7, "col_span": 3, "row_span": 3}
    assert lm.from_json(text) == lm.DEFAULT_LAYOUT
    assert lm.from_json("not json") == lm.DEFAULT_LAYOUT
    partial = lm.from_json('{"soru": {"col": 2, "row": 2, "col_span": 4, "row_span": 4},'
                           ' "cizim": {"col": 0, "row": 3, "col_span": 7, "row_span": 7}, "x": 1}')
    assert partial["soru"] == lm.PanelGeom(2, 2, 4, 4) and partial["ipucu"] == lm.DEFAULT_LAYOUT["ipucu"]
    assert "x" not in partial and "cizim" not in partial          # eski anahtar yok sayılır


def test_to_json_from_json_round_trips_fractional_values():
    custom: lm.Layout = {
        "soru": lm.PanelGeom(0.5, 1.25, 6.5, 4.75),
        "ipucu": lm.PanelGeom(6.5, 1.25, 5.5, 4.75),
        "webcam": lm.PanelGeom(8.75, 6.5, 3.25, 3.5),
    }
    text = lm.to_json(custom)
    assert lm.from_json(text) == custom                    # kesirli değerler aynen geri gelir


def test_load_save_layout(tmp_path):
    p = tmp_path / "duzen.json"
    assert lm.load_layout(p) == lm.DEFAULT_LAYOUT          # missing file -> defaults
    custom = dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 8, 2, 2))
    lm.save_layout(p, custom)
    assert lm.load_layout(p) == custom


_OLD = dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 6, 4, 4), soru=lm.PanelGeom(4, 0, 8, 5))


def test_failed_layout_save_keeps_the_old_layout_and_no_temp_file(tmp_path, monkeypatch):
    """B-5: duzen.json doğrudan yazılıyordu; yazımın ortasındaki hata (dolu disk) dosyayı yarım bırakıyor, uyarı
    'yeniden açılınca eski düzen gelir' derken açılışta VARSAYILAN düzen geliyordu. Yazım geçici dosyaya yapılır,
    tamamlanınca os.replace ile yerine konur: hatada eski düzen aynen kalır, geçici dosya silinir."""
    p = tmp_path / "duzen.json"
    lm.save_layout(p, _OLD)
    real_write_text = Path.write_text

    def half_written(self, data, *a, **k):
        real_write_text(self, data[: len(data) // 3], *a, **k)
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(Path, "write_text", half_written)
    with pytest.raises(OSError):
        lm.save_layout(p, dict(lm.DEFAULT_LAYOUT))
    monkeypatch.undo()
    assert lm.load_layout(p) == _OLD
    assert sorted(x.name for x in tmp_path.iterdir()) == ["duzen.json"]


_LAYOUT_DISK_FULL = textwrap.dedent('''
    import json, resource
    from pathlib import Path
    from matematigin_mantigi.core import layout_model as lm

    old = dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 6, 4, 4), soru=lm.PanelGeom(4, 0, 8, 5))
    p = Path("duzen.json")
    lm.save_layout(p, old)
    soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    resource.setrlimit(resource.RLIMIT_FSIZE, (100, hard))         # duzen.json ~600 bayt: 100. baytta EFBIG
    try:
        lm.save_layout(p, dict(lm.DEFAULT_LAYOUT))
        err = None
    except OSError as e:
        err = e.errno
    finally:
        resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))
    print("SONUC " + json.dumps({"hata": err, "eski_duzen": lm.load_layout(p) == old,
                                 "dosyalar": sorted(x.name for x in Path(".").iterdir())}))
''')


@pytest.mark.skipif(sys.platform == "win32", reason="RLIMIT_FSIZE yalnız POSIX'te")
def test_disk_full_mid_layout_save_keeps_the_old_layout(tmp_path):
    """B-5'in gerçek hâli (inceleme s04): yazım ortasında EFBIG'den sonra yeniden açılışta eski düzen gelir."""
    script = tmp_path / "calistir.py"
    script.write_text(_LAYOUT_DISK_FULL, encoding="utf-8")
    r = subprocess.run([sys.executable, str(script)], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("SONUC ")), None)
    assert r.returncode == 0 and line is not None, f"çıkış {r.returncode}:\n{r.stdout}\n{r.stderr[-2000:]}"
    res = json.loads(line[len("SONUC "):])
    assert res == {"hata": errno.EFBIG, "eski_duzen": True, "dosyalar": ["calistir.py", "duzen.json"]}


def _flaky_replace(monkeypatch, target: Path, failures):
    """target'a os.replace ilk `failures` denemede (None: her seferinde) PermissionError verir; denemeler listede."""
    real_replace = os.replace
    attempts = []

    def replace(src, dst, *a, **k):
        if os.fspath(dst) == os.fspath(target):
            attempts.append(time.monotonic())
            if failures is None or len(attempts) <= failures:
                raise PermissionError(errno.EACCES, "The process cannot access the file", os.fspath(src), None,
                                      os.fspath(dst))
        return real_replace(src, dst, *a, **k)
    monkeypatch.setattr(os, "replace", replace)
    return attempts


def test_brief_lock_on_layout_save_is_retried(tmp_path, monkeypatch):
    """Q5: Windows'ta OneDrive/Defender duzen.json'u ya da yeni geçici dosyayı anlık tutunca os.replace'in ilk
    PermissionError'ı 'Düzen kaydedilemedi' uyarısı veriyordu. Kısa aralarla yeniden denenir."""
    p = tmp_path / "duzen.json"
    lm.save_layout(p, _OLD)
    attempts = _flaky_replace(monkeypatch, p, failures=2)
    lm.save_layout(p, dict(lm.DEFAULT_LAYOUT))
    assert len(attempts) == 3 and lm.load_layout(p) == lm.DEFAULT_LAYOUT
    assert sorted(x.name for x in tmp_path.iterdir()) == ["duzen.json"]


def test_lasting_lock_on_layout_save_gives_up_quickly(tmp_path, monkeypatch):
    """Q5: kalıcı kilitte birkaç kısa denemeden sonra PermissionError çağırana (uyarıya) gider; eski düzen kalır, geçici
    dosya kalmaz, bekleme kısa (her sürüklemede çalışır, arayüz donmamalı)."""
    from matematigin_mantigi.core import question_loader
    p = tmp_path / "duzen.json"
    lm.save_layout(p, _OLD)
    attempts = _flaky_replace(monkeypatch, p, failures=None)
    t0 = time.monotonic()
    with pytest.raises(PermissionError):
        lm.save_layout(p, dict(lm.DEFAULT_LAYOUT))
    assert len(attempts) == len(question_loader.REPLACE_RETRY_S) + 1 and time.monotonic() - t0 < 2.0
    assert lm.load_layout(p) == _OLD and sorted(x.name for x in tmp_path.iterdir()) == ["duzen.json"]


def test_stale_layout_temp_files_are_removed_after_a_successful_save(tmp_path):
    """Q5: çökmede kalan eski '.duzen.json.<8 onaltılık>.tmp' artıkları başarılı bir kayıttan sonra silinir (bir saatten
    eskiler); yenileri ve kalıba uymayanlar kalır."""
    old = time.time() - 2 * 3600
    for name in (".duzen.json.0123abcd.tmp", ".duzen.json.fedcba98.tmp", ".duzen.json.yedek.tmp"):
        f = tmp_path / name
        f.write_text("{", encoding="utf-8")
        if name != ".duzen.json.fedcba98.tmp":
            os.utime(f, (old, old))
    lm.save_layout(tmp_path / "duzen.json", _OLD)
    assert sorted(x.name for x in tmp_path.iterdir()) == [".duzen.json.fedcba98.tmp", ".duzen.json.yedek.tmp",
                                                         "duzen.json"]


def test_load_layout_reads_legacy_integer_file_unchanged(tmp_path):
    """Görev 4 öncesi (serbest boyutlandırmadan önce) yazılmış tamsayı hücreli bir duzen.json bugün de
    aynı düzeni vermeli — geriye uyumluluk."""
    p = tmp_path / "duzen.json"
    p.write_text(json.dumps({
        "soru": {"col": 2, "row": 1, "col_span": 5, "row_span": 4},
        "ipucu": {"col": 7, "row": 1, "col_span": 5, "row_span": 4},
        "webcam": {"col": 0, "row": 8, "col_span": 2, "row_span": 2},
    }), encoding="utf-8")
    layout = lm.load_layout(p)
    assert layout["soru"] == lm.PanelGeom(2, 1, 5, 4)
    assert layout["ipucu"] == lm.PanelGeom(7, 1, 5, 4)
    assert layout["webcam"] == lm.PanelGeom(0, 8, 2, 2)


# --- Görev 5: tahta öğeleri (marka, logo, sunucu adı, rozet, durum satırı) ---------------------------

def test_item_keys_match_visibility_keys_strings_exactly():
    """ITEM_KEYS, settings.VISIBILITY_KEYS'teki karşılıklarıyla birebir aynı dizeleri kullanır -- görünürlük
    ve düzen anahtarları hizalı kalsın (Görev 6 buna dayanacak)."""
    from matematigin_mantigi.core.settings import VISIBILITY_KEYS
    visibility_key_strings = {k for k, _ in VISIBILITY_KEYS}
    assert lm.ITEM_KEYS == ("brand", "logo", "presenter", "badge", "status")
    assert set(lm.ITEM_KEYS) <= visibility_key_strings


def test_item_pos_pixel_round_trip():
    """item_pos_from_pixel/item_pixel_from_pos: stage_rect başlangıcına göreli piksel <-> kesirli ItemPos."""
    stage_w, stage_h = 1600, 900
    pos = lm.item_pos_from_pixel(480, 45, stage_w, stage_h)
    assert pos == lm.ItemPos(480 / 1600, 45 / 900)
    assert lm.item_pixel_from_pos(pos, stage_w, stage_h) == (480, 45)


def test_to_json_from_json_round_trips_item_positions():
    """Öğe konumları (ItemPos) da bölgeler gibi JSON'a yazılıp aynen geri okunmalı."""
    layout: lm.Layout = dict(lm.DEFAULT_LAYOUT)
    layout["brand"] = lm.ItemPos(0.4125, 0.0)
    layout["badge"] = lm.ItemPos(0.91, 0.032)
    text = lm.to_json(layout)
    restored = lm.from_json(text)
    assert restored["brand"] == lm.ItemPos(0.4125, 0.0)
    assert restored["badge"] == lm.ItemPos(0.91, 0.032)
    assert restored["soru"] == lm.DEFAULT_LAYOUT["soru"]
    assert "logo" not in restored and "presenter" not in restored and "status" not in restored


def test_from_json_legacy_zone_only_file_has_no_item_overrides():
    """Eski duzen.json (yalnız bölge anahtarları) öğe anahtarı içermez -- WorkArea bunu 'kayıtlı override
    yok, bugünkü formülü kullan' olarak okur (bkz. test_work_area.py'deki entegrasyon testi)."""
    text = json.dumps({
        "soru": {"col": 0, "row": 0, "col_span": 6, "row_span": 4},
        "ipucu": {"col": 6, "row": 0, "col_span": 6, "row_span": 4},
        "webcam": {"col": 9, "row": 7, "col_span": 3, "row_span": 3},
    })
    layout = lm.from_json(text)
    assert set(layout) == set(lm.ZONE_KEYS)
    for key in lm.ITEM_KEYS:
        assert key not in layout


def test_from_json_ignores_malformed_item_entry_but_keeps_others():
    """Bozuk bir öğe girdisi (float'a çevrilemeyen x) yalnız o anahtarı atlar; aynı dosyadaki başka bir
    öğe anahtarı etkilenmeden okunur -- bozuk bölge girdisiyle aynı 'sessizce yok say' davranışı, ama
    yok saymanın döngüyü tamamen durdurmadığının kanıtı."""
    text = json.dumps({"brand": {"x": "oops", "y": 0.1}, "logo": {"x": 0.02, "y": 0.01}})
    layout = lm.from_json(text)
    assert "brand" not in layout
    assert layout["logo"] == lm.ItemPos(0.02, 0.01)
