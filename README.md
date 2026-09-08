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
Sayfa başına tek soru; "Sıradaki soru →" (N) ve "← Önceki soru" (P) ile gezilir. Soru değişince metin harf harf
belirir, son harfler solarak gelir (varsayılan 40 ms/harf; ⚙ Ayarlar > "Soru yazma hızı", 0 = kapalı); tıklayınca
tamamlanır. İpucu kartları blur veya redakte ile gizlidir, tıklanmadan açılmaz; açılırken bulanıklık 300 ms'de çözülür.

⚙ Ayarlar: yazı tipi dosyası (.ttf/.otf; soru, seçenekler ve ipucu kartlarına uygulanır), logo dosyası (sol üst; yoksa
"MM" monogramı), kamera seçimi ("Kameraları tara" kare veren cihazları listeler, seçim kalıcıdır), soru yazma hızı,
yeşil perde (kaldır aç/kapat, tonun otomatik ölçümü) ve tahtadaki yazısal öğelerin görünürlüğü: ipucu kontrolleri (1/3 ◀ ▶ Blur Redakte),
"AKILLI İPUÇLARI" başlığı, durum satırı, kamera etiketi, marka plakası, "gizle" bağlantısı, soru numarası.

Araçlar: kalem (5 kalınlık: 1/2/4/8/12 px), silgi, lazer (izi 1,5 sn'de sönerek kaybolur), yazı (tıkla, yaz,
Enter ile tahtaya işle, Esc iptal; punto kalınlık kademesine göre), şekil (sürükle; Şekil düğmesine tekrar basınca
dikdörtgen → elips → üçgen → çizgi), Tıkla (6). Çizim araçlarında her basış tahtaya gider; mürekkep soru ve ipucu kartlarının üstünde, sadece webcam'in
altında görünür; kartı açmak,
kamerayı değiştirmek veya düğmelere basmak için Tıkla aracına geçilir (ya da klavye: Enter, H, ←/→).
İmleç araca göre ikon: renkli kurşun kalem (ucunda çizgi kalınlığı), silme alanı kadar silgi bloğu, kırmızı lazer
noktası; tahtanın ve bölgelerin her yerinde geçerli.

Webcam: perde pikselleri saydam olur, kişi tahtanın ve çizimlerin üstüne biner. Perdeyi kaldırma ⚙ Ayarlar'dan
açılıp kapanır (kameraya tıklamak değiştirmez). Yeşil perde kamera karesinin
kenarlarından otomatik ölçülür (yeşilimsi ve doygunsa), böylece #00ff3c olmayan
gerçek perdeler de temizlenir; kamera yokken sadece kısa bir durum yazısı görünür.
"⧉ Düzen" (L) modunda bölgeler OBS gibi taşınır/boyutlandırılır, 12x10 ızgaraya yapışır, `duzen.json`'a kaydedilir.
Normal kullanımda çerçeve ve bölge çizgisi yoktur; sadece düzen modunda görünür.

Ekran çerçevesi: tüm çalışma alanını saran 26 px koyu bant, üstüne çizilemez; "Matematiğin Mantığı" plakası üst
ortada, sunucu adı (varsayılan "Koray Varol", el yazısı fontu) webcam'in üstünde. İkisi de ⚙ Ayarlar'dan değişir
veya kapatılır. Logo alanı sonraki sürümde.

## Kısayollar

1-6 araçlar (6 = Tıkla) · Ctrl+Z geri al · Ctrl+Shift+X temizle · N sıradaki · P önceki · Space işle/tamamla · R kayıt ·
H soruyu gizle/göster · ←/→ ipucu · Enter ipucunu aç · L düzen · F11 tam ekran · Esc çık

## Soru şablonu ve PDF aktarımı

`sorular_sablon.xlsx` sütunları: `id, konu, sinif, soru, ipucu1, ipucu2, ipucu3, cevap` (zorunlu) ve
`ipucu4, a, b, c, d, gorsel` (isteğe bağlı). `gorsel` xlsx klasörüne göre göreli yol olabilir.

