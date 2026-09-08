# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: macOS .app (PyQt6 + OpenCV + numpy + openpyxl). Çalıştırma: pyinstaller mac/matematigin_mantigi.spec
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
    hiddenimports=["PyQt6.QtTest", "openpyxl", "cv2", "numpy", "pymupdf", "mss", "imageio_ffmpeg", "sounddevice", "_sounddevice_data"],
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
    name="MatematiginMantigi",          # ikili adı ASCII; görünen ad Info.plist'te
    debug=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False, name="MatematiginMantigi")
app = BUNDLE(
    coll,
    name="Matematiğin Mantığı.app",
    icon=None,                       # logo hazır olunca: mac/icon.icns
    bundle_identifier="com.matematiginmantigi.tahta",
    info_plist={
        "CFBundleDisplayName": "Matematiğin Mantığı",
        "CFBundleName": "Matematiğin Mantığı",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
        # İzin metinleri: bunlar olmadan macOS kamera/mikrofonu sessizce reddeder.
        "NSCameraUsageDescription": "Ders kaydında öğretmen görüntüsü ve yeşil perde için kamera gerekir.",
        "NSMicrophoneUsageDescription": "Ders kaydında ses için mikrofon gerekir.",
        "NSScreenCaptureUsageDescription": "Tahtanın video kaydı için ekran yakalama gerekir.",
        "NSAppleEventsUsageDescription": "Kalem kısayolları için otomasyon gerekir.",
    },
)
