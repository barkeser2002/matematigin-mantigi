"""Uygulama çapında hata yakalayıcı: yakalanmamış istisna veri klasöründeki hatalar.log'a yazılır, uygulama düşmez.

PyQt6, bir yuvada (slot), Qt sanal yönteminde ya da QThread.run içinde yakalanmamış istisnada, sys.excepthook
Python'un varsayılanıysa qFatal ile süreci kapatır: ders ortasında uygulama kaybolur, süren kayıt
birleştirilmeden kalır (denetim app#2). Kendi kancamız kuruluyken PyQt yalnız onu çağırır ve olay döngüsü sürer.
Bu modül Qt'ye dokunmaz; QApplication kurulmadan önce de güvenle kurulur. Kullanıcıya gösterilecek uyarı,
kurulumda verilen `notify` geri çağırmasıyla dışarıda (ui/error_notice.py) yapılır.
"""
from __future__ import annotations

import platform
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

from matematigin_mantigi import __version__

Notify = Callable[[str, str, str], None]            # (başlık, metin, anahtar); herhangi bir iş parçacığından çağrılır


def _summary(exc_type, exc) -> str:
    """'OSError: mesaj' biçiminde kısa özet; istisnanın str()'si patlasa bile."""
    try:
        return "".join(traceback.format_exception_only(exc_type, exc)).strip()[:300]
    except Exception:  # noqa: BLE001
        return getattr(exc_type, "__name__", "hata")


def signature(exc_type, tb) -> str:
    """Aynı hatayı tanıyan anahtar: tür + kod yolu (dosya:satır zinciri). Mesaj bilerek dışarıda: değişen bir
    sayı ya da yol içeren mesaj aynı hatayı yüzlerce farklı hata gibi göstermesin."""
    try:
        frames = ";".join(f"{f.filename}:{f.lineno}" for f in traceback.extract_tb(tb)) if tb is not None else ""
    except Exception:  # noqa: BLE001
        frames = ""
    return f"{getattr(exc_type, '__module__', '')}.{getattr(exc_type, '__qualname__', exc_type)}@{frames}"


def _milestone(n: int) -> bool:
    """10, 100, 1000 …: tekrarlar günlüğe logaritmik seyrekle düşer."""
    return n >= 10 and str(n).rstrip("0") == "1"


_LAST = ("last_exc", "last_type", "last_value", "last_traceback")


def _release_last(exc) -> None:
    """PyQt6 kurulu kancayı PyErr_Print() üzerinden çağırır; o da kancadan önce sys.last_exc/last_type/last_value/
    last_traceback'i bu istisnaya ayarlar. Bunlar bir sonraki istisnaya dek traceback'i, dolayısıyla patlayan
    çerçeveyi ve içindeki nesneleri canlı tutar: paintEvent'te etkin kalan QPainter her çizimde 'QBackingStore::
    endPaint() called with active painter' bastırıyordu. Kanca işini bitirince bu istisnanın kaydını bırakır; başka
    bir istisnanınkine (doğrudan çağrı) dokunmaz. İstisna fırlatmaz."""
    try:
        if exc is not None and (getattr(sys, "last_value", None) is exc or getattr(sys, "last_exc", None) is exc):
            for name in _LAST:
                setattr(sys, name, None)
    except Exception:  # noqa: BLE001
        pass


