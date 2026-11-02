# Windows paketleme: .venv kurar, kütüphaneleri yükler, testleri koşar, PyInstaller ile
# "Matematigin Mantigi" klasörünü (.exe) üretir.
# Kullanım (proje kökünde, PowerShell):  powershell -ExecutionPolicy Bypass -File windows\build_win.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$py = if ($env:PYTHON) { $env:PYTHON } else { "python" }
& $py -c "import sys; print('Python', sys.version.split()[0])"

if (-not (Test-Path .venv)) {
    & $py -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install --upgrade pip wheel -c constraints.txt
& .\.venv\Scripts\python.exe -m pip install -e ".[dev,pdf]" pyinstaller -c constraints.txt   # sürümler constraints.txt'ten
& .\.venv\Scripts\python.exe -c "import imageio_ffmpeg; print('ffmpeg:', imageio_ffmpeg.get_ffmpeg_exe())"

$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTHONUTF8 = "1"
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "testler geçmedi" }

if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist)  { Remove-Item -Recurse -Force dist }
& .\.venv\Scripts\pyinstaller.exe --noconfirm windows\matematigin_mantigi_win.spec
if ($LASTEXITCODE -ne 0) { throw "pyinstaller başarısız" }

Write-Host "== Bitti: dist\Matematigin Mantigi\Matematigin Mantigi.exe"
