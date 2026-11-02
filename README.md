# Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu)

## Çalıştırma

    python -m pip install -e ".[dev,pdf]" -c constraints.txt
    python -m matematigin_mantigi              # kamera 0, ./sorular_sablon.xlsx, ./duzen.json
    python -m matematigin_mantigi --kamera 1
    python -m matematigin_mantigi --kamera-yok --sorular C:\yol\sorular.xlsx

Windows PowerShell'de önce `$env:PYTHONUTF8 = "1"`.

## Testler

    python -m pytest -q          # başsız (QT_QPA_PLATFORM=offscreen), kamera ve tablet gerekmez

## Tahta

Tahta, 16:9 sahnenin çerçeve bandı içinde kalan düz beyaz tuvalidir; her yerine çizilir (bant ile sahne dışındaki
koyu kenarlara çizilemez). Üstünde üç şeffaf bölge: sol üstte soru (kırmızı
numara, kalın metin, görsel, A) B) C) D)), sağ üstte "AKILLI İPUÇLARI" kartları, sağ alt köşede çerçevesiz webcam.
Sayfa başına tek soru; "Sıradaki soru →" (N) ve "← Önceki soru" (P) ile gezilir. Soru değişince metin harf harf
belirir, son harfler solarak gelir (varsayılan 40 ms/harf; ⚙ Ayarlar > "Soru yazma hızı", 0 = kapalı); tıklayınca
tamamlanır. İpucu kartları blur veya redakte ile gizlidir, tıklanmadan açılmaz; açılırken bulanıklık 300 ms'de çözülür.

