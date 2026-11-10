#!/usr/bin/env bash
# macOS paketleme: .venv kurar, tüm kütüphaneleri yükler, PyInstaller ile "Matematiğin Mantığı.app" üretir.
# Kullanım (proje kökünde, macOS'ta):  bash mac/build_mac.sh
# Gerekli: arm64 Python 3.11+ (python.org veya Homebrew), Xcode Command Line Tools.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
echo "== Python: $($PY -c 'import sys, platform; print(sys.version.split()[0], platform.machine())')"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "HATA: Python 3.11+ gerekir. Örn: brew install python@3.12 && PYTHON=python3.12 bash mac/build_mac.sh" >&2
  exit 1
fi
if [ "$($PY -c 'import platform; print(platform.machine())')" != "arm64" ]; then
  echo "UYARI: arm64 Python değil (Rosetta?). Apple Silicon'da arm64 Python kullanın." >&2
fi

if [ ! -d .venv ]; then
  echo "== .venv oluşturuluyor"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel -c constraints.txt
echo "== Kütüphaneler: uygulama + PDF aktarımı + test + pyinstaller (sürümler constraints.txt'ten)"
python -m pip install -e ".[dev,pdf]" pyinstaller -c constraints.txt
python -c "import imageio_ffmpeg; print('ffmpeg:', imageio_ffmpeg.get_ffmpeg_exe())"   # ikili paketle gelir

echo "== Testler (başsız)"
QT_QPA_PLATFORM=offscreen python -m pytest -q

echo "== Paketleme"
rm -rf build dist
pyinstaller --noconfirm mac/matematigin_mantigi.spec

APP="dist/Matematiğin Mantığı.app"
echo "== Ad-hoc imza (derin) ve doğrulama"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
echo "== Bitti: $APP"
echo "   İlk açılışta macOS kamera ve mikrofon izni sorar (Info.plist metinleri gömülü)."
echo "   Uygulama ad-hoc imzalı, Apple onaylı değil. Başka Mac'e zip ile götürülürse açılmazsa/\"hasarlı\" derse:"
echo "     xattr -dr com.apple.quarantine \"/Applications/Matematiğin Mantığı.app\""
echo "   ya da Sistem Ayarları > Gizlilik ve Güvenlik > \"Yine de Aç\" (macOS 15'te sağ tık > Aç çalışmaz)."
echo "   Her yeni derlemede imza değişir; kamera/mikrofon/ekran kaydı izinleri yeniden istenebilir."
echo "   Kalem basıncı için XP-Pen sürücüsünü kurun; Sistem Ayarları > Gizlilik > Erişilebilirlik ve Giriş İzleme."
