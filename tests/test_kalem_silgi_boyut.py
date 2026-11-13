"""Kalem/silgi boyut hafızası ve gerçek araç geçişleri."""
import pytest
from PyQt6.QtCore import QSettings

from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.core.stroke import eraser_diameter


@pytest.mark.parametrize("width", [1, 4, 8, 12])
def test_old_settings_migrate_eraser_once_and_remember_sizes(tmp_path, width):
    path = str(tmp_path / "old.ini")
    backend = QSettings(path, QSettings.Format.IniFormat)
    backend.setValue("width", width)
    settings = AppSettings(backend)
    assert settings.eraser_size == eraser_diameter(width)
    settings.width = 2
    assert settings.eraser_size == eraser_diameter(width)
    settings.eraser_size = 96
    settings.sync()
    reopened = AppSettings(QSettings(path, QSettings.Format.IniFormat))
    assert reopened.width == 2
    assert reopened.eraser_size == 96


@pytest.mark.parametrize("stored, expected", [("bad", 34), (-1, 10), (9999, 120)])
def test_invalid_eraser_size_is_safe(tmp_path, stored, expected):
    backend = QSettings(str(tmp_path / "bad.ini"), QSettings.Format.IniFormat)
    backend.setValue("eraser/size", stored)
    assert AppSettings(backend).eraser_size == expected


def test_toolbar_switch_keeps_independent_sizes_and_erases_real_diameter(window, qtbot):
    from PyQt6.QtCore import QPointF, Qt
    from matematigin_mantigi.core.models import Tool

    window._on_width(8)
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert window.canvas.eraser_size == 34
    window._on_width(60)
    assert window.canvas.base_width == window.settings.width == 8
    assert window.canvas.eraser_size == window.settings.eraser_size == 60
    c = window.canvas
    c._strokes.fill(Qt.GlobalColor.black)
    c.begin_stroke(QPointF(100, 100), .5)
    c.end_stroke()
    assert c.strokes_image().pixelColor(100, 129).alpha() < 10
    assert c.strokes_image().pixelColor(100, 132).alpha() == 255
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.PEN], Qt.MouseButton.LeftButton)
    assert c.base_width == 8
    window._on_width(2)
    qtbot.mouseClick(window.toolbar.tool_buttons[Tool.ERASER], Qt.MouseButton.LeftButton)
    assert c.eraser_size == 60


def test_window_restores_both_sizes(window):
    from matematigin_mantigi.core.models import Tool
    window.settings.width = 12
    window.settings.eraser_size = 80
    window.settings.tool = Tool.ERASER
    window._restore_settings()
    assert window.canvas.base_width == 12
    assert window.canvas.eraser_size == 80
    window._on_tool(Tool.PEN)
    assert window.canvas.base_width == 12


def test_size_controls_follow_tool_and_do_not_emit_on_switch(window, qtbot):
    from PyQt6.QtCore import Qt
    from matematigin_mantigi.core.models import Tool
    from PyQt6.QtTest import QSignalSpy
    tb = window.toolbar
    spy = QSignalSpy(tb.widthSelected)
    window._on_width(8)
    window._on_tool(Tool.ERASER)
    assert tb.size_slider.minimum() == 10 and tb.size_slider.maximum() == 120
    assert tb.size_slider.value() == 34
    assert "Silgi" in tb.size_label.text() and "34" in tb.size_label.text()
    assert len(spy) == 0
    tb.size_slider.setValue(72)
    assert window.canvas.eraser_size == 72 and window.canvas.base_width == 8
    qtbot.mouseClick(tb.width_buttons[12], Qt.MouseButton.LeftButton)
    assert window.canvas.eraser_size == 120
    assert "120 px" in tb.width_buttons[12].toolTip()
    window._on_tool(Tool.PEN)
    assert tb.width_buttons[8].isChecked()
    assert tb.size_slider.isHidden()
    qtbot.mouseClick(tb.width_buttons[2], Qt.MouseButton.LeftButton)
    assert window.canvas.base_width == 2 and window.canvas.eraser_size == 120
    window._on_tool(Tool.ERASER)
    assert tb.size_slider.value() == 120


def tablet(canvas, tip, kind=None, pressure: float = 0, buttons=None):
    from PyQt6.QtCore import QEvent, QPointF, Qt
    from PyQt6.QtGui import QInputDevice, QPointingDevice, QTabletEvent
    from PyQt6.QtWidgets import QApplication
    device = QPointingDevice("test pen", 1, QInputDevice.DeviceType.Stylus, tip,
                             QInputDevice.Capability.Position | QInputDevice.Capability.Pressure, 1, 3)
    event = QTabletEvent(kind or QEvent.Type.TabletMove, device, QPointF(100, 100), QPointF(100, 100),
                         pressure, 0, 0, 0, 0, 0, Qt.KeyboardModifier.NoModifier,
                         Qt.MouseButton.LeftButton if kind == QEvent.Type.TabletPress else Qt.MouseButton.NoButton,
                         buttons or Qt.MouseButton.NoButton)
    QApplication.sendEvent(canvas, event)


