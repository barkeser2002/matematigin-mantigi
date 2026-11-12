from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, qInstallMessageHandler
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMessageBox

from matematigin_mantigi import paths
from matematigin_mantigi.core import crash_log
from matematigin_mantigi.core.autostart import Autostart
from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question
from matematigin_mantigi.core.question_loader import backup_path, ensure_template, load_questions
from matematigin_mantigi.core.recorder import MssFfmpegRecorder, RecorderState, RecorderError
from matematigin_mantigi.core.session_store import SessionStore
from matematigin_mantigi.core.settings import AppSettings
from matematigin_mantigi.ui import error_notice, theme
from matematigin_mantigi.ui.camera_worker import OpenCvSource
from matematigin_mantigi.ui.main_window import MainWindow
from matematigin_mantigi.ui.question_editor import describe_load_error


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="matematigin-mantigi")
    p.add_argument("--sorular", help="Soru şablonu (.xlsx) yolu")
    p.add_argument("--kamera", type=int, default=None, help="Kamera indeksi (varsayılan: ayarlardan)")
    p.add_argument("--kamera-yok", action="store_true", help="Kamerayı açma")
    p.add_argument("--duzen", default=None, help="Düzen dosyası (varsayılan: veri klasöründe duzen.json)")
    p.add_argument("--baslangic", action="store_true",
                   help="Bilgisayar açılışında başlatıldı: seçili ekran geç hazır olabilir, bir süre beklenir (kayıt başlamaz)")
    return p.parse_args(argv[1:])


def load_questions_or_samples(template: Path) -> tuple[list[Question], bool]:
    """Soru dosyasını yükler (yoksa örnek şablonu yazar); (sorular, dosyadan_okundu) döner. Dosya okunamazsa (bozuk,
    yarım kalmış, eksik sütun, okunamayan yol; her türlü hata) dosya adı ve sebep söylenir, uygulama örnek sorularla
    açılır (#17): yalnız QuestionTemplateError yakalandığı için yarım kalmış bir xlsx uygulamayı bir daha hiç açılmaz
    yapıyordu. O zaman ikinci değer False: pencere ve editör bunu bilir, editör örnek soruları o dosyanın (ya da
    yedeğinin) gerçek sorularının üzerine yazmaz; dosya sonradan düzelirse onları yüklemeyi önerir (#4, Q1). Dosya
    yok ama yedeği ya da iCloud yer tutucusu duruyorsa örnek şablon yazılmaz (U2, _samples_for_missing_file)."""
    try:
        if not template.exists() and paths.missing_file_traces(template):
            return _samples_for_missing_file(template)
        return load_questions(ensure_template(template)), True
    except Exception as err:  # noqa: BLE001 - açılış hiçbir soru dosyası yüzünden düşmez
        crash_log.log_handled(err, "soru dosyası")
        text = f"Soru dosyası okunamadı: {template.name}\nKlasör: {template.parent}\nSebep: {describe_load_error(err)}"
        bak = backup_path(template)
        if bak.is_file():
            text += f"\n\nÖnceki sürümün yedeği: {bak.name} (adını {template.name} yapıp uygulamayı yeniden açın)."
        QMessageBox.warning(None, "Soru dosyası okunamadı", f"{text}\n\nÖrnek sorularla devam ediliyor.")
        return list(SAMPLE_QUESTIONS), False