class CrashLog:
    """Kurulu kancaların durumu: günlük yolu, hata sayaçları ve (varsa) kullanıcıya uyarı gösteren geri çağırma.

    Kanca hiçbir koşulda istisna fırlatmaz (günlük yazılamasa, uyarı gösterilemese, istisnanın str()'si bozuk
    olsa bile): her adım ayrı korunur, biri düşerse diğerleri yine çalışır."""

    def __init__(self, path: Path, notify: Notify | None = None, clock: Callable[[], datetime] = datetime.now):
        self.path = Path(path)
        self.notify = notify
        self.counts: dict[str, int] = {}
        self._clock = clock
        self._lock = threading.RLock()          # kanca herhangi bir iş parçacığından çağrılabilir
        self._prev_hooks: tuple | None = None

    def record(self, exc_type, exc, tb, where: str = "", handled: bool = False) -> tuple[str, int, bool]:
        """Hatayı günlüğe ekler; dönüş (anahtar, bu oturumda kaçıncı kez, yazım hatasız mı: atlanan tekrarda da
        True). Aynı hata ilk kez zaman damgası ve traceback'le, sonra yalnız 10., 100. … tekrarında tek satırla
        yazılır: saniyede 60 kez patlayan bir çizim olayı bir saatlik derste diski doldurmasın."""
        key = signature(exc_type, tb)
        with self._lock:
            n = self.counts.get(key, 0) + 1
            self.counts[key] = n
            if n > 1 and not _milestone(n):
                return key, n, True
            try:
                stamp = self._clock().strftime("%Y-%m-%d %H:%M:%S")
                if n == 1:
                    kind = "yakalanan hata" if handled else "yakalanmamış hata"
                    head = f"==== {stamp} · {kind}" + (f" ({where})" if where else "") + " ===="
                    text = (f"{head}\nMatematiğin Mantığı {__version__} · Python {platform.python_version()} · "
                            f"{platform.platform()}\n" + "".join(traceback.format_exception(exc_type, exc, tb)) + "\n")
                else:
                    text = f"{stamp} · aynı hata {n}. kez: {_summary(exc_type, exc)}\n"
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(text)
                return key, n, True
            except Exception:  # noqa: BLE001 - günlük yazılamazsa da uygulama düşmez
                return key, n, False

    def _handle(self, exc_type, exc, tb, where: str) -> None:
        key, n, written = "", 1, False
        try:
            key, n, written = self.record(exc_type, exc, tb, where)
        except Exception:  # noqa: BLE001
            pass
        if n == 1 or _milestone(n):              # geliştirme terminali de aynı seyreklikte görsün
            try:
                if sys.stderr is not None:      # paketli Windows uygulamasında stderr yok
                    traceback.print_exception(exc_type, exc, tb, file=sys.stderr)
            except Exception:  # noqa: BLE001
                pass
        if n == 1 and self.notify is not None:   # aynı hata için tek uyarı: pencere yağmuru olmaz
            try:
                detail = f"Ayrıntı: {self.path}" if written else f"Ayrıntı günlüğe yazılamadı: {self.path}"
                text = ("Bir hata oluştu ama uygulama çalışmaya devam ediyor; süren bir kayıt varsa durdurulmadı."
                        f"\n\n{_summary(exc_type, exc)}\n\n{detail}")
                self.notify("Beklenmeyen hata", text, key)
            except Exception:  # noqa: BLE001
                pass

    def excepthook(self, exc_type, exc, tb) -> None:
        try:
            try:
                if issubclass(exc_type, KeyboardInterrupt):   # geliştirme terminalindeki Ctrl+C uygulama hatası değil
                    if sys.stderr is not None:
                        print("Ctrl+C: uygulama ve süren kayıt devam ediyor; çıkmak için pencereyi kapatın.",
                              file=sys.stderr)
                    return
                cur = threading.current_thread()
                where = "" if cur is threading.main_thread() else f"iş parçacığı: {cur.name}"
            except Exception:  # noqa: BLE001
                where = ""
            self._handle(exc_type, exc, tb, where)
        finally:
            _release_last(exc)

    def threading_hook(self, args) -> None:
        """threading.excepthook: threading.Thread'den (ör. ses yazıcısı) kaçan istisna da aynı günlüğe düşer."""
        if args.exc_type is SystemExit:          # threading'in varsayılanı gibi sessiz
            return
        name = getattr(args.thread, "name", None)
        self._handle(args.exc_type, args.exc_value, args.exc_traceback, f"iş parçacığı: {name}" if name else "")


_active: CrashLog | None = None                    # kurulu günlük (log_handled için); install/uninstall yönetir


def install(path: Path, notify: Notify | None = None) -> CrashLog:
    """sys.excepthook ve threading.excepthook'u kurar. Qt'ye dokunmaz: QApplication'dan önce ya da sonra güvenle
    çağrılır; `notify` sonradan (QApplication kurulunca) atanabilir."""
    global _active
    log = CrashLog(path, notify)
    log._prev_hooks = (sys.excepthook, threading.excepthook)
    sys.excepthook = log.excepthook
    threading.excepthook = log.threading_hook
    _active = log
    return log


def uninstall(log: CrashLog) -> None:
    """Kurulumu geri alır: kancalar hâlâ bu günlüğünse öncekiler geri gelir."""
    global _active
    if _active is log:
        _active = None
    if log._prev_hooks is None:
        return
    prev_sys, prev_thread = log._prev_hooks
    if sys.excepthook == log.excepthook:
        sys.excepthook = prev_sys
    if threading.excepthook == log.threading_hook:
        threading.excepthook = prev_thread
    log._prev_hooks = None


def log_handled(exc: BaseException, where: str = "") -> None:
    """Yakalanıp kullanıcıya kendi yolundan bildirilen hatayı da (traceback'iyle, ayrıntı için) günlüğe ekler;
    uyarı kutusu açmaz. Kanca kurulu değilse (testler, araçlar) bir şey yapmaz; istisna fırlatmaz."""
    log = _active
    if log is not None:
        log.record(type(exc), exc, exc.__traceback__, where, handled=True)
