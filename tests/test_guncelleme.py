"""Açılışta güncelleme kontrolü (core/updater.py, ui/update_dialog.py). Testlerde ağ yok: HTTP enjekte edilir ya da
yerel http.server kullanılır; subprocess taklit edilir; kutular monkeypatch'lenir."""
from __future__ import annotations

import hashlib
import http.server
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QWidget

from matematigin_mantigi import _build
from matematigin_mantigi.core import updater
from matematigin_mantigi.core.updater import ReleaseInfo, UpdateCancelled, UpdateError
from matematigin_mantigi.ui import update_dialog

PREFIX = "https://github.com/barkeser2002/matematigin-mantigi/releases/download/"


def release_json(build=16, *, installer_size=10, zip_size=20, digest=None, prefix=PREFIX):
    tag = f"build-{build}"

    def asset(name, size, **extra):
        return {"name": name, "size": size, "browser_download_url": f"{prefix}{tag}/{name}", **extra}

    return {"tag_name": tag, "name": f"Yapı {build}", "html_url": f"https://github.com/x/y/releases/tag/{tag}",
            "assets": [asset("Matematigin-Mantigi-Windows.zip", 30),
                       asset("Matematigin-Mantigi-Kurulum.exe", installer_size, **({"digest": digest} if digest else {})),
                       asset("Matematigin-Mantigi-macOS.zip", zip_size)]}


def info(build=16, size=10, name="Matematigin-Mantigi-Kurulum.exe", url="http://x/a", sha256=None):
    return ReleaseInfo(build=build, tag=f"build-{build}", url=url, name=name, size=size, sha256=sha256,
                       page_url="https://github.com/x/y/releases/tag/build-16")


# ---- sürüm ----

def test_parse_build():
    assert updater.parse_build("build-15") == 15
    assert updater.parse_build("build-100") == 100
    for bad in ("", None, "v1.2", "build-", "build-x", "build-1.5", "xbuild-3", "build--2"):
        assert updater.parse_build(bad) is None


def test_current_build_dev_is_none_and_number_is_int(monkeypatch):
    monkeypatch.setattr(_build, "BUILD", "dev")
    assert updater.current_build() is None and updater.build_label() == "geliştirme sürümü"
    monkeypatch.setattr(_build, "BUILD", "42")
    assert updater.current_build() == 42 and updater.build_label() == "Yapı 42"
    monkeypatch.setattr(_build, "BUILD", "abc")
    assert updater.current_build() is None


# ---- release çözümleme ve kontrol ----

def test_parse_release_picks_platform_asset():
    win = updater.parse_release(release_json(16), "win32")
    assert (win.build, win.name, win.size) == (16, "Matematigin-Mantigi-Kurulum.exe", 10)
    mac = updater.parse_release(release_json(16), "darwin")
    assert (mac.name, mac.size) == ("Matematigin-Mantigi-macOS.zip", 20)
    assert updater.parse_release(release_json(16), "linux") is None


def test_parse_release_rejects_foreign_urls_and_missing_assets():
    assert updater.parse_release(release_json(16, prefix="https://evil.example/"), "win32") is None
    data = release_json(16)
    data["assets"] = [a for a in data["assets"] if "Kurulum" not in a["name"]]       # eski yapı: kurulum programı yok
    assert updater.parse_release(data, "win32") is None
    assert updater.parse_release({"tag_name": "v9", "assets": []}, "win32") is None
    assert updater.parse_release(release_json(16, installer_size=0), "win32") is None     # boyut bilinmiyorsa doğrulanamaz
    assert updater.parse_release("çöp", "win32") is None


def test_parse_release_reads_sha256_digest():
    h = "a" * 64
    assert updater.parse_release(release_json(16, digest=f"sha256:{h}"), "win32").sha256 == h
    assert updater.parse_release(release_json(16), "win32").sha256 is None


def test_find_update_compares_builds():
    fetch = lambda: release_json(16)                       # noqa: E731
    assert updater.find_update(build=15, system="win32", fetch=fetch).build == 16
    assert updater.find_update(build=16, system="win32", fetch=fetch) is None
    assert updater.find_update(build=17, system="win32", fetch=fetch) is None
    assert updater.find_update(build=9, system="win32", fetch=lambda: release_json(10)).build == 10     # 10 > 9 sayısal


def test_find_update_is_off_for_dev_builds_and_never_fetches():
    def boom():
        raise AssertionError("dev yapıda ağa çıkılmaz")
    assert updater.find_update(build=None, system="win32", fetch=boom) is None


