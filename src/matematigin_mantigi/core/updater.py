"""Açılışta güncelleme: GitHub Releases'tan (public repo, kimliksiz) son yapıyı okur, indirir, kurar.

Qt'ye dokunmaz (arayüz ui/update_dialog.py'de). Ağ ve alt süreç her yerde enjekte edilebilir: testler gerçek ağa
çıkmaz. Kural: ağ hatası kullanıcıya gösterilmez, yalnız hatalar.log'a yazılır; yarım ya da boyutu/özeti tutmayan
dosya asla kurulmaz.

Yapı numarası _build.BUILD'den gelir (CI run numarası; depoda 'dev' = güncelleyici kapalı). Release etiketi
'build-N'.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from matematigin_mantigi import _build
from matematigin_mantigi.core import crash_log

REPO = "barkeser2002/matematigin-mantigi"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
TRUSTED_PREFIX = f"https://github.com/{REPO}/releases/download/"       # indirme yalnız bu depodan
WINDOWS_ASSET = "Matematigin-Mantigi-Kurulum.exe"
MAC_ASSET = "Matematigin-Mantigi-macOS.zip"
USER_AGENT = "MatematiginMantigi-Guncelleme"
SKIP_KEY = "guncelleme/atlanan_yapi"


class UpdateError(Exception):
    """Kullanıcıya gösterilebilir güncelleme hatası (indirme/kurulum); mesaj Türkçe ve açıktır."""


class UpdateCancelled(UpdateError):
    pass


@dataclass(frozen=True)
class ReleaseInfo:
    build: int
    tag: str
    name: str                   # indirilecek varlığın adı
    url: str
    size: int
    sha256: str | None
    page_url: str               # release sayfası (elle indirme yedeği)


# ---- sürüm ----

def parse_build(tag) -> int | None:
    m = re.fullmatch(r"build-(\d+)", tag) if isinstance(tag, str) else None
    return int(m.group(1)) if m else None


def current_build() -> int | None:
    """Bu uygulamanın yapı numarası; 'dev' (yerel derleme) ya da bozuk değer için None (güncelleyici kapalı)."""
    value = str(getattr(_build, "BUILD", "dev")).strip()
    return int(value) if value.isdigit() else None


def build_label() -> str:
    build = current_build()
    return f"Yapı {build}" if build is not None else "geliştirme sürümü"


def get_skipped(settings) -> int:
    """'Bu sürümü atla' ile kalıcı atlanan en yüksek yapı numarası (yoksa 0). settings: QSettings benzeri."""
    try:
        return int(settings.value(SKIP_KEY, 0) or 0)
    except (TypeError, ValueError):
        return 0


def set_skipped(settings, build: int) -> None:
    settings.setValue(SKIP_KEY, int(build))
    settings.sync()


# ---- release okuma ----

def parse_release(data, system: str, trusted_prefix: str = TRUSTED_PREFIX) -> ReleaseInfo | None:
    """releases/latest JSON'undan bu sistemin varlığını seçer. Tanınmayan etiket, eksik varlık, bilinmeyen boyut ya da
    güvenilmeyen indirme adresi için None (boyut doğrulanamayan dosya indirilmez)."""
    try:
        build = parse_build(data["tag_name"])
        wanted = WINDOWS_ASSET if system.startswith("win") else MAC_ASSET if system == "darwin" else None
        if build is None or wanted is None:
            return None
        for asset in data.get("assets") or []:
            if asset.get("name") != wanted:
                continue
            url, size = str(asset.get("browser_download_url") or ""), int(asset.get("size") or 0)
            if size <= 0 or not url.startswith(trusted_prefix):
                return None
            digest = str(asset.get("digest") or "")
            sha = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else None
            return ReleaseInfo(build=build, tag=data["tag_name"], name=wanted, url=url, size=size, sha256=sha,
                               page_url=str(data.get("html_url") or f"https://github.com/{REPO}/releases/latest"))
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    return None


def fetch_latest(url: str = LATEST_URL, opener=urllib.request.urlopen, timeout: float = 10) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT})
    with opener(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_update(*, build: int | None, system: str, fetch: Callable[[], dict] = fetch_latest, skipped: int = 0,
                trusted_prefix: str = TRUSTED_PREFIX) -> ReleaseInfo | None:
    """Yeni yapı varsa bilgisi, yoksa None. Yerel (dev) yapıda ağa hiç çıkılmaz; her hata sessizce günlüğe gider."""
    if build is None:
        return None
    try:
        info = parse_release(fetch(), system, trusted_prefix)
    except Exception as err:  # noqa: BLE001 - ağ, JSON, her şey: açılışı asla bozmaz
        crash_log.log_handled(err, "güncelleme kontrolü")
        return None
    if info is None or info.build <= build or info.build <= skipped:
        return None
    return info


# ---- indirme ----

def download(info: ReleaseInfo, dest_dir, progress: Callable[[int, int], None] | None = None,
             cancel: threading.Event | None = None, opener=urllib.request.urlopen, chunk: int = 65536,
             timeout: float = 30) -> Path:
    """Varlığı dest_dir'e indirir. Önce '.part'a yazılır; boyut (release API'deki size ve varsa Content-Length) ve
    (API verdiyse) SHA-256 tutarsa asıl adıyla yeniden adlandırılır, aksi halde hiçbir dosya bırakılmaz."""
    dest_dir = Path(dest_dir)
    final = dest_dir / info.name
    part = final.with_name(final.name + ".part")
    req = urllib.request.Request(info.url, headers={"User-Agent": USER_AGENT})
    try:
        digest = hashlib.sha256()
        done = 0
        with opener(req, timeout=timeout) as resp, open(part, "wb") as out:
            length = getattr(resp, "headers", {}).get("Content-Length") if hasattr(resp, "headers") else None
            if length and int(length) != info.size:
                raise UpdateError(f"İndirilen dosyanın boyutu beklenenle uyuşmuyor ({length} / {info.size} bayt).")
            while True:
                if cancel is not None and cancel.is_set():
                    raise UpdateCancelled("İndirme iptal edildi.")
                block = resp.read(chunk)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                done += len(block)
                if done > info.size:
                    raise UpdateError("İndirilen dosya beklenenden büyük; boyut uyuşmuyor.")
                if progress is not None:
                    progress(done, info.size)
        if done != info.size:
            raise UpdateError(f"İndirme yarım kaldı ya da boyut uyuşmuyor ({done} / {info.size} bayt).")
        if info.sha256 and digest.hexdigest() != info.sha256:
            raise UpdateError("İndirilen dosya doğrulanamadı (özet uyuşmuyor).")
        part.replace(final)
        return final
    except UpdateError:
        _remove(part, final)
        raise
    except Exception as err:  # noqa: BLE001
        _remove(part, final)
        raise UpdateError(f"İndirilemedi: {err}") from err


def _remove(*paths: Path) -> None:
    for p in paths:
        try:
            p.unlink()
        except OSError:
            pass


# ---- Windows ----

def windows_installed(exe: str | Path | None = None) -> bool:
    """Kurulum programıyla kurulmuş mu: Inno Setup uygulama klasörüne unins000.exe koyar."""
    exe = Path(exe if exe is not None else sys.executable)
    return (exe.parent / "unins000.exe").exists()


def windows_command(installer, silent: bool) -> list[str]:
    cmd = [str(installer)]
    if silent:
        cmd += ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    return cmd


def launch_windows(installer, silent: bool, popen=subprocess.Popen) -> None:
    """Kurulum programını uygulamadan bağımsız başlatır (uygulama hemen ardından kapanır). Sessizken Inno'nun
    [Run] bölümü kurulum sonrası uygulamayı yeniden açar."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    kwargs = {"close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = flags
    popen(windows_command(installer, silent), **kwargs)


