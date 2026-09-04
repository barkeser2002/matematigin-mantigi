from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = PACKAGE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
TEMPLATE_NAME = "sorular_sablon.xlsx"


def default_template_path() -> Path:
    return Path.cwd() / TEMPLATE_NAME


def default_session_root() -> Path:
    return Path.cwd() / "oturum"
