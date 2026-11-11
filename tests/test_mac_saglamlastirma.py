"""macOS dalları Linux'ta sahte AVFoundation/izin hatalarıyla sınanır."""
from types import ModuleType, SimpleNamespace
from pathlib import Path
import sys
import tomllib

import pytest
import numpy as np

from matematigin_mantigi.core import cameras


def _avfoundation(monkeypatch, devices):
    module = ModuleType("AVFoundation")
    module.AVMediaTypeVideo = "video"
    module.AVMediaTypeMuxed = "muxed"
    module.AVCaptureDevice = SimpleNamespace(devicesWithMediaType_=lambda kind: devices.get(kind, []))
    monkeypatch.setitem(sys.modules, "AVFoundation", module)
    return module


def _device(uid, name):
    return SimpleNamespace(uniqueID=lambda: uid, localizedName=lambda: name)


def _capture(monkeypatch, fail_avfoundation=False):
    opened = []

    class Capture:
        def __init__(self, index, backend):
            self.index, self.backend = index, backend
            opened.append((index, backend))

        def isOpened(self):
            return not (fail_avfoundation and self.backend == cameras.cv2.CAP_AVFOUNDATION)

        def read(self):
            return True, np.zeros((480, 640, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setattr(cameras.cv2, "VideoCapture", Capture)
    return opened


def test_mac_camera_names_follow_opencv_unique_id_order(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    _avfoundation(monkeypatch, {"video": [_device("z", "USB"), _device("a", "FaceTime")]})
    opened = _capture(monkeypatch)
    found = cameras.list_cameras(max_index=2, names=["Wrong USB", "Wrong FaceTime"], skip={0})
    assert [(c.index, c.name, c.label) for c in found] == [(1, "USB", "1: USB (640×480)")]
    assert opened == [(1, cameras.cv2.CAP_AVFOUNDATION)]


def test_mac_muxed_video_devices_keep_opencv_indices(monkeypatch):
    # OpenCV 5.0.0, cap_avfoundation_mac.mm: video + muxed, ardından uniqueID sırası.
    monkeypatch.setattr(sys, "platform", "darwin")
    _avfoundation(monkeypatch, {"video": [_device("z", "USB")], "muxed": [_device("a", "DV")]})
    _capture(monkeypatch)
    assert [c.name for c in cameras.list_cameras(max_index=2)] == ["DV", "USB"]


def test_unknown_camera_resolution_is_not_shown():
    assert cameras.CameraInfo(3, 0, 0).label == "Kamera 3"


@pytest.mark.parametrize("failure", ["missing", "query", "name"])
def test_mac_avfoundation_failure_uses_index_labels(monkeypatch, failure):
    monkeypatch.setattr(sys, "platform", "darwin")
    module = _avfoundation(monkeypatch, {"video": [_device("a", "FaceTime")]})
    def denied(*args):
        raise RuntimeError("AVFoundation error")
    if failure == "missing":
        monkeypatch.setitem(sys.modules, "AVFoundation", None)
    elif failure == "query":
        module.AVCaptureDevice.devicesWithMediaType_ = denied
    else:
        module.AVCaptureDevice.devicesWithMediaType_ = lambda kind: [SimpleNamespace(uniqueID=denied)]
    _capture(monkeypatch)
    assert [c.label for c in cameras.list_cameras(max_index=2, names=["Wrong", "Wrong"])] == [
        "Kamera 0 (640×480)", "Kamera 1 (640×480)"]


def test_mac_unverified_fallback_backend_never_gets_avfoundation_name(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    _avfoundation(monkeypatch, {"video": [_device("a", "FaceTime")]})
    _capture(monkeypatch, fail_avfoundation=True)
    assert cameras.list_cameras(max_index=1)[0].name == ""


def test_pyobjc_dependency_is_mac_only_and_pinned():
    from packaging.requirements import Requirement
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())
    dependencies = [Requirement(d) for d in project["project"]["dependencies"]]
    av = [d for d in dependencies if d.name == "pyobjc-framework-AVFoundation"]
    assert len(av) == 1
    assert av[0].marker is not None
    assert av[0].marker.evaluate({"sys_platform": "darwin"})
    assert not av[0].marker.evaluate({"sys_platform": "linux"})
    assert not av[0].marker.evaluate({"sys_platform": "win32"})
    assert 'pyobjc-framework-AVFoundation==13.0' in (root / "constraints.txt").read_text()
