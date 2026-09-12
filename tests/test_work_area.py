import json

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtWidgets import QWidget

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui import theme
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.work_area import WorkArea
from matematigin_mantigi.ui.zone import Zone

FAM = FontFamilies("Arial", "Arial", False)
B = theme.FRAME_BAND


def make(qtbot):
    wa = WorkArea(FAM)
    qtbot.addWidget(wa)
    zones = {}
    for key in lm.ZONE_KEYS:
        z = Zone()
        wa.add_zone(key, z)
        zones[key] = z
    wa.resize(1832, 1080)
    wa.show()
    qtbot.waitExposed(wa)
    return wa, zones


class DprArea(WorkArea):
    """devicePixelRatioF()'ü testten sürer: Windows'ta 125/150/175% ölçek kesirli dpr üretir
    (app.py: HighDpiScaleFactorRoundingPolicy.PassThrough)."""

    dpr = 1.0

    def devicePixelRatioF(self) -> float:
        return self.dpr


def cells(wa):
    inner = wa.inner_rect()
    return lm.cell_size(inner.width(), inner.height(), 14)


def item_widgets(wa):
    return {"brand": wa.brand, "logo": wa.logo_label, "presenter": wa.name_label,
            "badge": wa.badge_slot, "status": wa.status_label}


def brightest(img, y, xs) -> int:
    return max(img.pixelColor(x, y).value() for x in xs)


def test_board_inside_frame_and_zones_use_defaults(qtbot):
    wa, zones = make(qtbot)
    stage, inner = wa.stage_rect(), wa.inner_rect()
    assert abs(stage.width() / stage.height() - 16 / 9) < 0.01          # sahne 16:9
    assert stage != wa.rect() and wa.rect().contains(stage)             # kenarlarda bant kaldı
    assert inner == stage.adjusted(B, B, -B, -B)                        # bant sahnenin içine iner
    assert wa.board.geometry() == inner                                # çerçeve bandına çizilemez
    soru, ipucu, webcam = (zones[k].geometry() for k in ("soru", "ipucu", "webcam"))
    assert soru.left() == stage.left() + B and soru.top() == stage.top() + B
    assert ipucu.right() == stage.right() - B
    assert webcam.right() == stage.right() - B and webcam.bottom() == stage.bottom() - B
    assert abs(soru.width() / ipucu.width() - 1) < 0.02


def test_frame_paints_ink_band_and_can_be_hidden(qtbot):
    wa, _ = make(qtbot)
    stage = wa.stage_rect()
    y = stage.center().y()
    img = wa.grab().toImage()
    assert img.pixelColor(stage.left() + 12, y).value() < 70            # çerçeve bandı koyu (degrade)
    assert img.pixelColor(stage.left() + B + 40, y).name() == "#ffffff"  # tahta beyaz, çizgi yok
    wa.set_frame_visible(False)
    assert wa.inner_rect() == stage and wa.board.geometry() == stage    # bant yok: tahta tüm sahne
    assert wa.grab().toImage().pixelColor(stage.left() + 3, y).name() == "#ffffff"


def test_letterbox_stays_visible_when_frame_is_hidden(qtbot):
    """Çerçeve kapalıyken de sahne dışı ölü bölge görünür kalmalı: orada çizilen mürekkep kayda girmez."""
    wa, _ = make(qtbot)
    wa.set_frame_visible(False)
    stage = wa.stage_rect()
    assert wa.aspect_lock and stage.top() > 4 and stage.left() > 0      # bant gerçekten var
    img = wa.grab().toImage()
    inside = img.pixelColor(stage.center().x(), stage.top() + 200)
    band_top = img.pixelColor(stage.center().x(), stage.top() - 4)
    band_left = img.pixelColor(stage.left() - 2, stage.center().y())
    assert inside.name() == "#ffffff"
    assert band_top != inside and band_left != inside                  # sınır belli
    assert band_top.name() == theme.INK and band_left.name() == theme.INK
    wa.set_aspect_lock(False)                                          # kilit kapalı: eski tek renk görüntü
    assert wa.stage_rect() == wa.rect()
    assert wa.grab().toImage().pixelColor(3, 300).name() == "#ffffff"


def test_frame_dots_follow_the_stage(qtbot):
    """Nokta dokusu sahnenin kenarında: widget'a çivili kalsaydı üst/alt sıralar kayıttan kırpılırdı."""
    wa, _ = make(qtbot)
    stage = wa.stage_rect()
    img = wa.grab().toImage()
    xs = range(stage.right() - 200, stage.right() - 10)                 # marka plakası ve logodan uzak
    # Degrade aşağı doğru koyulaşır; daha aşağıdaki sıranın daha parlak olması ancak noktalarla mümkün.
    assert brightest(img, stage.top() + 5, xs) > brightest(img, stage.top() - 4, xs)
    assert brightest(img, stage.bottom() - 4, xs) > brightest(img, wa.height() - 5, xs)


