# Sağlamlaştırma: kayıt asla sessizce kaybolmasın

Tarih: 2026-09-23 · Dal: `saglamlastirma` · Kaynak: 61 ajanlık alt sistem denetimi + tüm depoyu okuyan kıdemli inceleme (f1d586f)

## Amaç

Uygulama başarılı akışta sağlam (341 test yeşil), ama kayıt sırasında bir şey ters gidince neredeyse hiçbir yol öğretmene haber vermiyor. Bu paketin tek ölçütü:

> **Bir ders kaydı hiçbir koşulda sessizce kaybolmaz, kısalmaz, sessizleşmez ya da yanlış bölgeyi kaydetmez. Bir şey ters giderse öğretmen bunu kayıt sırasında, kayda girmeyen bir yerde görür.**

İkincil amaç: denetimin bulduğu kalan kusurların (soru sistemi, tuval, kamera, düzen, paketleme) tamamını kapatmak ve çerçevesiz seçeneği eklemek.

Doğrulanmış 41 kusur + kıdemli incelemenin ek küçük bulguları (42-53) aşağıda numarasıyla geçer. Her numara bir regresyon testine bağlanır.

## Kullanıcı kararları (2026-09-23)

| Konu | Karar |
|---|---|
| Kapsam | Hepsi: 41 + ek küçükler + çerçevesiz seçenek |
| Kayıt sırasında pencere | F11 ve Esc (tam ekran çıkışı) kilitli. Pencere yine de taşınır/boyutlanır/tam ekran değişirse kayıt güvenle durdurulur ve büyük uyarı çıkar. |
| Mikrofon | Kayıt başında mikrofon seçilmemişse, bulunamazsa ya da açılamazsa "Sessiz devam edilsin mi?" sorulur. Kayıt sırasında ses kesilirse araç çubuğunda kırmızı uyarı. |
| Uyku | Kayıt sürerken sistem ve ekran uykusu engellenir. |
| Editör / Ayarlar kayıt sırasında | Açılabilir, önce "bu pencere kayda girer" uyarısı. |
| Çerçeve | Ayarlar'daki listede Klasik / HUD / Çerçevesiz; düzen çubuğunda "👁 Çerçeve" düğmesi; ikisi aynı `frame` ayarını değiştirir. |

## Temel ilke: uyarılar kayda girmeyen yerde

Kayıt yalnız 16:9 sahneyi yakalar. Araç çubuğu (88 px, sahnenin dışında) ve modal pencereler dışındaki her uyarı **araç çubuğunda** gösterilir: kayıt düğmesinin üstünde kırmızı bir uyarı şeridi (`ToolBar.set_alert(text | None)`). Tahtadaki durum satırı ve rozet uyarı taşımaz, çünkü kayda girer. Kayıt bittikten sonraki sonuç (başarı/uyarı) modal `QMessageBox` ile verilir; o an kayıt yoktur.

## Tasarım

### A. Kaydedici durum makinesi — #2

`MssFfmpegRecorder` açık bir duruma geçer: `IDLE → RECORDING → FINALIZING → IDLE`, `threading.Lock` altında.

- `start()` yalnız `IDLE`'da çalışır; `FINALIZING`'de `RecorderError("Önceki kayıt hâlâ kaydediliyor")` fırlatır.
- Her kayıt kendi `_Session` nesnesini taşır (video/wav/log yolu, son yol, `video_t0`, ses sonucu). `stop()` işini bu nesne üzerinden yapar; `start()` yeni bir nesne kurar, eskisine dokunamaz.
- `is_recording` yerine arayüz `state`'e bakar. `MainWindow.toggle_recording` ve R kısayolu `FINALIZING`'de hiçbir şey yapmaz, durum satırına değil araç çubuğuna "Kayıt kaydediliyor…" yazar.

### B. Birleştirme asla videoyu kısaltmaz — #1

- `mux_args` ses zincirine `apad` eklenir, `-shortest` kalır: eksik ses sessizlikle doldurulur, dosya her zaman videonun uzunluğunda biter.
- `_mux` sonrası çıktının süresi `ffprobe` ile ölçülür. Video süresinden 1 sn'den fazla kısaysa ara dosyalar **silinmez**, hata raporlanır.
- Ses süresi videodan 2 sn'den fazla kısaysa `audio_error = "Mikrofon kayıt sırasında kesildi (X. dakikadan sonra ses yok)"`.

### C. Çökmeye dayanıklı ara dosya ve kurtarma — #8

