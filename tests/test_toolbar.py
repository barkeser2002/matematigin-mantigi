from PyQt6.QtCore import Qt

from matematigin_mantigi.core.models import PALETTE, Tool
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.toolbar import ToolBar

FAM = FontFamilies("Arial", "Arial", False)


def make(qtbot):
    tb = ToolBar(FAM)
    qtbot.addWidget(tb)
    tb.show()
    return tb


def test_toolbar_is_88_wide_and_pen_selected(qtbot):
    tb = make(qtbot)
    assert tb.width() == 88
    assert tb.tool_buttons[Tool.PEN].isChecked()
    assert sum(b.isChecked() for b in tb.tool_buttons.values()) == 1


def test_clicking_eraser_emits_and_is_exclusive(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.toolSelected, timeout=1000) as sig:
        qtbot.mouseClick(tb.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert sig.args == [Tool.ERASER]
    assert tb.tool_buttons[Tool.ERASER].isChecked() and not tb.tool_buttons[Tool.PEN].isChecked()


def test_swatch_and_width_signals(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.colorSelected) as sig:
        qtbot.mouseClick(tb.swatches[PALETTE[1]], Qt.MouseButton.LeftButton)
    assert sig.args == ["#c8322b"]
    with qtbot.waitSignal(tb.widthSelected) as sig:
        qtbot.mouseClick(tb.width_buttons[8], Qt.MouseButton.LeftButton)
    assert sig.args == [8]


def test_record_button_toggles(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.recordToggled) as sig:
        qtbot.mouseClick(tb.record_button, Qt.MouseButton.LeftButton)
    assert sig.args == [True]
    tb.set_recording(True)
    assert tb.record_label.text() == "DURDUR"
    tb.set_recording(False)
    assert tb.record_label.text() == "KAYIT"


def test_silent_setters_do_not_emit(qtbot):
    tb = make(qtbot)
    fired = []
    tb.toolSelected.connect(lambda t: fired.append(t))
    tb.set_tool(Tool.LASER)
    assert tb.tool_buttons[Tool.LASER].isChecked() and fired == []


def test_layout_edit_button(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.layoutEditToggled) as sig:
        qtbot.mouseClick(tb.layout_button, Qt.MouseButton.LeftButton)
    assert sig.args == [True]


def test_settings_button(qtbot):
    tb = make(qtbot)
    with qtbot.waitSignal(tb.settingsRequested):
        qtbot.mouseClick(tb.settings_button, Qt.MouseButton.LeftButton)


def test_prev_and_next_buttons(qtbot):
    tb = make(qtbot)
    assert tb.prev_button.text() == "← Önceki soru" and tb.next_button.text() == "Sıradaki soru →"
    with qtbot.waitSignal(tb.prevRequested):
        qtbot.mouseClick(tb.prev_button, Qt.MouseButton.LeftButton)
    with qtbot.waitSignal(tb.nextRequested):
        qtbot.mouseClick(tb.next_button, Qt.MouseButton.LeftButton)
