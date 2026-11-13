# İkinci ekranda kamera önizlemesi: donma incelemesi

## Kanıtın kapsamı

- Kullanıcı netleştirdi: donan kaydedilmiş video değil, **RECORDING sırasında iki canlı kamera görünümü**; ikinci önizleme kapalıyken sorun yok. Olay bsync'e bağlı ev/ofis makinelerinden farklı bir bilgisayarda. PC günlük/medya incelemesi bu nedenle kapsam dışında bırakıldı; hiçbir PC günlüğü, kaydı veya ayarı okunmadı/değiştirilmedi.
- Linux'ta iki ayrı 1920×1080 offscreen Qt ekranı, 1280×720/30 fps sentetik kamera, gerçek `CameraWorker`, gerçek iki kamera görünümü ve gerçek `MssFfmpegRecorder`/ffmpeg ile önceki kaynak (`e1c00d5`) ve düzeltme karşılaştırıldı. Mikrofon yok.
- Yakalama sentetiktir; Windows/MSS görüntü yakalama doğrulaması değildir. Küçük kodlama deneyinde 640×360 video üretilir; iki Qt ekranı ve tam ekran önizleme gerçek boyutlarını korur. Bu, kamera maliyetini zaten doygun olan 1080p kodlayıcıdan ayırır.

## Kök neden

Harici görünüm en büyük fiziksel genişliği ortak kamera işçisine yazıyordu. 320 piksellik tahta kamerası, ikinci ekranda önizleme görünür olunca 1280 piksellik kamera görüntüsünü işlemek zorunda kalıyordu. Aynı görüntü **16 kat piksel** içeriyor. Kaynak boyutundan büyük yapay büyütme yoktu; 1920 genişlik istense bile 1280 kaynakta fiili işlem 1280 idi.

Özellikle float32 HSV maskesi, kenar yumuşatma ve dökülme bastırma pahalı. Dönüşümler zaten işçideydi; GUI'de yeşil perde hesaplanıyor demek yanlış olur. Ancak her görünümde QPainter'ın BGR/alfa dönüşümü ve büyük görüntü ölçeklemesi ayrıca GUI yükü yaratıyordu. İşçinin her kareyi ayrı Qt sinyaliyle panele kuyruğa koyması da yavaş GUI'nin eski kareleri sonradan oynatmasına izin veriyordu.

Kullanıcının bildirimine uyan yeniden üretim **iki canlı kamera görüntüsünün birlikte seyrek güncellenmesidir**, kalıcı GUI kilitlenmesi değil. Kaydedilmiş videonun donduğu iddia edilmiyor. Ayrıca yük altında eski kare kuyruğu ve bu sunucuya özgü kodlayıcı doygunluğu gözlendi. İlk deneylerden birinde büyük önizlemeli yeşil perde işlemi ortalama 2906 ms sürdü, 2 saniyelik GUI watchdog eski görüntüyü kaldırdı; kamera kaynağı yalnız bir kez açılmıştı. Bu durum yeniden bağlantı döngüsü değildi. Bu tek ölçümü genel hız garantisi saymıyoruz.

Ayrı gerçek kaydedicili regresyonda, önizlemenin kendi ekranı içinde taşınması üç geometri yoklaması boyunca kaydı durdurmadı; kamera yeniden açılmadı. Ekran sınırının dışına çıkan önizleme/gerçek topoloji değişimi için mevcut kayıt korumaları değiştirilmedi.

## Kayıt durumundayken iki görünümün teslim testi

`test_recording_preview_preserves_live_frame_distribution`, gerçek MainWindow ve MssFfmpegRecorder ile kayıt durumunu gerçekten `RECORDING` yapar. Önce yalnız tahtada kamera, sonra ikinci ekranda büyük önizleme açıkken iki gerçek `set_frame` yoluna ulaşan kareleri sayar. Yapay işlem gecikmesi veya sahte fps kullanılmaz. Süreye bağlı kırılgan hız eşiği yerine, ikinci önizlemenin kare başına anahtarlama boyutunu artırmaması ve aynı karenin iki görünüme de ulaşması sınanır.