def _samples_for_missing_file(template: Path) -> tuple[list[Question], bool]:
    """Soru dosyası klasörde yok ama gerçek soruları başka yerde: önceki sürümün yedeği (öğretmen bozuk dosyayı
    kaldırdı ya da taşıdı) ya da iCloud yer tutucusu (macOS 13 ve öncesinde iCloud dosyayı bu Mac'ten kaldırdı).
    Eskiden yerine örnek şablon sessizce yazılıyor (paketlide gömülü şablon kopyalanıyor) ve dosya 'okundu'
    sayılıyordu: editörün ilk Kaydet'i yedeği örneklerle eziyordu, gerçek sorular kayboluyordu (U2). Hiçbir şey
    yazılmaz; uygulama örnek sorularla açılır, sorular dosyadan okunmamış sayılır: editör yedeği yüklemeyi önerir."""
    lines = [f"Soru dosyası bulunamadı: {template.name}", f"Klasör: {template.parent}"]
    if paths.icloud_placeholder(template).exists():
        lines.append("Dosya bu bilgisayara henüz inmemiş, iCloud Drive'da duruyor: Finder'da açıp inmesini bekleyin, "
                     "sonra uygulamayı yeniden açın.")
    bak = backup_path(template)
    if bak.exists():
        lines.append(f"Önceki sürümün yedeği var: {bak.name} (adını {template.name} yapıp uygulamayı yeniden açın; "
                     "soru editörü de yedekteki soruları yüklemeyi önerir).")
    QMessageBox.warning(None, "Soru dosyası bulunamadı", "\n".join(lines) + "\n\nÖrnek sorularla devam ediliyor; "
                        "örnekler gerçek soruların yerine yazılmaz.")
    return list(SAMPLE_QUESTIONS), False


