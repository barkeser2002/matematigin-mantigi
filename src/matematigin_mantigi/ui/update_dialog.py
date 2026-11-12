"""Açılışta güncelleme soruları ve indirme penceresi. Mantık core/updater.py'de; burası yalnız Qt tarafı:
arka plan iş parçacığı, kayıt sürerken erteleme, soru, ilerleme çubuğu, kapatıp kurma.

Sahne dışıdır: kutular ana pencerenin üstünde açılır ama kayıt sürerken HİÇ açılmaz (kayıt bitince ya da sonraki
açılışta sorulur); ağ hatası sessizdir (hatalar.log)."""
from __future__ import annotations

import shutil
import sys
import tempfile
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QSettings, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox, QProgressDialog

from matematigin_mantigi import paths
from matematigin_mantigi.core import crash_log, updater
from matematigin_mantigi.core.recorder import RecorderState

CHECK_DELAY_MS = 8000            # açılıştan sonra: pencere yerleşsin, ilk kare çizilsin
RETRY_MS = 30000                 # kayıt sürüyorsa bu aralıkla yeniden bakılır


# ---- kutular (testlerde değiştirilir) ----

def ask_update(parent, text: str, can_skip: bool = True) -> str:
    """'yes' | 'later' | 'skip'."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setText(text)
    yes = box.addButton("Güncelle", QMessageBox.ButtonRole.AcceptRole)
    later = box.addButton("Sonra", QMessageBox.ButtonRole.RejectRole)
    skip = box.addButton("Bu sürümü atla", QMessageBox.ButtonRole.DestructiveRole) if can_skip else None
    box.setDefaultButton(yes)
    box.setEscapeButton(later)
    box.exec()
    clicked = box.clickedButton()
    return "yes" if clicked is yes else "skip" if skip is not None and clicked is skip else "later"


def show_error(parent, text: str) -> None:
    QMessageBox.warning(parent, "Güncelleme", text)


def open_page(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def prompt_text(info: updater.ReleaseInfo, current: int, installer_only: bool = False) -> str:
    head = f"Yapı {info.build} mevcut (şu an {current})."
    if installer_only:
        return (f"{head} Bu kopya kurulum programıyla kurulmamış; kurulum programı indirilip çalıştırılsın mı? "
                "Uygulama kapanır, kurulum bitince yeni sürümü Başlat menüsünden açabilirsiniz.")
    return f"{head} İndirilip kurulsun ve program yeniden başlasın mı?"


class _Signals(QObject):
    found = pyqtSignal(object)                  # ReleaseInfo | None
    progress = pyqtSignal(int, int)
    downloaded = pyqtSignal(object, str)        # (yol | None, hata metni; boş = iptal)


class UpdateController(QObject):
    """Açılışta bir kez kontrol eder. `win`: .recorder.state, .close(), .isVisible() olan ana pencere.
    Diğer parametreler testler için enjeksiyon noktalarıdır; üretimde hepsi varsayılandır."""

    def __init__(self, win, *, frozen: bool | None = None, build: int | None = ..., system: str | None = None,
                 fetch=None, settings: QSettings | None = None, delay_ms: int = CHECK_DELAY_MS,
                 retry_ms: int = RETRY_MS, downloader=None, launcher=None, trusted_prefix: str = updater.TRUSTED_PREFIX,
                 windows_installed: bool | None = None, mac_blocker_text: str | None = None,
                 temp_root: Path | None = None):
        super().__init__(win)
        self.win = win
        self.system = sys.platform if system is None else system
        self.build = updater.current_build() if build is ... else build
        self.enabled = (paths.is_frozen() if frozen is None else frozen) and self.build is not None
        self._fetch = fetch or updater.fetch_latest
        self._settings = settings
        self._delay, self._retry = delay_ms, retry_ms
        self._downloader = downloader or updater.download
        self._launcher = launcher
        self._prefix = trusted_prefix
        self._win_installed = windows_installed
        self._mac_blocker_text = mac_blocker_text
        self._temp_root = temp_root
        self._info: updater.ReleaseInfo | None = None
        self._path: Path | None = None
        self._tmp: Path | None = None
        self._cancel = threading.Event()
        self._progress: QProgressDialog | None = None
        self._busy_timer = QTimer(self)
        self._busy_timer.setSingleShot(True)
        self._busy_timer.timeout.connect(self._advance)
        self._sig = _Signals(self)
        self._sig.found.connect(self._on_found)
        self._sig.progress.connect(self._on_progress)
        self._sig.downloaded.connect(self._on_downloaded)
        self._stage = "idle"                    # idle | ask | ready

    # -- yardımcılar --

    def _store(self) -> QSettings:
        if self._settings is None:
            self._settings = QSettings("MatematiginMantigi", "Ogretim")
        return self._settings

    def _recording(self) -> bool:
        try:
            return self.win.recorder.state is not RecorderState.IDLE
        except Exception:  # noqa: BLE001 - durum okunamıyorsa meşgul say: kaydı asla böleriz
            return True

    def _installed(self) -> bool:
        return updater.windows_installed() if self._win_installed is None else self._win_installed

    # -- akış --

    def start(self) -> None:
        if not self.enabled:
            return
        QTimer.singleShot(self._delay, self._begin_check)

    def _begin_check(self) -> None:
        threading.Thread(target=self._check_worker, name="guncelleme-kontrol", daemon=True).start()

    def _check_worker(self) -> None:
        try:
            info = updater.find_update(build=self.build, system=self.system, fetch=self._fetch,
                                       skipped=updater.get_skipped(self._store()), trusted_prefix=self._prefix)
        except Exception as err:  # noqa: BLE001
            crash_log.log_handled(err, "güncelleme kontrolü")
            info = None
        self._sig.found.emit(info)

    def _on_found(self, info) -> None:
        if info is None:
            return
        self._info, self._stage = info, "ask"
        self._advance()

    def _advance(self) -> None:
        """Soru ve kurma adımları yalnız kayıt yokken; kayıt sürüyorsa sessizce yeniden denenir."""
        if self._stage == "idle" or self._info is None:
            return
        if self._recording():
            self._busy_timer.start(self._retry)
            return
        if self._stage == "ask":
            self._ask()
        elif self._stage == "ready":
            self._ask_restart()

    def _ask(self) -> None:
        info = self._info
        blocker = self._blocker()
        if blocker:
            self._stage = "idle"
            if ask_update(self.win, f"Yapı {info.build} mevcut (şu an {self.build}).\n\n{blocker}\n\n"
                          "İndirme sayfası açılsın mı?", can_skip=False) == "yes":
                open_page(info.page_url)
            return
        zip_run = self.system.startswith("win") and not self._installed()
        answer = ask_update(self.win, prompt_text(info, self.build, installer_only=zip_run))
        if answer == "skip":
            updater.set_skipped(self._store(), info.build)
            self._stage = "idle"
        elif answer == "yes":
            self._start_download()
        else:
            self._stage = "idle"

    def _blocker(self) -> str | None:
        if self._mac_blocker_text is not None:
            return self._mac_blocker_text
        if self.system == "darwin":
            return updater.mac_blocker(updater.mac_bundle())
        return None

    # -- indirme --

    def _start_download(self) -> None:
        root = self._temp_root
        if root is not None:
            root.mkdir(parents=True, exist_ok=True)
        self._tmp = Path(tempfile.mkdtemp(prefix="mm-guncelleme-", dir=str(root) if root else None))
        self._cancel.clear()
        dlg = QProgressDialog(f"Yapı {self._info.build} indiriliyor…", "İptal", 0, 100, self.win)
        dlg.setWindowTitle("Güncelleme")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)
        dlg.canceled.connect(self._cancel.set)
        self._progress = dlg
        dlg.show()
        threading.Thread(target=self._download_worker, name="guncelleme-indir", daemon=True).start()
        self._stage = "idle"

    def _download_worker(self) -> None:
        try:
            path = self._downloader(self._info, self._tmp, progress=lambda d, t: self._sig.progress.emit(d, t),
                                    cancel=self._cancel)
            self._sig.downloaded.emit(path, "")
        except updater.UpdateCancelled:
            self._sig.downloaded.emit(None, "")
        except Exception as err:  # noqa: BLE001
            crash_log.log_handled(err, "güncelleme indirme")
            self._sig.downloaded.emit(None, str(err))

    def _on_progress(self, done: int, total: int) -> None:
        if self._progress is not None and total > 0:
            self._progress.setValue(min(100, done * 100 // total))

    def _on_downloaded(self, path, error: str) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress.deleteLater()
            self._progress = None
        if path is None:
            self._cleanup()
            self._stage = "idle"
            if error:
                show_error(self.win, f"Güncelleme indirilemedi, bir şey kurulmadı.\n{error}\n"
                           f"Elle indirebilirsiniz: {self._info.page_url}")
            return
        self._path, self._stage = Path(path), "ready"
        if self._recording():                   # indirme sürerken kayıt başladıysa kapanma, bitince sor
            self._busy_timer.start(self._retry)
        else:
            self._install()

    def _ask_restart(self) -> None:
        if ask_update(self.win, f"Yapı {self._info.build} indirildi. Şimdi kurulup program yeniden başlasın mı?",
                      can_skip=False) == "yes":
            self._install()
        else:
            self._cleanup()
            self._stage = "idle"

    # -- kurma --

    def _install(self) -> None:
        """Pencereyi kapatır (kayıt/kayıtsız temiz kapanış), kapandıysa kurulumu başlatır."""
        info, path = self._info, self._path
        self._stage = "idle"
        self.win.close()
        if self.win.isVisible():                # kapanış iptal edildi (kaydedilmemiş iş, kayıt…): kurulum başlamaz
            show_error(self.win, "Uygulama kapatılamadığı için güncelleme kurulmadı. Dosya silindi; "
                       "bir sonraki açılışta yeniden sorulur.")
            self._cleanup()
            return
        try:
            (self._launcher or (lambda i, p: updater.launch_update(i, p, installed=self._win_installed)))(info, path)
        except Exception as err:  # noqa: BLE001
            crash_log.log_handled(err, "güncelleme kurma")
            show_error(None, f"Güncelleme kurulamadı: {err}\nElle indirebilirsiniz: {info.page_url}")
            self._cleanup()

    def _cleanup(self) -> None:
        if self._tmp is not None:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None


def install(win, **kwargs) -> UpdateController:
    """app.py'nin tek bağlantı noktası: kaynaktan çalışırken ya da dev yapıda hiçbir şey yapmaz."""
    controller = UpdateController(win, **kwargs)
    controller.start()
    return controller