@pytest.mark.parametrize("dpr", [1, 2])
def test_eraser_cursor_is_real_diameter_circle_at_each_dpi(window, monkeypatch, dpr):
    from PyQt6.QtCore import QSize
    from matematigin_mantigi.core.models import Tool
    monkeypatch.setattr(window.canvas, "devicePixelRatioF", lambda: dpr)
    window._on_tool(Tool.ERASER)
    window._on_width(60)
    pixmap = window.canvas.cursor().pixmap()
    assert pixmap.size() == QSize(62 * dpr, 62 * dpr)
    assert pixmap.devicePixelRatio() == dpr
    assert pixmap.toImage().pixelColor(4 * dpr, 4 * dpr).alpha() == 0
    assert window.canvas.cursor().hotSpot().x() == 31
    window._on_width(80)
    assert window.canvas.cursor().pixmap().width() == 82 * dpr


def test_hover_tip_switch_updates_cursor_toolbar_and_uses_independent_size(window):
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QPointingDevice
    from matematigin_mantigi.core.models import Tool
    window._on_width(8)
    window.settings.eraser_size = 60
    window.canvas.set_eraser_size(60)
    tablet(window.canvas, QPointingDevice.PointerType.Eraser)
    assert window.canvas.cursor().pixmap().width() == 62
    assert window.toolbar.tool_buttons[Tool.ERASER].isChecked()
    assert window.toolbar.size_slider.value() == 60
    assert window.settings.tool == window.canvas.tool == Tool.PEN
    window._on_width(80)
    assert window.canvas.base_width == 8
    window.canvas._strokes.fill(Qt.GlobalColor.black)
    tablet(window.canvas, QPointingDevice.PointerType.Eraser, QEvent.Type.TabletPress,
           .9, Qt.MouseButton.LeftButton)
    tablet(window.canvas, QPointingDevice.PointerType.Eraser, QEvent.Type.TabletRelease)
    assert window.canvas.strokes_image().pixelColor(100, 138).alpha() < 10
    assert window.canvas.strokes_image().pixelColor(100, 142).alpha() == 255
    tablet(window.canvas, QPointingDevice.PointerType.Pen)
    assert window.toolbar.tool_buttons[Tool.PEN].isChecked()
    assert window.toolbar.width_buttons[8].isChecked()
    assert window.canvas.cursor().pixmap().width() == 36
    assert window.canvas.base_width == 8 and window.canvas.eraser_size == 80


def test_pen_cursor_uses_pressure_settings_and_is_not_clipped(window):
    from dataclasses import replace
    from PyQt6.QtGui import QPointingDevice
    window._apply_pen_settings(replace(window.settings.pen(), min_width=20, max_width=40))
    window._on_width(12)
    tablet(window.canvas, QPointingDevice.PointerType.Pen, pressure=1)
    cur = window.canvas.cursor()
    image = cur.pixmap().toImage()
    x, y = cur.hotSpot().x(), cur.hotSpot().y()
    # 40 px uç × 12/4 = 120 px gerçek çizim; gösterge kırpılmamalı.
    assert x >= 60 and y >= 60
    assert image.pixelColor(x - 58, y).alpha() > 200
    assert image.pixelColor(x + 58, y).alpha() > 200


def test_bracket_keys_step_active_size_with_bounds_and_tip_override(window, qtbot):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QPointingDevice
    from matematigin_mantigi.core.models import Tool
    qtbot.keyClick(window, Qt.Key.Key_BracketRight)
    assert window.canvas.base_width == 8
    qtbot.keyClick(window, Qt.Key.Key_BracketLeft)
    assert window.canvas.base_width == 4
    tablet(window.canvas, QPointingDevice.PointerType.Eraser)
    qtbot.keyClick(window, Qt.Key.Key_BracketRight)
    assert window.canvas.eraser_size == 50 and window.canvas.base_width == 4
    qtbot.keyClick(window, Qt.Key.Key_BracketLeft)
    assert window.canvas.eraser_size == 34
    window._on_width(10)
    qtbot.keyClick(window, Qt.Key.Key_BracketLeft)
    assert window.canvas.eraser_size == 10
    window._on_width(120)
    qtbot.keyClick(window, Qt.Key.Key_BracketRight)
    assert window.canvas.eraser_size == 120
    window._on_tool(Tool.PEN)
    window._on_width(1)
    qtbot.keyClick(window, Qt.Key.Key_BracketLeft)
    assert window.canvas.base_width == 1
    window._on_width(12)
    qtbot.keyClick(window, Qt.Key.Key_BracketRight)
    assert window.canvas.base_width == 12


def test_brackets_are_text_while_writing(window, qtbot):
    from PyQt6.QtCore import QPointF
    from matematigin_mantigi.core.models import Tool
    window._on_tool(Tool.TEXT)
    window.canvas.begin_text(QPointF(100, 100))
    qtbot.keyClicks(window.canvas.text_edit, "[]")
    assert window.canvas.text_edit.text() == "[]"
    assert window.canvas.base_width == 4 and window.canvas.eraser_size == 34
    window.canvas.cancel_text()


