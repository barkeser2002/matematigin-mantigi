from PyQt6.QtCore import QPoint, Qt

from matematigin_mantigi.core import layout_model as lm
from matematigin_mantigi.ui.panel import PanelFrame
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.work_area import WorkArea

FAM = FontFamilies("Arial", "Arial", False)


def make(qtbot):
    wa = WorkArea(FAM)
    qtbot.addWidget(wa)
    panels = {}
    for key, num, title in (("soru", "1", "Soru"), ("ipucu", "3", "Akıllı ipuçları"),
                            ("cizim", "2", "El çizimi"), ("webcam", "4", "Webcam")):
        p = PanelFrame(num, title, FAM)
        wa.add_panel(key, p)
        panels[key] = p
    wa.resize(1832, 1080)
    wa.show()
    return wa, panels


def test_default_layout_places_panels(qtbot):
    wa, panels = make(qtbot)
    soru, cizim, ipucu = panels["soru"].geometry(), panels["cizim"].geometry(), panels["ipucu"].geometry()
    assert soru.left() == 210 and soru.top() == 30                     # padding left/top
    assert cizim.top() - soru.bottom() - 1 == 14                       # gap
    assert ipucu.right() == wa.width() - 30 - 1                        # padding right
    assert abs(soru.width() / ipucu.width() - 7 / 5) < 0.02


def test_edit_mode_drag_moves_and_snaps(qtbot):
    wa, panels = make(qtbot)
    wa.set_edit_mode(True)
    webcam = panels["webcam"]
    start = webcam.geometry().topLeft() + QPoint(40, 20)      # inside header
    cw, ch = lm.cell_size(wa.width() - 240, wa.height() - 90, 14)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    qtbot.mouseMove(wa, start + QPoint(-int(cw * 2), 0))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-int(cw * 2), 0))
    assert sig.args[0]["webcam"] == lm.PanelGeom(5, 5, 5, 5)


def test_edit_mode_resize_from_corner(qtbot):
    wa, panels = make(qtbot)
    wa.set_edit_mode(True)
    soru = panels["soru"]
    corner = soru.geometry().bottomRight() - QPoint(6, 6)
    cw, ch = lm.cell_size(wa.width() - 240, wa.height() - 90, 14)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=corner)
    qtbot.mouseMove(wa, corner + QPoint(0, int(ch)))
    with qtbot.waitSignal(wa.layoutChanged) as sig:
        qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=corner + QPoint(0, int(ch)))
    assert sig.args[0]["soru"] == lm.PanelGeom(0, 0, 7, 4)


def test_no_drag_outside_edit_mode(qtbot):
    wa, panels = make(qtbot)
    before = panels["webcam"].geometry()
    start = before.topLeft() + QPoint(40, 20)
    qtbot.mousePress(wa, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(wa, start + QPoint(-300, 0))
    qtbot.mouseRelease(wa, Qt.MouseButton.LeftButton, pos=start + QPoint(-300, 0))
    assert panels["webcam"].geometry() == before


def test_maximize_and_restore(qtbot):
    wa, panels = make(qtbot)
    wa.set_maximized("cizim")
    g = panels["cizim"].geometry()
    assert g.left() == 210 and g.right() == wa.width() - 30 - 1 and not panels["soru"].isVisible()
    wa.set_maximized(None)
    assert panels["soru"].isVisible() and panels["cizim"].geometry().top() > 30


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
    wa, panels = make(qtbot)
    qtbot.waitExposed(wa)
    img = wa.grab().toImage()
    assert img.pixelColor(3, 300).name() == "#e9e7e2"          # çerçeve çizilmedi, sayfa rengi
    assert all(not p.border_visible for p in panels.values())
    wa.set_edit_mode(True)
    img = wa.grab().toImage()
    assert img.pixelColor(3, 300).name() == "#1c1b19"          # düzen modunda 10px çerçeve
    assert all(p.border_visible for p in panels.values())
    wa.set_edit_mode(False)
    assert all(not p.border_visible for p in panels.values())