def test_title_plate_and_presenter_name_positions(qtbot):
    wa, zones = make(qtbot)
    stage = wa.stage_rect()
    assert wa.brand.text() == "Matematiğin Mantığı" and wa.brand.y() == stage.top()
    assert abs(wa.brand.x() + wa.brand.width() // 2 - stage.center().x()) <= 1
    cam = zones["webcam"].geometry()
    assert wa.name_label.text() == "Koray Varol"
    assert wa.name_label.geometry().bottom() < cam.top()               # webcam'in üstünde
    assert wa.name_label.geometry().right() <= cam.right()
    wa.set_presenter_name("")
    assert wa.name_label.isHidden()


def test_ink_layer_sits_above_zones_but_below_webcam(qtbot):
    wa, zones = make(qtbot)
    assert wa.ink.geometry() == wa.board.geometry()
    order = [c for c in wa.children() if c in (wa.board, wa.ink, zones["soru"], zones["ipucu"], zones["webcam"])]
    assert order.index(wa.board) < order.index(zones["soru"]) < order.index(wa.ink) < order.index(zones["webcam"])
    assert order.index(zones["ipucu"]) < order.index(wa.ink)


def test_logo_monogram_and_file(qtbot, tmp_path):
    from PyQt6.QtGui import QImage
    wa, _ = make(qtbot)
    inner, stage = wa.inner_rect(), wa.stage_rect()
    assert not wa.logo_is_file and wa.logo_label.text() == "MM"
    assert wa.logo_label.x() == inner.x() + 12 and wa.logo_label.y() == stage.top() + 2
    assert stage.contains(wa.logo_label.geometry())                    # logo sahnenin içinde: kayda girer
    assert wa.logo_label.height() == 48
    img = QImage(200, 100, QImage.Format.Format_RGB32); img.fill(Qt.GlobalColor.red)
    path = tmp_path / "logo.png"; img.save(str(path))
    wa.set_logo(str(path))
    assert wa.logo_is_file and wa.logo_label.text() == "" and wa.logo_label.height() == 48   # 96x48, en-boy korunur
    wa.set_logo("", size=96)
    assert not wa.logo_is_file and wa.logo_label.width() == 96 and wa.logo_size == 96
    wa.set_logo(str(path), size=32)
    assert wa.logo_label.height() == 32


def test_zone_forwards_drawing_to_board(qtbot):
    wa, zones = make(qtbot)
    z = zones["soru"]
    start, end = QPoint(100, 100), QPoint(180, 160)
    qtbot.mousePress(z, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(z, end)
    qtbot.mouseRelease(z, Qt.MouseButton.LeftButton, pos=end)
    assert not wa.board.is_empty()
    assert wa.board.strokes_image().pixelColor(140, 130).alpha() > 0    # soru bölgesi tahtanın (0,0)'ında


def test_edit_mode_drag_moves_and_snaps(qtbot):
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    start = zones["webcam"].geometry().center()
    cw, ch = cells(wa)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    # Ctrl: bırakış artık serbest (bkz. test_edit_mode_drag_free_by_default_does_not_snap) — ızgaraya
    # yapışmak için Ctrl basılı tutulmalı.
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-int(cw * 2), 0),
                           modifier=Qt.KeyboardModifier.ControlModifier)
    assert sig.args[0]["webcam"] == lm.PanelGeom(7, 7, 3, 3)
    assert wa.board.is_empty()                                        # düzen modunda çizim olmaz


def test_edit_mode_drag_through_real_event_path(qtbot):
    """Gerçek olay yolu (pencere -> çocuk isabet testi): bölge ve tuval şeffaf olmalı, sürükleme buraya ulaşmalı."""
    from PyQt6.QtTest import QTest
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    win = wa.windowHandle()
    start = zones["webcam"].geometry().center()
    cw, ch = cells(wa)
    end = start + QPoint(-int(cw * 2), 0)
    QTest.mousePress(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
    QTest.mouseMove(win, end)
    QTest.mouseMove(win, end + QPoint(1, 0))
    # Ctrl: ızgaraya yapış (bırakış artık varsayılan olarak serbest).
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, end + QPoint(1, 0))
    assert sig.args[0]["webcam"] == lm.PanelGeom(7, 7, 3, 3)
    assert wa.board.is_empty()                                        # tıklama tuvale çizim olarak gitmedi


def test_edit_mode_resize_from_corner(qtbot):
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    corner = zones["soru"].geometry().bottomRight() - QPoint(6, 6)
    cw, ch = cells(wa)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=corner)
    qtbot.mouseMove(wa, corner + QPoint(0, int(ch)))
    # Ctrl: ızgaraya yapış (bırakış artık varsayılan olarak serbest).
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=corner + QPoint(0, int(ch)),
                           modifier=Qt.KeyboardModifier.ControlModifier)
    assert sig.args[0]["soru"] == lm.PanelGeom(0, 0, 6, 5)


def test_edit_mode_drag_free_by_default_does_not_snap(qtbot):
    """Serbest sürükleme (varsayılan, Ctrl basılı değil): hücre değeri tam sayıya yapışmaz, bölge tam
    olarak bırakıldığı piksel konumunda/boyutunda kalır."""
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    start = zones["webcam"].geometry().center()
    end = start + QPoint(-37, -5)                     # ızgara adımının katı olmayan bir kaydırma
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, end)
    dragged = QRect(zones["webcam"].geometry())
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)
    g = sig.args[0]["webcam"]
    assert g.col != round(g.col) or g.row != round(g.row)            # yapışmadı: en az biri kesirli
    assert zones["webcam"].geometry() == dragged                     # widget bırakıldığı yerde kaldı