Aynı test eski kaynakla **kırmızı**: önizleme kapalı 25,78 kare/sn; açıkken tahta **1,61**, harici **1,61** kare/sn. Anahtarlama genişliği 72 → 800 px. Yeni kaynakla **yeşil**: kapalı 21,77; açıkken tahta **27,89**, harici **27,89** kare/sn; genişlik 72 → 72 px. Test küçük pencere/varsayılan offscreen boyutuyla çalışır; bu ölçüler FHD performans tablosundan farklıdır. Her iki senaryoda da işçi nesnesi aynı, kamera yalnız bir kez açılıyor, önizleme görünür kalıyor, geometri kesintisi yok. Sorun kayıt başlatınca bağlantıların kopması veya işçinin yeniden oluşturulması olarak yeniden üretilmedi.

```bash
QT_QPA_PLATFORM=offscreen XDG_CONFIG_HOME="$TMPDIR/mm-donma-recording" \
.venv/bin/python -m pytest -q -s -p no:cacheprovider \
  tests/test_kamera_kare_basinci.py::test_recording_preview_preserves_live_frame_distribution
```

## Karşılaştırma

Aynı betiğin ardışık eski/yeni koşusu; süre yaklaşık 6 sn/durum. Kamera sayacı kayıt durdurma/finalize süresini **içermez**. Sunucu paylaşımlıdır; zamanlar donanım garantisi ve istatistiksel benchmark değildir.

| Durum | Kamera fps önce → sonra | Yazım fps önce → sonra | İşçi toplam ms/kare önce → sonra |
|---|---:|---:|---:|
| Yeşil perde, önizleme kapalı | 24,11 → 19,93 | 29,51 → 29,90 | 34,81 → 46,16 |
| Yeşil perde, tam ekran önizleme | 3,18 → 19,20 | 28,30 → 29,99 | 318,88 → 38,21 |
| Ham kamera, önizleme kapalı | 18,98 → 27,44 | 13,74 → 29,87 | 32,85 → 12,30 |
| Ham kamera, tam ekran önizleme | 15,49 → 22,00 | 18,98 → 29,69 | 7,45 → 20,83 |

Tam ekran yeşil perdede yalnız anahtarlama 306,52 → 18,95 ms; QImage oluşturma 8,10 → 0,30 ms. GUI kare dağıtımı 1,42 → 0,94 ms; tahta kamera boyaması 5,31 → 2,99 ms; yardımcı önizleme boyaması 44,10 → 35,74 ms, fakat artık en fazla 10 Hz. Ham kamerada panel boyaması 6,97 → 1,90 ms, harici boyama 48,42 → 28,76 ms. QPixmap kullanılmıyor.

Olay döngüsü gecikmesinin p95'i yeşil perdede 32,69 → 41,17 ms (bu ölçü iyileşmedi), ham görüntüde 111,53 → 40,52 ms. En uzun gecikme sırasıyla 138,57 → 123,88 ve 193,21 → 93,21 ms. Eski ham kamera koşullarında kodlayıcı yetişemedi uyarısı çıktı; yeni dört koşulda çıkmadı. Diğer deneylerde yük nedeniyle düzeltilmiş kaynakta da uyarı görüldü: uyarının her makinede yok olacağı iddia edilmiyor.

1080p/30 sentetik video deneyinde sunucunun kodlayıcısı her iki kaynakta da doygundu: önizlemeli yeşil perdede yaklaşık 4,44 → 4,03 yazım fps, ham görüntüde 3,33 → 5,21 fps. Bütün 1080p koşulları kodlayıcı uyarısı üretti. Yeşil perdeli işçi maliyeti buna rağmen 596,10 → 54,81 ms oldu. Bu ortamda 1080p kodlama akıcılığı doğrulanmış sayılmaz; kayıt çekirdeği değiştirilmedi.

## Düzeltme ve bilinçli ödün

- Yeşil perdeli ortak görüntünün çözünürlüğünü tahta kamera kutusunun fiziksel genişliği belirler; ayrıca işçide 640 px üst sınır vardır. İkinci ekrandaki büyük anahtarlanmış görüntü daha yumuşak/pikselli olabilir; kayıt akıcılığı önceliklidir.
- Ham önizlemenin HD çözünürlüğü korunur. Tahtanın küçük çizim görüntüsü işçide ayrıca ölçeklenir; GUI yüksek çözünürlüklü kaynağı tekrar küçültmez.
- Yerel premultiplied QImage biçimi işçide bir kere hazırlanır; iki görünüm bunu kullanır.
- Panel işçiden yalnız bir bekleyen kare bildirimi alır. Arada gelen görüntüler tek hücreyi yeniler; GUI açıldığında en yeniyi alır. Sonlu işçi tüketicileri için eski `frameReady(QImage)` sinyali korunur, canlı panel ona bağlanmaz.
- Yardımcı önizlemenin yeniden boyaması 10 Hz ile sınırlıdır; tahta kamerasının hedef 30 fps akışı kısıtlanmaz. Kamera kopması/placeholder hemen gösterilir.
- `core/recorder.py` ve `core/audio_capture.py` değiştirilmedi.

