"""Kayıt: RecordRect + Recorder protokolü, NullRecorder (test/taslak) ve MssFfmpegRecorder (gerçek kayıt).

MssFfmpegRecorder: ekranın tahta bölgesini mss ile yakalar (yakalama iş parçacığı), sabit tempolu yazıcı iş
parçacığı en yeni kareyi boru ile ffmpeg'e verir (yakalama yavaşsa kare çoğaltılır; süre duvar saatiyle aynı kalır).
Ses ffmpeg'e DEĞİL, uygulama içinde PortAudio ile WAV'a alınır (core/audio_capture.py); durdurunca ffmpeg videoyu
kopyalayıp sesi ölçülen zaman farkıyla hizalayarak tek MP4'e birleştirir. Birleştirme videoyu asla kısaltmaz: eksik
ses sessizlikle dolar, birleşik dosyanın süresi ölçülür; kısa çıkarsa ya da ölçülemezse ham video ve WAV silinmez.

Durum: IDLE -> RECORDING -> FINALIZING -> IDLE. Kapanış (ffmpeg kapanışı + ses birleştirme) uzun derste onlarca
saniye sürer; bu sürede yeni kayıt başlamaz. Her kaydın yolları ve sonuçları kendi _Session nesnesindedir.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Callable, Protocol

import numpy as np

from matematigin_mantigi.core import crash_log
from matematigin_mantigi.core.audio_capture import AudioCapture, AudioResult


def _even(n: int) -> int:
    return n - (n % 2)


@dataclass(frozen=True)
class RecordRect:
    x: int
    y: int
    width: int
    height: int
    dpr: float = 1.0

    def physical(self) -> "RecordRect":
        s = self.dpr
        return RecordRect(round(self.x * s), round(self.y * s),
                          _even(round(self.width * s)), _even(round(self.height * s)), 1.0)

    def to_mss(self) -> dict[str, int]:
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}


def record_rect_for(rect5: tuple[int, int, int, int, float]) -> RecordRect:
    x, y, w, h, dpr = rect5
    return RecordRect(int(x), int(y), int(w), int(h), float(dpr))


class RecorderState(Enum):
    """Kaydedicinin durumu. FINALIZING: görüntü alımı durdu ama dosya henüz bitmedi (ffmpeg kapanışı, ses
    birleştirme); bu sürede yeni kayıt başlamaz."""
    IDLE = "idle"
    RECORDING = "recording"
    FINALIZING = "finalizing"


class RecorderError(RuntimeError):
    pass


class RecordingResult(RecorderError):
    """hatalar.log'daki kayıt sonucu girdisi: bir kaydın hatası, ses ve görüntü uyarısı, tek satır (fırlatılmaz)."""


class Recorder(Protocol):
    def start(self, rect: RecordRect, fps: int = 60) -> None: ...
    def stop(self) -> Path | None: ...
    @property
    def state(self) -> RecorderState: ...
    @property
    def is_recording(self) -> bool: ...
    @property
    def elapsed_seconds(self) -> int: ...


class NullRecorder:
    stop_is_quick = True

    def __init__(self) -> None:
        self.last_rect: RecordRect | None = None
        self.fps = 60
        self.started_at: float | None = None

    def start(self, rect: RecordRect, fps: int = 60) -> None:
        if self.started_at is not None:
            raise RecorderError("Kayıt zaten sürüyor")
        self.last_rect, self.fps, self.started_at = rect, fps, time.monotonic()

    def stop(self) -> Path | None:
        self.started_at = None
        return None

    @property
    def state(self) -> RecorderState:
        """Durdurma anında biter: FINALIZING'e hiç girmez."""
        return RecorderState.IDLE if self.started_at is None else RecorderState.RECORDING

    @property
    def is_recording(self) -> bool:
        return self.started_at is not None

    @property
    def elapsed_seconds(self) -> int:
        return 0 if self.started_at is None else int(time.monotonic() - self.started_at)


# --- gerçek kayıt ------------------------------------------------------------------

DISK_HINT = "Diskte boş yer ve kayıt klasörüne yazma izni olduğunu kontrol edin."
CREATE_NO_WINDOW = 0x08000000           # subprocess.CREATE_NO_WINDOW (yalnız Windows'ta tanımlı)


def no_window(platform: str | None = None) -> dict:
    """subprocess çağrısına eklenecek argüman: Windows'ta alt süreç konsol penceresi açmasın (paketli, konsolsuz
    .exe'de her ffmpeg çağrısı siyah bir pencere yakıp söndürüyordu: kayıt, birleştirme, süre ölçümü, kodlayıcı
    denemesi, kamera listesi). Başka sistemlerde boş. Bütün ffmpeg çağrıları bunu kullanır (#10; test kilitler)."""
    return {"creationflags": CREATE_NO_WINDOW} if (platform or sys.platform) == "win32" else {}


def find_ffmpeg() -> str | None:
    """Önce imageio-ffmpeg ile gelen ikili (paketlenmiş uygulamada da var), sonra PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - kütüphane yoksa veya ikili indirilemediyse PATH'e düş
        return shutil.which("ffmpeg")


def _new_mss():
    import mss
    return mss.MSS() if hasattr(mss, "MSS") else mss.mss()      # mss 10: MSS sınıfı; eski sürüm: mss()


def grab_screen(rect: RecordRect, sct=None) -> np.ndarray:
    """Ekran bölgesini BGRA uint8 HxWx4 olarak yakalar (mss). Windows'ta fiziksel piksel bekler."""
    own = sct is None
    if own:
        sct = _new_mss()
    try:
        shot = sct.grab(rect.to_mss())
        return np.frombuffer(shot.bgra, np.uint8).reshape(shot.height, shot.width, 4)
    finally:
        if own:
            sct.close()


RESOLUTIONS: tuple[tuple[str, int], ...] = (("Doğal (ekran)", 0), ("1080p", 1080), ("2K (1440p)", 1440), ("4K (2160p)", 2160))


ENCODER_ARGS: dict[str, list[str]] = {
    "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-b:v", "16M", "-realtime", "1"],
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0"],
    "h264_qsv": ["-c:v", "h264_qsv", "-global_quality", "23"],
    "h264_amf": ["-c:v", "h264_amf", "-quality", "speed"],
    "libx264": ["-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-crf", "22"],
}
_PREFERRED = {"darwin": ["h264_videotoolbox"], "win32": ["h264_nvenc", "h264_qsv", "h264_amf"]}
_encoder_cache: dict[str, str] = {}


def detect_encoder(exe: str, platform: str | None = None, runner=None) -> str:
    """Kullanılabilir ilk donanım H.264 kodlayıcısı; her aday 1 karelik deneme kodlamasıyla doğrulanır."""
    platform = platform or sys.platform
    key = f"{exe}|{platform}"
    if key in _encoder_cache and runner is None:
        return _encoder_cache[key]

    def default_runner(cmd: list[str]) -> int:
        try:
            return subprocess.run(cmd, capture_output=True, timeout=20, **no_window()).returncode
        except (OSError, subprocess.SubprocessError):
            return 1
    run = runner or default_runner
    chosen = "libx264"
    for enc in _PREFERRED.get(platform, []):
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=256x144:r=30",
               "-frames:v", "2", *ENCODER_ARGS[enc], "-f", "null", "-"]
        if run(cmd) == 0:
            chosen = enc
            break
    if runner is None:
        _encoder_cache[key] = chosen
    return chosen


