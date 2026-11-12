# Windows paketleme: .venv kurar, kütüphaneleri yükler, testleri koşar, PyInstaller ile
# "Matematigin Mantigi" klasörünü (.exe) üretir, ardından Inno Setup ile kurulum programını
# (kurulum\Matematigin-Mantigi-Kurulum.exe) derler. Inno Setup yoksa: CI'da (CI=true) choco ile kurar,
# yerelde atlar (yalnızca uyarı verir). Yapı numarası src\matematigin_mantigi\_build.py'den okunur ('dev' → 0).
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

# --- Kurulum programı (Inno Setup) ---
$build = "0"
$m = Select-String -Path "src\matematigin_mantigi\_build.py" -Pattern '^BUILD\s*=\s*"(\d+)"' | Select-Object -First 1
if ($m) { $build = $m.Matches[0].Groups[1].Value }

function Find-Iscc {
    $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($dir in @("${env:ProgramFiles(x86)}", "$env:ProgramFiles", "$env:LOCALAPPDATA\Programs")) {
        if (-not $dir) { continue }
        $p = Join-Path $dir "Inno Setup 6\ISCC.exe"
        if (Test-Path $p) { return $p }
    }
    return $null
}
$iscc = Find-Iscc
if (-not $iscc -and $env:CI) {
    # windows-latest imajında Inno Setup kurulu gelir (runner-images belgesi); yine de eksikse kur.
    choco install innosetup -y --no-progress
    $iscc = Find-Iscc
}
if (-not $iscc) {
    if ($env:CI) { throw "Inno Setup bulunamadı" }
    Write-Warning "Inno Setup (ISCC.exe) bulunamadı: kurulum programı derlenmedi. https://jrsoftware.org/isinfo.php"
} else {
    if (Test-Path kurulum) { Remove-Item -Recurse -Force kurulum }
    & $iscc "/DAppVersion=$build" windows\installer.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup derlemesi başarısız" }
    if (-not (Test-Path "kurulum\Matematigin-Mantigi-Kurulum.exe")) { throw "Kurulum programı üretilmedi" }
    Write-Host "== Kurulum programı: kurulum\Matematigin-Mantigi-Kurulum.exe (Yapı $build)"
}
