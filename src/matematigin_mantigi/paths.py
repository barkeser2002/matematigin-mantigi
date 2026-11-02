"""Dosya yolları. Geliştirmede her şey çalışma dizinindedir; paketlenmiş uygulamada (.app / PyInstaller)
çalışma dizini yazılamaz olabildiğinden veriler ~/Documents/Matematiğin Mantığı altına gider."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
TEMPLATE_NAME = "sorular_sablon.xlsx"
IMAGES_DIR_NAME = "sorular_gorsel"
APP_FOLDER_NAME = "Matematiğin Mantığı"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """PyInstaller'ın paketle gelen veri dosyalarını açtığı klasör (geliştirmede proje kökü)."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else PACKAGE_DIR.parent.parent


def data_dir() -> Path:
    """Kullanıcı verileri: şablon, görseller, oturum kayıtları, düzen."""
    if is_frozen():
        return Path.home() / "Documents" / APP_FOLDER_NAME
    return Path.cwd()


def ensure_user_data(target: Path | None = None) -> Path:
    """Paketlenmiş uygulamada ilk açılışta gömülü şablonu ve görselleri veri klasörüne kopyalar."""
    target = Path(target) if target is not None else data_dir()
    target.mkdir(parents=True, exist_ok=True)
    src = bundle_dir()
    if not (target / TEMPLATE_NAME).exists() and (src / TEMPLATE_NAME).exists() and src != target:
        shutil.copy2(src / TEMPLATE_NAME, target / TEMPLATE_NAME)
    if not (target / IMAGES_DIR_NAME).exists() and (src / IMAGES_DIR_NAME).is_dir() and src != target:
        shutil.copytree(src / IMAGES_DIR_NAME, target / IMAGES_DIR_NAME)
    return target


def default_template_path() -> Path:
    return data_dir() / TEMPLATE_NAME


def default_session_root() -> Path:
    return data_dir() / "oturum"


def default_layout_path() -> Path:
    return data_dir() / "duzen.json"


def default_error_log_path() -> Path:
    """Hata günlüğü (core/crash_log.py): yakalanmamış istisnalar ve ayrıntısı saklanan yakalanmış hatalar."""
    return data_dir() / "hatalar.log"
