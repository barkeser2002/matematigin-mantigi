# Graph Report - arayuz-soru-sistemi-metematigin-mantigi  (2026-09-12)

## Corpus Check
- 70 files · ~142,840 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1419 nodes · 3070 edges · 88 communities (63 shown, 25 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 279 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c0cfbd87`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- RecordRect
- support.js
- Zone
- DrawingCanvas
- ToolBar
- test_work_area.py
- MainWindow
- QuestionFlow
- QuestionZone
- AppSettings
- ImageSlot
- FontFamilies
- _StopWorker
- test_main_window.py
- File Structure
- HintZone
- PenSettingsDialog
- chroma_key.py
- cursors.py
- ChromaParams
- camera_worker.py
- extract_questions
- question_loader.py
- app.py
- test_theme.py
- SettingsDialog
- layout_model.py
- SessionStore
- Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu)
- _SlowCamera
- FakeCamera
- RecordBadge
- frames.py
- test_layout_model.py
- test_stroke.py
- ClickableLabel
- test_canvas.py
- WorkArea
- build_mac.sh
- matematigin-mantigi
- AudioCapture
- Question
- MssFfmpegRecorder
- QPoint
- recorder.py
- test_question_editor.py
- .inner_rect
- PenSettings
- WebcamPanel
- test_webcam_panel.py
- test_audio_capture.py
- _EditOverlay
- .__init__
- models.py
- ._place_eye_button
- .apply_ui_settings
- _TaggedCamera
- DprArea
- grab_screen
- Recorder
- find_ffmpeg
- ._on_record_stopped
- ffmpeg_args
- tablet
- _display_id
- detect_encoder
- test_legacy_duzen_json_without_item_keys_keeps_items_at_default_positions
- .layout
- test_free_resize_round_trips_across_very_different_window_sizes
- test_unmoved_items_render_at_todays_default_positions
- test_dragged_item_stays_proportional_to_stage_after_resize
- test_badge_drag_applies_to_real_widget_bound_after_construction
- .set_font_scale
- test_reset_layout_also_clears_item_overrides
- test_hidden_zone_and_item_render_as_translucent_ghost_not_normal_outline
- test_edit_mode_resize_from_nw_corner_moves_and_resizes
- test_presenter_name_and_visibility_do_not_stomp_each_other
- test_set_font_scale_updates_slider_without_reemitting_signal
- test_work_area_set_families_scales_its_own_labels_but_not_logo_monogram
- test_letterbox_stays_visible_when_frame_is_hidden
- test_eye_button_click_through_real_event_path
- test_presenter_visibility_survives_a_later_set_presenter_name_call
- test_default_frame_style_is_classic_with_unchanged_band
- test_hud_frame_style_hides_brand_and_presenter_until_frame_titles_disabled
- test_classic_frame_style_ignores_the_frame_titles_key
- test_hud_frame_paints_white_board_center_and_navy_band
- test_frame_style_setting_flows_from_settings_values_style

## God Nodes (most connected - your core abstractions)
1. `FontFamilies` - 79 edges
2. `MainWindow` - 65 edges
3. `AppSettings` - 57 edges
4. `WorkArea` - 54 edges
5. `make()` - 54 edges
6. `ChromaParams` - 47 edges
7. `DrawingCanvas` - 46 edges
8. `QuestionFlow` - 43 edges
9. `WebcamPanel` - 40 edges
10. `Question` - 38 edges

## Surprising Connections (you probably didn't know these)
- `test_build_window_offscreen()` --calls--> `FontFamilies`  [INFERRED]
  tests/test_models.py → src/matematigin_mantigi/ui/theme.py
- `createExternalModules()` --indirect_call--> `load()`  [INFERRED]
  support.js → image-slot.js
- `FakeAudioCapture` --uses--> `AudioResult`  [INFERRED]
  tests/test_recorder.py → src/matematigin_mantigi/core/audio_capture.py
- `test_list_camera_names_parses_mac_and_windows()` --calls--> `list_camera_names()`  [INFERRED]
  tests/test_cameras.py → src/matematigin_mantigi/core/cameras.py
- `_SlowCamera` --uses--> `ChromaParams`  [INFERRED]
  tests/test_webcam_panel.py → src/matematigin_mantigi/core/chroma_key.py

## Import Cycles
- None detected.

## Communities (88 total, 25 thin omitted)

### Community 0 - "RecordRect"
Cohesion: 0.23
Nodes (19): record_rect_for(), RecordRect, FakeAudioCapture, ndarray, skipif, Yakalama 10 kare/sn verse de 30 fps çıktı ~1 sn'lik kayıtta ~30 kare taşır…, Gerçek mikrofon yerine 1 kHz sinüs üretir; ilk örnek zamanı start() anıdır., _stream_seconds() (+11 more)

### Community 1 - "support.js"
Cohesion: 0.07
Nodes (52): boot(), cdnScriptFor(), collectProps(), compileAttr(), compileTemplate(), contentKey(), createComponentFactory(), createExternalModules() (+44 more)

### Community 2 - "Zone"
Cohesion: 0.19
Nodes (6): QMouseEvent, QPointF, QTabletEvent, QWidget, on: çizim aracı aktif; kart, düğme, kamera gibi çocuklar fareye şeffaf olur,…, Zone

### Community 3 - "DrawingCanvas"
Cohesion: 0.07
Nodes (25): QPaintEvent, QResizeEvent, QSize, _dot_tile(), DrawingCanvas, _grown(), QColor, QImage (+17 more)

### Community 4 - "ToolBar"
Cohesion: 0.06
Nodes (28): QAbstractButton, QFrame, QLabel, QWidget, Kayıt süresi araç çubuğunda sayar (kayda girmez): 'DURDUR · 01:23'., Bölge 9: dış araç çubuğu. Kayıtta görünmez., ToolBar, DotButton (+20 more)

### Community 5 - "test_work_area.py"
Cohesion: 0.13
Nodes (27): brightest(), make(), Nokta dokusu sahnenin kenarında: widget'a çivili kalsaydı üst/alt sıralar…, CRITICAL düzeltme: bir bölgenin TEK KENAR tutamağı (köşe değil) artık öğelere…, CRITICAL düzeltme (review): düğme WorkArea'nın kendi sınırlarının dışına…, paint_hud çok küçük pencerede -- stage_rect() eski davranışa dönüp tüm alanı…, test_board_inside_frame_and_zones_use_defaults(), test_edit_overlay_only_in_edit_mode() (+19 more)

### Community 6 - "MainWindow"
Cohesion: 0.14
Nodes (5): QMainWindow, MainWindow, Yazı aracının kutusu açıkken tek tuşlu kısayollar kutuya bırakılır., Yazıcı borusu koptuysa (ffmpeg çöktü) kaydı hemen kapat ve kullanıcıya söyle., Editörden gelen yeni listeyi uygular; akış başa döner, arayüz yeniden restart…

### Community 7 - "QuestionFlow"
Cohesion: 0.09
Nodes (14): QObject, QuestionFlow, Önceki sayfaya döner; durumları değiştirmez., Soru listesini tümüyle değiştirir; sıra başa döner, durumlar ve ipucu durumu…, test_empty_flow_is_safe(), test_hint_navigation_clamps(), test_initial_state(), test_next_question_marks_done_and_emits_in_order() (+6 more)

### Community 8 - "QuestionZone"
Cohesion: 0.07
Nodes (27): QFont, QMouseEvent, QuestionZone, Yazı tipini (ve tahta yazı ölçeğini, Görev 7) değiştirir (Ayarlar > yazı tipi…, A) B) C) D) etiketlerinin fontu -- set_families VE _build_options (yeni soruya…, hzone(), qzone(), Çizim aracı aktifken (click-through) kart tıklaması açmaz; Tıkla aracında açar. (+19 more)

### Community 9 - "AppSettings"
Cohesion: 0.10
Nodes (16): QSettings, setter, AppSettings, Tahtadaki yazısal öğe görünürlüğü; anahtarlar VISIBILITY_KEYS içinde., ini_settings(), VISIBILITY_KEYS'e Görev 8'de eklendi: Ayarlar'daki onay kutusu ızgarası…, question_zone/hint_zone/webcam VISIBILITY_KEYS'e Görev 6'da eklendi; badge…, test_font_scale_default_clipped_and_round_trips() (+8 more)

### Community 10 - "ImageSlot"
Cohesion: 0.14
Nodes (7): flushNow(), getSlot(), ImageSlot, load(), save(), setSlot(), toDataUrl()

### Community 11 - "FontFamilies"
Cohesion: 0.11
Nodes (24): FrameSpec, TOOL_META/SHAPE_META (core/models.py) ile aynı kayıt kalıbı: Ayarlar'daki…, Akıllı ipuçları bölgesi: ampul başlık, krem/turuncu kartlar. Kartlar…, Ana pencere: beyaz tahta + bölgeleri kurar ve sinyalleri bağlar. İş mantığı…, _card(), QFrame, Kalem, silgi & imleç ayarları penceresi (mockup 'Kalem ayarları' ekranı)., _card() (+16 more)

### Community 12 - "_StopWorker"
Cohesion: 0.14
Nodes (8): FrameSource, Protocol, _NoCamera, Path, QThread, recorder.stop() birkaç saniye sürebilir (ffmpeg kapanışı + ses birleştirme);…, camera_source_factory: kamera indeksinden kaynak üretir; None ise kamera…, _StopWorker

### Community 13 - "test_main_window.py"
Cohesion: 0.05
Nodes (13): WorkArea.set_edit_mode eskiden badge_slot'un WA_TransparentForMouseEvents…, Eski kod set_presenter_name("") geçerek gizliyordu -- bu ad METNİNİ de kalıcı…, IMPORTANT (review): apply_ui_settings'in görünürlük yolu artık rutin bir…, IMPORTANT (review): apply_ui_settings artık her göz düğmesi tıklamasında da…, settings.font_scale + apply_ui_settings tahtadaki yazıları (ipucu başlığı, soru…, IMPORTANT (review): badge.set_families() (main_window.py) rozeti adjustSize()…, test_apply_ui_settings_skips_reload_when_font_and_logo_unchanged_but_reloads_on_change(), test_badge_stays_right_anchored_after_font_scale_change_with_real_content() (+5 more)

### Community 14 - "File Structure"
Cohesion: 0.08
Nodes (24): Context, File Structure, Global Constraints, Matematiğin Mantığı — Görünüş Demosu (PyQt6) Implementation Plan, Next plans (not in this milestone), Task 10: Questions from the Excel template, Task 11: Question flow state machine, Task 12: Session snapshots (oturum/ PNG per question) (+16 more)

### Community 15 - "HintZone"
Cohesion: 0.14
Nodes (8): HintMaskMode, BulbIcon, HintCard, HintZone, QMouseEvent, QWidget, Basit ampul: sarı daire + koyu kenar + küçük duy., Yazı tipini (ve tahta yazı ölçeğini, Görev 7) değiştirir (Ayarlar > yazı tipi…

### Community 16 - "PenSettingsDialog"
Cohesion: 0.21
Nodes (8): PenSettingsDialog, QColor, QDialog, QVBoxLayout, test_apply_emits_and_accepts(), test_dialog_reflects_current_and_returns_edits(), test_min_never_exceeds_max(), test_reading_speed_passes_through_unchanged()

### Community 17 - "chroma_key.py"
Cohesion: 0.21
Nodes (19): apply_chroma_key(), apply_chroma_key_bgra(), composite(), green_mask(), ndarray, Program içi yeşil perde: HSV tabanlı yumuşak anahtar, kenar yumuşatma, dökülme…, Ön plan alfası [0,1] float32. Ton uzaklığına göre yumuşak anahtar; doygunluk ve…, Zemin yerine saydamlık: BGRA uint8, alfa = ön plan maskesi. Kişi tahtanın… (+11 more)

### Community 18 - "cursors.py"
Cohesion: 0.20
Nodes (19): QCursor, _clamp(), eraser_diameter(), pen_cursor_diameter(), pressure_width(), Saf çizim matematiği: basınç -> kalınlık, silgi ve imleç çapları., _blank(), cursor_for() (+11 more)

### Community 19 - "ChromaParams"
Cohesion: 0.17
Nodes (11): ChromaParams, CameraWorker, QThread, test_dead_camera_reports_error_and_finishes(), test_open_retries_until_camera_becomes_available(), test_stop_aborts_open_retries(), test_stream_end_reports_error(), test_worker_auto_calibrates_key_hue() (+3 more)

### Community 20 - "camera_worker.py"
Cohesion: 0.13
Nodes (14): estimate_key_hue(), Karenin kenar şeridinden perde tonunu ölçer. Kenarların en az %60'ı doygun ve…, OpenCvSource, ndarray, QImage, Kamera iş parçacığı: OpenCV yakalama -> (isteğe bağlı) yeşil perde -> QImage…, İlk açılış başarısızsa (ör. macOS izin penceresi henüz onaylanmadı) belirli…, OpenCV kamera kaynağı. İstenen indeks açılmazsa 0-3 arası diğer indeksleri de… (+6 more)

### Community 21 - "extract_questions"
Cohesion: 0.23
Nodes (11): _clean(), extract_questions(), PdfImportError, Path, RuntimeError, PDF (yatay, sayfa başına 1 soru + 'AKILLI İPUÇLARI' kartları) -> Question…, main(), Komut satırı: python -m matematigin_mantigi.pdf_import <pdf> [--cikti… (+3 more)

### Community 22 - "question_loader.py"
Cohesion: 0.16
Nodes (22): ensure_template(), load_questions(), Path, QuestionTemplateError, Excel şablonu: sütun doğrulama, örnek şablon üretme, soru yükleme/yazma., Soruları tüm sütunlarla yazar. Görsel yolu xlsx klasörüne göre göreli ise öyle…, Görseli images_dir içine kopyalar, ad çakışması varsa '_1' gibi ekle çözer.…, _same_file() (+14 more)

### Community 23 - "app.py"
Cohesion: 0.15
Nodes (21): Namespace, build_window(), load_questions_or_samples(), main(), parse_args(), Path, _qt_message_filter(), Bilinen zararsız Qt uyarılarını süzer; gerisini stderr'e yazar. (+13 more)

### Community 24 - "test_theme.py"
Cohesion: 0.07
Nodes (12): Matematiğin Mantığı — grafik tablet ders anlatım uygulaması., core/models.py'de Tool/Nib/HintMaskMode ile aynı yerde --…, test_build_window_offscreen(), test_frame_style_enum_values(), test_pen_settings_defaults(), test_question_optional_fields_default(), Koyu mod karşıtı palet: liste/açılır menü/çok satırlı kutular arka plan+yazı…, scale alanı FontFamilies'e EN SONA eklendi -- testlerdeki (ve app.py'deki) eski… (+4 more)

### Community 25 - "SettingsDialog"
Cohesion: 0.07
Nodes (28): QSlider, _backends(), CameraInfo, list_camera_names(), list_cameras(), Kamera keşfi: OpenCV ile indeksleri dener, kare veren cihazları listeler. Adlar…, ffmpeg'in gördüğü video aygıt adları, indeks sırasıyla. macOS: avfoundation,…, 0..max_index-1 indekslerini dener; açılıp kare verenleri döndürür (her biri… (+20 more)

### Community 26 - "layout_model.py"
Cohesion: 0.16
Nodes (23): cell_size(), clamp(), clamp_free(), free_rect(), from_json(), item_pixel_from_pos(), item_pos_from_pixel(), ItemPos (+15 more)

### Community 27 - "SessionStore"
Cohesion: 0.23
Nodes (8): datetime, Path, QImage, Soru başına tuval anlık görüntüsü: oturum/<zaman>/<id>_<nn>.png, SessionStore, test_snapshots_are_numbered_per_question(), test_unsafe_ids_are_sanitised(), white()

### Community 28 - "Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu)"
Cohesion: 0.12
Nodes (15): Bu sürümde taslak olan kısımlar, Kayıt, Kısayollar, macOS (hedef makine, XP-Pen), macOS izinleri (.app), macOS paketleme (.app), Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu), Otomatik yapı ve release (GitHub Actions) (+7 more)

### Community 29 - "_SlowCamera"
Cohesion: 0.20
Nodes (6): Görev 6 düzeltmesi: shutdown(timeout_ms) verilirse worker.wait bu sınırla döner…, 2. review turu (Important): CameraWorker.stop() bir bloklayan read() çağrısını…, `read()` gerçek bir sürücü arızasını taklit eder (çok yavaş): stop() çağrılsa…, _SlowCamera, test_shutdown_timeout_bounds_the_wait_on_a_stuck_camera(), test_start_after_a_timed_out_shutdown_still_produces_frames()

### Community 30 - "FakeCamera"
Cohesion: 0.17
Nodes (8): fixture, dead_camera(), DeadCamera, fake_camera(), FakeCamera, N adet sentetik BGR kare üretir; sonra None döndürür., sample_questions(), window()

### Community 31 - "RecordBadge"
Cohesion: 0.23
Nodes (3): QWidget, Yazı tipini (ve tahta yazı ölçeğini, Görev 7) değiştirir (Ayarlar > yazı tipi…, RecordBadge

### Community 32 - "frames.py"
Cohesion: 0.09
Nodes (34): FrameContext, _hud_corner_bracket(), _hud_corner_motif(), _hud_label_band(), _hud_left_ruler(), _hud_rail(), _hud_right_edge(), paint_classic() (+26 more)

### Community 33 - "test_layout_model.py"
Cohesion: 0.08
Nodes (14): Görev 4 öncesi (serbest boyutlandırmadan önce) yazılmış tamsayı hücreli bir…, ITEM_KEYS, settings.VISIBILITY_KEYS'teki karşılıklarıyla birebir aynı dizeleri…, item_pos_from_pixel/item_pixel_from_pos: stage_rect başlangıcına göreli piksel…, Öğe konumları (ItemPos) da bölgeler gibi JSON'a yazılıp aynen geri okunmalı., Eski duzen.json (yalnız bölge anahtarları) öğe anahtarı içermez -- WorkArea…, Bozuk bir öğe girdisi (float'a çevrilemeyen x) yalnız o anahtarı atlar; aynı…, area_w/area_h/gap verilmezse (from_json, WorkArea.set_layout -- yükleme yolu)…, test_clamp_free_without_area_never_touches_span() (+6 more)

### Community 35 - "ClickableLabel"
Cohesion: 0.50
Nodes (3): ClickableLabel, QLabel, QMouseEvent

### Community 36 - "test_canvas.py"
Cohesion: 0.24
Nodes (23): alpha_at(), _drag(), draw_diagonal(), make(), test_clear_is_undoable(), test_color_is_used(), test_eraser_clears(), test_eraser_tip_overrides_tool_for_one_stroke() (+15 more)

### Community 37 - "WorkArea"
Cohesion: 0.11
Nodes (11): Ayarlar > Tahta'daki çerçeve stili açılır listesinden gelir (Görev 8).…, (etkin FrameSpec, çerçeve kendi başlıklarını fiilen çiziyor mu). İkincisi hem…, Etkin çerçeve stili sunucu adını/markayı KENDİSİ çiziyorsa…, PNG/JPG logo; boşsa veya yüklenemezse yuvarlak 'MM' monogramı. size: piksel…, WorkArea'nın kendi etiketlerinin (durum satırı, marka plakası, sunucu adı) yazı…, Kullanıcı kaydırıcıyı sürükledikçe: etiket hemen güncellenir, MainWindow'a…, Yalnız METNİ taşır; GÖRÜNÜRLÜĞÜ artık tek başına belirlemez (bkz.…, relayout()'un sonunda çağrılır: her bölge ve her öğe için köşesine bir göz… (+3 more)

### Community 40 - "AudioCapture"
Cohesion: 0.14
Nodes (14): _all_input_devices(), AudioCapture, _hostapi_rank(), list_input_devices(), Path, Mikrofon yakalama: PortAudio (sounddevice) ile uygulama içinde, büyük kuyruk,…, Tek kayıt için mikrofon yakalayıcı: start(wav_yolu) ... stop() -> AudioResult., Aygıtı sağlam çöz: seçilen ad, sonra PortAudio varsayılanı, o da yoksa… (+6 more)

### Community 41 - "Question"
Cohesion: 0.19
Nodes (5): Question, Path, QDialog, QuestionEditorDialog, Soru dosyasının (xlsx) görsel düzenleyicisi. Kaydet, write_questions ile yazar…

### Community 42 - "MssFfmpegRecorder"
Cohesion: 0.19
Nodes (7): _even(), MssFfmpegRecorder, ndarray, Path, Gerçek kaydedici. grabber(rect) -> BGRA kare; varsayılan ekran yakalama (mss).…, Kaydı kapatır ve sesi videoyla birleştirir. Uzun sürebilir (birkaç sn); arayüz…, Yazıcı iş parçacığı: sabit tempoda (fps) en yeni kareyi ffmpeg'e yazar.…

### Community 43 - "QPoint"
Cohesion: 0.12
Nodes (19): QPoint, cells(), Gerçek olay yolu (pencere -> çocuk isabet testi): bölge ve tuval şeffaf olmalı,…, Serbest sürükleme (varsayılan, Ctrl basılı değil): hücre değeri tam sayıya…, Bölge tahtanın dışına sürüklenmeye çalışılsa da sürükleme sırasında…, clamp_free'nin asgarisi 80x60 px'ten türer, MIN_SPAN=2 hücreden değil. Yükleme…, Düzen modunda marka plakasını sürükle -> yeni konuma gidiyor, layoutChanged…, IMPORTANT 1: öğeler kendi aralarında çakışırsa görsel olarak ÜSTTEKİ (gerçek Qt… (+11 more)

### Community 44 - "recorder.py"
Cohesion: 0.15
Nodes (13): AudioResult, İlk örnekten durdurmaya kadar geçen gerçek süre (saat kaymasını ölçmek için)., audio_rate_correction(), mux_args(), datetime, RuntimeError, Kayıt: RecordRect + Recorder protokolü, NullRecorder (test/taslak) ve…, Video (kopya) + WAV -> MP4 (AAC). offset_s > 0: ses videodan önce başladı, başı… (+5 more)

### Community 45 - "test_question_editor.py"
Cohesion: 0.23
Nodes (15): _dialog(), Satır düzenlenirken (_sync_label) ve liste yeniden yüklenirken (_reload_list,…, _format_label boşluğu kendi içinde temizlemeli; aksi halde henüz temizlenmemiş…, test_add_and_delete_rows(), test_edit_and_save_round_trips(), test_empty_soru_blocks_save(), test_format_label_strips_whitespace_regardless_of_source(), test_image_pick_copies_and_round_trips() (+7 more)

### Community 46 - ".inner_rect"
Cohesion: 0.16
Nodes (9): _paint_ghost(), QMouseEvent, QPainter, QRect, Tahtanın 16:9 sahnesi: pencerede ortalanır, artan yer bant olarak kalır. Ölçü…, Gizli (göz düğmesiyle kapatılmış) bölge/öğe: normal kesikli çerçeve yerine…, Çizilebilir alan: sahnedeki çerçeve bandının içi., Kayda giren dikdörtgen: 16:9 sahnenin tamamı (kenar bantları kayda girmez). (+1 more)

### Community 47 - "PenSettings"
Cohesion: 0.12
Nodes (15): PenSettings, NullRecorder, Webcam paneli gizlenince CameraWorker iş parçacığı gerçekten durmalı…, camera_source_factory None ise (main_window.py __init__'teki kalıp)…, Göz düğmesine tıklama WorkArea.visibilityToggled yayar;…, Kaydırıcı fontScaleChanged yayar; MainWindow._on_font_scale_changed ayara yazar…, test_eye_button_click_writes_setting_through_main_window_and_persists_on_restart(), test_font_scale_slider_writes_setting_and_persists_on_restart() (+7 more)

### Community 48 - "WebcamPanel"
Cohesion: 0.09
Nodes (13): CameraView, QImage, QMouseEvent, QWidget, Kamera değişimi: eski iş parçacığı durur, yenisi aynı ayarlarla başlar., Emekli `worker` artık çalışmıyor: listeden ÇIKAR ve sil -- bu ikisi hep…, Emeklilerden hâlâ ÇALIŞAN (durdurulamamış) olanların sayısı. Bitmiş olanları bu…, Üst sınır dolu mu: yeni iş parçacığı AÇILAMAZ, 'Kamera yanıt vermiyor'… (+5 more)

### Community 49 - "test_webcam_panel.py"
Cohesion: 0.14
Nodes (14): Event, 2. review turu: bu testin ÖNCEKİ hâli argümansız bir shutdown() çağrısının 2000…, FINDING 2 (3. review turu): read() GERÇEKTEN hiç dönmezse (yavaş değil, tamamen…, 4. review turu (CRITICAL): üst sınıra ULAŞILDIĞINDA eski kod `self.worker`ı…, 5. review turu (Important): üst sınır kontrolü ve göstergesi artık yalnız…, `read()` bir `threading.Event` üzerinde SÜRESİZ bekler -- gerçekten takılı bir…, test_panel_stays_usable_after_a_wedged_camera_recovers(), test_placeholder_without_camera() (+6 more)

### Community 50 - "test_audio_capture.py"
Cohesion: 0.17
Nodes (8): skipif, Sahte PortAudio: callback'i ayrı iş parçacığından 20 ms'lik bloklarla besler., Aygıt indeksleri değişince WASAPI'de giriş kalmayabilir; liste boş kalmamalı,…, Varsayılan giriş -1 (PortAudioError) olduğunda ilk listelenen mikrofona düşer,…, test_capture_writes_wav_and_measures_first_sample(), test_list_falls_back_when_wasapi_has_no_inputs(), test_real_microphone_short_capture(), test_start_falls_back_when_no_default_input()

### Community 51 - "_EditOverlay"
Cohesion: 0.25
Nodes (6): _EditOverlay, InkLayer, QWidget, Mürekkep katmanı: tuvalin çizgilerini soru ve ipucu bölgelerinin ÜSTÜNDE,…, Kayıtlı bir geçersiz kılma (`self._item_pos[key]`, stage_rect'e göre kesirli)…, Düzen modunda ızgara ve bölge sınırlarını en üstte çizer; fareye şeffaftır.

### Community 52 - ".__init__"
Cohesion: 0.39
Nodes (3): QScrollArea, QVBoxLayout, QWidget

### Community 53 - "models.py"
Cohesion: 0.22
Nodes (14): Enum, FrameStyle, next_shape(), Nib, QuestionStatus, Tahtanın ekran çerçevesi stili -- Ayarlar > Tahta kartından seçilir (bkz.…, Shape, Tool (+6 more)

### Community 54 - "._place_eye_button"
Cohesion: 0.25
Nodes (4): QPushButton, MainWindow.apply_ui_settings'in her görünürlük anahtarı için çağırdığı…, Bir göz düğmesine tıklanınca: WorkArea kendi bilgisini hemen günceller (buton…, Düğme normalde köşenin üst-sağında, bölgenin/öğenin GEOMETRİSİNİN TAMAMEN…

### Community 55 - ".apply_ui_settings"
Cohesion: 0.29
Nodes (3): Düzen modundaki göz düğmesine tıklandığında (work_area.visibilityToggled):…, Düzen çubuğundaki yazı boyutu kaydırıcısı (work_area.fontScaleChanged): ayara…, Ayarlardaki yazı tipi, yazma hızı, otomatik perde tonu ve görünürlükleri…

### Community 56 - "_TaggedCamera"
Cohesion: 0.25
Nodes (4): FINDING 1 (3. review turu): _make_worker her worker için…, Ürettiği her karede kendi ETİKETİNİ taşıyan sahte kamera (tüm piksel değerleri…, _TaggedCamera, test_retiring_worker_is_disconnected_and_cannot_paint_a_stale_frame()

### Community 57 - "DprArea"
Cohesion: 0.29
Nodes (6): DprArea, devicePixelRatioF()'ü testten sürer: Windows'ta 125/150/175% ölçek kesirli dpr…, ffmpeg `scale=-2:{out_height}`: genişlik orana göre en yakın çift sayıya…, Sahne 16:9'a yaklaşık değil, TAM eşit; yoksa ffmpeg 2560x1440 yerine 2558x1440…, scaled_width(), test_stage_ratio_is_exact_and_records_at_2560x1440()

### Community 58 - "grab_screen"
Cohesion: 0.33
Nodes (4): grab_screen(), _new_mss(), Ekran bölgesini BGRA uint8 HxWx4 olarak yakalar (mss). Windows'ta fiziksel…, Yakalama iş parçacığı: en fazla fps hızında kare alır, en yenisini bırakır.

### Community 60 - "find_ffmpeg"
Cohesion: 0.40
Nodes (5): find_ffmpeg(), Önce imageio-ffmpeg ile gelen ikili (paketlenmiş uygulamada da var), sonra PATH., Pencere üzerinden ses+video: mikrofon (sahte) alınır, mux edilir, ara dosyalar…, test_real_recorder_through_window(), test_real_recorder_with_audio_muxes_and_cleans_up()

### Community 62 - "ffmpeg_args"
Cohesion: 0.50
Nodes (4): ffmpeg_args(), Video ffmpeg komutu: ham BGRA kareler stdin'den, H.264 MP4 (ses yok; ses ayrı…, test_ffmpeg_args_encoder_selection(), test_ffmpeg_args_video_only()

### Community 63 - "tablet"
Cohesion: 0.29
Nodes (7): tablet(), test_mouse_press_ignored_while_stylus_down(), XP-Pen bug: Tıkla modunda kalemle karta dokununca Zone.tabletEvent olayı…, DrawingCanvas.tabletEvent kendi başına da (bir Zone üzerinden değil, tahtanın…, test_click_tool_tablet_press_on_empty_board_is_not_swallowed(), test_click_tool_tablet_press_over_hint_card_is_not_swallowed(), test_pen_tool_tablet_draws_over_hint_card_and_does_not_reveal()

### Community 64 - "_display_id"
Cohesion: 0.50
Nodes (4): _display_id(), Listede gösterilecek kimlik: S07 gibi iki+ haneli kalıpları korur, S1 -> S01…, parametrize, test_display_id_table()

### Community 65 - "detect_encoder"
Cohesion: 0.67
Nodes (3): detect_encoder(), Kullanılabilir ilk donanım H.264 kodlayıcısı; her aday 1 karelik deneme…, test_detect_encoder_prefers_hardware_when_probe_succeeds()

### Community 66 - "test_legacy_duzen_json_without_item_keys_keeps_items_at_default_positions"
Cohesion: 0.67
Nodes (3): item_widgets(), Görev 5 öncesi yazılmış (yalnız bölge anahtarlı) bir duzen.json bugün de…, test_legacy_duzen_json_without_item_keys_keeps_items_at_default_positions()

## Knowledge Gaps
- **38 isolated node(s):** `build_mac.sh script`, `matematigin-mantigi`, `Çalıştırma`, `Testler`, `Tahta` (+33 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FontFamilies` connect `FontFamilies` to `RecordRect`, `ToolBar`, `MainWindow`, `QuestionZone`, `_StopWorker`, `HintZone`, `PenSettingsDialog`, `app.py`, `test_theme.py`, `SettingsDialog`, `_SlowCamera`, `FakeCamera`, `RecordBadge`, `frames.py`, `WorkArea`, `Question`, `PenSettings`, `WebcamPanel`, `test_webcam_panel.py`, `_EditOverlay`, `.__init__`, `models.py`, `_TaggedCamera`, `DprArea`, `test_work_area_set_families_scales_its_own_labels_but_not_logo_monogram`?**
  _High betweenness centrality (0.164) - this node is a cross-community bridge._
- **Why does `WorkArea` connect `WorkArea` to `frames.py`, `Zone`, `DrawingCanvas`, `.layout`, `test_work_area.py`, `MainWindow`, `.set_font_scale`, `FontFamilies`, `_StopWorker`, `.inner_rect`, `_EditOverlay`, `models.py`, `._place_eye_button`, `DprArea`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `ToolBar`, `QuestionFlow`, `QuestionZone`, `AppSettings`, `FontFamilies`, `_StopWorker`, `HintZone`, `PenSettingsDialog`, `app.py`, `SettingsDialog`, `SessionStore`, `FakeCamera`, `RecordBadge`, `WorkArea`, `Question`, `recorder.py`, `PenSettings`, `WebcamPanel`, `models.py`, `.apply_ui_settings`, `Recorder`, `._on_record_stopped`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 36 inferred relationships involving `FontFamilies` (e.g. with `FrameContext` and `FrameSpec`) actually correct?**
  _`FontFamilies` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `MainWindow` (e.g. with `PenSettings` and `Question`) actually correct?**
  _`MainWindow` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `AppSettings` (e.g. with `ChromaParams` and `FrameStyle`) actually correct?**
  _`AppSettings` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `WorkArea` (e.g. with `MainWindow` and `_NoCamera`) actually correct?**
  _`WorkArea` has 10 INFERRED edges - model-reasoned connections that need verification._