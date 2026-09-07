# Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu)

## Çalıştırma

    python -m pip install -e ".[dev,pdf]"
    python -m matematigin_mantigi              # kamera 0, ./sorular_sablon.xlsx, ./duzen.json
    python -m matematigin_mantigi --kamera 1
    python -m matematigin_mantigi --kamera-yok --sorular C:\yol\sorular.xlsx

Windows PowerShell'de önce `$env:PYTHONUTF8 = "1"`.

## Testler

    python -m pytest -q          # başsız (QT_QPA_PLATFORM=offscreen), kamera ve tablet gerekmez

## Tahta

Çalışma alanının tamamı düz beyaz tuval; her yerine çizilir. Üstünde üç şeffaf bölge: sol üstte soru (kırmızı
numara, kalın metin, görsel, A) B) C) D)), sağ üstte "AKILLI İPUÇLARI" kartları, sağ alt köşede çerçevesiz webcam.
Sayfa başına tek soru; "Sıradaki soru →" (N) ve "← Önceki soru" (P) ile gezilir. Soru değişince metin kelime
kelime belirir, o an okunan kelime kırmızı vurgulanır (varsayılan 350 ms/kelime; Kalem ayarlarında "Okuma hızı",
0 = kapalı); tıklayınca tamamlanır. İpucu kartları blur veya redakte ile gizlidir, tıklanmadan açılmaz; açılırken
bulanıklık 300 ms'de çözülür.

Araçlar: kalem (5 kalınlık: 1/2/4/8/12 px), silgi, lazer (izi 1,5 sn'de sönerek kaybolur), yazı ve şekil (taslak).
İmleç araca göre ikon: renkli kurşun kalem (ucunda çizgi kalınlığı), silme alanı kadar silgi bloğu, kırmızı lazer
noktası; tahtanın ve bölgelerin her yerinde geçerli.

Webcam: yeşil perde kamera karesinin kenarlarından otomatik ölçülür (yeşilimsi ve doygunsa), böylece #00ff3c olmayan
gerçek perdeler de temizlenir; kamera yokken sadece kısa bir durum yazısı görünür.
"⧉ Düzen" (L) modunda bölgeler OBS gibi taşınır/boyutlandırılır, 12x10 ızgaraya yapışır, `duzen.json`'a kaydedilir.
Normal kullanımda çerçeve ve bölge çizgisi yoktur; sadece düzen modunda görünür.

## Kısayollar

1-5 araçlar · Ctrl+Z geri al · Ctrl+Shift+X temizle · N sıradaki · P önceki · Space işle/tamamla · R kayıt ·
H soruyu gizle/göster · ←/→ ipucu · Enter ipucunu aç · L düzen · F11 tam ekran · Esc çık

## Soru şablonu ve PDF aktarımı

`sorular_sablon.xlsx` sütunları: `id, konu, sinif, soru, ipucu1, ipucu2, ipucu3, cevap` (zorunlu) ve
`ipucu4, a, b, c, d, gorsel` (isteğe bağlı). `gorsel` xlsx klasörüne göre göreli yol olabilir.

Yatay soru PDF'ini (sayfa başına 1 soru + AKILLI İPUÇLARI kartları) aktarmak için:

    python -m matematigin_mantigi.pdf_import "ornek.pdf" --cikti sorular_sablon.xlsx --gorsel sorular_gorsel

Soru metni, A–D seçenekleri, 3–4 ipucu ve şekiller (`sorular_gorsel/SNN.png`) alınır; `konu` ve `cevap` boş
kalır, Excel'de doldurulur. `pymupdf` gerekir (`pip install pymupdf`).

## macOS (hedef makine, XP-Pen)

- arm64 Python kullanın (`python3 -c "import platform; print(platform.machine())"` → arm64). PyQt6 universal2 wheel, macOS 12+.
- Kamera izni terminal uygulamasına (Terminal/iTerm/VS Code) verilir: Sistem Ayarları > Gizlilik ve Güvenlik > Kamera.
- Ekran kaydı izni (sonraki sürümdeki mss kaydedici için) aynı yerde "Ekran Kaydı".
- XP-Pen sürücüsünü kurun, Erişilebilirlik ve Giriş İzleme izinlerini verin; sürücü yoksa sadece fare olayları gelir.
- Paketlenince (py2app/PyInstaller) Info.plist'e `NSCameraUsageDescription` eklenmeli.

## Windows (geliştirme makinesi)

- XP-Pen sürücüsünde "Windows Ink" açık olmalı; Qt 6 kalem verisini WM_POINTER üzerinden alır.
- Windows Ink kapalıysa alternatif: `$env:QT_QPA_PLATFORM = "windows:nowmpointer"` (WinTab yolu).
- Ekran ölçeği %125+ ise pencere 1920x1080'den küçük başlar; bölgeler ızgarayla orantılı küçülür.
- Kamera önce DirectShow ile, açılmazsa varsayılan arka uçla (MSMF) denenir.

## Oturum çıktıları

`oturum/<tarih-saat>/<soruId>_<nn>.png` — soru değişirken tuval boş değilse kaydedilir.

## Bu sürümde taslak olan kısımlar

Kayıt düğmesi (NullRecorder + rozet), Keras tanıma, Yazı ve Şekil araçları.