def test_edit_mode_drag_clamps_live_to_inner_rect(qtbot):
    """Bölge tahtanın dışına sürüklenmeye çalışılsa da sürükleme sırasında inner_rect() içinde kalır
    (canlı kırpma) — eskiden yalnız bırakışta clamp() kurtarıyordu."""
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    inner = wa.inner_rect()
    start = zones["soru"].geometry().center()
    end = QPoint(inner.x() - 500, inner.y() - 500)    # tahtanın çok dışı
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, end)
    assert inner.contains(zones["soru"].geometry())                  # sürüklenirken bile tahtanın içinde
    with qtbot.waitSignal(wa.layoutChanged):
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)
    assert inner.contains(zones["soru"].geometry())


def test_edit_mode_resize_from_nw_corner_moves_and_resizes(qtbot):
    """Kuzey-batı köşesinden boyutlandırma hem konumu hem boyutu değiştirir; karşı (güney-doğu) köşe
    yerinde kalır."""
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    geo = zones["ipucu"].geometry()
    start = geo.topLeft() + QPoint(4, 4)              # kuzey-batı tutamağı
    d = QPoint(30, 20)
    end = start + d
    right, bottom = geo.right(), geo.bottom()
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, end)
    new_geo = zones["ipucu"].geometry()
    assert new_geo.left() == geo.left() + d.x() and new_geo.top() == geo.top() + d.y()
    assert new_geo.right() == right and new_geo.bottom() == bottom   # karşı köşe sabit kaldı
    with qtbot.waitSignal(wa.layoutChanged):
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)


def test_free_resize_below_two_cells_survives_save_and_load(qtbot, tmp_path):
    """clamp_free'nin asgarisi 80x60 px'ten türer, MIN_SPAN=2 hücreden değil. Yükleme yolu (from_json,
    WorkArea.set_layout) hâlâ clamp() kullansaydı, serbestçe 2 hücreden küçük boyutlandırılmış bir bölge
    her yeniden başlatmada sessizce büyürdü -- bu da görevin amacını (serbest boyutlandırmanın kalıcı
    olması) boşa çıkarırdı."""
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    geo = zones["webcam"].geometry()
    start = geo.topLeft() + QPoint(4, 4)                          # kuzey-batı tutamağı
    end = start + QPoint(geo.width() - 100, geo.height() - 70)    # ~100x70 px kalsın: >=80x60, <2 hücre
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, end)
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)
    saved = sig.args[0]["webcam"]
    assert saved.col_span < lm.MIN_SPAN and saved.row_span < lm.MIN_SPAN     # gerçekten 2 hücreden küçük

    p = tmp_path / "duzen.json"
    lm.save_layout(p, wa.layout())
    loaded = lm.load_layout(p)
    assert loaded["webcam"] == saved                              # from_json büyütmedi

    wa.set_layout(loaded)                                         # MainWindow kurucusundaki gerçek yol
    assert wa.layout()["webcam"] == saved                         # set_layout de büyütmedi


def test_free_resize_round_trips_across_very_different_window_sizes(qtbot, tmp_path):
    """Kesirli bir düzen çözünürlükten bağımsız olmalı. Büyük bir pencerede (2560x1440, tam ekran gibi)
    80x60 px sürükleme asgarisine küçültülen bir bölge, kaydedilip ÇOK farklı ölçüde bir pencerede (1280x720)
    yüklendiğinde o pencerenin kendi (çok daha kaba) piksel tabanına göre büyütülmemeli -- ve tersi de
    geçerli. (`test_free_resize_below_two_cells_survives_save_and_load` tek pencere boyutunda -- 1832x1080 --
    çalıştığından, önceki sabit 1920x1080 referans-alan hatasını yakalamıyordu: o boyuttaki değer zaten
    referans tabanının üstündeydi.)"""
    wa, _ = make(qtbot)

    wa.resize(2560, 1440)                                           # büyük "tam ekran" pencere
    inner_big = wa.inner_rect()
    saved_big = lm.free_rect(0, 0, lm.MIN_FREE_W, lm.MIN_FREE_H,
                              inner_big.width(), inner_big.height(), theme.GRID_GAP)
    assert saved_big.col_span < 0.55 and saved_big.row_span < 0.55   # eski (yanlış) 1920x1080 referans tabanından bile küçük

    p_big = tmp_path / "buyuk.json"
    lm.save_layout(p_big, dict(wa.layout(), webcam=saved_big))

    wa.resize(1280, 720)                                            # ÇOK farklı, küçük bir pencere
    wa.set_layout(lm.load_layout(p_big))
    assert wa.layout()["webcam"] == saved_big                       # küçük pencerenin kaba tabanına büyümedi

    # ters yön: aynı 80x60 px, küçük pencerede çok daha büyük bir hücre payına karşılık gelir.
    inner_small = wa.inner_rect()
    saved_small = lm.free_rect(0, 0, lm.MIN_FREE_W, lm.MIN_FREE_H,
                                inner_small.width(), inner_small.height(), theme.GRID_GAP)
    assert saved_small.col_span > saved_big.col_span and saved_small.row_span > saved_big.row_span

    p_small = tmp_path / "kucuk.json"
    lm.save_layout(p_small, dict(wa.layout(), webcam=saved_small))

    wa.resize(2560, 1440)                                           # büyük pencereye dön
    wa.set_layout(lm.load_layout(p_small))
    assert wa.layout()["webcam"] == saved_small                     # büyük pencerenin ince tabanına küçülmedi


