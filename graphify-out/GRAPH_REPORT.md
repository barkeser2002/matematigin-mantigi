# Graph Report - arayuz-soru-sistemi-metematigin-mantigi  (2026-09-08)

## Corpus Check
- 62 files · ~120,446 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 975 nodes · 2150 edges · 40 communities (36 shown, 4 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 174 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `74186b49`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- RecordRect
- support.js
- WorkArea
- DrawingCanvas
- ToolBar
- test_main_window.py
- MainWindow
- QuestionFlow
- QuestionZone
- AppSettings
- ImageSlot
- FontFamilies
- WebcamPanel
- test_canvas.py
- File Structure
- HintZone
- PenSettings
- ChromaParams
- cursors.py
- CameraWorker
- camera_worker.py
- Question
- load_questions
- app.py
- test_models.py
- SettingsDialog
- layout_model.py
- SessionStore
- Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu)
- models.py
- DeadCamera
- .__init__
- list_cameras
- test_stroke.py
- ClickableLabel
- _NoCamera
- build_mac.sh
- matematigin-mantigi

## God Nodes (most connected - your core abstractions)
1. `FontFamilies` - 54 edges
2. `MainWindow` - 53 edges
3. `AppSettings` - 50 edges
4. `DrawingCanvas` - 46 edges
5. `QuestionFlow` - 41 edges
6. `ChromaParams` - 36 edges
7. `WorkArea` - 35 edges
8. `Zone` - 30 edges
9. `PenSettings` - 28 edges
10. `QuestionZone` - 28 edges

## Surprising Connections (you probably didn't know these)
- `test_build_window_offscreen()` --calls--> `FontFamilies`  [INFERRED]
  tests/test_models.py → src/matematigin_mantigi/ui/theme.py
- `DeadCamera` --uses--> `PenSettings`  [INFERRED]
  tests/conftest.py → src/matematigin_mantigi/core/models.py
- `FakeCamera` --uses--> `PenSettings`  [INFERRED]
  tests/conftest.py → src/matematigin_mantigi/core/models.py
- `test_pen_settings_round_trip_through_window()` --calls--> `PenSettings`  [EXTRACTED]
  tests/test_main_window.py → src/matematigin_mantigi/core/models.py
- `test_pen_settings_defaults()` --calls--> `PenSettings`  [EXTRACTED]
  tests/test_models.py → src/matematigin_mantigi/core/models.py

## Import Cycles
- None detected.

## Communities (40 total, 4 thin omitted)

### Community 0 - "RecordRect"
Cohesion: 0.06
Nodes (45): skipif, detect_encoder(), _even(), ffmpeg_args(), find_ffmpeg(), grab_screen(), list_audio_devices(), MssFfmpegRecorder (+37 more)

### Community 1 - "support.js"
Cohesion: 0.07
Nodes (51): boot(), cdnScriptFor(), collectProps(), compileAttr(), compileTemplate(), contentKey(), createComponentFactory(), createHelmetManager() (+43 more)

### Community 2 - "WorkArea"
Cohesion: 0.06
Nodes (21): QRect, _EditOverlay, InkLayer, Layout, QMouseEvent, QPainter, QWidget, PNG/JPG logo; boşsa veya yüklenemezse yuvarlak 'MM' monogramı. size: piksel… (+13 more)

### Community 3 - "DrawingCanvas"
Cohesion: 0.09
Nodes (19): QFont, QPaintEvent, QResizeEvent, _dot_tile(), DrawingCanvas, _grown(), QColor, QImage (+11 more)

### Community 4 - "ToolBar"
Cohesion: 0.06
Nodes (27): QAbstractButton, QFrame, QLabel, QWidget, Kayıt süresi araç çubuğunda sayar (kayda girmez): 'DURDUR · 01:23'., Bölge 9: dış araç çubuğu. Kayıtta görünmez., ToolBar, DotButton (+19 more)

### Community 5 - "test_main_window.py"
Cohesion: 0.06
Nodes (26): QPoint, QSize, test_eraser_cursor_scales_with_width(), test_laser_text_shape(), test_pen_cursor_is_pencil_icon_with_tip_hotspot(), test_retina_doubles_pixmap_keeps_hotspot(), test_pen_settings_round_trip_through_window(), test_tool_cursor_also_applies_over_zones() (+18 more)

### Community 6 - "MainWindow"
Cohesion: 0.08
Nodes (10): QMainWindow, Son kayıtta gerçekten yakalanan kare/sn (yazılan değil)., MainWindow, Path, Yazı aracının kutusu açıkken tek tuşlu kısayollar kutuya bırakılır., Ayarlardaki yazı tipi, yazma hızı, otomatik perde tonu ve görünürlükleri…, camera_source_factory: kamera indeksinden kaynak üretir; None ise kamera…, QWidget (+2 more)

### Community 7 - "QuestionFlow"
Cohesion: 0.10
Nodes (15): QObject, QuestionStatus, QuestionFlow, Soru akışı: sıra, durumlar, soru gizleme, ipucu gezinme ve açma durumu., Önceki sayfaya döner; durumları değiştirmez., test_empty_flow_is_safe(), test_hint_navigation_clamps(), test_initial_state() (+7 more)