def test_find_update_respects_skipped_build():
    fetch = lambda: release_json(16)                       # noqa: E731
    assert updater.find_update(build=15, system="win32", fetch=fetch, skipped=16) is None
    assert updater.find_update(build=15, system="win32", fetch=fetch, skipped=17) is None
    assert updater.find_update(build=15, system="win32", fetch=fetch, skipped=15).build == 16     # daha yeni yapı yine sorulur


def test_find_update_network_error_is_silent_and_only_logged(monkeypatch):
    logged = []
    monkeypatch.setattr(updater.crash_log, "log_handled", lambda exc, where="": logged.append((type(exc), where)))

    def down():
        raise OSError("ağ yok")
    assert updater.find_update(build=1, system="win32", fetch=down) is None
    assert logged == [(OSError, "güncelleme kontrolü")]


class _Handler(http.server.BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):                                       # noqa: N802
        body, status = self.routes.get(self.path, (b"yok", 404))
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    _Handler.routes = {}
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", _Handler.routes
    srv.shutdown()
    srv.server_close()


def test_fetch_latest_over_real_http(server):
    base, routes = server
    routes["/latest"] = (json.dumps(release_json(16)).encode(), 200)
    assert updater.fetch_latest(base + "/latest")["tag_name"] == "build-16"
    with pytest.raises(OSError):
        updater.fetch_latest(base + "/yok")


def test_download_success_reports_progress(server, tmp_path):
    base, routes = server
    body = os.urandom(300_000)
    routes["/a.exe"] = (body, 200)
    seen = []
    path = updater.download(info(size=len(body), url=base + "/a.exe", sha256=hashlib.sha256(body).hexdigest()),
                            tmp_path, progress=lambda done, total: seen.append((done, total)))
    assert path.read_bytes() == body and path.name == "Matematigin-Mantigi-Kurulum.exe"
    assert seen[-1] == (len(body), len(body)) and len(seen) > 1
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_download_size_mismatch_installs_nothing(server, tmp_path):
    base, routes = server
    routes["/a.exe"] = (b"x" * 100, 200)
    with pytest.raises(UpdateError, match="boyut"):
        updater.download(info(size=101, url=base + "/a.exe"), tmp_path)
    assert list(tmp_path.iterdir()) == []                   # ne asıl dosya ne .part kalır


def test_download_truncated_connection_leaves_nothing(tmp_path):
    class Short:
        headers = {"Content-Length": "100"}

        def __init__(self):
            self.parts = [b"x" * 40, b""]

        def read(self, n=-1):
            return self.parts.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    with pytest.raises(UpdateError):
        updater.download(info(size=100), tmp_path, opener=lambda req, timeout=None: Short())
    assert list(tmp_path.iterdir()) == []