def test_no_drag_outside_edit_mode(qtbot):
    wa, zones = make(qtbot)
    before = zones["webcam"].geometry()
    start = before.center()
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, start + QPoint(-300, 0))
    qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-300, 0))
    assert zones["webcam"].geometry() == before


def test_reset_layout_emits_default(qtbot):
    wa, _ = make(qtbot)
    wa.set_layout(dict(lm.DEFAULT_LAYOUT, webcam=lm.PanelGeom(0, 8, 2, 2)))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        wa.reset_layout()
    assert sig.args[0] == lm.DEFAULT_LAYOUT


def test_recording_rect_matches_16_9_stage(qtbot):
    wa, _ = make(qtbot)
    stage = wa.stage_rect()
    x, y, w, h, dpr = wa.recording_rect()
    assert (w, h) == (stage.width(), stage.height()) and dpr >= 1.0    # kayıt sahneye eşit (çerçeve dahil)
    assert abs(w / h - 16 / 9) < 0.01 and w % 2 == 0 and h % 2 == 0    # ffmpeg -s WxH tam 16:9
    top_left = wa.mapToGlobal(stage.topLeft())
    assert (x, y) == (top_left.x(), top_left.y())                      # bantlar kayda girmez
    assert (stage.left(), stage.top()) == ((wa.width() - w) // 2, (wa.height() - h) // 2)


def test_stage_is_16_9_and_centred_for_any_window_ratio(qtbot):
    wa, _ = make(qtbot)
    for width, height in ((1832, 1080), (900, 1200), (1000, 1000), (1280, 400)):
        wa.resize(width, height)
        stage = wa.stage_rect()
        assert abs(stage.width() / stage.height() - 16 / 9) < 0.01, (width, height, stage)
        assert stage.width() % 2 == 0 and stage.height() % 2 == 0, stage      # tek sayı oranı bozar
        assert stage.width() <= width and stage.height() <= height, stage
        assert stage.left() == (width - stage.width()) // 2, stage            # ortalı
        assert stage.top() == (height - stage.height()) // 2, stage
        assert wa.inner_rect() == stage.adjusted(B, B, -B, -B), stage
        assert wa.board.geometry() == wa.inner_rect()


def scaled_width(phys_w: int, phys_h: int, out_height: int) -> int:
    """ffmpeg `scale=-2:{out_height}`: genişlik orana göre en yakın çift sayıya yuvarlanır."""
    return round(out_height * phys_w / phys_h / 2) * 2


def test_stage_ratio_is_exact_and_records_at_2560x1440(qtbot):
    """Sahne 16:9'a yaklaşık değil, TAM eşit; yoksa ffmpeg 2560x1440 yerine 2558x1440 üretir.
    Kesirli dpr dahil (Windows 125/150/175%): RecordRect.physical() mantıksal ölçüyü dpr ile çarpıp
    iki ekseni bağımsız çiftlediği için sahne dpr'nin paydasına da hizalanmalı."""
    from pathlib import Path
    from matematigin_mantigi.core.recorder import ffmpeg_args, record_rect_for
    wa = DprArea(FAM)
    qtbot.addWidget(wa)
    for dpr in (1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5):        # Windows ölçek merdiveni
        wa.dpr = dpr
        for width, height in ((1832, 1080), (1920, 1080), (2560, 1440), (1466, 900), (900, 1200),
                              (1280, 400), (1192, 720), (1278, 768)):
            wa.resize(width, height)
            stage = wa.stage_rect()
            assert stage.width() * 9 == stage.height() * 16, (dpr, width, height, stage)  # tam 16:9
            assert stage.width() % 2 == 0 and stage.height() % 2 == 0, (dpr, stage)
            phys = record_rect_for((0, 0, stage.width(), stage.height(), dpr)).physical()
            assert phys.width * 9 == phys.height * 16, (dpr, stage, phys)      # _even() oranı bozmuyor
            assert phys.width % 2 == 0 and phys.height % 2 == 0, (dpr, phys)
            assert scaled_width(phys.width, phys.height, 1440) == 2560, (dpr, stage, phys)
            assert scaled_width(phys.width, phys.height, 1080) == 1920, (dpr, stage, phys)
    wa.dpr = 1.0
    wa.resize(1832, 1080)
    stage = wa.stage_rect()
    phys = record_rect_for((0, 0, stage.width(), stage.height(), 1.0)).physical()
    args = ffmpeg_args("ffmpeg", phys.width, phys.height, 60, Path("k.mp4"), out_height=1440)
    assert f"{phys.width}x{phys.height}" in args and "scale=-2:1440:flags=bilinear" in args


def test_aspect_lock_off_restores_full_work_area(qtbot):
    wa, _ = make(qtbot)
    wa.set_aspect_lock(False)
    assert wa.stage_rect() == wa.rect()                                # eski sözleşme: sahne = tüm alan
    assert wa.inner_rect() == wa.rect().adjusted(B, B, -B, -B)
    x, y, w, h, _ = wa.recording_rect()
    assert (w, h) == (wa.width(), wa.height())
    assert (x, y) == (wa.mapToGlobal(QPoint(0, 0)).x(), wa.mapToGlobal(QPoint(0, 0)).y())
    wa.set_aspect_lock(True)
    assert wa.stage_rect() != wa.rect() and abs(wa.stage_rect().width() / wa.stage_rect().height() - 16 / 9) < 0.01


def test_edit_overlay_only_in_edit_mode(qtbot):
    wa, _ = make(qtbot)
    assert wa.overlay.isHidden()
    wa.set_edit_mode(True)
    assert wa.overlay.isVisible() and wa.edit_bar.isVisible()
    wa.set_edit_mode(False)
    assert wa.overlay.isHidden()


def test_status_line(qtbot):
    wa, _ = make(qtbot)
    wa.set_status("Araç: Kalem · Kalınlık: 4 px · Basınç: XP-Pen")
    assert wa.status_label.text().startswith("Araç: Kalem")
    inner = wa.inner_rect()
    assert wa.status_label.x() == inner.x() + 12 and wa.status_label.geometry().bottom() <= inner.bottom()


# --- Görev 5: tahta öğeleri de taşınabilsin ------------------------------------------------------------

def test_unmoved_items_render_at_todays_default_positions(qtbot):
    """Hiç sürüklenmemiş öğeler (kayıtlı override yok) bugünkü sert kodlu formüllerle birebir aynı yerde
    olmalı -- else dalı regresyon testi (Görev 5 öncesi davranış)."""
    wa, zones = make(qtbot)
    stage, inner = wa.stage_rect(), wa.inner_rect()
    assert (wa.logo_label.x(), wa.logo_label.y()) == (inner.x() + 12, stage.y() + 2)
    assert (wa.status_label.x(), wa.status_label.y()) == (
        inner.x() + 12, inner.bottom() - wa.status_label.height() - 6)
    assert wa.brand.y() == stage.y()
    assert wa.brand.x() == stage.x() + (stage.width() - wa.brand.width()) // 2
    cam = zones["webcam"].geometry()
    assert (wa.name_label.x(), wa.name_label.y()) == (
        cam.right() - wa.name_label.width() - 8, cam.top() - wa.name_label.height() - 2)
    assert (wa.badge_slot.x(), wa.badge_slot.y()) == (
        inner.right() - wa.badge_slot.width() - 12, inner.y() + 4)


def test_edit_mode_drag_moves_brand_and_round_trips_via_duzen_json(qtbot, tmp_path):
    """Düzen modunda marka plakasını sürükle -> yeni konuma gidiyor, layoutChanged yayılıyor, duzen.json
    yuvarlak yolculuğundan sonra aynı yerde."""
    wa, _ = make(qtbot)
    original = (wa.brand.x(), wa.brand.y())
    wa.set_edit_mode(True)
    start = wa.brand.geometry().center()
    end = start + QPoint(60, 4)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, end)
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)
    assert isinstance(sig.args[0]["brand"], lm.ItemPos)
    moved = (wa.brand.x(), wa.brand.y())
    assert moved != original

    p = tmp_path / "duzen.json"
    lm.save_layout(p, wa.layout())
    wa.set_layout(lm.load_layout(p))
    assert (wa.brand.x(), wa.brand.y()) == moved