### Community 8 - "QuestionZone"
Cohesion: 0.09
Nodes (20): QMouseEvent, QuestionZone, hzone(), qzone(), Çizim aracı aktifken (click-through) kart tıklaması açmaz; Tıkla aracında açar., test_animation_waits_until_zone_is_shown(), test_card_click_reveals_only_that_card(), test_click_skips_animation() (+12 more)

### Community 9 - "AppSettings"
Cohesion: 0.13
Nodes (10): QSettings, setter, AppSettings, Tahtadaki yazısal öğe görünürlüğü; anahtarlar VISIBILITY_KEYS içinde., test_defaults(), test_garbage_values_fall_back(), test_record_and_logo_settings(), test_round_trip_through_ini() (+2 more)

### Community 10 - "ImageSlot"
Cohesion: 0.13
Nodes (8): flushNow(), getSlot(), ImageSlot, load(), save(), setSlot(), toDataUrl(), createExternalModules()

### Community 11 - "FontFamilies"
Cohesion: 0.13
Nodes (19): Akıllı ipuçları bölgesi: ampul başlık, krem/turuncu kartlar. Kartlar…, Ana pencere: beyaz tahta + bölgeleri kurar ve sinyalleri bağlar. İş mantığı…, Soru bölgesi: kırmızı numara, kalın soru metni, görsel, A) B) C) D). Soru…, ⚙ Ayarlar: yazı tipi dosyası, soru yazma hızı, otomatik perde tonu, tahtadaki…, SettingsValues, build_stylesheet(), font(), FontFamilies (+11 more)

### Community 12 - "WebcamPanel"
Cohesion: 0.10
Nodes (11): FrameSource, Protocol, CameraView, QImage, QMouseEvent, QWidget, Kamera değişimi: eski iş parçacığı durur, yenisi aynı ayarlarla başlar., WebcamPanel (+3 more)

### Community 13 - "test_canvas.py"
Cohesion: 0.22
Nodes (25): alpha_at(), _drag(), draw_diagonal(), make(), tablet(), test_clear_is_undoable(), test_color_is_used(), test_eraser_clears() (+17 more)

### Community 14 - "File Structure"
Cohesion: 0.08
Nodes (24): Context, File Structure, Global Constraints, Matematiğin Mantığı — Görünüş Demosu (PyQt6) Implementation Plan, Next plans (not in this milestone), Task 10: Questions from the Excel template, Task 11: Question flow state machine, Task 12: Session snapshots (oturum/ PNG per question) (+16 more)

### Community 15 - "HintZone"
Cohesion: 0.14
Nodes (8): HintMaskMode, BulbIcon, HintCard, HintZone, QMouseEvent, QWidget, Basit ampul: sarı daire + koyu kenar + küçük duy., Yazı tipini değiştirir (Ayarlar > yazı tipi dosyası).

### Community 16 - "PenSettings"
Cohesion: 0.16
Nodes (13): QSlider, PenSettings, _card(), PenSettingsDialog, QColor, QDialog, QFrame, QVBoxLayout (+5 more)

### Community 17 - "ChromaParams"
Cohesion: 0.22
Nodes (21): apply_chroma_key(), apply_chroma_key_bgra(), ChromaParams, composite(), green_mask(), ndarray, Program içi yeşil perde: HSV tabanlı yumuşak anahtar, kenar yumuşatma, dökülme…, Ön plan alfası [0,1] float32. Ton uzaklığına göre yumuşak anahtar; doygunluk ve… (+13 more)

### Community 18 - "cursors.py"
Cohesion: 0.20
Nodes (19): QCursor, _clamp(), eraser_diameter(), pen_cursor_diameter(), pressure_width(), Saf çizim matematiği: basınç -> kalınlık, silgi ve imleç çapları., _blank(), cursor_for() (+11 more)

### Community 19 - "CameraWorker"
Cohesion: 0.12
Nodes (9): QThread, CameraWorker, FakeCamera, N adet sentetik BGR kare üretir; sonra None döndürür., test_dead_camera_reports_error_and_finishes(), test_stream_end_reports_error(), test_worker_auto_calibrates_key_hue(), test_worker_emits_keyed_frames() (+1 more)

### Community 20 - "camera_worker.py"
Cohesion: 0.15
Nodes (13): estimate_key_hue(), Karenin kenar şeridinden perde tonunu ölçer. Kenarların en az %60'ı doygun ve…, OpenCvSource, ndarray, QImage, Kamera iş parçacığı: OpenCV yakalama -> (isteğe bağlı) yeşil perde -> QImage…, OpenCV kamera kaynağı. İstenen indeks açılmazsa 0-3 arası diğer indeksleri de…, BGRA (saydam zemin) -> QImage ARGB32; derin kopya. (+5 more)

### Community 21 - "Question"
Cohesion: 0.16
Nodes (15): Question, _clean(), extract_questions(), PdfImportError, Path, RuntimeError, PDF (yatay, sayfa başına 1 soru + 'AKILLI İPUÇLARI' kartları) -> Question…, Soruları tüm sütunlarla yazar. Görsel yolu xlsx klasörüne göre göreli ise öyle… (+7 more)