# ---- macOS ----

# Uygulama kapanınca çalışır: yeni .app önce yanına hazırlanır (kopya başarısızsa eskiye dokunulmaz), eski yedeğe
# alınır, yeni yerine konur; başarısızlıkta yedek geri gelir. Karantina özniteliği kaldırılır, uygulama açılır.
MAC_SCRIPT = r"""#!/bin/bash
# Matematiğin Mantığı güncelleme betiği: degistir.sh <pid> <yeni.app> <eski.app> <çalışma klasörü>
PID="$1"; NEW="$2"; OLD="$3"; WORK="$4"
LOG="$WORK/guncelle.log"
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }
n=0
while kill -0 "$PID" 2>/dev/null; do
  sleep 0.5
  n=$((n + 1))
  if [ "$n" -gt 240 ]; then log "uygulama kapanmadı, güncelleme yapılmadı"; exit 1; fi
done
STAGE="$OLD.yeni-$$"
BACKUP="$OLD.eski-$$"
rm -rf "$STAGE" "$BACKUP"
if ! ditto "$NEW" "$STAGE" >> "$LOG" 2>&1; then
  log "yeni sürüm kopyalanamadı"
  rm -rf "$STAGE"
  open "$OLD"
  exit 1
fi
xattr -dr com.apple.quarantine "$STAGE" >> "$LOG" 2>&1 || true
if ! mv "$OLD" "$BACKUP" >> "$LOG" 2>&1; then
  log "eski sürüm yedeğe alınamadı"
  rm -rf "$STAGE"
  open "$OLD"
  exit 1
fi
if ! mv "$STAGE" "$OLD" >> "$LOG" 2>&1; then
  log "yeni sürüm yerine konamadı, eskisi geri alınıyor"
  rm -rf "$OLD" "$STAGE"
  mv "$BACKUP" "$OLD" >> "$LOG" 2>&1
  open "$OLD"
  exit 1
fi
xattr -dr com.apple.quarantine "$OLD" >> "$LOG" 2>&1 || true
rm -rf "$BACKUP"
open "$OLD"
rm -rf "$WORK"
"""