def test_dragged_item_stays_proportional_to_stage_after_resize(qtbot):
    """Sürüklenmiş bir öğe pencere yeniden boyutlandığında (letterbox bantları kayarken bile) sahneye göre
    aynı oranlı noktada kalmalı -- Görev 5'in koordinat tabanı kararının (stage_rect, inner_rect DEĞİL)
    doğrudan testi."""
    wa, _ = make(qtbot)
    wa.set_layout(dict(wa.layout(), brand=lm.ItemPos(0.3, 0.1)))
    stage1 = wa.stage_rect()
    assert (wa.brand.x(), wa.brand.y()) == (stage1.x() + round(0.3 * stage1.width()),
                                            stage1.y() + round(0.1 * stage1.height()))

    wa.resize(900, 1200)                       # çok farklı en-boy oranı: bantlar tamamen değişir
    stage2 = wa.stage_rect()
    assert stage2 != stage1
    assert (wa.brand.x(), wa.brand.y()) == (stage2.x() + round(0.3 * stage2.width()),
                                            stage2.y() + round(0.1 * stage2.height()))


def test_badge_drag_applies_to_real_widget_bound_after_construction(qtbot):
    """Rozet tembel okunuyor: MainWindow work_area.badge_slot'u gerçek RecordBadge ile değiştirdikten
    (main_window.py:83) SONRA rozet sürüklenebiliyor -- __init__'te yakalanmış öksüz bir placeholder'a
    değil, o anki self.badge_slot'a uygulanıyor."""
    wa, _ = make(qtbot)
    placeholder = wa.badge_slot
    placeholder_pos_before = (placeholder.x(), placeholder.y())

    real_badge = QWidget(wa)                   # main_window.py:83'teki RecordBadge atamasını taklit eder
    real_badge.resize(160, 28)
    real_badge.show()
    wa.badge_slot = real_badge
    wa.relayout()                              # __init__ sonrası ilk relayout: gerçek akışla aynı sıra

    wa.set_edit_mode(True)
    # Rozetin dikey merkezi ipucu bölgesinin üst kenar tutamağına (GRIP=18px) çok yakın -- bilerek
    # rozetin alt kısmından tutuyoruz, yoksa isabet testi tutamağa mı yoksa rozete mi gittiği belirsiz olur.
    start = QPoint(real_badge.geometry().center().x(), real_badge.geometry().bottom() - 3)
    end = start + QPoint(-30, 10)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, end)
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=end)

    assert isinstance(sig.args[0]["badge"], lm.ItemPos)
    assert (placeholder.x(), placeholder.y()) == placeholder_pos_before   # öksüz placeholder hiç kıpırdamadı