def build_window(args: argparse.Namespace, fam: theme.FontFamilies, settings: AppSettings | None = None,
                 autostart: Autostart | None = None) -> MainWindow:
    settings = settings or AppSettings()
    autostart = autostart or Autostart()
    autostart.repair()          # uygulama güncellendi/taşındıysa AÇIK olan kayıt güncel yola sessizce düzelir
    state = settings.session_state            # kapanıştaki oturum; pencere kurulurken eskisinin üzerine yazılmasın
    session_notice = None
    fallback_data = None
    user_data_denied = False
    if paths.is_frozen():
        # .app: şablon + görseller yalnız gerçek soru dosyası/yedeği yokken kopyalanır.
        try:
            paths.ensure_user_data()
            if sys.platform == "darwin" and not settings.record_folder:
                with tempfile.TemporaryFile(dir=paths.data_dir()):
                    pass
        except PermissionError:
            if sys.platform != "darwin":
                raise
            if settings.record_folder:
                user_data_denied = True
                detail = ("Seçtiğiniz kayıt klasörü değiştirilmedi. Soru dosyası ve tahta görüntüleri için "
                          "Belgeler erişimi gerekir; varsayılan soru dosyası yerine örnek sorular açılacak.")
            else:
                fallback_data = Path.home() / "Movies" / paths.APP_FOLDER_NAME
                try:
                    paths.ensure_user_data(fallback_data)
                    with tempfile.TemporaryFile(dir=fallback_data):
                        pass
                    detail = f"Bu oturumda kayıtlar ve uygulama verileri şu yedek klasöre yazılacak:\n{fallback_data}"
                except PermissionError:
                    user_data_denied = True
                    detail = (f"Yedek klasöre de yazılamıyor:\n{fallback_data}\n"
                              "Örnek sorularla devam ediliyor; kayıt için Ayarlar'dan erişilebilir bir klasör seçin. "
                              "Tahta görüntülerini kaydetmek için klasör erişim iznini düzeltin.")
            QMessageBox.warning(None, "Belgeler klasörüne erişilemiyor",
                                "Belgeler (Documents) klasörüne erişim izni verilmedi.\n" + detail + "\n\n"
                                "İzni Sistem Ayarları › Gizlilik ve Güvenlik › Dosyalar ve Klasörler'den değiştirebilirsiniz.")
    template = (Path(args.sorular) if args.sorular else
                fallback_data / paths.TEMPLATE_NAME if fallback_data else paths.default_template_path())
    if not args.sorular and state.questions_file:
        # Son oturumda başka bir soru dosyası açıksa (örn. --sorular) o dosyayla devam; yoksa varsayılan + kısa uyarı.
        try:
            saved_file = Path(state.questions_file)
            if saved_file.is_file():
                template = saved_file
            else:
                session_notice = "Son açık soru dosyası bulunamadı; varsayılan soru dosyası açıldı."
        except OSError:
            session_notice = "Son açık soru dosyasına erişilemedi; varsayılan soru dosyası açıldı."
    questions, from_file = ((list(SAMPLE_QUESTIONS), False) if user_data_denied and not args.sorular
                            else load_questions_or_samples(template))
    if args.kamera is not None:
        settings.camera_index = args.kamera
    factory = None if args.kamera_yok else (lambda index: OpenCvSource(index))
    layout_path = (Path(args.duzen) if args.duzen else
                   fallback_data / "duzen.json" if fallback_data else paths.default_layout_path())
    store = SessionStore(fallback_data / "oturum") if fallback_data else SessionStore()
    default_record_folder = store.session_dir
    def recording_folder() -> Path:
        nonlocal default_record_folder
        configured = settings.record_folder
        if not configured:
            try:
                default_record_folder.mkdir(parents=True, exist_ok=True)
                if sys.platform == "darwin" and paths.is_frozen():
                    with tempfile.TemporaryFile(dir=default_record_folder):
                        pass
            except PermissionError:
                if sys.platform != "darwin" or not paths.is_frozen():
                    raise
                fallback = Path.home() / "Movies" / paths.APP_FOLDER_NAME / "oturum" / store.session_dir.name
                fallback.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryFile(dir=fallback):
                    pass
                default_record_folder = fallback
                QMessageBox.warning(None, "Kayıt klasörüne erişilemiyor",
                                    "Belgeler (Documents) klasörüne erişim izni verilmedi.\n"
                                    f"Varsayılan kayıt klasörü yerine şu yedek klasör kullanılacak:\n{fallback}")
            return default_record_folder
        folder = Path(configured)
        if not folder.is_absolute() or not folder.is_dir():
            raise RecorderError(f"Kayıt klasörü bulunamadı veya geçersiz: {configured}\nAyarlar'dan erişilebilir bir klasör seçin.")
        return folder
    recorder = MssFfmpegRecorder(recording_folder, create_output_dir=False, fps=settings.record_fps,
                                 audio_device=settings.audio_device or None, out_height=settings.record_height)
    # Kayıtlı soru konumu yalnız AYNI soru dosyası açıldıysa geri gelir (başka dosyanın kimlikleriyle karışmasın).
    restore_questions = (from_file and not session_notice
                         and str(template) == (state.questions_file or str(paths.default_template_path())))
    win = MainWindow(fam, questions, settings, recorder, store, factory, layout_path, questions_path=template,
                     questions_from_file=from_file, session_state=state if restore_questions else None,
                     startup=args.baslangic, autostart=autostart)
    win.resize(1920, 1080)
    win.restore_window_state(state)
    if session_notice:
        win.show_session_notice(session_notice)
    return win


_HARMLESS_QT_MESSAGES = ("cached device pixel ratio value was stale",
                         "QFont::setPointSize: Point size <= 0")      # piksel boyutlu uygulama fontuyla combo kutusu


def _qt_message_filter(mode, context, message: str) -> None:
    """Bilinen zararsız Qt uyarılarını süzer; gerisini stderr'e yazar."""
    if any(s in message for s in _HARMLESS_QT_MESSAGES):
        return
    print(message, file=sys.stderr)


def _recorded_rect(win: MainWindow) -> QRect:
    """Kayda giren sahne (ekran koordinatı): uyarı kutusu bununla en az çakışacak yere konur."""
    x, y, w, h, _ = win.work_area.recording_rect()
    return QRect(x, y, w, h)


