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


def cells(wa):
    inner = wa.inner_rect()
    return lm.cell_size(inner.width(), inner.height(), 14)


def test_board_inside_frame_and_zones_use_defaults(qtbot):
    wa, zones = make(qtbot)
    inner = wa.inner_rect()
    assert inner == wa.rect().adjusted(B, B, -B, -B)
    assert wa.board.geometry() == inner                                # çerçeve bandına çizilemez
    soru, ipucu, webcam = (zones[k].geometry() for k in ("soru", "ipucu", "webcam"))
    assert soru.left() == B and soru.top() == B
    assert ipucu.right() == wa.width() - 1 - B
    assert webcam.right() == wa.width() - 1 - B and webcam.bottom() == wa.height() - 1 - B
    assert abs(soru.width() / ipucu.width() - 1) < 0.02


def test_frame_paints_ink_band_and_can_be_hidden(qtbot):
    wa, _ = make(qtbot)
    img = wa.grab().toImage()
    assert img.pixelColor(12, 300).value() < 70                       # çerçeve bandı koyu (degrade)
    assert img.pixelColor(B + 40, 300).name() == "#ffffff"           # tahta beyaz, çizgi yok
    wa.set_frame_visible(False)
    assert wa.inner_rect() == wa.rect() and wa.board.geometry() == wa.rect()
    assert wa.grab().toImage().pixelColor(3, 300).name() == "#ffffff"


def test_title_plate_and_presenter_name_positions(qtbot):
    wa, zones = make(qtbot)
    assert wa.brand.text() == "Matematiğin Mantığı" and wa.brand.y() == 0
    assert abs(wa.brand.x() + wa.brand.width() // 2 - wa.width() // 2) <= 1
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
    inner = wa.inner_rect()
    assert not wa.logo_is_file and wa.logo_label.text() == "MM"
    assert wa.logo_label.x() == inner.x() + 12 and wa.logo_label.y() == 2
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


def test_recording_rect_covers_whole_work_area(qtbot):
    wa, _ = make(qtbot)
    x, y, w, h, dpr = wa.recording_rect()
    assert (w, h) == (wa.width(), wa.height()) and dpr >= 1.0         # çerçeve de kayda girer


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