def test_legacy_duzen_json_without_item_keys_keeps_items_at_default_positions(qtbot, tmp_path):
    """Görev 5 öncesi yazılmış (yalnız bölge anahtarlı) bir duzen.json bugün de sorunsuz okunmalı ve beş
    öğe de varsayılan (bugünkü formül) konumunda kalmalı -- geriye uyumluluk."""
    wa, _ = make(qtbot)
    widgets = item_widgets(wa)
    defaults = {k: (w.x(), w.y()) for k, w in widgets.items()}

    p = tmp_path / "duzen.json"
    p.write_text(json.dumps({
        "soru": {"col": 0, "row": 0, "col_span": 6, "row_span": 4},
        "ipucu": {"col": 6, "row": 0, "col_span": 6, "row_span": 4},
        "webcam": {"col": 9, "row": 7, "col_span": 3, "row_span": 3},
    }), encoding="utf-8")

    wa.set_layout(lm.load_layout(p))
    for k, w in widgets.items():
        assert (w.x(), w.y()) == defaults[k], k
    assert not (set(lm.ITEM_KEYS) & set(wa.layout()))     # dosyada öğe yoktu -> hiç override kaydı yok


# --- Görev 5 düzeltme turu: isabet testi önceliği, taşan bölge tutamağı köşeyle sınırlı --------------

def test_hit_test_center_of_logo_and_badge_returns_the_item_not_a_zone(qtbot):
    """CRITICAL düzeltme: bir bölgenin TEK KENAR tutamağı (köşe değil) artık öğelere koşulsuz öncelikli
    değil. Rozetin merkezi ipucu'nun üst kenar tutamağına, logo'nun merkezi de soru'nun üst kenar
    tutamağına isabet eder (GRIP=18px) -- düzeltmeden önce ikisi de kendi öğesi değil, bölgenin kenar
    tutamağı olarak çözümlenirdi (rozette isabetlerin ~%79'u, logo'da ~%42'si -- review bulgusu)."""
    wa, _ = make(qtbot)
    assert wa._hit(wa.logo_label.geometry().center()) == ("logo", "move")
    assert wa._hit(wa.badge_slot.geometry().center()) == ("badge", "move")