## Tekrar üretme

İki offscreen ekran için Qt config JSON:

```json
{"screens":[{"name":"board","x":0,"y":0,"width":1920,"height":1080,"logicalDpi":96,"logicalBaseDpi":96,"dpr":1},{"name":"preview","x":1920,"y":0,"width":1920,"height":1080,"logicalDpi":96,"logicalBaseDpi":96,"dpr":1}]}
```

Config'i scratch'te `mm-donma-screens.json` adıyla oluşturduktan sonra:

```bash
QT_QPA_PLATFORM="offscreen:configfile=$TMPDIR/mm-donma-screens.json" \
XDG_CONFIG_HOME="$TMPDIR/mm-donma" \
.venv/bin/python scripts/measure_camera_preview.py --output "$TMPDIR/kamera-sonra.json"
```

1080p kodlayıcı kontrolü için `--full`; süre için `--seconds 6`. Betik `--output` JSON'unun yanındaki klasörde **sentetik** MP4 üretir; gerçek kamera/mikrofon açmaz, kullanıcı kayıtlarını okumaz. Eski kaynak için `git archive e1c00d5 src` ile scratch'e açılan kaynak ağacı `PYTHONPATH` olarak verilmelidir; ana checkout değiştirilmez. Windows offscreen config dosya yolunu göreli verin (Qt seçeneklerinde sürücü iki noktası ayrıştırılır).

Regresyonlar: `tests/test_kamera_kare_basinci.py` (anahtarlama sınırı, biçim, mod geçişi, en yeni kare/tek bildirim, küçük panel için işçi ölçeklemesi, resize/DPR güncellemesi, önizleme çizim sınırı, gerçek kaydediciyle geometri kontrolü). Mevcut kamera ve çift ekran testlerinin beklentileri gevşetilmedi.

Gerçek XP-Pen, Windows kamera sürücüsü, GPU kodlayıcı ve çoklu ekran compositor davranışı hedef bilgisayarda ayrıca denenmelidir.

## 10 Hz sınırının kaldırılması (d470c41 sonrası)

Önceki bölümlerdeki 10 Hz ödünü `d470c41` durumunu anlatır. Sınır
`ui/main_window.py::_Preview` içindeki tek atımlık 100 ms zamanlayıcıdaydı:
`set_frame` yaklaşık kamera hızında çalışsa bile gerçek `paintEvent` yaklaşık
10/sn (yük altında daha az) çalışıyordu. Bu yüzden yalnız teslim sayan eski
regresyon akıcılık sorununu yakalamıyordu.

### Değişiklik

