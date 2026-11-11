"""macOS dalları Linux'ta sahte AVFoundation/izin hatalarıyla sınanır."""
from types import ModuleType, SimpleNamespace
from pathlib import Path
import sys
import tempfile
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


@pytest.fixture
def mac_home(monkeypatch, tmp_path, request):
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi import app, paths
    # app/Qt ve platforma bağımlı modüller gerçek platformda yüklensin.
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(paths, "bundle_dir", lambda: tmp_path / "bundle")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text, *a, **kw: warnings.append(text))
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text, *a, **kw: warnings.append(text))
    documents = tmp_path / "Documents"
    denied_operation = getattr(request, "param", "mkdir")
    original_mkdir = Path.mkdir
    def mkdir(path, *args, **kwargs):
        if denied_operation == "mkdir" and (path == documents or documents in path.parents):
            raise PermissionError("Documents access denied")
        return original_mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    original_temporary = tempfile.TemporaryFile
    def temporary(*args, **kwargs):
        folder = Path(kwargs["dir"])
        if denied_operation == "write" and documents in folder.parents:
            raise PermissionError("Documents write denied")
        return original_temporary(*args, **kwargs)
    monkeypatch.setattr(tempfile, "TemporaryFile", temporary)
    return app, paths, warnings, tmp_path / "Movies" / paths.APP_FOLDER_NAME


@pytest.mark.parametrize("mac_home", ["mkdir", "write"], indirect=True)
def test_documents_permission_denied_at_startup_uses_movies(qtbot, ini_settings, mac_home):
    from matematigin_mantigi.ui.theme import FontFamilies
    app, paths, warnings, fallback = mac_home
    win = app.build_window(app.parse_args(["prog", "--kamera-yok"]), FontFamilies("Arial", "Arial", False), ini_settings)
    qtbot.addWidget(win)
    assert win.session_store.root == fallback / "oturum"
    assert win.recorder._output_dir() == win.session_store.session_dir
    assert win.questions_path == fallback / paths.TEMPLATE_NAME
    assert win.layout_path == fallback / "duzen.json"
    assert ini_settings.record_folder == ""  # kullanıcı tercihi olarak kaydedilmez
    assert any("Belgeler" in text and "erişim izni" in text and str(fallback) in text for text in warnings)


def test_documents_denial_never_redirects_custom_record_folder(qtbot, ini_settings, mac_home, tmp_path):
    from matematigin_mantigi.core.recorder import RecorderError
    from matematigin_mantigi.ui.theme import FontFamilies
    app, paths, warnings, fallback = mac_home
    selected = tmp_path / "Seçilen kayıtlar"
    selected.mkdir()
    ini_settings.record_folder = str(selected)
    win = app.build_window(app.parse_args(["prog", "--kamera-yok"]), FontFamilies("Arial", "Arial", False), ini_settings)
    qtbot.addWidget(win)
    assert win.recorder._output_dir() == selected
    selected.rmdir()
    with pytest.raises(RecorderError, match="Kayıt klasörü"):
        win.recorder._output_dir()
    assert not selected.exists()
    assert not fallback.exists()
    assert ini_settings.record_folder == str(selected)
    assert any("Belgeler" in text and "değiştirilmedi" in text for text in warnings)