def test_hit_test_topmost_item_wins_when_items_overlap(qtbot):
    """IMPORTANT 1: öğeler kendi aralarında çakışırsa görsel olarak ÜSTTEKİ (gerçek Qt yığın sırası,
    raise_() ile güncellenir) kazanmalı. logo, brand'den SONRA raise_() edilir (bkz. relayout()'taki
    _place_item çağrı sırası) -- yani logo marka plakasının üstüne sürüklenirse isabet testi logo'yu
    döndürmeli, brand'i değil. Bu, self._items sözlük sırasıyla _place_item çağrı sırasının elle senkron
    tutulmasına değil, self.children()'dan (raise_()'in bizzat güncellediği) türetilen gerçek isabet
    sırasına dayanır -- ikisi ileride ayrı ayrı değiştirilse bile bu test görüneni yansıtmaya devam eder."""
    wa, _ = make(qtbot)
    stage = wa.stage_rect()
    target = wa.brand.geometry().center()                       # brand'in tam ortası
    top_left = target - QPoint(wa.logo_label.width() // 2, wa.logo_label.height() // 2)
    frac = lm.item_pos_from_pixel(top_left.x() - stage.x(), top_left.y() - stage.y(),
                                  stage.width(), stage.height())
    wa.set_layout(dict(wa.layout(), logo=frac))
    assert wa.logo_label.geometry().contains(target) and wa.brand.geometry().contains(target)  # çakışıyor
    assert wa._hit(target) == ("logo", "move")                  # üstteki (logo) kazanır, brand değil


def test_reset_layout_also_clears_item_overrides(qtbot):
    """IMPORTANT 2: reset_layout() ("Sıfırla") bölgelerle simetrik olarak öğe geçersiz kılmalarını da
    temizler (set_layout TAM DEĞİŞTİRİR, birleştirmez) -- korunması istenen, ama pinlenmemiş davranış."""
    wa, _ = make(qtbot)
    wa.set_layout(dict(wa.layout(), brand=lm.ItemPos(0.2, 0.05)))
    assert "brand" in wa.layout()
    wa.reset_layout()
    assert "brand" not in wa.layout()


# --- Görev 6: göz düğmeleri + tam panel gizleme -----------------------------------------------------

EYE_KEYS = {"question_zone", "hint_zone", "webcam", "brand", "logo", "presenter", "badge", "status"}


def test_hidden_zone_is_excluded_from_hit_test(qtbot):
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    center = zones["soru"].geometry().center()
    assert wa._hit(center) == ("soru", "move")            # önce sürüklenebilir (regresyon emniyeti)
    wa.set_item_visible("question_zone", False)
    assert wa._hit(center) is None                        # artık yokmuş gibi davranılır, sürüklenmez


def test_hidden_item_is_excluded_from_hit_test(qtbot):
    wa, _ = make(qtbot)
    wa.set_edit_mode(True)
    center = wa.logo_label.geometry().center()
    assert wa._hit(center) == ("logo", "move")
    wa.set_item_visible("logo", False)
    assert wa._hit(center) is None


def test_hidden_zone_and_item_render_as_translucent_ghost_not_normal_outline(qtbot):
    """_EditOverlay artık gizli bölge/öğeyi normal kesikli çerçeve yerine yarı saydam bir 'hayalet'
    dolguyla çiziyor (bkz. work_area._paint_ghost) -- kesikli çerçeve hiçbir zaman iç dolgu çizmediği
    için bölge/öğenin ortası düzen modunda bugün beyaz kalır; hayalet modda artık dolu."""
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    zprobe = zones["webcam"].geometry().center()
    iprobe = wa.badge_slot.geometry().center()             # gizli varsayılan placeholder: kendi başına hiç çizmez
    img = wa.grab().toImage()
    assert img.pixelColor(zprobe).name() == "#ffffff"
    assert img.pixelColor(iprobe).name() == "#ffffff"

    wa.set_item_visible("webcam", False)
    wa.set_item_visible("badge", False)
    img2 = wa.grab().toImage()
    assert img2.pixelColor(zprobe).name() != "#ffffff"     # hayalet dolgu artık var
    assert img2.pixelColor(iprobe).name() != "#ffffff"


def test_eye_buttons_exist_for_all_zones_and_items_and_only_show_in_edit_mode(qtbot):
    wa, _ = make(qtbot)
    assert EYE_KEYS <= set(wa._eye_buttons)
    for key in EYE_KEYS:
        assert wa._eye_buttons[key].isHidden()             # henüz düzen modu kapalı
    wa.set_edit_mode(True)
    for key in EYE_KEYS:
        assert wa._eye_buttons[key].isVisible() and wa._eye_buttons[key].isChecked()   # varsayılan görünür
    wa.set_edit_mode(False)
    for key in EYE_KEYS:
        assert wa._eye_buttons[key].isHidden()


def test_eye_button_click_toggles_hit_test_and_emits_signal(qtbot):
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    btn = wa._eye_buttons["webcam"]
    center = zones["webcam"].geometry().center()
    assert btn.isChecked() and wa._hit(center) == ("webcam", "move")

    with qtbot.waitSignal(wa.visibilityToggled) as sig:
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert sig.args == ["webcam", False]
    assert not btn.isChecked() and wa._hit(center) is None

    with qtbot.waitSignal(wa.visibilityToggled) as sig2:
        qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert sig2.args == ["webcam", True]
    assert btn.isChecked() and wa._hit(center) == ("webcam", "move")


def test_eye_button_click_through_real_event_path(qtbot):
    """Göz düğmesi gerçek bir Qt çocuğu: pencere seviyesinde yönlendirilen gerçek bir tıklama (qtbot.mouseClick
    gibi widget'a doğrudan gönderilen değil) düğmeye ulaşmalı, WorkArea.mousePressEvent/_hit()'e değil --
    aksi hâlde düzen modunda düğme yalnız sentetik testlerde çalışıp gerçek kullanıcıda tıklanamaz olurdu."""
    from PyQt6.QtTest import QTest
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    btn = wa._eye_buttons["webcam"]
    center = btn.mapTo(wa, btn.rect().center())
    win = wa.windowHandle()
    QTest.mouseClick(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, center)
    assert not btn.isChecked()
    assert wa._hit(zones["webcam"].geometry().center()) is None   # tıklama sürükleme başlatmadı, görünürlüğü kapattı


def test_eye_buttons_stay_reachable_at_common_window_sizes(qtbot):
    """CRITICAL düzeltme (review): düğme WorkArea'nın kendi sınırlarının dışına taşarsa -- pencere
    WorkArea'ya sıfır kenar boşluğuyla bitişik olduğundan (main_window.py) -- fiilen pencerenin dışında/
    başlık çubuğunda kalır, tıklanamaz olur. Bu, çerçeve kapalıyken ya da pencere tam/dara-yakın 16:9
    iken (stage.y() == 0'a çok yakın) YAYGINDIR: 1920x1080, 1280x720, 1600x900 hepsi review'da brand/
    logo/soru için negatif y üretiyordu. `wa.childAt(center)` gerçek Qt hit-testiyle (childAt overlay'in
    WA_TransparentForMouseEvents'ini atlar) düğmenin GERÇEKTEN tıklanabilir olduğunu doğrular."""
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    sizes = [(1832, 1080), (1920, 1080), (1280, 720), (1600, 900), (1600, 850), (1920, 1000)]
    for w, h in sizes:
        wa.resize(w, h)
        for key in EYE_KEYS:
            btn = wa._eye_buttons[key]
            center = btn.geometry().center()
            assert wa.rect().contains(center), (w, h, key, center)
            assert wa.childAt(center) is btn, (w, h, key, center)

    # Çerçeve kapalıyken inner_rect == stage_rect: "soru" bölgesi de stage'in en üst satırına biner.
    wa.set_frame_visible(False)
    for w, h in ((1920, 1080), (1280, 720), (1600, 900)):
        wa.resize(w, h)
        for key in ("question_zone", "hint_zone", "webcam"):
            btn = wa._eye_buttons[key]
            center = btn.geometry().center()
            assert wa.rect().contains(center), (w, h, key, center)
            assert wa.childAt(center) is btn, (w, h, key, center)


def test_presenter_name_and_visibility_do_not_stomp_each_other(qtbot):
    """Görev 6'nın 'presenter tuzağı': set_presenter_name artık metni GÖRÜNÜRLÜKTEN bağımsız taşır (eski
    kod boş metin geçerek gizliyordu, bu da metni kalıcı olarak siliyordu) -- set_item_visible ayrı."""
    wa, _ = make(qtbot)
    wa.set_presenter_name("Barış Keser")
    wa.set_item_visible("presenter", False)
    assert wa.name_label.isHidden()                        # dolu ad + kapalı görünürlük -> gizli
    assert wa.name_label.text() == "Barış Keser"           # metin silinmedi, korunuyor

    wa.set_presenter_name("")
    wa.set_item_visible("presenter", True)
    assert wa.name_label.isHidden()                        # açık görünürlük + boş ad -> yine gizli (gösterilecek yok)

    wa.set_presenter_name("Barış Keser")
    assert not wa.name_label.isHidden()                    # ikisi de dolu/açık -> görünür


def test_presenter_visibility_survives_a_later_set_presenter_name_call(qtbot):
    """IMPORTANT (review): sıra tersine çevrilirse de doğru olmalı. Bugüne kadarki testlerin hepsi
    set_presenter_name'i set_item_visible'dan HEMEN ÖNCE çağırıyordu (apply_ui_settings'in kendi sırası
    da bu) -- bu, set_presenter_name'in kendi görünürlük kontrolünü hep maskeliyordu: o satır tamamen
    silinse bile (reviewer'ın doğruladığı gibi) tüm suit hâlâ 282/282 geçiyordu. Burada göz düğmesiyle
    ÖNCE kapatılıyor, SONRA (araya başka hiçbir set_item_visible girmeden) yalnız set_presenter_name
    çağrılıyor -- bir canlı ad-alanı önizlemesinin (yalnız metni güncelleyip görünürlüğe dokunmayan)
    karşılaşacağı sıra. Etiket yine de gizli kalmalı."""
    wa, _ = make(qtbot)
    wa.set_item_visible("presenter", False)
    wa.set_presenter_name("Barış Keser")
    assert wa.name_label.isHidden()


# --- Görev 7: düzenle modunda yazı boyutu kaydırıcısı ---------------------------------------------------

def test_font_scale_slider_exists_with_expected_range_and_default(qtbot):
    wa, _ = make(qtbot)
    assert wa.font_scale_slider.minimum() == 70 and wa.font_scale_slider.maximum() == 160
    assert wa.font_scale_slider.value() == 100
    assert wa.font_scale_label.text() == "Yazı %100"


def test_moving_font_scale_slider_emits_signal_and_updates_label(qtbot):
    wa, _ = make(qtbot)
    with qtbot.waitSignal(wa.fontScaleChanged) as sig:
        wa.font_scale_slider.setValue(150)
    assert sig.args == [1.5]
    assert wa.font_scale_label.text() == "Yazı %150"


def test_set_font_scale_updates_slider_without_reemitting_signal(qtbot):
    """set_font_scale, apply_ui_settings'in HER çağrıda kalıcı değeri geri bildirdiği yol -- MainWindow
    <-> WorkArea arasında sonsuz döngü olmasın diye (fontScaleChanged -> settings.font_scale ->
    apply_ui_settings -> set_font_scale -> ...) sinyali YENİDEN YAYMAMALI."""
    wa, _ = make(qtbot)
    fired = []
    wa.fontScaleChanged.connect(lambda v: fired.append(v))
    wa.set_font_scale(1.25)
    assert wa.font_scale_slider.value() == 125
    assert wa.font_scale_label.text() == "Yazı %125"
    assert fired == []


def test_work_area_set_families_scales_its_own_labels_but_not_logo_monogram(qtbot):
    """WorkArea.set_families (Görev 7) durum satırı/marka plakası/sunucu adını ölçekli aileyle günceller;
    logo monogramı ("MM") KENDİ logo_size kaydırıcısına sahip, tahta yazı ölçeğinin kapsamı DIŞINDA kalmalı
    (bkz. brief envanteri: '-- ölçek dışında')."""
    wa, _ = make(qtbot)
    base_logo_px = wa.logo_label.font().pixelSize()
    wa.set_families(FontFamilies("Arial", "Arial", False, scale=1.5))
    assert wa.status_label.font().pixelSize() == round(10 * 1.5)
    assert wa.brand.font().pixelSize() == round(30 * 1.5)
    assert wa.name_label.font().pixelSize() == round(28 * 1.5)
    assert wa.logo_label.font().pixelSize() == base_logo_px            # dokunulmadı, ölçek dışında kaldı
