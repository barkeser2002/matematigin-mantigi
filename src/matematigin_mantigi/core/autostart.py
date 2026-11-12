"""Bilgisayar açılınca uygulamayı başlatma (oturum açılışında).

Windows: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run altında 'MatematiginMantigi' değeri.
macOS: ~/Library/LaunchAgents/com.barkeser.matematiginmantigi.plist (RunAtLoad).
Linux (geliştirme): ~/.config/autostart/matematigin-mantigi.desktop.

Durumun tek doğru kaynağı sistemin kendi kaydıdır (kayıt defteri / plist / .desktop): ayar dosyasında ayrıca bir
'açık' bayrağı tutulmaz, kullanıcı kaydı elle silerse onay kutusu doğru görünür. Çalıştırma açılışta tek başına
kayıt oluşturmaz; yalnız var olan kaydın yolunu güncel tutar (repair). Kayıt hiçbir koşulda KAYDI başlatmaz:
`--baslangic` yalnız açılış biçimini söyler.

Testler gerçek kayıt defterine / ev klasörüne yazmasın diye platform, winreg, ev ve yapılandırma klasörü
enjekte edilir.
"""
from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WIN_VALUE_NAME = "MatematiginMantigi"
MAC_LABEL = "com.barkeser.matematiginmantigi"
LINUX_FILE = "matematigin-mantigi.desktop"
STARTUP_ARG = "--baslangic"
APP_NAME = "Matematiğin Mantığı"


class AutostartError(Exception):
    """Kayıt yazılamadı/silinemedi; metin kullanıcıya gösterilir."""


