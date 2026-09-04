from PyQt6.QtCore import Qt

from matematigin_mantigi.core.chroma_key import ChromaParams
from matematigin_mantigi.ui.theme import FontFamilies
from matematigin_mantigi.ui.webcam_panel import WebcamPanel

FAM = FontFamilies("Arial", "Arial", False)


def test_shows_frames_and_toggles_on_click(qtbot, fake_camera):
    panel = WebcamPanel(FAM, lambda: fake_camera, ChromaParams())
    qtbot.addWidget(panel); panel.resize(600, 400); panel.show()
    with qtbot.waitSignal(panel.worker.frameReady, timeout=2000):
        panel.start()
    assert panel.has_camera and panel.overlay_label.text().startswith("yeşil perde: kaldırıldı")
    with qtbot.waitSignal(panel.chromaToggled) as sig:
        qtbot.mouseClick(panel.view, Qt.MouseButton.LeftButton)
    assert sig.args == [False] and panel.chroma_enabled is False
    assert panel.overlay_label.text().startswith("yeşil perde: ham görüntü")
    panel.shutdown()
    assert panel.worker.isFinished()


def test_placeholder_without_camera(qtbot, dead_camera):
    panel = WebcamPanel(FAM, lambda: dead_camera, ChromaParams())
    qtbot.addWidget(panel); panel.show()
    with qtbot.waitSignal(panel.worker.cameraError, timeout=2000):
        panel.start()
    qtbot.waitUntil(lambda: not panel.has_camera, timeout=2000)
    assert "Kamera" in panel.view.placeholder_text
    panel.shutdown()


def test_start_can_be_skipped(qtbot, dead_camera):
    panel = WebcamPanel(FAM, lambda: dead_camera, ChromaParams())
    qtbot.addWidget(panel)
    panel.shutdown()          # never started: must not raise