def ffmpeg_args(exe: str, width: int, height: int, fps: int, out: Path,
                platform: str | None = None, out_height: int = 0, encoder: str = "libx264") -> list[str]:
    """Video ffmpeg komutu: ham BGRA kareler stdin'den, H.264 MP4 (ses yok; ses ayrı alınıp sonda birleştirilir).
    Giriş kuyruğu bilerek küçük (8 kare): Retina'da kare ~20 MB; büyük kuyruk belleği şişirir. Kodlayıcı geride
    kalırsa geri basınç Python yazıcısına ulaşır, o da kareyi çoğaltarak süreyi korur.
    +faststart YOK: ffmpeg onunla EOF'tan sonra bütün dosyayı yeniden yazar (moov'u başa taşımak için 7 GB oku + yaz,
    yavaş diskte dakikalar; kare sayısı da dosya boyu da değişmez), kapanış bunu 'yanıt vermiyor' sanıp bütün dersi
    kaybettirebilirdi. moov sona yazılır (EOF'tan sonra saniyeler); faststart yalnız birleşik dosyada (mux_args)."""
    args = [exe, "-y", "-hide_banner", "-loglevel", "warning", "-nostats", "-thread_queue_size", "8",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
    if out_height and out_height != height:
        args += ["-filter_threads", "4", "-vf", f"scale=-2:{out_height}:flags=bilinear"]
    args += [*ENCODER_ARGS.get(encoder, ENCODER_ARGS["libx264"]), "-pix_fmt", "yuv420p",
             "-r", str(fps), "-fps_mode", "cfr", str(out)]
    return args


PAD_MARGIN_S = 1.0      # ses dolgusu videodan bu kadar uzun: -shortest dosyayı her zaman videonun sonunda bitirir
MIC_GAP_S = 2.0         # ses videodan bundan fazla erken bitiyorsa mikrofon kayıt sırasında kesilmiştir
SHORT_MUX_S = 1.0       # birleşik dosya videodan bundan fazla kısaysa (kısa kayıtta: sürenin 1/4'ü) ham dosyalar kalır
TAIL_KEEP_S = 0.25      # video durdurma anından bundan fazla erken bittiyse birleştirme sesin ucunu korur (end_s)
STOP_DEBT_S = 2.0       # durdurmada yazıcının borcu bundan küçükse yazılır (kısa takılma), büyükse hiç yazılmaz
LAG_START_S = 5.0       # kodlayıcı kaydın ilk bu kadar saniyesinde geride kaldıysa görüntü uyarısı 'kayıt boyunca' der

# Kapanışın her adımı sınırlı; testler bu sabitleri kısaltır. ffmpeg ancak İLERLEMİYORSA öldürülür: yazıcı WRITER_JOIN_S
# boyunca tek kare yazamadıysa (ffmpeg stdin'i okumuyor: donan kodlayıcı, takılan disk) ya da EOF'tan sonra
# FFMPEG_EXIT_S boyunca dosyaya tek bayt yazılmadıysa. Yavaş ama okuyan/yazan ffmpeg beklenir: öldürülen ffmpeg moov'u
# yazamaz, videonun TAMAMI açılmaz (K1). Öldürülünce yazıcı kırılan borudan KILL_JOIN_S içinde çıkar.
WRITER_JOIN_S = 10.0    # kapanışta yazıcının bir kareyi daha yazabilmesi için beklenen süre (ilerleme penceresi)
KILL_JOIN_S = 2.0       # yanıt vermeyen ffmpeg öldürüldükten sonra yazıcının çıkması için süre
FFMPEG_EXIT_S = 60.0    # stdin kapandıktan sonra ffmpeg'in dosyaya hiç yazmadan geçirebileceği en uzun süre
FFMPEG_EXIT_MAX_S = 600.0   # EOF'tan sonra ilerlese de en çok bu kadar beklenir (moov sonda: gerçekte saniyeler)
AUDIO_STOP_S = 25.0     # mikrofonun kapanması (AudioCapture.stop: akış en çok 5 sn, WAV yazıcısı en çok 15 sn)
DURATION_TIMEOUT_S = 30.0   # media_duration: başlık okuma
MUX_MIN_S = 120.0       # birleştirmenin en kısa zaman aşımı; uzun derste kayıt süresinin iki katı


def _mux_timeout(duration: float) -> float:
    """Birleştirmenin zaman aşımı. 60 dk'lık derste 2 saat: 7 GB'ın kopyası + faststart (bir kez daha oku/yaz) yavaş
    harici diskte (~80 MB/sn) ~6 dk sürer. Aşılırsa ham dosyalar kalır (_mux_failed), ders kaybolmaz."""
    return max(MUX_MIN_S, duration * 2)


def _close_limit(duration: float) -> float:
    """Kapanışın en uzun süresi: adımların kendi sınırlarının toplamı (+ pay). Kapanışı bekleyen ikinci stop() bundan
    uzun beklemez; kapanış meşru biçimde sürerken de vazgeçmez. Durdurulan yazıcı en çok bir pencere borç yazar, sonra
    son kareleri (üç ilerleme penceresi); süre ölçümü en çok üç kez (ara video, birleşik dosya, bozuk videonun
    denetimi)."""
    return (3 * WRITER_JOIN_S + KILL_JOIN_S + AUDIO_STOP_S + FFMPEG_EXIT_MAX_S + 3 * DURATION_TIMEOUT_S
            + _mux_timeout(duration) + 30.0)


def mux_args(exe: str, video: Path, audio: Path, out: Path, offset_s: float,
             asetrate: int | None = None, out_rate: int = 48000, video_s: float | None = None,
             end_s: float | None = None) -> list[str]:
    """Video (kopya) + WAV -> MP4 (AAC). offset_s > 0: ses videodan önce başladı, başı atılır (-ss);
    offset_s < 0: ses geç başladı, geciktirilir (-itsoffset). asetrate: ölçülen gerçek örnekleme hızı
    (mikrofon saati kaymasını düzeltir; ppm düzeyi, duyulmaz). Ses girişi -f wav ile açılır: biçim tahmine
    bırakılırsa ffmpeg 9.0.2 düz WAV'ı mpegts sanıp düşüyor (imageio-ffmpeg 0.8.0).
    video_s: videonun süresi. Verilince ses, zincirin sonunda (hız düzeltmesi ve fade-in'den sonra) sessizlikle
    video_s + PAD_MARGIN_S'ye dek doldurulur (apad), -shortest dosyayı videonun sonunda bitirir: mikrofon kayıt
    ortasında kesilse de video kısalmaz (#1). Dolgu bilerek sınırlı: sınırsız apad + -shortest + -c:v copy ffmpeg
    7.0.2'de hiç bitmiyor (ses kodlayıcısı sonsuz sessizlik üretirken çıktıya tek paket yazılmıyor).
    end_s: video durdurma anından erken bittiyse (kodlayıcı yetişemedi) çıktının sonu, sesin durdurmaya dek süren
    ucu. -shortest yerine -t: ses kesilmez, video izi kısa kalır (oynatıcı son kareyi tutar)."""
    args = [exe, "-y", "-hide_banner", "-loglevel", "warning", "-nostats", "-i", str(video)]
    if offset_s >= 0:
        args += ["-ss", f"{offset_s:.3f}", "-f", "wav", "-i", str(audio)]
    else:
        args += ["-itsoffset", f"{-offset_s:.3f}", "-f", "wav", "-i", str(audio)]
    af = ["afade=t=in:st=0:d=0.01"]                  # -ss kesim noktasındaki tek örneklik tıkı yumuşatır (10 ms)
    if asetrate:
        af = [f"asetrate={asetrate}", f"aresample={out_rate}", *af]
    pad_to = end_s if end_s is not None else video_s
    if pad_to is not None:
        af.append(f"apad=whole_dur={pad_to + PAD_MARGIN_S:.3f}")
    args += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", ",".join(af)]
    args += ["-ar", str(out_rate), "-c:a", "aac", "-b:a", "160k"]
    args += ["-t", f"{end_s:.3f}"] if end_s is not None else ["-shortest"]
    args += ["-movflags", "+faststart", str(out)]
    return args


_DURATION = re.compile(rb"^\s*Duration: (\d+):(\d\d):(\d\d(?:\.\d+)?)", re.M)    # kendi satırı: etiket değeri değil


def media_duration(exe: str, path: Path, timeout: float = DURATION_TIMEOUT_S) -> float | None:
    """Dosyanın süresi (sn), ffmpeg'in giriş başlığı dökümünden ('Duration: 01:00:00.00'); ffprobe paketle gelmiyor.
    MP4'te yalnız moov kutusu okunur: video çözülmez, paketler taranmaz. 60 dakikalık 60 kare/sn dosyada ~0,1 sn
    (paketleri okumak 600 MB'ta ~6 sn sürüyor; 1440p60 bir ders ~7 GB). Okunamazsa ya da süre yoksa (N/A) None.
    WAV -f wav ile açılır: ffmpeg 9.0.2 düz WAV'ı biçim tahminiyle tanımıyor (mux_args'taki gibi)."""
    fmt = ["-f", "wav"] if Path(path).suffix.lower() == ".wav" else []
    try:
        res = subprocess.run([exe, "-hide_banner", "-nostdin", *fmt, "-i", str(path)], capture_output=True,
                             timeout=timeout, **no_window())
    except (OSError, subprocess.SubprocessError):
        return None
    m = _DURATION.search(res.stderr)                 # çıktı dosyası verilmediği için ffmpeg 1 ile çıkar: beklenen
    if m is None:
        return None
    h, mi, sec = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(sec)


def clock_text(seconds: float) -> str:
    """Süre okunur 'dakika:saniye' (toplam dakika, saniye aşağı yuvarlanır): 1215.7 -> '20:15', 4530 -> '75:30'."""
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


def span_text(seconds: float) -> str:
    """Kısa bir süre okunur: '1 sn', '12 sn', dakikadan uzunsa '2 dk 15 sn' (en az 1 sn)."""
    s = max(1, round(seconds))
    return f"{s} sn" if s < 60 else f"{s // 60} dk {s % 60} sn"


def encoder_lag_text(skipped_s: float, lag_from_s: float, sound: bool, tail_kept: bool) -> str:
    """Görüntü kodlayıcısı gerçek zamana yetişemeyen kaydın uyarısı (video_warning), izleyicinin göreceğiyle. Geride
    kalan yazıcı aynı kareyi art arda yazar: görüntü slayt gösterisi gibi donarak ilerler ve sesin önüne geçer; arası
    sona doğru durdurmadaki borca (skipped_s) dek açılır, video o kadar erken biter (sesin ucu korunduysa son kare ses
    bitene dek ekranda kalır). lag_from_s: yazıcının tempoda olduğu son an (kaydın başından); kodlayıcı ancak sonra
    geride kaldıysa (ısınan makine, takılan disk) öncesi sağlamdır, metin o dakikayı söyler. sound: kayıtta ses var;
    yoksa sesten söz edilmez. Eski metin ('görüntü takılmış olabilir') hasarı küçümsüyordu (son inceleme s8)."""
    span = span_text(skipped_s)
    when = "kayıt boyunca" if lag_from_s <= LAG_START_S else f"{clock_text(lag_from_s)}. dakikadan sonra"
    text = f"Görüntü kodlayıcısı kayda yetişemedi: görüntü {when} donarak ilerledi"
    if sound:
        text += f", sesle arası sona doğru {span}'ye çıktı"
    text += (f"; görüntü {span} erken bitiyor, son kare ses bitene dek ekranda kalıyor" if tail_kept
             else f"; video {span} erken bitiyor")
    return text + " (30 kare/sn ya da daha düşük çözünürlük deneyin)"


def audio_end_in_video(audio: AudioResult, offset_s: float, asetrate: int | None = None) -> float:
    """Sesin birleşik dosyada (videonun zaman ekseninde) bittiği an, sn. offset_s > 0 ise baştan atılır (-ss), < 0 ise
    ses geciktirilir (-itsoffset): ikisinde de 'süre - offset_s'. asetrate süreyi ölçülen gerçek hıza göre değiştirir
    (-ss payının hızla ölçeklenmesi ppm düzeyinde, yok sayılır)."""
    rate = asetrate or audio.samplerate
    return (audio.samples / float(rate) if rate else 0.0) - offset_s


def mic_cut_text(video_s: float, audio_end_s: float) -> str | None:
    """Ses videodan MIC_GAP_S'den fazla erken bitiyorsa '<dk:sn>. dakikadan sonra ses yok', yoksa None. Pay: sürücü
    tamponu ve durdurma sırası yüzünden ses videodan biraz önce ya da sonra biter; bu bir kesilme değil. Payın
    altındaki çok kısa kayıtta uyarı çıkmaz (videonun kendisi korunur, yalnız bilgi eksik kalır)."""
    if video_s - audio_end_s <= MIC_GAP_S:
        return None
    return f"{clock_text(audio_end_s)}. dakikadan sonra ses yok"


def _joined(*parts: str | None) -> str | None:
    """Boş olmayan uyarıları '; ' ile birleştirir: sonraki bir uyarı öncekini silmesin."""
    return "; ".join(p for p in parts if p) or None


def _with_paragraph(text: str | None, more: str) -> str:
    """Hata metnine yeni paragraf ekler: önceki sebep silinmesin."""
    return f"{text}\n\n{more}" if text else more


def exception_text(err: BaseException) -> str:
    """İstisnanın okunur özeti, hiçbir zaman boş değil: 'PermissionError: [Errno 13] … : yol'; mesajsızsa 'OSError()'
    (str(OSError()) boştur, arayüz hiçbir şey göstermiyordu)."""
    text = str(err)
    return f"{type(err).__name__}: {text}" if text else repr(err)


def _file_size(path: Path) -> int:
    """Dosyanın boyu (bayt); yoksa ya da okunamazsa -1. Kapanışta ffmpeg'in ilerlediğini (dosyaya yazdığını) ölçer."""
    try:
        return path.stat().st_size
    except OSError:
        return -1


def sound_note(audio: AudioResult | None) -> str:
    """Ham ses dosyasının durumu, hata metinleri için: 'ses sağlam, 0:15' / 'ses 0:03, sonrası yazılamadı' / 'ses
    yok'. Öğretmen dosyanın içinde ne olduğunu açmadan bilsin."""
    if audio is None:
        return "ses dosyası"
    if audio.samples <= 0:
        return "ses yok"
    if audio.error:
        return f"ses {clock_text(audio.duration)}, sonrası yazılamadı"
    return f"ses sağlam, {clock_text(audio.duration)}"


# Saat kayması düzeltmesinin üst sınırı. Mikrofonun örnekleme saati bilgisayarın saatinden biraz farklı işler: kristal
# toleransı tipik ±20-100 ppm, ucuz USB/Bluetooth aygıtlarda en çok birkaç yüz ppm (60 dk'da 0,1-1 sn). Bundan büyük
# fark saat kayması değildir: kaybolan örnek (taşma, takılan sürücü) ya da kesilen mikrofon. Onu "düzeltmek" (asetrate)
# sesi bütün derse yayar: ton düşer, senkron giderek kayar, kesinti uyarısız kalırdı (O1: eski sınır %1'di, 620 sn'lik
# derste son 5 sn'lik kesik %0,8 çıkıp düzeltiliyordu).
MAX_DRIFT_PPM = 1000.0


def audio_rate_correction(result: AudioResult, min_duration: float = 600.0, min_ppm: float = 100.0) -> int | None:
    """Uzun kayıtta mikrofon saati ile bilgisayar saati arasındaki farkı ölç: örnek sayısı / ilk ile son örnek arasında
    geçen gerçek süre. Kısa kayıtta ölçüm gürültüsü (±30 ms) gerçek kaymadan büyük olduğu için uygulanmaz.
    Mikrofon durdurmadan MIC_GAP_S'den önce sustuysa uygulanmaz: eksik ses kayma değil kesintidir; birleştirme sesi
    olduğu gibi koyar, sonu sessizlikle dolar, uyarı kesildiği yeri söyler (O1). Ölçü son örneğe dek: sona yakın kısa
    bir susma (MIC_GAP_S'den kısa) ölçümü bozmaz."""
    if result.tail_gap > MIC_GAP_S:
        return None
    span = result.heard_duration
    if span < min_duration or result.samples <= 0:
        return None
    actual = result.samples / span
    ppm = abs(actual / result.samplerate - 1.0) * 1e6
    if ppm < min_ppm or ppm > MAX_DRIFT_PPM:
        return None
    return int(round(actual))


@dataclass(eq=False)
class _Session:
    """Tek bir kaydın her şeyi: yollar, ffmpeg süreci, mikrofon, iş parçacıkları, sonuç ve hata alanları.
    stop() yalnız kendi oturumuyla çalışır; start() yeni oturum kurar, kapanmakta olan eskisine dokunamaz. Böylece
    kapanan kaydın birleştirmesi yeni kaydın dosyalarını kullanamaz, hatası yeni kayda yazılmaz (#2)."""
    rect: RecordRect
    encoder: str
    final_path: Path                  # kayit_<saat>.mp4: kullanıcıya kalan dosya
    video_path: Path                  # mikrofon varsa ara kayit_<saat>.video.mp4, yoksa final_path
    log_path: Path                    # ffmpeg'in stderr'i
    wav_path: Path | None = None      # mikrofon varsa ara kayit_<saat>.wav
    proc: subprocess.Popen | None = None
    log_file: BinaryIO | None = None
    audio: AudioCapture | None = None
    thread: threading.Thread | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)    # kapanış bitti (bekleyen stop() için)
    latest: bytes = b""
    latest_lock: threading.Lock = field(default_factory=threading.Lock)
    fps: int = 60
    started_at: float = 0.0
    stopped_at: float = 0.0           # durdurma anı (monotonic): videonun duvar saatine göre bitmesi gereken yer
    video_t0: float | None = None
    on_time_at: float = 0.0           # yazıcının tempoda olduğu son an (monotonic): kodlayıcı ancak sonra geride kaldı
    duration: float = 0.0
    frames_written: int = 0
    frames_grabbed: int = 0
    frames_skipped: int = 0           # durdurmada yazılmayan borç (kodlayıcı geride kaldı): video bu kadar erken biter
    audio_result: AudioResult | None = None
    audio_error: str | None = None    # ses uyarısı (mikrofon açılmadı, kesildi, WAV yazılamadı): kayıt yine kaydedildi
    video_warning: str | None = None  # görüntü uyarısı (kodlayıcı yetişemedi): dosya tam, görüntü donarak ilerledi
    error: str | None = None
    failed: bool = False
    tail_kept: bool = False           # video erken bittiği için birleştirme sesin ucunu korudu (son kare ekranda)
    mic_lost: str | None = None       # mikrofon kapanmadı/kapatılamadı: ses dosyası birleştirilemez (sebep)