def _desktop_quote(arg: str) -> str:
    """.desktop Exec bağımsız değişkeni: boşluk/özel karakter varsa tırnaklı, \\ \" $ ` kaçışlı."""
    if arg and not any(c in arg for c in ' \t\n"\'\\><~|&;$*?#()`'):
        return arg
    escaped = (arg.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`"))
    return f'"{escaped}"'


class Autostart:
    def __init__(self, *, platform: str | None = None, frozen: bool | None = None,
                 executable: str | None = None, winreg=None, home: Path | None = None,
                 config_home: Path | None = None):
        self.platform = platform if platform is not None else sys.platform
        if frozen is None:
            from matematigin_mantigi import paths
            frozen = paths.is_frozen()
        self.frozen = frozen
        self.executable = executable if executable is not None else sys.executable
        self._winreg = winreg
        self.home = Path(home) if home is not None else Path.home()
        self._config_home = Path(config_home) if config_home is not None else None

    # --- destek ---------------------------------------------------------------
    @property
    def unsupported_reason(self) -> str:
        """Boş: destekleniyor. Dolu: seçeneğin neden kapalı olduğu (ipucunda gösterilir)."""
        if self.platform.startswith("linux"):
            return ""                        # geliştirme ortamı: paketsiz de çalışır (python -m ile)
        if not self.platform.startswith(("win", "darwin")):
            return "Bu işletim sisteminde bilgisayar açılınca başlatma desteklenmiyor."
        if not self.frozen:
            return ("Uygulama kaynak koddan çalışıyor; bilgisayar açılınca başlatma yalnız paketli "
                    "(kurulmuş) uygulamada kullanılabilir.")
        return ""

    @property
    def supported(self) -> bool:
        return not self.unsupported_reason

    def command_line(self) -> list[str]:
        """Açılışta çalışacak komut: [çalıştırılabilir, ...bağımsız değişkenler, --baslangic]."""
        if self.frozen:
            return [self.executable, STARTUP_ARG]
        return [self.executable, "-m", "matematigin_mantigi", STARTUP_ARG]

    # --- Windows --------------------------------------------------------------
    def _wr(self):
        if self._winreg is None:
            import winreg                    # yalnız Windows'ta var
            self._winreg = winreg
        return self._winreg

    def _windows_command(self) -> str:
        args = self.command_line()
        return " ".join(f'"{a}"' if i == 0 else a for i, a in enumerate(args))

    def _windows_read(self) -> str | None:
        wr = self._wr()
        try:
            with wr.OpenKey(wr.HKEY_CURRENT_USER, RUN_KEY, 0, wr.KEY_QUERY_VALUE) as key:
                value, _kind = wr.QueryValueEx(key, WIN_VALUE_NAME)
        except FileNotFoundError:
            return None
        return value if isinstance(value, str) and value else None

    def _windows_write(self, command: str) -> None:
        wr = self._wr()
        with wr.CreateKeyEx(wr.HKEY_CURRENT_USER, RUN_KEY, 0, wr.KEY_SET_VALUE) as key:
            wr.SetValueEx(key, WIN_VALUE_NAME, 0, wr.REG_SZ, command)

    def _windows_remove(self) -> None:
        wr = self._wr()
        try:
            with wr.OpenKey(wr.HKEY_CURRENT_USER, RUN_KEY, 0, wr.KEY_SET_VALUE) as key:
                wr.DeleteValue(key, WIN_VALUE_NAME)
        except FileNotFoundError:
            pass

    # --- macOS ----------------------------------------------------------------
    @property
    def mac_plist_path(self) -> Path:
        return self.home / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"

    def _mac_content(self) -> bytes:
        return plistlib.dumps({"Label": MAC_LABEL, "ProgramArguments": self.command_line(), "RunAtLoad": True})

    # --- Linux ----------------------------------------------------------------
    @property
    def linux_desktop_path(self) -> Path:
        base = self._config_home
        if base is None:
            env = os.environ.get("XDG_CONFIG_HOME")
            base = Path(env) if env else self.home / ".config"
        return base / "autostart" / LINUX_FILE

    def _linux_content(self) -> str:
        exec_line = " ".join(_desktop_quote(a) for a in self.command_line())
        return (f"[Desktop Entry]\nType=Application\nName={APP_NAME}\nExec={exec_line}\n"
                "X-GNOME-Autostart-enabled=true\n")

    # --- ortak ----------------------------------------------------------------
    def _file_target(self) -> tuple[Path, "bytes | str"] | None:
        if self.platform.startswith("darwin"):
            return self.mac_plist_path, self._mac_content()
        if self.platform.startswith("linux"):
            return self.linux_desktop_path, self._linux_content()
        return None

    def _current(self) -> "bytes | str | None":
        """Sistemdeki mevcut kaydın içeriği (yoksa None)."""
        if self.platform.startswith("win"):
            return self._windows_read()
        target = self._file_target()
        if target is None:
            return None
        path, expected = target
        try:
            return path.read_bytes() if isinstance(expected, bytes) else path.read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            return None
        except (OSError, UnicodeDecodeError):
            return "?"                         # var ama okunamıyor: açık say, repair yeniden yazar

    def _expected(self) -> "bytes | str":
        if self.platform.startswith("win"):
            return self._windows_command()
        target = self._file_target()
        assert target is not None
        return target[1]

    def is_enabled(self) -> bool:
        """Gerçek kayda bakar (desteklenmiyorsa False). Okuma hatası kullanıcıya 'kapalı' gösterir, çökertmez."""
        if not self.supported:
            return False
        try:
            return self._current() is not None
        except OSError:
            return False

    def set_enabled(self, on: bool) -> None:
        if on and not self.supported:
            raise AutostartError(self.unsupported_reason)
        if not self.supported:
            return
        try:
            if on:
                self._write()
            else:
                self._remove()
        except AutostartError:
            raise
        except OSError as err:
            verb = "yazılamadı" if on else "silinemedi"
            raise AutostartError(f"Bilgisayar açılınca başlatma kaydı {verb}: {err}") from err

    def _write(self) -> None:
        if self.platform.startswith("win"):
            self._windows_write(self._windows_command())
            return
        target = self._file_target()
        assert target is not None
        path, content = target
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        if isinstance(content, bytes):
            tmp.write_bytes(content)
        else:
            tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)

    def _remove(self) -> None:
        if self.platform.startswith("win"):
            self._windows_remove()
            return
        target = self._file_target()
        if target is not None:
            try:
                target[0].unlink()
            except FileNotFoundError:
                pass

    def repair(self) -> bool:
        """Seçenek AÇIKSA ve kayıttaki komut güncel yoldan farklıysa (uygulama güncellendi/taşındı) sessizce
        günceller. Kapalıysa hiçbir şey yazmaz (kendiliğinden açmaz). Dönüş: kayıt yeniden yazıldı mı."""
        if not self.supported:
            return False
        try:
            current = self._current()
            if current is None or current == self._expected():
                return False
            self._write()
            return True
        except (OSError, AutostartError) as err:
            from matematigin_mantigi.core import crash_log
            crash_log.log_handled(err, "açılışta başlatma kaydı")
            return False