def test_download_hash_mismatch_installs_nothing(server, tmp_path):
    base, routes = server
    routes["/a.exe"] = (b"x" * 10, 200)
    with pytest.raises(UpdateError, match="doğrulanamadı"):
        updater.download(info(size=10, url=base + "/a.exe", sha256="0" * 64), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_cancel_removes_partial_file(server, tmp_path):
    base, routes = server
    routes["/a.exe"] = (b"x" * 500_000, 200)
    cancel = threading.Event()

    def progress(done, total):
        cancel.set()
    with pytest.raises(UpdateCancelled):
        updater.download(info(size=500_000, url=base + "/a.exe"), tmp_path, progress=progress, cancel=cancel)
    assert list(tmp_path.iterdir()) == []


# ---- Windows ----

def test_windows_silent_command_and_detached_launch(tmp_path):
    exe = tmp_path / "Matematigin-Mantigi-Kurulum.exe"
    assert updater.windows_command(exe, silent=True) == [str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    assert updater.windows_command(exe, silent=False) == [str(exe)]
    calls = []
    updater.launch_windows(exe, silent=True, popen=lambda cmd, **kw: calls.append((cmd, kw)))
    cmd, kw = calls[0]
    assert cmd[1:] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    assert kw["close_fds"] is True and "shell" not in kw


def test_windows_installed_detection(tmp_path):
    exe = tmp_path / "Matematigin Mantigi.exe"
    exe.touch()
    assert updater.windows_installed(exe) is False          # ZIP'ten çalışıyor
    (tmp_path / "unins000.exe").touch()
    assert updater.windows_installed(exe) is True


def test_launch_update_on_windows_zip_run_opens_installer_interactively(tmp_path):
    calls = []
    updater.launch_update(info(), tmp_path / "k.exe", system="win32", installed=False,
                          popen=lambda cmd, **kw: calls.append(cmd))
    assert calls == [[str(tmp_path / "k.exe")]]
    calls.clear()
    updater.launch_update(info(), tmp_path / "k.exe", system="win32", installed=True,
                          popen=lambda cmd, **kw: calls.append(cmd))
    assert "/VERYSILENT" in calls[0]


# ---- macOS ----

def make_app(root: Path, name="Matematiğin Mantığı.app") -> Path:
    app = root / name
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "MacOS" / "MatematiginMantigi").write_text("eski")
    return app


def test_mac_bundle_from_executable(tmp_path):
    app = make_app(tmp_path)
    assert updater.mac_bundle(app / "Contents" / "MacOS" / "MatematiginMantigi") == app
    assert updater.mac_bundle(tmp_path / "bin" / "python") is None


def test_mac_blocker_for_unwritable_bundle(tmp_path):
    app = make_app(tmp_path)
    assert updater.mac_blocker(app) is None
    assert "yazılabilir değil" in updater.mac_blocker(app, writable=lambda p: False)
    assert "yazılabilir değil" in updater.mac_blocker(Path("/private/var/folders/x/AppTranslocation/y/d/Uygulama.app"))
    assert updater.mac_blocker(None) is not None


def test_mac_prepare_extracts_with_ditto_and_starts_script(tmp_path):
    app = make_app(tmp_path / "Uygulamalar")
    zip_path = tmp_path / "Matematigin-Mantigi-macOS.zip"
    zip_path.write_bytes(b"zip")
    runs, popens = [], []

    def fake_run(cmd, **kw):
        runs.append(cmd)
        if cmd[0] == "ditto" and "-x" in cmd:
            make_app(Path(cmd[-1]), "Yeni.app")
        return subprocess.CompletedProcess(cmd, 0)
    updater.launch_mac(zip_path, app, pid=1234, run=fake_run, popen=lambda cmd, **kw: popens.append((cmd, kw)))
    assert runs[0][:4] == ["ditto", "-x", "-k", str(zip_path)]
    cmd, kw = popens[0]
    assert cmd[0] == "/bin/bash" and cmd[2:4] == ["1234", str(Path(runs[0][-1]) / "Yeni.app")]
    assert cmd[4] == str(app) and kw["start_new_session"] is True
    script = Path(cmd[1]).read_text()
    assert "xattr -dr com.apple.quarantine" in script and 'open "$OLD"' in script


def test_mac_prepare_fails_cleanly_when_zip_has_no_app(tmp_path):
    zip_path = tmp_path / "z.zip"
    zip_path.write_bytes(b"zip")
    popens = []
    with pytest.raises(UpdateError, match="uygulama"):
        updater.launch_mac(zip_path, make_app(tmp_path / "A"), pid=1,
                           run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0),
                           popen=lambda *a, **k: popens.append(a))
    assert popens == []


def test_mac_prepare_ditto_failure_raises(tmp_path):
    zip_path = tmp_path / "z.zip"
    zip_path.write_bytes(b"zip")
    with pytest.raises(UpdateError):
        updater.launch_mac(zip_path, make_app(tmp_path / "A"), pid=1,
                           run=lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stderr="kötü"),
                           popen=lambda *a, **k: None)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash yok")
def test_mac_script_is_valid_bash(tmp_path):
    script = tmp_path / "s.sh"
    script.write_text(updater.MAC_SCRIPT)
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0


