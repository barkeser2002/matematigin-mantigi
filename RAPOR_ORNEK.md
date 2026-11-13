# Tanıma örneği topla (Hedef B) — rapor

Dal: `kanban/tanima` (worktree `/root/matematigin-mantigi-wt/tanima`), push: `ci/tanima`. Yalnız toplama ve eğitim betik iskeleti; uygulamada çıkarım YOK.

## Sembol listesi (19, sıra kilitli)
`0 1 2 3 4 5 6 7 8 9 + − × ÷ = ( ) x y` (prototip `symbol/classes.json` ile birebir). Sembol başına hedef: 30 (`core/ornek_toplama.HEDEF_ORNEK`).

## Kayıt formatı
- Klasör: `<kullanıcı veri klasörü>/tanima-ornekleri/<sembol>/` (`paths.default_tanima_ornek_root()`; paketli uygulamada `~/Documents/Matematiğin Mantığı/`).
- Dosya: `<sembol>_<YYYYmmdd-HHMMSS>_<n>.json` + aynı adla `.png`. Çakışmada `n` artar.
- JSON alanları: `sembol`, `sinif_indeksi`, `cizgiler` (her nokta `x, y, basinc, zaman`), `cizgi_sinirlari` (`x0,y0,x1,y1`), `cizim_kutu_boyutu`, `kanvas`, `png`, `boyut_png` ([28,28]).
- PNG: 28×28, 8-bit gri, stdlib `zlib`+`struct` ile yazılır (yeni bağımlılık yok). Normalleştirme prototipteki mantık: >30 piksel kırpma, en-boy korunarak küçültme, ortalama. Fark: prototip 32 tuvalde 24 iç kutu kullandı; burada 28 tuvalde orantılı 21 iç kutu. Küçültme numpy bilinear (PIL LANCZOS değil) — piksel düzeyinde birebir aynı değil.
- ZIP: `tanima-ornekleri` ağacı (`<sembol>/…`), pencerede "ZIP olarak dışa aktar…" dialogu.

## Pencere
- Araç çubuğunda `▦ Tanıma` düğmesi (Sorular'ın altında). Kayıt sürerken açılışta mevcut "Bu pencere kayda girer" onayı.
- Kaydet / Sonraki / Sil. Kaydedilmemiş çizim varken Sonraki engellenir (uyarı metni). İlerleme: `n / 30` ve `Toplam: t / 570`.
- Yan panel: FULL eşiği 1010→1030 (düğme ~28 px ekledi). En küçük kademe (MINI) yüksekliğe sığmadığı için düğme MINI'de gizlenir: 1280×720 @160%/120 dpi kaydırmasız kalsın diye. MINI'de Tanıma penceresi açılamaz.

## Eğitim betiği
- `tools/tanima_egit.py KAYNAK… [--mnist] [--epoch 15] [--batch 64] [--seed 7] [--cikti x.npz]`. Girdi: klasör veya ZIP. TF yalnız `model_kur`/`egit`/`mnist_al` içinde import edilir.
- Çıktı `.npz`: `<katman>__<i>` ağırlıkları, `siniflar`, `girdi_boyutu` [28,28,1]. Model: Conv16 → Pool → Conv32 → Pool → Dense64 → Dense19 softmax.
- `pyproject.toml` extra `tanima-egitim` (linux: `tensorflow-cpu`, diğer: `tensorflow`). Uygulama bağımlılığına girmez.
- `--mnist`: MNIST CC BY-SA 3.0 (ShareAlike). Varsayılan kapalı. Bu çalıştırmada denenmedi (indirme yapılmadı).

## Duman testi (sahte veri, 1 epoch)
- Veri: `$TMPDIR/tanima_sahte_veri.py` gerçek `ornek_kaydet` yolundan 19 sembol × 3 = 57 örnek üretti (`ornek sayilari` çıktısı: her sembol 3).
- TF: `tensorflow-cpu 2.21.0` (Python 3.12 venv `$TMPDIR/tf-venv`), `nice -n 19`.
- Klasör girdisi: `{'ornek': 57, 'egitim': 48, 'dogrulama': 9, 'atlanan': 0, … 'cikti': …/w_dir.npz}`, exit 0.
- ZIP girdisi: aynı sayılar, `w.npz`, exit 0; 29,7 sn.
- `np.load` anahtarları: `cikti__0 (64,19), cikti__1 (19,), conv1__0 (3,3,1,16), conv1__1 (16,), conv2__0 (3,3,16,32), conv2__1 (32,), dense1__0 (1568,64), dense1__1 (64,), girdi_boyutu (3,), siniflar (19,)`.
- Doğruluk anlamsız (1 epoch, sahte veri, doğrulama 9 örnek). Kalite ölçümü yapılmadı.

## Testler
- Yeni: `tests/test_ornek_toplama.py` (18), `tests/test_ornek_toplama_pencere.py` (13), `tests/test_tanima_egit.py` (7).
- Değişen: `tests/test_toolbar.py` (FULL eşiği 1030'a göre sınırlar).
- Tam paket (sunucu, offscreen): `1716 passed, 2 skipped, 2 xfailed`, exit 0.

## Bilinen sınırlar
- Gerçek kalemle (XP-Pen) çizim doğrulanmadı; tabletEvent yolu yalnız kodda, testte fare kullanıldı.
- Gerçek el yazısı verisi yok; sentetik duman sonucu kalite kanıtı değil.
- MINI kademede tanıma penceresi açılmıyor (yer kısıtı).
- `--mnist` yolu çalıştırılmadı (ağ indirmesi ve lisans kararı Barış'ta).
- Windows/macOS: CI derlemesi ci/tanima dalında (bkz. aşağıdaki durum).
