# Matematiğin Mantığı — grafik tablet ders uygulaması (görünüş demosu)

## Çalıştırma

    python -m pip install -e ".[dev]"
    python -m matematigin_mantigi              # kamera 0, ./sorular_sablon.xlsx, ./duzen.json
    python -m matematigin_mantigi --kamera 1
    python -m matematigin_mantigi --kamera-yok --sorular C:\yol\sorular.xlsx

Windows PowerShell'de önce `$env:PYTHONUTF8 = "1"`.

## Testler

    python -m pytest -q          # başsız (QT_QPA_PLATFORM=offscreen), kamera ve tablet gerekmez

## Bölgeler

1 Soru · 2 El çizimi · 3 Akıllı ipuçları · 4 Webcam · 9 Dış araç çubuğu (kayıtta görünmez).
"⧉ Düzen" (L) ile paneller OBS gibi taşınır/boyutlandırılır, 12x10 ızgaraya yapışır, `duzen.json`'a kaydedilir.
Normal kullanımda panel kenarları ve çerçeve çizilmez; çizgiler sadece düzen modunda görünür.

## Kısayollar

1-5 araçlar · Ctrl+Z geri al · Ctrl+Shift+X temizle · N sıradaki soru · Space işle/tamamla · R kayıt ·
H soruyu gizle/göster · ←/→ ipucu · Enter ipucunu aç · L düzen · F11 tam ekran · Esc çık

## Soru şablonu

`sorular_sablon.xlsx` ilk çalıştırmada üretilir. Sütunlar: id, konu, sinif, soru, ipucu1, ipucu2, ipucu3, cevap.
Boş ipucu hücreleri atlanır; `soru` boşsa satır numarasıyla hata verilir.

## macOS (hedef makine, XP-Pen)

- arm64 Python kullanın (`python3 -c "import platform; print(platform.machine())"` → arm64). PyQt6 universal2 wheel, macOS 12+.
- Kamera izni terminal uygulamasına (Terminal/iTerm/VS Code) verilir: Sistem Ayarları > Gizlilik ve Güvenlik > Kamera.
- Ekran kaydı izni (sonraki sürümdeki mss kaydedici için) aynı yerde "Ekran Kaydı".
- XP-Pen sürücüsünü kurun, Erişilebilirlik ve Giriş İzleme izinlerini verin; sürücü yoksa sadece fare olayları gelir.
- Paketlenince (py2app/PyInstaller) Info.plist'e `NSCameraUsageDescription` eklenmeli.

## Windows (geliştirme makinesi)

- XP-Pen sürücüsünde "Windows Ink" açık olmalı; Qt 6 kalem verisini WM_POINTER üzerinden alır.
- Windows Ink kapalıysa alternatif: `$env:QT_QPA_PLATFORM = "windows:nowmpointer"` (WinTab yolu).
- Ekran ölçeği %125+ ise pencere 1920x1080'den küçük başlar; paneller ızgarayla orantılı küçülür.
- Kamera önce DirectShow ile, açılmazsa varsayılan arka uçla (MSMF) denenir.

## Oturum çıktıları

`oturum/<tarih-saat>/<soruId>_<nn>.png` — "Sıradaki soru" veya soru seçimi sırasında tuval boş değilse kaydedilir.

## Bu sürümde taslak olan kısımlar

Kayıt düğmesi (NullRecorder + rozet), Keras tanıma durumu (sabit metin), Yazı ve Şekil araçları.