### Community 22 - "load_questions"
Cohesion: 0.21
Nodes (16): ensure_template(), load_questions(), Path, QuestionTemplateError, Excel şablonu: sütun doğrulama, örnek şablon üretme, soru yükleme/yazma., _text(), write_template(), test_blank_rows_skipped_and_missing_hints_dropped() (+8 more)

### Community 23 - "app.py"
Cohesion: 0.20
Nodes (12): Namespace, build_window(), load_questions_or_samples(), main(), parse_args(), Path, _qt_message_filter(), Bilinen zararsız Qt uyarılarını süzer; gerisini stderr'e yazar. (+4 more)

### Community 24 - "test_models.py"
Cohesion: 0.12
Nodes (3): Matematiğin Mantığı — grafik tablet ders anlatım uygulaması., test_build_window_offscreen(), test_pen_settings_defaults()

### Community 25 - "SettingsDialog"
Cohesion: 0.20
Nodes (8): QDialog, SettingsDialog, test_apply_emits_values(), test_camera_scan_fills_combo(), test_choose_font_file_and_default(), test_dialog_reflects_settings_and_returns_values(), test_logo_choose_and_clear(), test_record_and_logo_size_fields()

### Community 26 - "layout_model.py"
Cohesion: 0.30
Nodes (13): cell_size(), clamp(), from_json(), load_layout(), PanelGeom, pixel_rect(), Layout, Path (+5 more)

### Community 27 - "SessionStore"
Cohesion: 0.23
Nodes (8): datetime, Path, QImage, Soru başına tuval anlık görüntüsü: oturum/<zaman>/<id>_<nn>.png, SessionStore, test_snapshots_are_numbered_per_question(), test_unsafe_ids_are_sanitised(), white()

### Community 28 - "Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu)"
Cohesion: 0.15
Nodes (12): Bu sürümde taslak olan kısımlar, Kayıt, Kısayollar, macOS (hedef makine, XP-Pen), macOS paketleme (.app), Matematiğin Mantığı — grafik tablet ders uygulaması (beyaz tahta demosu), Oturum çıktıları, Soru şablonu ve PDF aktarımı (+4 more)

### Community 29 - "models.py"
Cohesion: 0.36
Nodes (8): Enum, next_shape(), Nib, Shape, Tool, QSettings üzerinde tipli ayarlar., Tahta çizim yüzeyi: tablet basıncı, fare geri dönüşü, silgi, lazer (sönen iz),…, str

### Community 30 - "DeadCamera"
Cohesion: 0.27
Nodes (7): fixture, dead_camera(), DeadCamera, fake_camera(), ini_settings(), sample_questions(), window()

### Community 31 - ".__init__"
Cohesion: 0.29
Nodes (5): QPushButton, Yazı tipini değiştirir (Ayarlar > yazı tipi dosyası)., _card(), QFrame, QVBoxLayout

### Community 32 - "list_cameras"
Cohesion: 0.32
Nodes (5): _backends(), CameraInfo, list_cameras(), Kamera keşfi: OpenCV ile indeksleri dener, kare veren cihazları listeler. Ad…, 0..max_index-1 indekslerini dener; açılıp kare verenleri döndürür (her biri…

### Community 35 - "ClickableLabel"
Cohesion: 0.50
Nodes (3): ClickableLabel, QLabel, QMouseEvent

## Knowledge Gaps
- **35 isolated node(s):** `build_mac.sh script`, `matematigin-mantigi`, `Çalıştırma`, `Testler`, `Tahta` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FontFamilies` connect `FontFamilies` to `RecordRect`, `WorkArea`, `_NoCamera`, `ToolBar`, `MainWindow`, `QuestionZone`, `WebcamPanel`, `HintZone`, `PenSettings`, `CameraWorker`, `app.py`, `test_models.py`, `SettingsDialog`, `DeadCamera`, `.__init__`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `MainWindow` connect `MainWindow` to `RecordRect`, `WorkArea`, `ToolBar`, `QuestionFlow`, `QuestionZone`, `AppSettings`, `FontFamilies`, `WebcamPanel`, `HintZone`, `PenSettings`, `CameraWorker`, `Question`, `app.py`, `SettingsDialog`, `SessionStore`, `models.py`, `DeadCamera`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `DrawingCanvas` connect `DrawingCanvas` to `test_canvas.py`, `WorkArea`, `FontFamilies`, `models.py`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `FontFamilies` (e.g. with `BulbIcon` and `HintCard`) actually correct?**
  _`FontFamilies` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `MainWindow` (e.g. with `PenSettings` and `Question`) actually correct?**
  _`MainWindow` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AppSettings` (e.g. with `ChromaParams` and `HintMaskMode`) actually correct?**
  _`AppSettings` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `DrawingCanvas` (e.g. with `Shape` and `Tool`) actually correct?**
  _`DrawingCanvas` has 5 INFERRED edges - model-reasoned connections that need verification._