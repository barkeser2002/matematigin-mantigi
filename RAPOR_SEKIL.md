# Şekil düzeltme — ölçüm ve durum raporu (Hedef A)

Dal: `kanban/tanima` · Kapsam: kalem çizgisini ML'siz geometriyle şekle düzeltme (`core/shape_recognition.py`, `ui/canvas.py`, `ui/pen_settings.py`).

## Durum

- Açma/kapama: araç çubuğu "Kalem" → Kalem ayarları → "Şekil düzeltme" anahtarı. Kilitsiz, varsayılan KAPALI, `QSettings`'te kalıcı. Ayrı araç çubuğu düğmesi eklenmedi (yan panel yerleşimini Windows/Mac'te görsel doğrulayamam; mevcut yol tek tık + tek anahtar).
- Geri al: ilk geri al ham çizgiyi geri getirir, ikincisi çizgiyi siler; yinele düzeltmeyi yeniden uygular (testli).
- Tahta PNG kaydı, ölçek ve oturum geri yüklemesi: bellek içi snapshot ve PNG dosya yazma/okuma + 2 kat ölçekli geri yükleme testli (`test_corrected_shape_survives_png_file_and_scaled_restore`).
- Kurallar: yalnız yuvarlak uçlu kalem, Shift yok, kısa kenar/uzunluk < 40 px dokunulmaz, 1,2 sn içinde komşu yazı varsa dönüşmez.

## Ölçüm (sentetik veri, seed 20261113, `scripts/sekil_olcum.py`)

| Metrik | Değer | Sayı |
|---|---|---|
| Doğruluk (pozitif, beklenen tür) | 90,8 % | 545/600 |
| Serbest çizim yanlış kabulü | 8,9 % | 25/280 |
| Küçük boyut (<60 px) yanlış kabulü | 0,0 % | 0/200 |
| El yazısı benzeri yanlış kabul | 0,0 % | 0/200 |
| Küçük şekil doğruluğu (<70 px) | 51,7 % | 31/60 |

Sınıf doğruluğu: çizgi 97, daire 96, elips 90, üçgen 81, dikdörtgen 89, çokgen 92 (%).

Sürelik: ortalama 11 ms / çizim, p95 33 ms.

## Eşik araştırması

Serbest çizim yanlış kabullerinin TAMAMI "closed_blob" ailesinden (kapalı organik leke). Güven eşiği taraması:

| Eşik | Doğruluk | Serbest yanlış kabul | Küçük şekil |
|---|---|---|---|
| 0,68 (seçilen) | 90,8 % | 8,9 % | 51,7 % |
| 0,75 | 89,2 % | 8,9 % | — |
| 0,80 | 86,7 % | 5,7 % | 35,0 % |

0,80 yanlış kabulü 3 puan düşürüyor ama doğruluğu 4, küçük şekil doğruluğunu 17 puan düşürüyor. Bu takas kabul edilmedi; eşik 0,68 kaldı. Kapalı leke yanlış kabulü bilinen sınır olarak `test_organic_closed_blob_is_not_turned_into_a_polygon` içinde `xfail(strict=True)` ile işaretli.

## Bilinen sınırlar

- Tüm veri SENTETİK. Ölçümler gerçek el yazısı/gerçek kalem doğruluğu DEĞİL. "El yazısı benzeri" üretici de sentetiktir.
- Serbest çizim yanlış kabulü (%8,9) gerçek çizimde farklı olabilir; gerçek kullanımla ayarlanmalı.
- XP-Pen donanımı (basınç, kalem uç tipi, gerçek örnekleme aralığı) bu sunucuda doğrulanmadı.
- Windows/macOS görsel yerleşim (Kalem ayarları penceresi, araç çubuğu) doğrulanmadı; CI derlemesi yalnız derleme/test kanıtı verir.
- Eşik 0,68 "güven" sezgisel skordur, kalibre olasılık değildir.
- Tanıma yalnız tek-stroke; çoklu çizgi şekiller (ör. üst üste iki çizgi) kapsam dışı.

## Test

- `tests/test_sekil_duzeltme.py` + `tests/test_recognition_unavailable.py`: 29 geçti, 1 xfail (yukarıdaki bilinen sınır).
- Tam paket sonucu: bkz. commit mesajı ve dönüş raporu.