def test_pen_settings_refresh_cursor_without_moving_pointer(window):
    from dataclasses import replace
    before = window.canvas.cursor().pixmap().toImage()
    window._apply_pen_settings(replace(window.settings.pen(), min_width=20, max_width=20))
    assert window.canvas.cursor().pixmap().toImage() != before


@pytest.mark.parametrize("height", [720, 768, 1080])
def test_eraser_controls_fit_sidebar_without_scroll(qtbot, height):
    from PyQt6.QtWidgets import QApplication
    from matematigin_mantigi.core.models import Tool
    from matematigin_mantigi.ui.toolbar import ToolBar
    from matematigin_mantigi.ui.theme import FontFamilies
    tb = ToolBar(FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(tb)
    tb.resize(88, height)
    tb.show()
    qtbot.waitExposed(tb)
    tb.set_size_context(Tool.ERASER, 120)
    QApplication.processEvents()
    assert tb.scroll_area.verticalScrollBar().maximum() == 0
    assert tb.size_slider.width() <= tb.scroll_area.viewport().width()
    tb.set_size_context(Tool.PEN, 4)
    QApplication.processEvents()
    assert tb.scroll_area.verticalScrollBar().maximum() == 0


def test_small_eraser_sidebar_prioritizes_slider_and_keeps_presets_on_tall_panel(qtbot):
    from matematigin_mantigi.core.models import Tool
    from matematigin_mantigi.ui.toolbar import ToolBar
    from matematigin_mantigi.ui.theme import FontFamilies
    tb = ToolBar(FontFamilies("Arial", "Arial", False))
    qtbot.addWidget(tb)
    tb.resize(88, 720)
    tb.show()
    qtbot.waitExposed(tb)
    tb.set_size_context(Tool.ERASER, 80)
    assert tb.size_slider.isVisible() and tb.size_label.isVisible()
    assert all(button.isHidden() for button in tb.width_buttons.values())
    tb.set_size_context(Tool.PEN, 4)
    assert all(button.isVisible() for button in tb.width_buttons.values())
    tb.resize(88, 1100)
    tb.set_size_context(Tool.ERASER, 80)
    assert all(button.isVisible() for button in tb.width_buttons.values())


def test_existing_status_reports_effective_size_on_tip_switch(window):
    from PyQt6.QtGui import QPointingDevice
    window._on_width(8)
    window.canvas.set_eraser_size(60)
    tablet(window.canvas, QPointingDevice.PointerType.Eraser)
    assert "Araç: Silgi" in window.work_area.status_label.text()
    assert "Kalınlık: 60 px" in window.work_area.status_label.text()
    window._on_width(80)
    assert "Kalınlık: 80 px" in window.work_area.status_label.text()
    tablet(window.canvas, QPointingDevice.PointerType.Pen)
    assert "Araç: Kalem" in window.work_area.status_label.text()
    assert "Kalınlık: 8 px" in window.work_area.status_label.text()


def test_pen_dialog_previews_remembered_eraser_size(window, monkeypatch):
    from PyQt6.QtWidgets import QLabel
    from matematigin_mantigi.ui.pen_settings import PenSettingsDialog
    window.canvas.set_eraser_size(80)
    seen = []
    def inspect_dialog(dialog):
        seen.extend(label.pixmap().width() for label in dialog.findChildren(QLabel)
                    if not label.pixmap().isNull())
        return 0
    monkeypatch.setattr(PenSettingsDialog, "exec", inspect_dialog)
    window.open_pen_settings()
    assert 82 in seen


@pytest.mark.parametrize("w,h", [(1920, 1080), (1366, 768), (1280, 720)])
@pytest.mark.parametrize("stretch,dpi", [("default", 96), (160, 120)])
def test_eraser_layout_on_real_fullscreen_with_wide_font(tmp_path, w, h, stretch, dpi):
    import json
    import os
    import subprocess
    import sys
    from test_tam_ekran import CHILD
    cfg = {"screens": [{"name": "S", "x": 0, "y": 0, "width": round(w * dpi / 96),
                        "height": round(h * dpi / 96), "logicalDpi": dpi,
                        "logicalBaseDpi": 96, "dpr": 1.0}]}
    (tmp_path / "screen.json").write_text(json.dumps(cfg), encoding="utf-8")
    script = CHILD.replace("win.show()", "from matematigin_mantigi.core.models import Tool\nwin._on_tool(Tool.ERASER)\nwin._on_width(120)\nwin.show()")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen:configfile=screen.json", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    result = subprocess.run([sys.executable, "-c", script, str(stretch)], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=90)
    lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
    assert result.returncode == 0 and lines, (result.returncode, result.stdout, result.stderr)
    state = json.loads(lines[-1])
    details = json.dumps(state, ensure_ascii=False)
    assert (state["w"], state["h"]) == (w, h), details
    assert not state["bar"] and not state["tasan"] and not state["metin_tasan"], details
