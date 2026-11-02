import sys
from pathlib import Path

from matematigin_mantigi import paths


def test_dev_mode_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert not paths.is_frozen()
    assert paths.data_dir() == tmp_path
    assert paths.default_template_path() == tmp_path / "sorular_sablon.xlsx"
    assert paths.default_session_root() == tmp_path / "oturum"
    assert paths.default_layout_path() == tmp_path / "duzen.json"
    assert paths.default_error_log_path() == tmp_path / "hatalar.log"


def test_frozen_app_uses_documents_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert paths.data_dir() == tmp_path / "Documents" / "Matematiğin Mantığı"
    assert paths.default_error_log_path() == tmp_path / "Documents" / "Matematiğin Mantığı" / "hatalar.log"


def test_ensure_user_data_copies_bundled_template_and_images_once(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"; (bundle / "sorular_gorsel").mkdir(parents=True)
    (bundle / "sorular_sablon.xlsx").write_bytes(b"xlsx")
    (bundle / "sorular_gorsel" / "S07.png").write_bytes(b"png")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    target = tmp_path / "veri"
    assert paths.ensure_user_data(target) == target
    assert (target / "sorular_sablon.xlsx").read_bytes() == b"xlsx"
    assert (target / "sorular_gorsel" / "S07.png").exists()
    (target / "sorular_sablon.xlsx").write_bytes(b"kullanici")     # kullanıcı düzenledi
    paths.ensure_user_data(target)
    assert (target / "sorular_sablon.xlsx").read_bytes() == b"kullanici"   # üzerine yazılmaz


def test_ensure_user_data_without_bundle_files_is_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bos"), raising=False)
    target = tmp_path / "veri2"
    paths.ensure_user_data(target)
    assert target.is_dir() and not (target / "sorular_sablon.xlsx").exists()