Yatay soru PDF'ini (sayfa başına 1 soru + AKILLI İPUÇLARI kartları) aktarmak için:

    python -m matematigin_mantigi.pdf_import "ornek.pdf" --cikti sorular_sablon.xlsx --gorsel sorular_gorsel

Soru metni, A–D seçenekleri, 3–4 ipucu ve şekiller (`sorular_gorsel/SNN.png`) alınır; `konu` ve `cevap` boş
kalır, Excel'de doldurulur. `pymupdf` gerekir (`pip install pymupdf`).

## macOS paketleme (.app)

Mac'te proje kökünde:

    bash mac/build_mac.sh

Betik `.venv` kurar, tüm kütüphaneleri (`PyQt6, opencv-python, numpy, openpyxl, pymupdf, pytest, pyinstaller`)
yükler, testleri koşar ve `dist/Matematiğin Mantığı.app` üretir. Kamera, mikrofon ve ekran kaydı izin metinleri
(`NSCameraUsageDescription` vb.) `mac/matematigin_mantigi.spec` içinde gömülüdür; ilk açılışta macOS izin sorar.
İmzasız uygulama için ilk açılış: sağ tık > Aç (veya `xattr -dr com.apple.quarantine "dist/Matematiğin Mantığı.app"`).

Paketlenmiş uygulama verilerini `~/Documents/Matematiğin Mantığı/` altında tutar: ilk açılışta `sorular_sablon.xlsx`
ve `sorular_gorsel/` oraya kopyalanır; `oturum/` (kayıtlar, PNG'ler) ve `duzen.json` da orada oluşur. Soruları
o klasördeki Excel'de düzenleyin.

Mac elinizde değilse: depoyu GitHub'a gönderin, Actions > "macOS paketi" > Run workflow; Apple Silicon runner
`bash mac/build_mac.sh` çalıştırır ve `Matematigin-Mantigi-macOS.zip` artifact'ini üretir (`.github/workflows/mac.yml`).
Homebrew Python için: `brew install python@3.12` sonra `PYTHON=python3.12 bash mac/build_mac.sh`.
Logo hazır olunca `mac/icon.icns` ekleyip spec'teki `icon` alanına yazın.

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

## Kayıt

KAYIT düğmesi (R) tahtayı (araç çubuğu hariç) `mss` ile yakalar, `ffmpeg` (imageio-ffmpeg ile gelir, ayrıca
kurulum gerekmez) H.264 MP4 yazar: `oturum/<tarih-saat>/kayit_<saat>.mp4`. Varsayılan 60 fps ve 2K (1440p'ye
ölçeklenir); ⚙ Ayarlar > Kayıt'tan 30/60 fps, Doğal/1080p/2K/4K ve mikrofon ("Ses aygıtlarını listele": Windows
dshow, macOS avfoundation) seçilir. Süre araç çubuğundaki DURDUR düğmesinin altında sayar; tahtadaki
"KAYIT · 00:00" rozeti varsayılan kapalıdır (kayda girer), Görünürlük'ten açılabilir.
Kodlayıcı otomatik seçilir: macOS'ta VideoToolbox, Windows'ta NVENC/QSV/AMF, yoksa libx264 (ultrafast). Yakalama ayrı iş
parçacığında koşar; yakalama fps'nin altında kalırsa kareler çoğaltılır, video süresi her zaman gerçek zamanla aynıdır.
Durdurunca durum satırı gerçek yakalama hızını yazar (Windows'ta GDI ~30 kare/sn ile sınırlar; macOS CoreGraphics daha hızlıdır).
macOS'ta ilk kayıtta "Ekran Kaydı" izni istenir (Sistem Ayarları > Gizlilik ve Güvenlik); izin verilmezse kare siyah gelir.

## Bu sürümde taslak olan kısımlar

Keras tanıma.
