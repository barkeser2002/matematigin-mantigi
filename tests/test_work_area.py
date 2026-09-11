from PyQt6.QtCore import QPoint, Qt

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
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-int(cw * 2), 0))
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
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        QTest.mouseRelease(win, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end + QPoint(1, 0))
    assert sig.args[0]["webcam"] == lm.PanelGeom(7, 7, 3, 3)
    assert wa.board.is_empty()                                        # tıklama tuvale çizim olarak gitmedi


def test_edit_mode_resize_from_corner(qtbot):
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    corner = zones["soru"].geometry().bottomRight() - QPoint(6, 6)
    cw, ch = cells(wa)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=corner)
    qtbot.mouseMove(wa, corner + QPoint(0, int(ch)))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=corner + QPoint(0, int(ch)))
    assert sig.args[0]["soru"] == lm.PanelGeom(0, 0, 6, 5)


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