⚙ Ayarlar: yazı tipi dosyası (.ttf/.otf; soru, seçenekler ve ipucu kartlarına uygulanır), logo dosyası (sol üst; yoksa
"MM" monogramı) ve boyutu, kamera seçimi ("Kameraları tara" kare veren cihazları listeler, seçim kalıcıdır), soru yazma hızı,
yeşil perde (kaldır aç/kapat, tonun otomatik ölçümü), **Tahta**: "Tahtayı 16:9 oranında tut" (açıkken tahta pencerede
ortalanır, artan yer koyu bant olur ve kayıt tam 16:9 çıkar; kapalıyken tüm pencereyi kaplar) ve **çerçeve stili**
(Klasik / HUD, aşağıda) — ve tahtadaki öğelerin görünürlüğü: ipucu kontrolleri (1/3 ◀ ▶ Blur Redakte),
"AKILLI İPUÇLARI" başlığı, durum satırı, kamera etiketi, marka plakası, "gizle" bağlantısı, soru numarası, ekran
çerçevesi, çerçeve sunucu/marka bantları, sunucu adı, logo, kayıt rozeti, soru/ipucu/webcam panelleri.

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
"⧉ Düzen" (L) modunda bölgeler OBS gibi serbestçe taşınır/boyutlandırılır (8 kenar/köşe tutamağı); Ctrl basılı
tutulursa 12x10 ızgaraya yapışır. Bölgelerin yanı sıra tahtanın **öğeleri** de (marka plakası, logo, sunucu adı,
kayıt rozeti, durum satırı) sürüklenir — bunlar bandın üstünde de durabilir, boyutları içeriklerinden gelir,
sahnenin dışına çıkamazlar. Her bölge ve öğenin köşesinde bir **göz düğmesi** (👁) çıkar: tek tıkla o panel ya da
öğe tamamen gizlenir/geri gelir (⚙ Ayarlar > Görünürlük ile aynı anahtarlar). Düzen çubuğundaki **yazı boyutu
kaydırıcısı** tahtadaki tüm yazıları %70–%160 arasında ölçekler (araç çubuğu ve pencereler etkilenmez; logo
monogramının kendi boyutu ⚙ Ayarlar'dadır). Bölge ölçüleri ve öğe konumları `duzen.json`'a; görünürlükler ile yazı
ölçeği diğer ayarlarla birlikte kaydedilir; düzen çubuğundaki "Sıfırla" bölge ve öğe konumlarını varsayılana döndürür.
Normal kullanımda bölge çizgisi yoktur; sadece düzen modunda görünür.

Ekran çerçevesi: 16:9 sahneyi saran bant (tüm pencereyi değil), üstüne çizilemez. İki stil var (⚙ Ayarlar > Tahta >
Çerçeve stili): **Klasik (koyu bant)** 26 px degradeli koyu bant, turuncu iç çizgi ve köşe süsleri; "Matematiğin
Mantığı" plakası üst ortada, sunucu adı (varsayılan "Koray Varol", el yazısı fontu) webcam'in üstünde. **HUD
(teknik çizim)** 52 px beyaz bant üstünde lacivert raylar, cetvel şeridi ve köşe motifleri; sunucu adı ile markayı
sağ üst/sağ alt yazı bantlarına KENDİSİ yazar, bu yüzden eski plaka ve el yazısı gizlenir ("Çerçeve sunucu/marka
bantları" kapatılırsa eski düzene dönülür). Logo sol üst köşede, sahnenin üst bandına asılıdır (kayda girer);
dosyası ve boyutu ⚙ Ayarlar'dan, konumu düzen modundan değişir.

## Kısayollar

1-6 araçlar (6 = Tıkla) · Ctrl+Z geri al · Ctrl+Shift+X temizle · N sıradaki · P önceki · Space işle/tamamla · R kayıt ·
H soruyu gizle/göster · ←/→ ipucu · Enter ipucunu aç · L düzen · F11 tam ekran · Esc çık (düzen modundaysa
önce düzenden, sonra tam ekrandan)

## Soru şablonu ve PDF aktarımı

`sorular_sablon.xlsx` sütunları: `id, konu, sinif, soru, ipucu1, ipucu2, ipucu3, cevap` (zorunlu) ve
`ipucu4, a, b, c, d, gorsel` (isteğe bağlı). `gorsel` xlsx klasörüne göre göreli yol olabilir.

Yatay soru PDF'ini (sayfa başına 1 soru + AKILLI İPUÇLARI kartları) aktarmak için:

    python -m matematigin_mantigi.pdf_import "ornek.pdf" --cikti sorular_sablon.xlsx --gorsel sorular_gorsel

Soru metni, A–D seçenekleri, 3–4 ipucu ve şekiller (`sorular_gorsel/SNN.png`) alınır; `konu` ve `cevap` boş
kalır, Excel'de doldurulur. `pymupdf` gerekir (`pip install pymupdf`).

Excel'i elle açmadan: sol araç çubuğundaki **✎ Sorular** tuşu soru editörünü açar. Soru ekle/sil, `id/konu/sınıf`,
soru metni, A–D şıkları, cevap ve 4 ipucu doldur, **Resim seç…** ile görsel seç (otomatik `sorular_gorsel/` altına
kopyalanır). **Kaydet** xlsx'e yazar ve uygulamayı yeniden başlatmadan tazeler. `--sorular` verilmezse veri
klasöründeki `sorular_sablon.xlsx` düzenlenir.

Kaydet önce dosyanın o anki hâlini yanına `sorular_sablon.xlsx.bak` olarak kopyalar, yeni sürümü geçici bir dosyaya
yazar ve ancak yazım tamamlanınca yerine koyar: disk dolsa, USB çıkarılsa ya da dosya Excel'de açık olsa da soru
dosyası yarım kalmaz (mesaj dosyanın değişmediğini söyler). Bir önceki sürüme dönmek için uygulama kapalıyken `.bak`
dosyasının adını `sorular_sablon.xlsx` yapın. Soru dosyası okunamazsa uygulama dosya adını ve sebebi söyleyip örnek
sorularla açılır; editör böyle bir dosyanın üzerine yazmaz (önce düzeltilmeli ya da klasörden kaldırılmalı).
`duzen.json` da aynı yolla (geçici dosya + yerine koyma) yazılır.

## Hatalar ve uyarılar

Beklenmeyen bir hata uygulamayı ve süren kaydı durdurmaz. Ayrıntısı (zaman, sürüm, traceback) veri klasöründeki
`hatalar.log` dosyasına yazılır: geliştirmede çalışma klasörü, paketlenmiş uygulamada `~/Documents/Matematiğin
Mantığı/`. Aynı hata bir kez tam, sonra yalnız 10., 100. … tekrarında tek satır olarak düşer. Hata bildirirken bu
dosyayı ekleyin. Uyarı kutusu kayıt sürerken (kayıt kaydedilirken de) açılmaz, çünkü kayda girerdi: araç çubuğunun
kırmızı şeridinde "⚠ … — ayrıntı kayıt bitince" yazar, kutu kayıt bitince açılır.

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

## macOS izinleri (.app)

Kamera, mikrofon, ekran kaydı ve Documents klasörü izinleri ilk kullanımda sorulur; uygulama kamera açılana kadar
2 sn arayla 15 kez yeniden dener, izin verildikten sonra görüntü kendiliğinden gelir. İzin penceresi hiç çıkmazsa
(imzasız .app) Terminal'de:

    codesign --force --deep --sign - "/Applications/Matematiğin Mantığı.app" && xattr -dr com.apple.quarantine "/Applications/Matematiğin Mantığı.app"
    tccutil reset Camera com.matematiginmantigi.tahta; tccutil reset Microphone com.matematiginmantigi.tahta; tccutil reset ScreenCapture com.matematiginmantigi.tahta
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"

Ekran kaydı izni verildikten sonra uygulamayı yeniden başlat (macOS bunu ister). Birden fazla kamera varsa
(ör. OBS Virtual Camera 0, FaceTime 1) ⚙ Ayarlar > Kamera > "Kameraları tara" gerçek adlarıyla listeler.

## Windows paketi (.exe)

Yerelde: `powershell -ExecutionPolicy Bypass -File windows\build_win.ps1` — `.venv` kurar, testleri koşar,
`dist\Matematigin Mantigi\Matematigin Mantigi.exe` (tek klasör) üretir. ffmpeg ve PortAudio (ses) ikilileri pakete girer.

## Otomatik yapı ve release (GitHub Actions)

`main`'e her push'ta `.github/workflows/release.yml` **Windows `.exe`** ve **macOS `.app`** derler, ikisini bir
GitHub Release'e (`build-<numara>`) ekler. Elle: Actions > **Release** > Run workflow (ya da `gh workflow run release.yml`).
Bir daldan elle çalıştırılırsa yalnız derler, Release yayınlamaz (dalı main'e almadan önce iki platformu denemek için).
Yalnız Mac için `.github/workflows/mac.yml` de var. İndirdikten sonra Windows: klasörü kopyala, `.exe` çalıştır;
macOS: `.app`'i sağ tık > Aç (imzasız).

Kütüphane sürümleri `constraints.txt` dosyasında sabittir; derleme betikleri ve CI `pip install -c constraints.txt`
ile kurar. Yerelde de aynısı: `python -m pip install -e ".[dev,pdf]" -c constraints.txt`. Sürüm yükseltmek için
dosyayı değiştir, testleri koş, dalda iki platformu derle, sonra main'e al.

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
kurulum gerekmez) H.264 MP4 yazar: `oturum/<tarih-saat>/kayit_<saat>.mp4`. Kayda giren dikdörtgen 16:9 **sahnenin
tamamı**dır: oran kilidi açıkken kenarlardaki koyu bantlar kayda GİRMEZ — bu yüzden tahtada görünür bırakılırlar,
bandın üstüne düşen bir çizgi ya da öğe videoda olmaz. Varsayılan 60 fps ve 2K (1440p'ye
ölçeklenir); ⚙ Ayarlar > Kayıt'tan 30/60 fps, Doğal/1080p/2K/4K ve mikrofon ("Ses aygıtlarını listele": PortAudio
aygıtları — Windows'ta en iyi host API, macOS'ta CoreAudio) seçilir. Süre araç çubuğundaki DURDUR düğmesinin altında sayar; tahtadaki
"KAYIT · 00:00" rozeti varsayılan kapalıdır (kayda girer), Görünürlük'ten açılabilir.
Kodlayıcı otomatik seçilir: macOS'ta VideoToolbox, Windows'ta NVENC/QSV/AMF, yoksa libx264 (ultrafast). Yakalama ayrı iş
parçacığında koşar; yakalama fps'nin altında kalırsa kareler çoğaltılır, video süresi her zaman gerçek zamanla aynıdır.
Mikrofon ffmpeg'e değil, uygulama içinde PortAudio (sounddevice) ile alınır: ffmpeg'in avfoundation girişi tek
tampon tutar ve video karesi geciktiğinde onu düşürür (cızırtı, birikince kayma). PortAudio geri çağrısı örnekleri
dakikalarca yer olan bir kuyruğa koyar, ayrı iş parçacığı WAV yazar; ilk örneğin zamanı ölçülür. Durdurunca ffmpeg
videoyu kopyalayıp sesi ölçülen farkla hizalar (48 kHz AAC 160 kb/s); ara `.video.mp4`/`.wav` dosyaları yalnız
birleşik dosyanın süresi videonunkiyle aynı ölçülünce silinir (süre ffmpeg'in dosya başlığından okunur, 60 dakikalık
derste de saniyenin altında). 10 dakikadan uzun kayıtlarda mikrofon saati kayması da (en çok 1000 ppm; ilk ile son
örnek arasında ölçülür) `asetrate` ile düzeltilir; mikrofon durdurmadan önce sustuysa düzeltme yapılmaz, eksik ses
kayma sanılıp derse yayılmaz. Birleştirme videoyu asla kısaltmaz: mikrofon kayıt sırasında kesilirse (kablo çekildi,
Bluetooth/AirPods koptu) ya da ses dosyası yazılamazsa (disk dolu) eksik ses sessizlikle doldurulur, video tam
uzunlukta kalır ve durum satırı uyarır ("UYARI: Mikrofon kayıt sırasında kesildi (20:15. dakikadan sonra ses yok)",
"UYARI: Ses dosyası yazılamadı: …"). Birleşik dosya yine de videodan kısa çıkarsa, süresi ölçülemezse ya da
birleştirme düşerse (yarım birleşik dosya silinir) ham video ve ses silinmez, son ada taşınmaz; "Kayıt hatası" penceresi
ne olduğunu ve dosyaların yerini durumlarıyla yazar ("… (video 42:10)", "… (ses sağlam, 42:11)"). ffmpeg kayıt
sırasında durursa (kodlayıcı çöktü, bellek ya da disk bitti) kayıt hemen kapanır, pencere ffmpeg'in hangi dakikada
durduğunu, videonun açılıp açılmadığını ve sağlam sesin yerini yazar; ham dosyalar silinmez (video açılıyorsa ses yine
birleştirilir). ffmpeg'in çıktısı `kayit_<saat>.log` dosyasına gider.
Durdurma birkaç saniye (uzun derste onlarca saniye) sürebilir: arayüz donmaz,
kayıt düğmesinin üstünde kırmızı "Kayıt kaydediliyor…" şeridi görünür ve kayıt bitene kadar ne düğme ne R yeni kayıt
başlatır (kapanan dersin dosyaları yenisine karışmasın). Şerit araç çubuğunda olduğu için kayda girmez (tahtadaki
durum satırı ve rozet girer). Kayıt sürerken pencere kapatılırsa (pencere düğmesi ya da ⌘Q) önce "Kayıt sürüyor,
durdurulup çıkılsın mı?" diye sorulur (varsayılan: kayda devam); "Durdur ve çık" kaydı arka planda kaydettirir, şerit
"Kayıt kaydediliyor… bitince pencere kapanacak" der ve kayıt bitince (varsa hata gösterildikten sonra) pencere kendisi
kapanır. Kayıt zaten kaydediliyorsa soru sorulmadan aynı bekleme olur. ffmpeg ancak ilerlemiyorsa öldürülür
(borudan 10 sn boyunca tek kare okumazsa ya da durdurduktan sonra 60 sn boyunca dosyaya hiç yazmazsa); yavaş ama
okuyan ffmpeg beklenir. Öldürülen ffmpeg dosyayı bitiremediği için video büyük olasılıkla hiç açılmaz: kayıt "ffmpeg
yanıt vermedi; kayıt zorla kapatıldı" hatasıyla biter, birleştirme denenmez, ara dosyalar silinmez ve pencere
yerlerini yazar. Kodlayıcı gerçek zamana yetişemezse (yazılan kare duvar saatinin gerisinde) durdurmada birikmiş
kareler yazılmaz (2 sn'den azsa yazılır): video düğmeye basılan andan erken biter, birleşik dosyada ses yine sonuna
dek sürer (son kare ekranda kalır) ve durum satırı uyarır ("UYARI: Görüntü kodlayıcısı kayda yetişemedi: …"). Ara
video moov'u sona yazar (`+faststart` yok: kapanışta 7 GB'lık dosyayı yeniden yazmak dakikalar sürebiliyordu);
faststart yalnız birleşik dosyada. Mikrofon videoyla aynı anda, ayrı iş parçacığında kapanır: ses sürücüsü akışı
kapatırken takılırsa (USB mikrofon çekildi) 5 sn sonra o ana dek gelen sesle devam edilir ve durum satırı uyarır;
mikrofon 25 sn içinde hiç kapanmazsa video sessiz kaydedilir, pencere ses dosyasının yerini yazar. Mikrofon
açılamazsa kayıt sessiz sürer, geride ses dosyası ya da iş parçacığı kalmaz. Kayıt başlatılamazsa (ffmpeg yok, kayıt
klasörü ya da dosyası açılamıyor: disk dolu, izin yok; beklenmeyen bir hata da) sebebi bir pencerede yazar, açılmış
ffmpeg ve mikrofon kapatılır, araç çubuğu "KAYIT"a döner. Kayıt hataları, ses uyarıları ve kayıt yolunda yakalanan
istisnalar veri klasöründeki `hatalar.log`'a da yazılır. Windows'ta ffmpeg çağrıları konsol penceresi açmaz.
Durdurunca durum satırı gerçek yakalama hızını yazar (Windows'ta GDI ~30 kare/sn ile sınırlar; macOS CoreGraphics daha hızlıdır).
macOS'ta ilk kayıtta "Ekran Kaydı" izni istenir (Sistem Ayarları > Gizlilik ve Güvenlik); izin verilmezse kare siyah gelir.

## Bu sürümde taslak olan kısımlar

Keras tanıma.