def _run_mac_script(tmp_path, *, ditto_ok=True, mv_new_ok=True):
    """Betiği gerçek bash'te sahte ditto/xattr/open ile koşar: yedek, değiştirme ve geri alma gerçekten sınanır."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "log.txt"
    (bin_dir / "ditto").write_text(f'#!/bin/bash\n{"" if ditto_ok else "exit 1"}\ncp -R "$1" "$2"\n')
    (bin_dir / "xattr").write_text(f'#!/bin/bash\necho "xattr $@" >> "{log}"\n')
    (bin_dir / "open").write_text(f'#!/bin/bash\necho "open $@" >> "{log}"\n')
    for f in bin_dir.iterdir():
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    root = tmp_path / "Apps"
    old = make_app(root)
    new = make_app(tmp_path / "yeni", "Yeni.app")
    (new / "Contents" / "MacOS" / "MatematiginMantigi").write_text("yeni")
    work = tmp_path / "work"
    work.mkdir()
    script = work / "degistir.sh"
    script.write_text(updater.MAC_SCRIPT)
    dead = subprocess.Popen(["true"])
    dead.wait()
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}")
    res = subprocess.run(["bash", str(script), str(dead.pid), str(new), str(old), str(work)], env=env,
                         capture_output=True, text=True, timeout=60)
    return res, old, work, log


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash yok")
def test_mac_script_replaces_app_removes_quarantine_and_reopens(tmp_path):
    res, old, work, log = _run_mac_script(tmp_path)
    assert res.returncode == 0, res.stderr
    assert (old / "Contents" / "MacOS" / "MatematiginMantigi").read_text() == "yeni"
    assert sorted(p.name for p in old.parent.iterdir()) == [old.name]            # yedek ve hazırlık kopyası kalmadı
    text = log.read_text()
    assert "xattr -dr com.apple.quarantine" in text and f"open {old}" in text
    assert not work.exists()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash yok")
def test_mac_script_leaves_old_app_when_copy_fails(tmp_path):
    res, old, work, log = _run_mac_script(tmp_path, ditto_ok=False)
    assert res.returncode != 0
    assert (old / "Contents" / "MacOS" / "MatematiginMantigi").read_text() == "eski"
    assert sorted(p.name for p in old.parent.iterdir()) == [old.name]
    assert f"open {old}" in log.read_text()                                      # eski sürüm yine açılır
    assert work.exists()                                                         # günlük incelenebilsin


# ---- denetleyici (arayüz) ----

class FakeRecorder:
    def __init__(self):
        from matematigin_mantigi.core.recorder import RecorderState
        self.state = RecorderState.IDLE


class FakeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.recorder = FakeRecorder()
        self.show()


@pytest.fixture
def ctl_env(qtbot, tmp_path, monkeypatch):
    """Sahte pencere + ini ayarları + kutu kaydı; kutular asla gerçekten açılmaz."""
    win = FakeWindow()
    qtbot.addWidget(win)
    store = QSettings(str(tmp_path / "x.ini"), QSettings.Format.IniFormat)
    env = type("Env", (), {})()
    env.win, env.store, env.asked, env.errors, env.launched = win, store, [], [], []
    env.answer = "yes"
    monkeypatch.setattr(update_dialog, "ask_update", lambda parent, text, can_skip=True:
                        (env.asked.append(text), env.answer)[1])
    monkeypatch.setattr(update_dialog, "show_error", lambda parent, text: env.errors.append(text))

    def make(**kw):
        args = dict(frozen=True, build=15, system="win32", fetch=lambda: release_json(16), settings=store, delay_ms=0,
                    retry_ms=20, downloader=lambda i, d, progress=None, cancel=None: _fake_download(i, d),
                    launcher=lambda i, p: env.launched.append((i.build, p.name)), temp_root=tmp_path / "tmp", windows_installed=True)
        args.update(kw)
        c = update_dialog.UpdateController(win, **args)
        return c
    env.make = make
    return env


def _fake_download(i, d):
    p = Path(d) / i.name
    p.write_bytes(b"x")
    return p


def test_controller_asks_with_the_agreed_wording_and_installs_on_yes(qtbot, ctl_env):
    c = ctl_env.make()
    c.start()
    qtbot.waitUntil(lambda: bool(ctl_env.launched), timeout=5000)
    assert ctl_env.asked[0].startswith("Yapı 16 mevcut (şu an 15). İndirilip kurulsun ve program yeniden başlasın mı?")
    assert ctl_env.launched == [(16, "Matematigin-Mantigi-Kurulum.exe")]
    assert not ctl_env.win.isVisible()                      # uygulama kapandı
    assert ctl_env.errors == []


def test_controller_off_when_not_frozen(qtbot, ctl_env):
    def boom():
        raise AssertionError("kaynaktan çalışırken ağa çıkılmaz")
    c = ctl_env.make(frozen=False, fetch=boom)
    c.start()
    qtbot.wait(150)
    assert ctl_env.asked == [] and not c.enabled


def test_controller_off_for_dev_build(qtbot, ctl_env):
    c = ctl_env.make(build=None, fetch=lambda: (_ for _ in ()).throw(AssertionError("dev")))
    c.start()
    qtbot.wait(150)
    assert ctl_env.asked == [] and not c.enabled


def test_controller_no_prompt_when_up_to_date(qtbot, ctl_env):
    c = ctl_env.make(build=16)
    c.start()
    qtbot.wait(300)
    assert ctl_env.asked == [] and ctl_env.launched == []


def test_controller_network_error_is_silent(qtbot, ctl_env):
    def down():
        raise OSError("ağ yok")
    c = ctl_env.make(fetch=down)
    c.start()
    qtbot.wait(300)
    assert ctl_env.asked == [] and ctl_env.errors == [] and ctl_env.launched == []


def test_controller_defers_while_recording_then_asks(qtbot, ctl_env):
    from matematigin_mantigi.core.recorder import RecorderState
    for state in (RecorderState.RECORDING, RecorderState.FINALIZING):
        ctl_env.win.recorder.state = state
        ctl_env.asked.clear()
        c = ctl_env.make()
        c.start()
        qtbot.wait(300)
        assert ctl_env.asked == [], f"{state}: kayıt sürerken soru çıkmamalı"
        ctl_env.win.recorder.state = RecorderState.IDLE
        qtbot.waitUntil(lambda: bool(ctl_env.asked), timeout=5000)
        qtbot.waitUntil(lambda: bool(ctl_env.launched), timeout=5000)
        ctl_env.launched.clear()
        ctl_env.win.show()


def test_controller_skip_is_persistent(qtbot, ctl_env):
    ctl_env.answer = "skip"
    c = ctl_env.make()
    c.start()
    qtbot.waitUntil(lambda: bool(ctl_env.asked), timeout=5000)
    qtbot.wait(100)
    assert ctl_env.launched == []
    assert updater.get_skipped(ctl_env.store) == 16
    ctl_env.asked.clear()
    c2 = ctl_env.make()                                     # sonraki açılış
    c2.start()
    qtbot.wait(300)
    assert ctl_env.asked == []
    c3 = ctl_env.make(fetch=lambda: release_json(17))       # daha yeni yapı yine sorulur
    c3.start()
    qtbot.waitUntil(lambda: bool(ctl_env.asked), timeout=5000)


def test_controller_later_downloads_nothing(qtbot, ctl_env):
    ctl_env.answer = "later"
    downloads = []
    c = ctl_env.make(downloader=lambda *a, **k: downloads.append(a))
    c.start()
    qtbot.waitUntil(lambda: bool(ctl_env.asked), timeout=5000)
    qtbot.wait(100)
    assert downloads == [] and ctl_env.launched == [] and updater.get_skipped(ctl_env.store) == 0


def test_controller_size_mismatch_does_not_install(qtbot, ctl_env, server):
    base, routes = server
    routes["/a"] = (b"x" * 50, 200)
    bad = json.loads(json.dumps(release_json(16, installer_size=99)))
    for a in bad["assets"]:
        a["browser_download_url"] = base + "/a"
    c = ctl_env.make(fetch=lambda: bad, downloader=updater.download, trusted_prefix=base + "/")
    c.start()
    qtbot.waitUntil(lambda: bool(ctl_env.errors), timeout=5000)
    assert ctl_env.launched == [] and ctl_env.win.isVisible()
    assert "boyut" in ctl_env.errors[0]


def test_controller_zip_run_on_windows_offers_the_installer(qtbot, ctl_env):
    c = ctl_env.make(windows_installed=False)
    c.start()
    qtbot.waitUntil(lambda: bool(ctl_env.launched), timeout=5000)
    assert "kurulum programı" in ctl_env.asked[0] and "Yapı 16 mevcut (şu an 15)" in ctl_env.asked[0]


def test_controller_mac_blocked_bundle_shows_message_with_page(qtbot, ctl_env, monkeypatch):
    opened = []
    monkeypatch.setattr(update_dialog, "open_page", lambda url: opened.append(url))
    c = ctl_env.make(system="darwin", fetch=lambda: release_json(16), mac_blocker_text="Klasör yazılabilir değil.")
    c.start()
    qtbot.waitUntil(lambda: bool(ctl_env.asked), timeout=5000)
    assert "yazılabilir değil" in ctl_env.asked[0]
    qtbot.waitUntil(lambda: bool(opened), timeout=3000)
    assert opened == ["https://github.com/x/y/releases/tag/build-16"] and ctl_env.launched == []


def test_controller_recording_started_during_download_waits_for_idle(qtbot, ctl_env):
    from matematigin_mantigi.core.recorder import RecorderState
    started = threading.Event()
    release = threading.Event()

    def slow(i, d, progress=None, cancel=None):
        started.set()
        release.wait(5)
        return _fake_download(i, d)
    c = ctl_env.make(downloader=slow)
    c.start()
    qtbot.waitUntil(started.is_set, timeout=5000)
    ctl_env.win.recorder.state = RecorderState.RECORDING        # indirme sürerken kayıt başladı
    release.set()
    qtbot.wait(300)
    assert ctl_env.launched == [] and ctl_env.win.isVisible()   # kayıt sürerken uygulama kapanmaz
    ctl_env.win.recorder.state = RecorderState.IDLE
    qtbot.waitUntil(lambda: bool(ctl_env.launched), timeout=5000)