- Harici görünüm yeni kare geldikçe yeniden çizim ister. Önceki istekten
  kalan 1/30 sn bütçesi hassas tek atımlık zamanlayıcıyla beklenir; her kareye
  sabit 33 ms gecikme eklenmez (bu, 30 fps kaynağı yaklaşık 15 fps'ye bölebilir).
- Bekleyen en fazla tek çizim isteği vardır; arada gelen kareler eskisini
  değiştirir. Yeni kare yoksa zamanlayıcı kendiliğinden tekrar çalışmaz.
  Kamera kopması/placeholder bekleyen isteği iptal eder ve hemen çizilir.
- GUI'deki büyük harici görüntü `SmoothPixmapTransform` olmadan, yakın komşu
  hızlı yoluyla kendi dikdörtgenine ölçeklenir. Tahtanın yumuşak çizimi,
  işçideki premultiplied dönüşüm/küçük görüntü hazırlığı, tek hücreli kare
  dağıtımı ve yeşil perde için tahta boyutu/640 px sınırı değişmedi.
- Yeşil perde işçidedir; GUI'ye taşınmadı. Harici önizlemede bilinear
  yumuşatma yerine daha pikselli görüntü bilinçli ödündür. Kayıt çekirdeği
  (`core/recorder.py`, `core/audio_capture.py`) değiştirilmedi.

### Kırmızı → yeşil: gerçek RECORDING ve gerçekten çizilen kareler

Yeni `test_recording_external_preview_paints_at_camera_rate`, mevcut pencere
ve küçük sentetik ffmpeg yakalayıcı kurgusunu kullanır. 160×90 kamera,
800×800 harici görünüm, yaklaşık 2,2 sn ortak ölçüm aralığı vardır. Aynı
`QImage.cacheKey()`'in gerçek harici yuvaya teslimini ve gerçek çizimden sonra
farklı cacheKey sayısını **ayrı** sayar; finalize başlamadan sayaçları dondurur.
QMessageBox yanıtları monkeypatch edilir.

| Durum | Tahtaya teslim | Tahtada çizilen | Harici teslim | Haricide çizilen |
|---|---:|---:|---:|---:|
| d470c41, kırmızı | 26,71 | 26,71 | 26,71 | **7,70** |
| Düzeltme, yeşil | 27,21 | 27,21 | 27,21 | **27,21** |

Birim kare/sn. Test teslim/tahta çizimi için ≥20, harici çizim için
≥max(20, tahta×0,70) ve ≤32 sınar. İşçi aynı kalmalı, kamera bir kez
açılmalı ve kayıt geometri kesintisi yaşamamalıdır. Ayrı piksel testi eski
kodda bilinear karışım nedeniyle 129 yerine beklenen 255 kırmızıyı üretemez;
yeni kodda harici hızlı yol ve tahtanın yumuşak yolu ayrı doğrulanır.
Deterministik saat testi 30 Hz bütçesinden kalan süreyi, kare birleştirmeyi,
yeni kare yokken zamanlayıcının susmasını ve kopma iptalini sınar.

İlk dal CI koşusunda (`43376307186`) Windows paket/test/artifact yeşil,
macOS'ta bu yeni test kırmızıydı: kaynak teslimi, tahta çizimi ve harici çizim
hep 9,37 fps idi (yani 10 Hz harici sınırı değil, bütün sentetik akış yavaştı).
Bu nedenle zamanlayıcı regresyonunun çizim yükü de 320×180 mantıksal piksele
sınırlandı; ≥20 eşiği ve göreli koşul düşürülmedi, tam ekran ölçümü betikte
korundu. Aynı son test tekrar arşivlenmiş d470c41 kaynakla kırmızı
(harici 7,70; tahta 24,46), yeni kaynakla yeşil (harici 21,44; tahta 23,26)
oldu. Bu son Linux örneği tam paketle eşzamanlı koşuldu; ilk 27,21 fps
kanıtı yukarıda ayrı tutulmuştur.

### Önce/sonra: iki FHD offscreen ekran

`scripts/measure_camera_preview.py` artık teslim ve **farklı çizilen kare**
hızlarını ayrı yazar; bütün sayaçlar RECORDING aralığıyla sınırlıdır.
Aynı güncellenmiş betik üretim kodu değiştirilmeden önce ve sonra koşuldu.
Her durum yaklaşık 6 sn, iki Qt ekranı 1920×1080, harici pencere tam ekran,
sentetik kodlama 640×360/30 fps. Sunucu paylaşımlı/yavaştır; bunlar istatistiksel
benchmark veya gerçek donanım akıcılık garantisi değildir.

| Kaynak / mod / harici | Tahta çizim önce → sonra | Harici teslim önce → sonra | Harici çizim önce → sonra | Kodlama önce → sonra |
|---|---:|---:|---:|---:|
| 160×90 / yeşil perde / kapalı | 18,92 → 25,28 | — | — | 14,94 → 29,97 |
| 160×90 / yeşil perde / açık | 17,35 → 26,14 | 17,35 → 26,14 | **5,46 → 25,61** | 16,71 → 29,65 |
| 160×90 / ham / kapalı | 26,18 → 28,74 | — | — | 28,56 → 29,61 |
| 160×90 / ham / açık | 22,68 → 23,63 | 22,83 → 23,63 | **6,82 → 23,63** | 24,26 → 25,05 |
| 1280×720 / yeşil perde / kapalı | 19,22 → 15,70 | — | — | 27,78 → 19,19 |
| 1280×720 / yeşil perde / açık | 22,05 → 15,47 | 22,22 → 15,47 | **6,35 → 15,31** | 23,39 → 23,62 |
| 1280×720 / ham / kapalı | 23,04 → 25,86 | — | — | 21,67 → 29,51 |
| 1280×720 / ham / açık | 16,55 → 14,28 | 17,59 → 15,71 | **5,52 → 13,49** | 19,48 → 20,94 |

Birim kare/sn. Küçük kaynakta yeşil perdeli büyük önizleme boyaması ortalama
54,58 → 8,93 ms; ham görüntüde 33,00 → 12,08 ms. HD kaynakta sırasıyla
30,78 → 21,98 ms ve 45,77 → 23,85 ms. Yeşil perde ve HD kaynak maliyeti
bu sunucuda hâlâ değişken/doygun: HD koşulunda tahta hızı da düşük ve yeni
kodda daha düşüktür; **HD kaynak + FHD harici pencere için ≥20/25 fps ve tahta
hızının korunması bu ölçümle doğrulanmış değildir**. Küçük kaynaklı kayıt
regresyonu ve FHD ölçümünde hedef yakalandı; gerçek PC/Mac performansına
buradan genelleme yapılmaz.

Küçük kaynak önceki yeşil perde koşullarında kodlayıcı yetişemedi uyarısı
vardı; sonraki dört küçük kaynak koşulunda yoktu. HD sonraki kapalı yeşil
perde koşulunda uyarı çıktı; diğer yedi HD koşulunda çıkmadı. Bütün koşulda
`record_error=null`, kamera açılışı bir kez. 1080p gerçek ekran yakalama,
mikrofon, GPU kodlayıcı, XP-Pen ve compositor bu çalışmanın kapsamı dışında.

### Ham kanıtlar ve komutlar

Sunucudaki kanıt kökü:
`/root/hermes/profiles/baris-beyin/cache/scratch/mm-onizleme-fps-kanit/`.
Scratch budanabilir; temel sonuçlar bu belgede korunur.

- `tdd-kirmizi.log`: eski kodda hız testinin beklenen assertion hatası; çıkış 1.
- `olcekleme-kirmizi.log`: eski kodda hızlı ölçekleme piksel testi; çıkış 1.
- `hedef-yesil.log`: ilk yeşil 13 test ve yukarıdaki 27,21 fps ölçümü.
- `kamera-hedefleri.log`: kamera/önizleme/çift ekran hedef paketi.
- `once-kucuk.json`, `sonra-kucuk.json`, `once-hd.json`, `sonra-hd.json`:
  dört durumun ham sayaç/maliyet/uyarı sonuçları; eş adlı `.log` dosyaları
  stdout/stderr. Yan klasörler yalnız sentetik MP4 içerir.
- `tam-paket.log`, `tam-paket.exit`: tam paket sonucu ve gerçek çıkış kodu.
- `ekranlar.json`: ölçümde kullanılan iki ekran konfigürasyonu.

```bash
QT_QPA_PLATFORM=offscreen XDG_CONFIG_HOME="$TMPDIR/mm-onizleme-fps" \
.venv/bin/python -m pytest -q -s -p no:cacheprovider \
  tests/test_kamera_kare_basinci.py > "$TMPDIR/kamera-test.log" 2>&1

QT_QPA_PLATFORM="offscreen:configfile=$TMPDIR/mm-onizleme-fps-kanit/ekranlar.json" \
XDG_CONFIG_HOME="$TMPDIR/mm-onizleme-fps" \
.venv/bin/python scripts/measure_camera_preview.py --source-width 160 --seconds 6 \
  --output "$TMPDIR/kamera-kucuk.json" > "$TMPDIR/kamera-kucuk.log" 2>&1
```

HD kaynak için `--source-width 1280` (varsayılan). Önceki üretim kodu
`d470c41`; yeniden karşılaştırmada aynı güncellenmiş ölçüm betiğine
`git archive d470c41 src` ile scratch'e açılmış `src` ağacını `PYTHONPATH`
olarak verin, ana checkout'u değiştirmeyin. Test çıktısını `tail`'e borulamak
çıkış kodunu gizler; dosyaya yazıp gerçek sonucu ayrı saklayın.