def _toolbar_bottom(win: MainWindow) -> QRect:
    """Araç çubuğunun altı (uyarı şeridi, kayıt düğmesi ve yazısı; ekran koordinatı): uyarı kutusu burayı örtmez,
    öğretmen kaydı başlatıp durdurabilsin ve şeridi görsün."""
    tb = win.toolbar
    top = tb.alert_label.y() if tb.alert_label.isVisible() else tb.record_button.y()
    return QRect(tb.mapToGlobal(QPoint(0, top)), QSize(tb.width(), tb.height() - top))


def _wire_notice(notice: error_notice.ErrorNotice, win: MainWindow) -> None:
    """Uyarı kutusunu pencereye bağlar: kayıt dışında sahneye ve araç çubuğunun altına değmeyen yere konur; kayıt
    sürerken (kaydedilirken de) hiç açılmaz, araç çubuğunun şeridine yazar, kayıt bitince açılır. Kaydedici
    testlerde/ayarlarda değişebildiği için durum her seferinde pencereden okunur. Uygulama kapanırken (aboutToQuit)
    kutu pencereyle bütün bağı keser: yorumlayıcı sonlanırken silinen pencere kutunun Python koduna uğramaz (U1)."""
    notice.set_anchor(win, avoid=lambda: _recorded_rect(win), keep_clear=lambda: _toolbar_bottom(win))
    notice.set_recording_route(is_recording=lambda: win.recorder.state is not RecorderState.IDLE,
                               show_alert=lambda text: win.toolbar.set_alert(error_notice.ALERT_KEY, text))
    # Kaydedici ilk kareyi start() içinde yakalar: açık kutu start()'tan hemen önce gizlenir, ilk karelere girmez.
    win.recordingAboutToStart.connect(notice.prepare_recording)
    # Kayıt rozeti kayıt başlar başlamaz (sonra saniyede bir) tik atar: kayıt başlangıcı ve bitişi yoklamayı
    # beklemeden de görülür.
    win.badge.ticked.connect(lambda _seconds: notice.recording_changed())
    QApplication.instance().aboutToQuit.connect(notice.release)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    # Önce hata kancası: açılış hataları da hatalar.log'a düşer; yuvadaki yakalanmamış istisna PyQt6'nın qFatal'ıyla
    # uygulamayı (ve süren kaydı) öldürmez. Qt'ye dokunmadığı için QApplication'dan önce kurulabilir.
    crash = crash_log.install(paths.default_error_log_path())
    qInstallMessageHandler(_qt_message_filter)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv)
    notice = error_notice.install()            # GUI iş parçacığında; kancanın modal olmayan uyarısı buradan açılır
    crash.notify = notice.post
    if hasattr(app.styleHints(), "setColorScheme"):      # Qt >= 6.8
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)   # tema açık renkli; sistem koyu modu paleti ezmesin
    app.setApplicationName("Matematiğin Mantığı")
    fam = theme.load_fonts(paths.FONTS_DIR)
    app.setFont(theme.font(fam, 13))            # varsayılan aile; stil sayfası font-family kullanmaz
    app.setStyleSheet(theme.build_stylesheet(fam))
    win = build_window(parse_args(argv), fam)
    # Ana pencere kapanınca süreç biter. Qt'nin kendi çıkışı (son pencere kapandı) kuyruğa konan bir olaydır; o
    # işlenmeden gösterilen herhangi bir pencere onu kuyruktan siler: 'Durdur ve çık'tan sonra gizli ana pencerenin
    # çocuğu olarak yeniden açılan uyarı kutusu pencereyi kapatıp süreci görünmez bırakıyordu (Windows'ta arka plan
    # süreci). exit() pencere sormaz; kamera ve ayarlar closeEvent'te kapandı.
    win.closed.connect(lambda: QTimer.singleShot(0, lambda: app.exit(0)))
    win.show()
    _wire_notice(notice, win)          # gösterildikten sonra: kutu pencerenin (artık kurulu) görünürlüğünü izler
    return app.exec()