- Ara video parçalı MP4 olarak yazılır (`-movflags +frag_keyframe+empty_moov+default_base_moof`, `+faststart` yok). Elektrik kesilse de o ana kadarki kısım oynatılabilir. `+faststart` yalnız son birleştirmede yapılır.
- Açılışta kayıt klasörü taranır: son `.mp4`'ü olmayan `kayit_*.video.mp4` (± `.wav`) çiftleri için "Tamamlanmamış kayıt bulundu, kurtarılsın mı?" sorulur; evet → birleştirilir, hayır → dokunulmaz.
- Başlarken boş disk kontrol edilir (`shutil.disk_usage`): bir saatlik kayıt + birleştirme için ~15 GB'tan azsa kaç dakikalık yer olduğu söylenir ve sorulur. Kayıt sırasında 2 GB altı → kırmızı uyarı; 500 MB altı → kayıt güvenle durdurulur.
- Dosya adları çakışmaz: aynı saniyede ikinci kayıt `-2` son eki alır (#37).

### D. Kayıt sağlık gözetimi — #7, #52, #42

Kaydedici bir `health()` özeti verir: son başarılı yakalamanın yaşı, yakalama hızı (kare/sn), ses örneği artıyor mu, kodlayıcı ne kadar geride. `MainWindow` saniyelik tikte bakar:

- Yakalama 2 sn boyunca başarısız → kayıt güvenle durdurulur, modal uyarı ("Ekran yakalanamıyor: ekran kilitlendi ya da uyku"). Donmuş kare yazılmaz.
- Ses örnekleri 2 sn artmıyorsa → kırmızı uyarı "Mikrofon ses göndermiyor"; video sürer, eksik ses sessizlikle dolar.
- Yakalama hızı hedefin %90'ının altındaysa araç çubuğunda "~32 kare/sn" gibi gerçek hız görünür; kayıt sonunda raporlanır.
- Kodlayıcı birikimi sınırlanır; durdurmada zaman aşımı sahte "boru kapandı" hatası üretmez (#42).

### E. Mikrofon politikası — #6, #43

- PortAudio aygıt listesi okunmadan önce yeniden başlatılır; kayıttan sonra takılan mikrofon görünür.
- Kayıt başında: mikrofon seçilmemişse, kayıtlı mikrofon bulunamazsa ya da açılamazsa **modal soru**: "Mikrofon: <durum>. Sessiz kayda devam edilsin mi?" Bulunamayan mikrofon için başka bir mikrofona sessizce geçilmez; açılan aygıtın adı `AudioResult`'a yazılır ve sonuç mesajında gösterilir.
- Mikrofon açılamazsa yazıcı iş parçacığı ve WAV sızmaz (#43).
- Ses tamamen sessizse (tepe değer ~0, ör. macOS mikrofon izni kapalı) kayıt sırasında kırmızı uyarı, sonda modal uyarı ve izin yolu: Sistem Ayarları › Gizlilik ve Güvenlik › Mikrofon.

### F. Kayıt sırasında pencere kilidi — #5, #11

- F11 ve tam ekranda Esc, kayıt sürerken çalışmaz; araç çubuğunda "Kayıt sürerken pencere değiştirilemez".
- `MainWindow` taşınma/boyut/durum değişikliklerini izler; kayıt dikdörtgeni değiştiyse kayıt güvenle durdurulur ve modal uyarı çıkar. (macOS yeşil düğmesi de bu yoldan yakalanır.)
- Ayarlar'daki oran kilidi kayıt sırasında uygulanmaz, kayıt bitince uygulanır.
- Kapatma: kayıt sürerken "Kayıt sürüyor, durdurulup çıkılsın mı?"; evet → kayıt arka planda kaydedilir, bittiğinde pencere kendisi kapanır. 60 sn'lik kesme kalkar; kullanıcı beklerken araç çubuğunda ilerleme görür.

### G. Uyku engelleme — #12

`core/keep_awake.py`: kayıt başında açılır, bitince kapanır. macOS: `caffeinate -dims -w <pid>` alt süreci. Windows: `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)`. Başarısızlık kaydı engellemez, uyarı verir.

### H. Uygulama çapında hata yakalayıcı — #3

`app.py` bir `sys.excepthook` kurar: hata veri klasöründeki `hatalar.log`'a yazılır, modal olmayan bir uyarı gösterilir, uygulama ve kayıt **devam eder** (PyQt6'nın qFatal ile kapatması engellenir). Buna ek olarak bilinen dosya yazan yuvalar kendi hatalarını yakalayıp anlamlı mesaj verir: soru editörü Kaydet, anlık görüntü kaydı, düzen kaydı, kayıt başlatma (`OSError` dahil), kamera iş parçacığı `run()`.

### I. Soru sistemi — #4, #16, #17, #28, #29, #27

- Soru dosyası okunamazsa (bozuk, boş, kilitli, her türlü hata) açılışta dosya adı ve sebep gösterilir, örnek sorularla açılır ve **editör o dosyaya yazamaz** ("Önce soru dosyasını düzeltin"). (#4, #17)
- Editör yazımı: önce `.bak` yedeği, sonra geçici dosyaya yazıp `os.replace` (yarıda kalan yazım dosyayı bozmaz). Mevcut çalışma kitabı açılıp yalnız bilinen sütunlar yazılır; ek sütunlar, diğer sayfalar ve biçim korunur. (#29)
- Kaydet hataları (Excel'de açık, izin) mesajla gösterilir, pencere açık kalır, düzenlemeler kaybolmaz. Yapıştırılan kontrol karakterleri temizlenir. Sınıf alanı yalnız rakam kabul eder. (#3)
- Kaydet sonrası tahtaya yükleyicinin normalleştirdiği veri gönderilir: boş şık ve ipuçları elenir, resim yolları mutlak olur. (#16)
- Hücre değerleri Türkçe gösterilir: `2,5`, `%50`; tarih hücresi için "hücreyi Metin yapın" uyarısı. (#28)
- Çift tıklanan ipucu kartı gerçekten gizli kalır; çift tık tek geçiş sayılır. (#27)

### J. Tuval ve kalem — #18, #19, #20, #30, #31, #32, #33, #41

- Geri Al, geri yüklenen görüntüyü güncel tahta boyutuna büyütür (#18).
- Soru değişirken açık yazı kutusu önce işlenir (#19); tahta temizlenirken geri alma geçmişi sıfırlanır (#20).
- Kapanışta ve soru yeniden yüklenirken mevcut sorunun tahtası kaydedilir; "Otomatik kaydet: her 30 sn" gerçekten çalışır (#30).
- Kalem ayarları uygulanır (#31): basınç eğrisi (0 yumuşak … 100 sert → üs), yumuşatma (nokta ortalaması), en az/en çok kalınlık (piksel sınırı), uç tipi: **Yuvarlak** bugünkü çizgi; **Keçeli** düz kesik uç, basınca yarı duyarlı, %85 opaklık; **Tebeşir** tam opak ama rastgele boşluklu noktalı doku (tahta tebeşiri izi). Henüz var olmayan özellikler (matematik tanıma, şekil düzeltme, şablon eşleme) "yakında" diye kilitli gösterilir; sessizce yok sayılmaz.
- Kaçan kalem-kaldırma olayı: hareket olayında düğme basılı değilse çizgi biter (#32). Yazı kutusu ipucu kartlarının üstünde görünür (#33). Tahta boyutu değişince mürekkep aynı oranda ölçeklenir (#41).

### K. Kamera — #13, #14, #15, #21, #22, #44

- Kamera ad ile saklanır; açılışta ad dizine çözülür. Seçilen kamera yoksa **başka kamera gösterilmez**; panelde "Seçilen kamera bulunamadı: <ad>" yazar ve deneme sürer (#13).
- Akış koparsa iş parçacığı kendini yeniden bağlamaya çalışır; donuk kare yerine "Kamera bekleniyor…" gösterilir (#14).
- "Kameraları tara" kullanımdaki kamerayı açmaz, onu "(kullanımda)" diye listeler (#15).
- macOS'ta ad↔dizin eşlemesi OpenCV'nin kendi sırasıyla (AVFoundation, `uniqueID` sıralı) yapılır: yalnız macOS için `pyobjc-framework-AVFoundation` bağımlılığı. Yoksa "Kamera N (G×Y)" etiketi (#21).
- Kameradan 1280×720 istenir, görüntü panelin fiziksel genişliğine göre küçültülür (#22). İş parçacığı başlamadan gelen durdurma kaybolmaz (#44).

### L. Düzen ve çerçeve — #23, #24, #25, #39, çerçevesiz

- Çerçevesiz seçenek ve düzen çubuğu düğmesi (kararlar tablosu). Çerçevesizken marka plakası görünür ve sürüklenmemişse tahta üstten plaka yüksekliği kadar boşluk bırakır. Kayıt alanı değişmez.
- Göz düğmeleri yalnız bir kez oluşturulur (#23). macOS'ta ızgaraya yapıştırma ⌘ ve Ctrl ile çalışır, ipucu metni "⌘" der (#24). Kenar sahne dışına çekilince yalnız o kenar kırpılır (#25). HUD bandının çizdiği marka/ad için düzen modunda hayalet kutu çıkmaz (#39).

### M. Ayarlar ve pencereler — #26, #38, #46, #51

- Ayarlar'da Enter "Uygula"yı çalıştırır (#26).
- Kayıt sürerken soru editörü ya da Ayarlar açılmak istenirse önce "Bu pencere kayda girer (editör cevapları gösterir). Yine de açılsın mı?" (#38).
- Durum satırı kayıt sonrası tam yol değil yalnız dosya adını gösterir (#46). Rozet gerçek kayıt çözünürlüğünü gösterir (#51).

### N. Kayıt kalitesi ve platform — #9, #10, #34, #45, #47

- macOS Retina: yakalama nominal çözünürlük bayrağı kaldırılarak gerçek pikselle yapılır (1408×792 nokta sahne → 2816×1584 → 2560×1440'a küçültme). Yakalama hızı D'deki göstergeyle izlenir; Mac kontrol listesinde ölçülür (#9).
- Windows paketinde tüm ffmpeg çağrıları `CREATE_NO_WINDOW` ile; konsol penceresi açılmaz (#10).
- Video BT.709 matrisiyle dönüştürülür ve renk etiketleri yazılır (#34).
- Kare kopyaları azaltılır (bellek görünümüyle yazım) (#45). Farklı ölçekli ikinci monitörde fiziksel dikdörtgen doğru hesaplanır (#47).

### O. Paketleme, CI, belgeler — #35, #36, #40, #48, #49, #50, #53

- macOS Documents izni reddedilirse uygulama sessizce kapanmaz: açıklayan mesaj + `~/Movies/Matematiğin Mantığı` yedek klasörü; Info.plist'e `NSDocumentsFolderUsageDescription` (#35).
- Release notu ve README: güncel macOS için "Sistem Ayarları › Gizlilik ve Güvenlik › Yine de Aç" + `xattr` komutu (#36). `LSMinimumSystemVersion` 14.0 (#40).
- `PyQt6>=6.8` (#48). CI kurulumları sabit sürüm listesiyle (`constraints.txt`) (#49). Yalnız belge/grafik değişen push'lar release üretmez (#53). README bayat satırları düzeltilir, tamamlanmamış kayıt kurtarma anlatılır (#50).

## Test stratejisi

- Her madde önce kırmızıya dönen bir testle başlar (TDD). Denetimin `scratchpad/audit` ve `scratchpad/review` altındaki yeniden üretim scriptleri teste dönüştürülür.
- Kaydedici için hata enjeksiyonu donanımı: ölen mikrofon, ölen WAV yazıcısı, kayıt ortasında hata veren yakalayıcı, yavaş birleştirme, öldürülen ffmpeg, sessiz mikrofon, dolu disk.
- Geometri değişmezlik testine çerçevesiz durum eklenir (4 pencere şekli × 3 çerçeve seçeneği).
- `python -m pytest -q` tamamen yeşil; paket hem tam hem dosya dosya.
- Oturum açıkken gerçek kayıt duman testi: 5 dakikalık gerçek kayıt, ffprobe ile çözünürlük/kare hızı/ses süresi, mikrofon çekme senaryosu.

## Mac kontrol listesi (`docs/mac-kontrol-listesi.md`)

Kodla doğrulanamayan, gerçek MacBook + XP-Pen gerektiren adımlar: ilk açılışta izin istemleri (kamera, mikrofon, ekran kaydı, Belgeler); donanım kodlayıcı (`h264_videotoolbox`) kullanılıyor mu; araç çubuğundaki gerçek kare hızı; Retina keskinliği; 60 dakikalık kayıt ve birleştirme süresi; ⌘Q'nun kaydı güvenle kapatması; yeşil düğmeyle tam ekranın kaydı durdurup uyarması; alkış testiyle kamera–ses dudak senkronu; XP-Pen silgi ucu ve basınç; kapak kapatma/uyku.

## Kapsam dışı

- Developer ID imzası ve noterlik (ücretli Apple hesabı gerekir).
- ScreenCaptureKit ile yerel 60 kare/sn yakalama: önce Mac'te ölçülür; gerekirse ayrı proje.
- Kamera–ses gecikme telafisi: önce ölçülür.
- Keras tabanlı tanıma özellikleri (taslak).

## Riskler

- Retina'da 4 kat büyük kareler yakalama hızını düşürebilir → D'deki gösterge ve Mac kontrol listesi bunu görünür kılar; düşükse ayar ile nokta çözünürlüğüne dönülebilir.
- `pyobjc` bağımlılığı paket boyutunu büyütür ve PyInstaller toplama ayarı ister → CI macOS işinde doğrulanır; toplanamazsa etiket geri dönüşü devreye girer.
- Pencere kilidi, kullanıcının kayıt sırasında pencereyi bilerek değiştirmesini de durdurur; bu karar kasıtlı (sessiz yanlış kayıt yerine yüksek sesle durma).