def mac_bundle(exe: str | Path | None = None) -> Path | None:
    """Çalışan .app paketinin yolu (…/X.app/Contents/MacOS/ikili); paket değilse None."""
    exe = Path(exe if exe is not None else sys.executable)
    try:
        app = exe.parents[2]
    except IndexError:
        return None
    return app if app.suffix == ".app" and exe.parent.name == "MacOS" else None


def _writable(path: Path) -> bool:
    import os
    return os.access(path, os.W_OK)


def mac_blocker(app: Path | None, writable: Callable[[Path], bool] = _writable) -> str | None:
    """Kendi kendini güncellemenin neden yapılamayacağı (yoksa None). Metin kullanıcıya gösterilir."""
    if app is None:
        return "Uygulama bir .app paketi olarak çalışmıyor; otomatik güncelleme yapılamıyor."
    if "AppTranslocation" in str(app) or not (writable(app) and writable(app.parent)):
        return (f"Uygulamanın bulunduğu klasör yazılabilir değil ({app.parent}). Uygulamayı Uygulamalar'a taşıyıp "
                "oradan açın ya da yeni sürümü elle indirip eskisinin üzerine koyun.")
    return None


def launch_mac(zip_path, app: Path, pid: int, run=subprocess.run, popen=subprocess.Popen) -> None:
    """ZIP'i geçici dizine ditto ile açar (öznitelik ve sembolik bağlar korunur), değiştirme betiğini başlatır."""
    work = Path(tempfile.mkdtemp(prefix="mm-guncelleme-"))
    try:
        extract = work / "yeni"
        extract.mkdir()
        res = run(["ditto", "-x", "-k", str(zip_path), str(extract)], capture_output=True, text=True)
        if res.returncode != 0:
            raise UpdateError(f"İndirilen paket açılamadı: {(res.stderr or '').strip()[:200]}")
        apps = sorted(p for p in extract.iterdir() if p.suffix == ".app")
        if len(apps) != 1:
            raise UpdateError("İndirilen pakette uygulama bulunamadı.")
        script = work / "degistir.sh"
        script.write_text(MAC_SCRIPT, encoding="utf-8")
        script.chmod(0o755)
        popen(["/bin/bash", str(script), str(pid), str(apps[0]), str(app), str(work)],
              start_new_session=True, close_fds=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL)
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise


def launch_update(info: ReleaseInfo, path, system: str | None = None, installed: bool | None = None,
                  popen=subprocess.Popen, run=subprocess.run) -> None:
    """İndirilen dosyayı platforma göre devreye alır; çağıran bundan hemen sonra uygulamayı kapatır."""
    import os
    system = sys.platform if system is None else system
    if system.startswith("win"):
        launch_windows(path, silent=windows_installed() if installed is None else installed, popen=popen)
    elif system == "darwin":
        app = mac_bundle()
        blocker = mac_blocker(app)
        if blocker:
            raise UpdateError(blocker)
        launch_mac(path, app, os.getpid(), run=run, popen=popen)
    else:
        raise UpdateError("Bu sistemde otomatik güncelleme desteklenmiyor.")