def _session_field(name: str, default=None) -> property:
    """Son kaydın (süren ya da biten) oturum alanını salt okunur açar; hiç kayıt yoksa default."""
    return property(lambda self: default if self._session is None else getattr(self._session, name))


class MssFfmpegRecorder:
    """Gerçek kaydedici. grabber(rect) -> BGRA kare; varsayılan ekran yakalama (mss).
    audio_device verilirse ses PortAudio ile alınır (audio_factory testte sahte yakalayıcı verir).
    Durum (IDLE -> RECORDING -> FINALIZING -> IDLE) ve geçerli oturum self._lock altında değişir. Kilit yalnız durum
    geçişlerinde ve start()'ın kısa açılış adımlarında tutulur; uzun kapanış (ffmpeg + birleştirme) kilitsiz koşar."""

    # Son kaydın sonuçları (arayüz ve testler okur); değerler o kaydın kendi _Session'ında durur.
    last_path = _session_field("final_path")
    last_rect = _session_field("rect")
    encoder = _session_field("encoder", "libx264")
    video_t0 = _session_field("video_t0")
    last_duration = _session_field("duration", 0.0)
    frames_written = _session_field("frames_written", 0)
    frames_grabbed = _session_field("frames_grabbed", 0)
    audio_result = _session_field("audio_result")
    audio_error = _session_field("audio_error")
    video_warning = _session_field("video_warning")
    error = _session_field("error")
    failed = _session_field("failed", False)

    def __init__(self, output_dir: Callable[[], Path], fps: int = 60, audio_device: str | None = None,
                 ffmpeg_exe: str | None = None, grabber: Callable[[RecordRect], np.ndarray] | None = None,
                 clock: Callable[[], datetime] = datetime.now, out_height: int = 1440,
                 audio_factory: Callable[[str | None], AudioCapture] | None = None):
        self._output_dir = output_dir
        self.fps = fps
        self.out_height = out_height
        self.audio_device = audio_device or None
        self._audio_factory = audio_factory or (lambda dev: AudioCapture(dev))
        self._ffmpeg_exe = ffmpeg_exe
        self._grabber = grabber
        self._clock = clock
        self._lock = threading.Lock()                # durum ve geçerli oturum yalnız bu kilitle değişir
        self._state = RecorderState.IDLE
        self._session: _Session | None = None        # süren ya da son biten kayıt

    # --- Recorder ---------------------------------------------------------------
    def start(self, rect: RecordRect, fps: int | None = None) -> None:
        """Yeni kayıt başlatır; yalnız IDLE'da. Önceki kayıt hâlâ kaydediliyorsa (FINALIZING) RecorderError: yeni
        kayıt eskisinin kapanışına karışmasın (#2). Hata olursa durum IDLE kalır, açılan dosya/mikrofon kapanır."""
        self._ensure_idle()                          # hızlı ret: ekranı yakalayıp kodlayıcı denemeden
        fps = fps or self.fps
        exe = self._ffmpeg_exe or find_ffmpeg()
        if not exe:
            raise RecorderError("ffmpeg bulunamadı (pip install imageio-ffmpeg)")
        grab_rect = rect.physical() if sys.platform == "win32" else RecordRect(rect.x, rect.y, rect.width, rect.height, 1.0)
        try:
            first = self._grab(grab_rect)
        except Exception as err:  # noqa: BLE001
            raise RecorderError(f"Ekran yakalanamadı: {err}") from err
        # Kodlayıcı denemesi ilk çağrıda saniyeler sürebilir: kilit dışında. Testte (grabber verilince) hızlı yol.
        encoder = detect_encoder(exe) if self._grabber is None else "libx264"
        with self._lock:
            self._ensure_idle()                      # asıl kontrol: açılış ile durum değişimi bölünmez
            self._session = self._open_session(exe, rect, grab_rect, first, fps, encoder)
            self._state, self.fps = RecorderState.RECORDING, fps

    def stop(self) -> Path | None:
        """Kaydı kapatır ve sesi videoyla birleştirir; son dosyanın yolunu döndürür. Uzun sürebilir (birkaç sn,
        uzun derste onlarca sn); arayüz bunu ayrı iş parçacığında çağırmalı. Kapanış kilitsiz koşar ve yalnız bu
        kaydın oturumuyla çalışır; her adımı sınırlı (ffmpeg yanıt vermezse öldürülür). Başka bir stop() zaten
        kapatıyorsa (pencere kapatma + işçi) onun bitmesini en çok kapanışın kendi sınırları kadar bekler; kapanış
        hatayla bittiyse RecorderError fırlatır (dönecek dosya eksik ya da hiç yok olabilir)."""
        with self._lock:
            s, state = self._session, self._state
            if state is RecorderState.RECORDING:
                self._state = RecorderState.FINALIZING
        if s is None:                                # hiç kayıt yapılmadı
            return None
        if state is RecorderState.RECORDING:
            try:
                self._finalize(s)
            except BaseException as err:             # sebep oturuma: arayüz ve kapanışı bekleyen stop() da görsün
                s.error = _with_paragraph(s.error, f"Kayıt kapatılamadı: {exception_text(err)}\n"
                                                   f"Kayıt klasörü: {s.final_path.parent}")
                raise
            finally:                                 # kapanış patlasa da FINALIZING'de takılı kalınmasın
                with self._lock:
                    self._state = RecorderState.IDLE
                self._log_result(s)
                s.finished.set()
        elif state is RecorderState.FINALIZING:
            limit = _close_limit(max(s.duration, time.monotonic() - s.started_at))
            if not s.finished.wait(limit):
                raise RecorderError(f"Önceki kaydın kapanışı {clock_text(limit)} dakikada bitmedi: {s.final_path}")
            if s.error:
                raise RecorderError(s.error)
        return s.final_path

    @property
    def state(self) -> RecorderState:
        return self._state

    @property
    def is_recording(self) -> bool:
        """Geriye uyum: yalnız RECORDING'de True, kapanış sürerken False. Arayüz state'e bakar."""
        return self._state is RecorderState.RECORDING

    @property
    def elapsed_seconds(self) -> int:
        s = self._session
        return int(time.monotonic() - s.started_at) if s is not None and self.is_recording else 0

    @property
    def capture_fps(self) -> float:
        """Son kayıtta gerçekten yakalanan kare/sn (yazılan değil)."""
        return self.frames_grabbed / self.last_duration if self.last_duration else 0.0

    @property
    def av_offset_ms(self) -> float | None:
        """Ölçülen ses-video başlangıç farkı (ms, + = ses önce başladı). Son kayıt için."""
        r = self.audio_result
        if r is None or r.first_sample_monotonic is None or self.video_t0 is None:
            return None
        return (self.video_t0 - r.first_sample_monotonic) * 1000.0

    # --- iç ----------------------------------------------------------------------
    def _ensure_idle(self) -> None:
        if self._state is RecorderState.FINALIZING:
            raise RecorderError("Önceki kayıt hâlâ kaydediliyor")
        if self._state is RecorderState.RECORDING:
            raise RecorderError("Kayıt zaten sürüyor")

    def _open_session(self, exe: str, rect: RecordRect, grab_rect: RecordRect, first: np.ndarray, fps: int,
                      encoder: str) -> _Session:
        """Yeni kaydın klasörünü, dosyalarını, mikrofonunu ve ffmpeg'ini açıp yazıcıyı başlatır. Bir adım düşerse o
        ana dek açılanlar kapatılır ve anlamlı bir RecorderError fırlar; kaydedicinin durumuna dokunmaz."""
        h, w = _even(first.shape[0]), _even(first.shape[1])
        try:
            out_dir = Path(self._output_dir())
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as err:                       # disk dolu, izin yok (macOS'ta Belgeler izni reddedildi)...
            raise RecorderError(f"Kayıt klasörü oluşturulamadı: {err}\n{DISK_HINT}") from err
        stamp = self._clock().strftime("%Y%m%d-%H%M%S")
        out = out_dir / f"kayit_{stamp}.mp4"
        s = _Session(rect=rect, encoder=encoder, final_path=out, log_path=out_dir / f"kayit_{stamp}.log",
                     video_path=out_dir / f"kayit_{stamp}.video.mp4" if self.audio_device else out,
                     wav_path=out_dir / f"kayit_{stamp}.wav" if self.audio_device else None, fps=fps)
        if s.wav_path is not None:
            # Ses önce başlar: ilk örneğin zamanı ölçülür, video t0 ile fark durdurunca telafi edilir.
            try:
                s.audio = self._audio_factory(self.audio_device)
                s.audio.start(s.wav_path)
            except Exception as err:  # noqa: BLE001 - mikrofon açılmazsa kayıt sessiz devam eder
                self._abort_audio(s)                 # yarım açılan yakalayıcı iz bırakmasın (yazıcı, açık WAV; k2)
                s.audio_error = f"Mikrofon açılamadı: {err}"
        args = ffmpeg_args(exe, w, h, fps, s.video_path, out_height=self.out_height, encoder=encoder)
        try:
            s.log_file = open(s.log_path, "wb")     # stderr borusu dolarsa ffmpeg donar; dosyaya yaz
        except OSError as err:
            self._abort_audio(s)
            raise RecorderError(f"Kayıt dosyası açılamadı: {err}\n{DISK_HINT}") from err
        try:
            s.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=s.log_file,
                                      **no_window())
        except OSError as err:
            self._close_log(s)
            self._abort_audio(s)
            raise RecorderError(f"ffmpeg başlatılamadı: {err}") from err
        try:
            s.started_at = time.monotonic()
            s.thread = threading.Thread(target=self._loop, args=(s, grab_rect, first, w, h, fps), daemon=True)
            s.thread.start()
        except BaseException as err:                 # beklenmeyen (ör. iş parçacığı açılamadı): hiçbir şey sızmasın
            self._kill(s.proc)
            self._close_log(s)
            self._abort_audio(s)
            if not isinstance(err, Exception):       # KeyboardInterrupt/SystemExit olduğu gibi gitsin
                raise
            raise RecorderError(f"Kayıt başlatılamadı: {exception_text(err)}") from err
        return s

    def _finalize(self, s: _Session) -> None:
        """Kapanış: yazıcıyı durdurur, mikrofonu kapatır, ffmpeg'in dosyayı bitirmesini bekler, sesi birleştirir.
        Yalnız bu kaydın oturumuyla çalışır; kilit tutulmaz (start() bu sürede FINALIZING görüp reddeder).
        ffmpeg yanıt vermediyse (stdin'i okumadı ya da EOF'tan sonra çıkmadı; öldürüldü) birleştirme denenmez: video
        eksik ya da bozuktur, hiçbir dosyaya dokunulmaz ve hata öğretmene dosyaların yerini söyler."""
        s.stop_event.set()
        s.stopped_at = time.monotonic()
        s.duration = s.stopped_at - s.started_at
        mic = self._begin_audio_stop(s)              # yardımcı iş parçacığında: takılan ses sürücüsü videoyu bekletmez
        hung = self._stop_writer(s)
        proc = s.proc
        if proc is not None and not self._close_ffmpeg(s, proc):
            hung = True                              # EOF'tan sonra da kapanmadı: öldürüldü
        self._close_log(s)
        audio = self._end_audio_stop(s, mic)
        if hung:                                     # (yazıcının öldürmeden sonra yazdığı boru hatası sebep değil)
            s.error = self._hung_text(s, audio)
            return
        if s.failed:                                 # ffmpeg kayıt sırasında durdu (kodlayıcı çöktü, bellek, disk)
            self._report_death(s, proc, audio)
            return
        if proc is not None and proc.returncode not in (0, None) and not s.error:
            s.error = f"ffmpeg hata kodu {proc.returncode}: {self._log_tail(s)}"
        if audio is not None:
            self._mux(s, audio)
        else:
            if s.video_path != s.final_path and s.video_path.exists():
                s.video_path.replace(s.final_path)  # mikrofon açılamadı ya da kapanmadı: yalnız video
            if s.mic_lost:
                self._report_lost_audio(s)
        self._report_lag(s)

    def _stop_writer(self, s: _Session) -> bool:
        """Yazıcı iş parçacığını durdurur; ffmpeg yanıt vermediyse True. Durdurulan yazıcı küçük borcu (STOP_DEBT_S) en
        çok WRITER_JOIN_S içinde yazar, büyüğünü bırakır, sonra en yeni ekranı (_settle_on_stop): ffmpeg yavaş da olsa
        okudukça beklenir, 'iş parçacığı hâlâ canlı' diye öldürülmez (öldürülen ffmpeg moov'u yazamaz, videonun tamamı
        açılmaz; K1). WRITER_JOIN_S boyunca tek kare bile okunmadıysa ffmpeg takılmıştır: yazıcı write()'ta borunun
        kilidini tutarak bekler, stdin.close() da communicate() da o kilidi bekler, hiçbir zaman aşımı işlemez. O
        durumda süreç öldürülür: boru kırılır, write() hatayla döner, yazıcı çıkar. (Döngü sınırlı: her pencerede ya
        ilerleme var ya öldürme; durdurulan yazıcının işi en çok bir pencere + son iki kare.)"""
        if s.thread is None:
            return False
        while True:
            written = s.frames_written
            s.thread.join(timeout=WRITER_JOIN_S)
            if not s.thread.is_alive():
                return False
            if s.frames_written == written:          # bu pencerede tek kare okunmadı: ffmpeg yanıt vermiyor
                break
        if s.proc is not None:
            self._kill(s.proc)
        s.thread.join(timeout=KILL_JOIN_S)
        return True

    def _close_ffmpeg(self, s: _Session, proc: subprocess.Popen) -> bool:
        """stdin'i kapatır (EOF: ffmpeg dosyayı bitirir) ve çıkmasını bekler. Bekleme ilerlemeye bağlı: ffmpeg dosyaya
        yazdıkça (kalan kareler, moov; yavaş disk) beklenir, FFMPEG_EXIT_S boyunca dosya hiç büyümezse ya da
        FFMPEG_EXIT_MAX_S dolarsa öldürülür ve False döner: video eksik ya da bozuk (moov yazılmadı), yanıt vermeyen
        ffmpeg gibi ele alınır. Yazıcı hâlâ write()'taysa boru kapatılmaz: close() onun kilidini bekleyip kapanışı
        yine kilitlerdi."""
        stdin, proc.stdin = proc.stdin, None        # wait()/communicate() kapalı boruyu bir daha flush etmesin
        if stdin is not None and not (s.thread is not None and s.thread.is_alive()):
            try:
                stdin.close()
            except (OSError, ValueError):
                pass
        give_up = time.monotonic() + FFMPEG_EXIT_MAX_S
        size = _file_size(s.video_path)
        while True:
            try:
                proc.wait(timeout=FFMPEG_EXIT_S)
                return True
            except subprocess.TimeoutExpired:
                now = _file_size(s.video_path)
                if now == size or time.monotonic() >= give_up:     # pencere boyunca tek bayt yazılmadı
                    self._kill(proc)
                    return False
                size = now

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        """ffmpeg'i öldürür ve toplar (zombi kalmasın); istisna fırlatmaz."""
        try:
            proc.kill()
            proc.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass

    @staticmethod
    def _log_result(s: _Session) -> None:
        """Kaydın hatası, ses ve görüntü uyarısı hatalar.log'a tek satır (günlük kurulu değilse hiçbir şey): öğretmen
        'Kayıt hatası' penceresini ya da uyarı kutusunu okumadan kapatsa da sonradan ne olduğu görülür. Günlük aynı
        türden ve aynı yoldan gelen hatayı oturumda bir kez yazar (sonra 10., 100. tekrarı); her kaydın sonucu ayrı bir
        olay olduğu için türün adı kaydın dosya adını taşır, kendi anahtarını alır (yoksa oturumun ikinci kaydı
        günlüğe hiç girmiyordu). İstisna fırlatmaz."""
        parts = [f"hata: {s.error}" if s.error else "", f"ses: {s.audio_error}" if s.audio_error else "",
                 f"görüntü: {s.video_warning}" if s.video_warning else ""]
        text = " · ".join(p for p in parts if p)
        if text:
            line = " | ".join(p.strip() for p in f"{s.final_path.name} · {text}".splitlines() if p.strip())
            entry = type(RecordingResult.__name__, (RecordingResult,),
                         {"__qualname__": f"{RecordingResult.__qualname__}[{s.final_path.name}]"})
            crash_log.log_handled(entry(line), "kayıt sonucu")

    def _hung_text(self, s: _Session, audio: AudioResult | None = None) -> str:
        """Zorla kapatılan kaydın hatası. Öldürülen ffmpeg moov'u yazamadığı için video büyük olasılıkla bütünüyle
        açılmaz (yalnız sonu değil): öğretmen bunu ve ham dosyaların (video, ses) yerini görür; hiçbiri silinmez."""
        text = "ffmpeg yanıt vermedi; kayıt zorla kapatıldı."
        kept = []
        if s.video_path.exists():
            text += " ffmpeg dosyayı bitiremediği için video büyük olasılıkla hiç açılmaz."
            kept.append(str(s.video_path))
        else:
            text += " Video dosyası oluşmadı."
        if s.wav_path is not None and s.wav_path.exists():
            kept.append(f"{s.wav_path} ({sound_note(audio)})")
        if kept:
            text += " Dosyalar silinmedi:\n" + "\n".join(kept)
        tail = self._log_tail(s, 300)
        return f"{text}\nffmpeg çıktısı: {tail}" if tail else text

    def _report_death(self, s: _Session, proc: subprocess.Popen | None, audio: AudioResult | None) -> None:
        """ffmpeg kayıt sırasında durdu (kodlayıcı çöktü, bellek ya da disk bitti): yazıcı kırık boruyu gördü (failed).
        Hata kendi başına anlaşılır (arayüz yalnız onu gösterir): ne oldu, video ve ses ne durumda, dosyalar nerede.
        Hiçbir dosya silinmez, açılmayan ara video son ada taşınmaz (O3: 48 B'lık bozuk video kayit_*.mp4 oluyor,
        sağlam WAV'ın yeri söylenmiyordu). Video açılıyorsa (ffmpeg dosyayı bitirip çıktı) ses yine birleştirilir: o
        ana dek kaydedilen tek dosyada; ham dosyalar yine kalır."""
        exe = self._ffmpeg_exe or find_ffmpeg()
        video = s.video_path
        video_s = media_duration(exe, video) if exe and video.exists() else None
        code = proc.returncode if proc is not None else None
        text = (f"ffmpeg kayıt sırasında durdu ({clock_text(s.frames_written / s.fps)}. dakikada"
                + (f", çıkış kodu {code}" if code is not None else "") + ").")
        s.error = None                               # yazıcının 'boru kapandı' notu yerine bütün hikâye
        if not video.exists():
            text += " Video dosyası oluşmadı."
        elif video_s is None:
            text += " ffmpeg dosyayı bitiremediği için video büyük olasılıkla hiç açılmaz."
        else:
            text += f" Video o ana dek kaydedildi ({clock_text(video_s)})."
            if audio is not None and video != s.final_path:
                self._mux(s, audio)                  # failed: ham dosyalar silinmez; düşerse sebebi s.error'da
                if s.error is None and s.final_path.exists():
                    text += f" Ses birleştirildi: {s.final_path}"
        if s.error:                                  # birleştirmenin sorunu
            text += "\n" + s.error
        if s.mic_lost:                               # mikrofon da kapanmadı: ses dosyası bitmemiş olabilir
            text += f"\n{s.mic_lost}."
        lines = self._raw_lines(s, audio, video_s)
        if lines:
            text += "\nDosyalar silinmedi:\n" + "\n".join(lines)
        tail = self._log_tail(s, 300)
        s.error = f"{text}\nffmpeg çıktısı: {tail}" if tail else text

    @staticmethod
    def _raw_lines(s: _Session, audio: AudioResult | None, video_s: float | None) -> list[str]:
        """Kalan ham dosyalar, durumlarıyla: '<yol> (video 42:10)', '<yol> (video okunamadı)', '<yol> (ses sağlam,
        42:11)'. Öğretmen hangi dosyada ne olduğunu açmadan bilsin."""
        lines = []
        if s.video_path.exists():
            lines.append(f"{s.video_path} (video {clock_text(video_s) if video_s is not None else 'okunamadı'})")
        if audio is not None and audio.path.exists():
            lines.append(f"{audio.path} ({sound_note(audio)})")
        elif audio is None and s.wav_path is not None and s.wav_path.exists():
            lines.append(f"{s.wav_path} ({sound_note(None)})")      # mikrofon kapanmadı: içeriği bilinmiyor
        return lines

    def _report_lag(self, s: _Session) -> None:
        """Kodlayıcı gerçek zamana yetişemediyse (durdurmada yazılmayan borç; ancak STOP_DEBT_S'den büyük borçta ya da
        çok yavaş kodlayıcıda kalır) kaydın görüntü uyarısı (video_warning) bunu ve izleyicinin ne göreceğini söyler
        (encoder_lag_text): görüntü donarak ilerledi, sesle arası açıldı, video erken bitiyor. Dosya açılır ve tamdır:
        hata değil, kaydedilen kaydın uyarısı; arayüz kayıt bitince uyarı kutusunda gösterir. Eskiden ses uyarısı
        alanına (audio_error) ekleniyordu, arayüz mikrofonsuz kayıtta bile 'Kayıtta ses sorunu' diyordu (R1). Ölçü
        yazıcının kendi borcu, durdurma çağrısının zamanı değil: stop() geç çağrılsa da video düğmeye basılan yerde
        biter. ffmpeg kayıt sırasında öldüyse (failed) sebep odur, bu uyarı eklenmez."""
        skipped = s.frames_skipped / s.fps
        if s.failed or skipped <= TAIL_KEEP_S:
            return
        t0 = s.video_t0 if s.video_t0 is not None else s.started_at
        sound = s.audio_result is not None and s.audio_result.samples > 0
        s.video_warning = _joined(s.video_warning, encoder_lag_text(skipped, max(0.0, s.on_time_at - t0), sound,
                                                                     s.tail_kept))

    def _grab(self, rect: RecordRect, sct=None) -> np.ndarray:
        return self._grabber(rect) if self._grabber else grab_screen(rect, sct)

    def _close_log(self, s: _Session) -> None:
        if s.log_file is not None:
            try:
                s.log_file.close()
            except OSError:
                pass
            s.log_file = None

    def _log_tail(self, s: _Session, n: int = 400) -> str:
        try:
            return s.log_path.read_text(encoding="utf-8", errors="replace").strip()[-n:]
        except OSError:
            return ""

    def _abort_audio(self, s: _Session) -> None:
        if s.audio is not None:
            try:
                s.audio.stop()
            except Exception:  # noqa: BLE001
                pass
            s.audio = None

    @staticmethod
    def _begin_audio_stop(s: _Session) -> tuple[threading.Thread, dict, float] | None:
        """Mikrofonu yardımcı iş parçacığında kapatmaya başlar: (iş parçacığı, sonuç kutusu, başlangıç) ya da None.
        Mikrofonun kapanması kapanışın tek sınırsız adımıydı ve ffmpeg'e EOF'tan önce koşuyordu (k1): ses sürücüsü
        takılınca kaydedici sonsuza dek 'kaydediliyor'da kalıyor, video da bitmiyordu. Şimdi video beklemeden kapanır,
        ses durdurma anında durur."""
        if s.audio is None:
            return None
        audio, box = s.audio, {}

        def run() -> None:
            try:
                box["result"] = audio.stop()
            except Exception as err:  # noqa: BLE001 - sebep kaydın hatasına
                box["error"] = err
        thread = threading.Thread(target=run, daemon=True, name="mikrofon-kapanış")
        thread.start()
        return thread, box, time.monotonic()

    def _end_audio_stop(self, s: _Session, mic: tuple[threading.Thread, dict, float] | None) -> AudioResult | None:
        """Mikrofonun kapanmasını en çok AUDIO_STOP_S (başlangıcından) bekler. Kapanmazsa ya da hata verirse ses
        birleştirilemez (WAV bitmemiş olabilir): mic_lost sebebi tutar, video sessiz kaydedilir, WAV silinmez."""
        if mic is None:
            return None
        thread, box, began = mic
        thread.join(max(0.0, began + AUDIO_STOP_S - time.monotonic()))
        s.audio, s.audio_result = None, box.get("result")
        if thread.is_alive():
            s.mic_lost = f"Mikrofon {span_text(AUDIO_STOP_S)} içinde kapanmadı (ses sürücüsü yanıt vermedi)"
        elif "error" in box:
            s.mic_lost = f"Mikrofon kapatılamadı ({exception_text(box['error'])})"
        elif s.audio_result is not None and getattr(s.audio_result, "close_error", None):
            s.audio_error = _joined(s.audio_error, f"Mikrofon düzgün kapanmadı ({s.audio_result.close_error}); o "
                                                   f"ana dek gelen ses kayıtta")
        return s.audio_result

    def _report_lost_audio(self, s: _Session) -> None:
        """Mikrofon kapanmadığı için ses birleştirilemedi: video sessiz son dosya oldu, ses ayrı dosyada (silinmez).
        Arayüz hatayı pencerede gösterir: öğretmen sesin nerede olduğunu bilsin."""
        text = f"{s.mic_lost}; ses videoya eklenemedi."
        if s.final_path.exists():
            text += f" Video sessiz kaydedildi: {s.final_path}"
        if s.wav_path is not None and s.wav_path.exists():
            text += f"\nSes ayrı dosyada (silinmedi): {s.wav_path}"
        s.error = _with_paragraph(s.error, text)

    def _mux(self, s: _Session, audio: AudioResult) -> None:
        """Video (kopya) + WAV -> son MP4. Birleştirme düşerse ham video ve WAV yerinde kalır, hata ikisinin de yerini
        söyler (_mux_failed); video hiç oluşmadıysa (ffmpeg başta öldü) WAV durur ve hata yerini söyler. Birleştirme
        videoyu asla kısaltmaz (#1): eksik ses sessizlikle dolar; ara dosyalar yalnız birleşik dosyanın videonun tam
        uzunluğunda olduğu ölçülünce ve kayıt hatasız bittiyse silinir. Mikrofon kesildiyse ya da WAV yazılamadıysa
        audio_error söyler."""
        exe = self._ffmpeg_exe or find_ffmpeg()
        video, out = s.video_path, s.final_path
        if audio.error:                              # WAV yazıcısı öldü (disk dolu...): o ana dek yazılan ses kalır
            s.audio_error = s.audio_error or f"Ses dosyası yazılamadı: {audio.error}"
        if not video.exists():                       # ffmpeg kayıt başında öldü: birleştirilecek video yok
            sound = audio.samples > 0 and audio.path.exists()
            s.error = _with_paragraph(s.error, "Video dosyası oluşmadı" + (
                f"; ses ayrı dosyada duruyor (silinmedi):\n{audio.path}" if sound else "; ses de kaydedilemedi."))
            return
        if not exe or audio.samples <= 0 or not audio.path.exists():
            s.audio_error = s.audio_error or "Ses kaydedilemedi (örnek yok)"
            if not s.failed:                         # ffmpeg kayıt sırasında durduysa ara video adıyla kalır
                video.replace(out)
            return
        video_s = media_duration(exe, video)         # ara videonun gerçek süresi: dolgu ve doğrulama ölçüsü
        length = video_s if video_s is not None else s.duration     # ölçülemezse duvar süresi (video ondan uzun değil)
        t0 = s.video_t0 if s.video_t0 is not None else (audio.first_sample_monotonic or 0.0)
        offset = t0 - (audio.first_sample_monotonic if audio.first_sample_monotonic is not None else t0)
        rate = audio_rate_correction(audio)
        end = audio_end_in_video(audio, offset, rate)
        skipped = s.frames_skipped / s.fps
        stop_s = s.stopped_at - s.video_t0 if s.video_t0 is not None and s.stopped_at else length + skipped
        cut = mic_cut_text(max(length, stop_s), end)    # video erken bittiyse de (K1) ses durdurmaya dek sürmeliydi
        if cut:                                      # yazıcı hatası varsa sebep odur; yalnız yeri eklenir
            s.audio_error = f"{s.audio_error} ({cut})" if s.audio_error else f"Mikrofon kayıt sırasında kesildi ({cut})"
        # Kodlayıcı yetişemediği için durdurmada borç yazılmadıysa video düğmeye basılan andan erken biter; sesin o
        # aralığı korunur: -shortest onu keserdi, ara WAV da silinince dersin son sözleri kaybolurdu (K1). Ölçü
        # yazıcının bıraktığı borç: stop() geç çağrıldıysa (arayüz meşgul) düğmeden sonraki ses eklenmez.
        end_s = None
        if video_s is not None and skipped > TAIL_KEEP_S:
            tail = min(end, video_s + skipped, stop_s)   # sesin ucu, en çok durdurma anına dek
            end_s = tail if tail > video_s + TAIL_KEEP_S else None
        args = mux_args(exe, video, audio.path, out, offset, asetrate=rate, video_s=length, end_s=end_s)
        timeout = _mux_timeout(s.duration)
        try:
            res = subprocess.run(args, capture_output=True, timeout=timeout, **no_window())
        except subprocess.TimeoutExpired:
            self._mux_failed(s, audio, video_s, f"{clock_text(timeout)} dakikada bitmedi, zaman aşımı")
            return
        except (OSError, subprocess.SubprocessError) as err:
            self._mux_failed(s, audio, video_s, exception_text(err))
            return
        if res.returncode != 0 or not out.exists():
            lines = [ln.strip() for ln in res.stderr.decode("utf-8", "replace").splitlines() if ln.strip()]
            self._mux_failed(s, audio, video_s, " / ".join(lines[-3:])[-300:] or f"çıkış kodu {res.returncode}")
            return
        out_s = media_duration(exe, out)
        if video_s is None or out_s is None:         # doğrulanamayan dosya için tek tam kopyayı silme
            self._keep_raw(s, audio, f"Birleştirilen kaydın süresi ölçülemedi, tam olduğu doğrulanamadı: {out}",
                           video_s)
            return
        whole = end_s if end_s is not None else video_s     # birleşik dosyanın olması gereken süresi
        if out_s < whole - min(SHORT_MUX_S, whole / 4):
            self._keep_raw(s, audio, f"Birleştirilen kayıt videodan kısa çıktı ({clock_text(out_s)} / "
                                     f"{clock_text(whole)}): {out}", video_s)
            return
        s.tail_kept = end_s is not None
        if s.failed:                                 # kayıt hatayla bitti: ham dosyalar kalır (_report_death)
            return
        for p in (video, audio.path):
            try:
                p.unlink()
            except OSError:
                pass

    def _keep_raw(self, s: _Session, audio: AudioResult, why: str, video_s: float | None) -> None:
        """Birleşik dosyaya güvenilemiyor ya da yok: ham video ve WAV silinmez, son ada taşınmaz; hata (arayüzde 'Kayıt
        hatası') ne olduğunu, ham dosyaların yerini ve durumunu söyler. Birleşik dosya varsa o da kalır; öğretmen
        hangisini kullanacağını görür. ffmpeg kayıt sırasında durduysa dosyaları _report_death listeler."""
        if s.failed:
            s.error = _with_paragraph(s.error, why)
            return
        text = f"{why}\nHam video ve ses silinmedi; kaydın tamamı bu dosyalarda:\n" + "\n".join(
            self._raw_lines(s, audio, video_s))
        s.error = _with_paragraph(s.error, text)

    def _mux_failed(self, s: _Session, audio: AudioResult, video_s: float | None, reason: str) -> None:
        """Birleştirme düştü (hata kodu, zaman aşımı, ffmpeg açılamadı): ara video eskiden son ada taşınıyor (video
        bozuksa 'kaydedildi' görünen açılmaz bir dosya), WAV'ın yeri söylenmiyordu (O3). Şimdi yarım kalan birleşik
        dosya silinir (kaydın tamamı ham dosyalarda), ham dosyalar yerinde kalır, hata ikisini de söyler."""
        if s.final_path != s.video_path:
            try:
                s.final_path.unlink(missing_ok=True)
            except OSError:
                pass
        self._keep_raw(s, audio, f"Ses ile görüntü birleştirilemedi ({reason}).", video_s)

    def _grab_loop(self, s: _Session, rect: RecordRect, w: int, h: int, fps: int) -> None:
        """Yakalama iş parçacığı: en fazla fps hızında kare alır, en yenisini bırakır."""
        sct = None
        if self._grabber is None:
            sct = _new_mss()                     # mss nesnesi kendi iş parçacığında oluşturulmalı
        period = 1.0 / fps
        try:
            while not s.stop_event.is_set():
                t = time.monotonic()
                try:
                    frame = self._grab(rect, sct)
                except Exception:  # noqa: BLE001 - tek kare kaçarsa son kare tekrar yazılır
                    time.sleep(0.005)
                    continue
                data = np.ascontiguousarray(frame[:h, :w]).tobytes()
                with s.latest_lock:
                    s.latest = data
                s.frames_grabbed += 1
                rest = period - (time.monotonic() - t)      # fps'ten hızlı yakalamak boşa CPU
                if rest > 0:
                    time.sleep(rest)
        finally:
            if sct is not None:
                sct.close()

    def _put_frame(self, s: _Session, data: bytes) -> bool:
        """Bir kareyi bu kaydın ffmpeg'ine yazar. Boru kapandıysa (ffmpeg öldü) sebebi oturuma yazar, False döner."""
        try:
            s.proc.stdin.write(data)      # type: ignore[union-attr]
        except (BrokenPipeError, OSError, ValueError, AttributeError):
            s.error = "ffmpeg borusu kapandı: " + (self._log_tail(s, 200) or "ayrıntı yok")
            s.failed = True
            return False
        s.frames_written += 1
        return True

    def _settle_on_stop(self, s: _Session, t0: float, fps: int, data: bytes) -> None:
        """Durdurma, yazıcı geride kalmışken (borç yazarken) geldi. Borç küçükse (en çok STOP_DEBT_S: kısa bir takılma,
        ffmpeg yeni açıldı) en çok WRITER_JOIN_S içinde yazılır: video yine düğmeye basılan ana dek sürer, birleştirme
        her zamanki gibi. Büyük borç hiç yazılmaz (frames_skipped): yavaş kodlayıcıda bütün borcu yazmak dakikalar
        sürüyor, kapanış sınırı dolunca ffmpeg öldürülüp videonun tamamı açılmaz kalıyordu (K1); sesin o aralığı
        birleştirmede korunur (_mux, end_s). Son kare en yeni ekran."""
        owed = int((time.monotonic() - t0) * fps) - s.frames_written
        pay = owed - 1 if owed <= STOP_DEBT_S * fps else 0
        until, paid = time.monotonic() + WRITER_JOIN_S, 0
        while paid < pay and time.monotonic() < until:
            if not self._put_frame(s, data):
                return
            paid += 1
        s.frames_skipped = max(0, owed - paid - 1)
        with s.latest_lock:
            data = s.latest
        self._put_frame(s, data)

    def _loop(self, s: _Session, rect: RecordRect, first: np.ndarray, w: int, h: int, fps: int) -> None:
        """Yazıcı iş parçacığı: sabit tempoda (fps) en yeni kareyi bu kaydın ffmpeg'ine yazar.
        Yakalama yavaşsa aynı kare tekrar yazılır; süre duvar saatiyle aynı kalır. Kodlayıcı geride kalırsa yazılacak
        kareler birikir (borç; kare yazımı ffmpeg okudukça döner). Durdurulunca yalnız küçük borç yazılır
        (_settle_on_stop), son kare en yeni ekran olur. Video duvar saatinden kısa kalırsa birleştirme sesin ucunu
        korur (son kare ekranda kalır), uyarı kodlayıcının yetişemediğini söyler (_report_lag)."""
        period = 1.0 / fps
        s.latest = np.ascontiguousarray(first[:h, :w]).tobytes()
        grabber = threading.Thread(target=self._grab_loop, args=(s, rect, w, h, fps), daemon=True)
        grabber.start()
        t0 = time.monotonic()
        s.video_t0 = t0
        data = s.latest
        try:
            while not s.stop_event.is_set():
                with s.latest_lock:
                    data = s.latest
                now = time.monotonic()
                due = int((now - t0) * fps) - s.frames_written
                if due <= 1:                        # yazıcı tempoda (kodlayıcı yetişiyor): geride kalma ancak sonra
                    s.on_time_at = now
                for _ in range(max(1, due)):
                    if s.stop_event.is_set():
                        break
                    if not self._put_frame(s, data):
                        return                      # ffmpeg öldü: sebep oturumda (failed)
                delay = (t0 + s.frames_written * period) - time.monotonic()
                if delay > 0:
                    s.stop_event.wait(delay)
            # Durduruldu (yazıcı nerede olursa olsun: borç yazarken, bir yazımın içinde, tempoyu beklerken): yalnız
            # küçük borç, sonra son ekran. Durdurma bir yığının son yazımına denk gelince eskiden doğrudan çıkılıyordu:
            # borç hesaba girmiyor (frames_skipped 0), uyarı çıkmıyor, sesin ucu -shortest ile kesiliyordu.
            self._settle_on_stop(s, t0, fps, data)
        finally:
            s.stop_event.set()
            grabber.join(timeout=5)
