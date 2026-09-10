# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: Windows tek klasör (.exe). Çalıştırma: pyinstaller windows/matematigin_mantigi_win.spec
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(SPECPATH).parent
PKG = ROOT / "src" / "matematigin_mantigi"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()          # ikili pakete girer; imageio_ffmpeg pakette aynı yoldan bulur

block_cipher = None

a = Analysis(
    [str(PKG / "__main__.py")],
    pathex=[str(ROOT / "src")],
    binaries=[(FFMPEG, "imageio_ffmpeg/binaries")],
    datas=[
        (str(PKG / "assets" / "fonts"), "matematigin_mantigi/assets/fonts"),
        (str(ROOT / "sorular_sablon.xlsx"), "."),
        (str(ROOT / "sorular_gorsel"), "sorular_gorsel"),
    ],
    hiddenimports=["PyQt6.QtTest", "openpyxl", "cv2", "numpy", "pymupdf", "mss", "imageio_ffmpeg",
                   "sounddevice", "_sounddevice_data", "cffi"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "PIL.ImageQt"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Matematigin Mantigi",           # .exe adı ASCII (çift tıklanabilir)
    debug=False,
    strip=False,
    upx=False,
    console=False,                        # pencere uygulaması; konsol açılmaz
    icon=None,                            # logo hazır olunca: windows/icon.ico
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="Matematigin Mantigi")
