from PyQt6.QtCore import QPoint, Qt

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.work_area import WorkArea
from matematigin_mantigi.ui.zone import Zone

FAM = FontFamilies("Arial", "Arial", False)


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


def test_board_fills_area_and_zones_use_defaults(qtbot):
    wa, zones = make(qtbot)
    assert wa.board.geometry() == wa.rect()
    soru, ipucu, webcam = (zones[k].geometry() for k in ("soru", "ipucu", "webcam"))
    assert soru.left() == 0 and soru.top() == 0                       # kenar boşluğu yok
    assert ipucu.right() == wa.width() - 1
    assert webcam.right() == wa.width() - 1 and webcam.bottom() == wa.height() - 1
    assert abs(soru.width() / ipucu.width() - 1) < 0.02


def test_zone_forwards_drawing_to_board(qtbot):
    wa, zones = make(qtbot)
    z = zones["soru"]
    start, end = QPoint(100, 100), QPoint(180, 160)
    qtbot.mousePress(z, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(z, end)
    qtbot.mouseRelease(z, Qt.MouseButton.LeftButton, pos=end)
    assert not wa.board.is_empty()
    assert wa.board.strokes_image().pixelColor(140, 130).alpha() > 0    # soru bölgesi (0,0)'da: tahta koordinatı aynı


def test_edit_mode_drag_moves_and_snaps(qtbot):
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    start = zones["webcam"].geometry().center()
    cw, ch = lm.cell_size(wa.width(), wa.height(), 14)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-int(cw * 2), 0))
    assert sig.args[0]["webcam"] == lm.PanelGeom(7, 7, 3, 3)
    assert wa.board.is_empty()                                        # düzen modunda çizim olmaz


def test_edit_mode_resize_from_corner(qtbot):
    wa, zones = make(qtbot)
    wa.set_edit_mode(True)
    corner = zones["soru"].geometry().bottomRight() - QPoint(6, 6)
    cw, ch = lm.cell_size(wa.width(), wa.height(), 14)
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
    assert (w, h) == (wa.width(), wa.height()) and dpr >= 1.0


def test_no_lines_outside_edit_mode(qtbot):
    wa, _ = make(qtbot)
    img = wa.grab().toImage()
    assert img.pixelColor(3, 300).name() == "#ffffff"          # düz beyaz tahta, çerçeve yok
    wa.set_edit_mode(True)
    img = wa.grab().toImage()
    assert img.pixelColor(3, 300).name() == "#1c1b19"          # düzen modunda 10px çerçeve
    wa.set_edit_mode(False)
    img = wa.grab().toImage()
    assert img.pixelColor(3, 300).name() == "#ffffff"


def test_status_line(qtbot):
    wa, _ = make(qtbot)
    wa.set_status("Araç: Kalem · Kalınlık: 4 px · Basınç: XP-Pen")
    assert wa.status_label.text().startswith("Araç: Kalem")
    assert wa.status_label.y() > wa.height() - 60 and wa.status_label.x() == 16