@pytest.mark.parametrize("mac_home", ["later"], indirect=True)
@pytest.mark.parametrize("operation", ["mkdir", "write"])
def test_documents_permission_revoked_before_recording_uses_movies(qtbot, ini_settings, mac_home, monkeypatch, operation):
    from matematigin_mantigi.ui.theme import FontFamilies
    app, paths, warnings, fallback = mac_home
    win = app.build_window(app.parse_args(["prog", "--kamera-yok"]), FontFamilies("Arial", "Arial", False), ini_settings)
    qtbot.addWidget(win)
    original_mkdir = Path.mkdir
    def denied(path, *args, **kwargs):
        if paths.data_dir() == path or paths.data_dir() in path.parents:
            raise PermissionError("Documents revoked")
        return original_mkdir(path, *args, **kwargs)
    if operation == "mkdir":
        monkeypatch.setattr(Path, "mkdir", denied)
    else:
        original_temporary = tempfile.TemporaryFile
        def denied_write(*args, **kwargs):
            if paths.data_dir() in Path(kwargs["dir"]).parents:
                raise PermissionError("Documents write revoked")
            return original_temporary(*args, **kwargs)
        monkeypatch.setattr(tempfile, "TemporaryFile", denied_write)
    target = win.recorder._output_dir()
    assert target == fallback / "oturum" / win.session_store.session_dir.name
    assert target.is_dir()
    assert any(str(fallback) in text for text in warnings)
    assert win.recorder._output_dir() == target
    assert len(warnings) == 1


def test_documents_and_movies_denied_still_opens_with_warning(qtbot, ini_settings, mac_home, monkeypatch):
    from matematigin_mantigi.ui.theme import FontFamilies
    app, paths, warnings, fallback = mac_home
    original_mkdir = Path.mkdir
    def denied(path, *args, **kwargs):
        if fallback == path or fallback in path.parents:
            raise PermissionError("Movies access denied")
        return original_mkdir(path, *args, **kwargs)
    monkeypatch.setattr(Path, "mkdir", denied)
    win = app.build_window(app.parse_args(["prog", "--kamera-yok"]), FontFamilies("Arial", "Arial", False), ini_settings)
    qtbot.addWidget(win)
    assert not win.questions_from_file
    assert any("Belgeler" in text and "yazılamıyor" in text and str(fallback) in text for text in warnings)
    with pytest.raises(PermissionError):
        win.recorder._output_dir()


def test_mac_bundle_declares_documents_usage_in_turkish():
    import ast
    spec = Path(__file__).resolve().parents[1] / "mac" / "matematigin_mantigi.spec"
    tree = ast.parse(spec.read_text())
    plist = next(ast.literal_eval(kw.value) for node in ast.walk(tree) if isinstance(node, ast.Call)
                 for kw in node.keywords if kw.arg == "info_plist")
    text = plist.get("NSDocumentsFolderUsageDescription", "")
    assert "Belgeler" in text and "kayıt" in text


def test_main_survives_documents_denial_in_real_process(tmp_path):
    import os
    import subprocess
    import textwrap
    script = textwrap.dedent('''
        from pathlib import Path
        import sys
        from PyQt6.QtCore import QSettings, QTimer
        from PyQt6.QtWidgets import QMessageBox
        from matematigin_mantigi import app, paths
        from matematigin_mantigi.core.settings import AppSettings
        home = Path(sys.argv[1])
        paths.is_frozen = lambda: True
        paths.bundle_dir = lambda: home / "bundle"
        Path.home = lambda: home
        app.AppSettings = lambda: AppSettings(QSettings(str(home / "settings.ini"), QSettings.Format.IniFormat))
        warnings = []
        QMessageBox.warning = lambda parent, title, text, *a, **kw: warnings.append(text)
        original_mkdir = Path.mkdir
        def mkdir(path, *a, **kw):
            if home / "Documents" in path.parents:
                raise PermissionError("Documents access denied")
            return original_mkdir(path, *a, **kw)
        Path.mkdir = mkdir
        build = app.build_window
        def checked_build(*a, **kw):
            win = build(*a, **kw)
            assert win.session_store.root == home / "Movies" / paths.APP_FOLDER_NAME / "oturum"
            assert warnings and "Belgeler" in warnings[0]
            QTimer.singleShot(0, win.close)
            return win
        app.build_window = checked_build
        sys.platform = "darwin"
        status = app.main(["prog", "--kamera-yok"])
        print("STARTUP_OK", status)
        raise SystemExit(status)
    ''')
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                            capture_output=True, text=True, timeout=30,
                            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STARTUP_OK 0" in result.stdout
