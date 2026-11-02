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
            return subprocess.run(cmd, capture_output=True, timeout=20).returncode
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
    kalırsa geri basınç Python yazıcısına ulaşır, o da kareyi çoğaltarak süreyi korur."""
    args = [exe, "-y", "-hide_banner", "-loglevel", "warning", "-nostats", "-thread_queue_size", "8",
            "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
    if out_height and out_height != height:
        args += ["-filter_threads", "4", "-vf", f"scale=-2:{out_height}:flags=bilinear"]
    args += [*ENCODER_ARGS.get(encoder, ENCODER_ARGS["libx264"]), "-pix_fmt", "yuv420p",
             "-r", str(fps), "-fps_mode", "cfr", "-movflags", "+faststart", str(out)]
    return args


PAD_MARGIN_S = 1.0      # ses dolgusu videodan bu kadar uzun: -shortest dosyayı her zaman videonun sonunda bitirir
MIC_GAP_S = 2.0         # ses videodan bundan fazla erken bitiyorsa mikrofon kayıt sırasında kesilmiştir
SHORT_MUX_S = 1.0       # birleşik dosya videodan bundan fazla kısaysa (kısa kayıtta: sürenin 1/4'ü) ham dosyalar kalır


def mux_args(exe: str, video: Path, audio: Path, out: Path, offset_s: float,
             asetrate: int | None = None, out_rate: int = 48000, video_s: float | None = None) -> list[str]:
    """Video (kopya) + WAV -> MP4 (AAC). offset_s > 0: ses videodan önce başladı, başı atılır (-ss);
    offset_s < 0: ses geç başladı, geciktirilir (-itsoffset). asetrate: ölçülen gerçek örnekleme hızı
    (mikrofon saati kaymasını düzeltir; ppm düzeyi, duyulmaz). Ses girişi -f wav ile açılır: biçim tahmine
    bırakılırsa ffmpeg 9.0.2 düz WAV'ı mpegts sanıp düşüyor (imageio-ffmpeg 0.8.0).
    video_s: videonun süresi. Verilince ses, zincirin sonunda (hız düzeltmesi ve fade-in'den sonra) sessizlikle
    video_s + PAD_MARGIN_S'ye dek doldurulur (apad), -shortest dosyayı videonun sonunda bitirir: mikrofon kayıt
    ortasında kesilse de video kısalmaz (#1). Dolgu bilerek sınırlı: sınırsız apad + -shortest + -c:v copy ffmpeg
    7.0.2'de hiç bitmiyor (ses kodlayıcısı sonsuz sessizlik üretirken çıktıya tek paket yazılmıyor)."""
    args = [exe, "-y", "-hide_banner", "-loglevel", "warning", "-nostats", "-i", str(video)]
    if offset_s >= 0:
        args += ["-ss", f"{offset_s:.3f}", "-f", "wav", "-i", str(audio)]
    else:
        args += ["-itsoffset", f"{-offset_s:.3f}", "-f", "wav", "-i", str(audio)]
    af = ["afade=t=in:st=0:d=0.01"]                  # -ss kesim noktasındaki tek örneklik tıkı yumuşatır (10 ms)
    if asetrate:
        af = [f"asetrate={asetrate}", f"aresample={out_rate}", *af]
    if video_s is not None:
        af.append(f"apad=whole_dur={video_s + PAD_MARGIN_S:.3f}")
    args += ["-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", ",".join(af)]
    args += ["-ar", str(out_rate), "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)]
    return args


_DURATION = re.compile(rb"^\s*Duration: (\d+):(\d\d):(\d\d(?:\.\d+)?)", re.M)    # kendi satırı: etiket değeri değil


def media_duration(exe: str, path: Path, timeout: float = 30.0) -> float | None:
    """Dosyanın süresi (sn), ffmpeg'in giriş başlığı dökümünden ('Duration: 01:00:00.00'); ffprobe paketle gelmiyor.
    MP4'te yalnız moov kutusu okunur: video çözülmez, paketler taranmaz. 60 dakikalık 60 kare/sn dosyada ~0,1 sn
    (paketleri okumak 600 MB'ta ~6 sn sürüyor; 1440p60 bir ders ~7 GB). Okunamazsa ya da süre yoksa (N/A) None."""
    try:
        res = subprocess.run([exe, "-hide_banner", "-nostdin", "-i", str(path)], capture_output=True, timeout=timeout)
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


def audio_rate_correction(result: AudioResult, min_duration: float = 600.0, min_ppm: float = 100.0) -> int | None:
    """Uzun kayıtta mikrofon saati ile bilgisayar saati arasındaki farkı ölç: örnek sayısı / duvar süresi.
    Kısa kayıtta ölçüm gürültüsü (±30 ms) gerçek kaymadan büyük olduğu için uygulanmaz."""
    wall = result.wall_duration
    if wall < min_duration or result.samples <= 0:
        return None
    actual = result.samples / wall
    ppm = abs(actual / result.samplerate - 1.0) * 1e6
    if ppm < min_ppm or ppm > 10_000:            # %1'den büyük fark ölçüm hatasıdır, dokunma
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
    started_at: float = 0.0
    video_t0: float | None = None
    duration: float = 0.0
    frames_written: int = 0
    frames_grabbed: int = 0
    audio_result: AudioResult | None = None
    audio_error: str | None = None
    error: str | None = None
    failed: bool = False


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
        kaydın oturumuyla çalışır. Başka bir stop() zaten kapatıyorsa (pencere kapatma + işçi) onun bitmesini bekler."""
        with self._lock:
            s, state = self._session, self._state
            if state is RecorderState.RECORDING:
                self._state = RecorderState.FINALIZING
        if s is None:                                # hiç kayıt yapılmadı
            return None
        if state is RecorderState.RECORDING:
            try:
                self._finalize(s)
            finally:                                 # kapanış patlasa da FINALIZING'de takılı kalınmasın
                with self._lock:
                    self._state = RecorderState.IDLE
                s.finished.set()
        elif state is RecorderState.FINALIZING:
            s.finished.wait()
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
                     wav_path=out_dir / f"kayit_{stamp}.wav" if self.audio_device else None)
        if s.wav_path is not None:
            # Ses önce başlar: ilk örneğin zamanı ölçülür, video t0 ile fark durdurunca telafi edilir.
            try:
                s.audio = self._audio_factory(self.audio_device)
                s.audio.start(s.wav_path)
            except Exception as err:  # noqa: BLE001 - mikrofon açılmazsa kayıt sessiz devam eder
                s.audio, s.audio_error = None, f"Mikrofon açılamadı: {err}"
        args = ffmpeg_args(exe, w, h, fps, s.video_path, out_height=self.out_height, encoder=encoder)
        try:
            s.log_file = open(s.log_path, "wb")     # stderr borusu dolarsa ffmpeg donar; dosyaya yaz
        except OSError as err:
            self._abort_audio(s)
            raise RecorderError(f"Kayıt dosyası açılamadı: {err}\n{DISK_HINT}") from err
        try:
            s.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=s.log_file)
        except OSError as err:
            self._close_log(s)
            self._abort_audio(s)
            raise RecorderError(f"ffmpeg başlatılamadı: {err}") from err
        s.started_at = time.monotonic()
        s.thread = threading.Thread(target=self._loop, args=(s, grab_rect, first, w, h, fps), daemon=True)
        s.thread.start()
        return s

    def _finalize(self, s: _Session) -> None:
        """Kapanış: yazıcıyı durdurur, mikrofonu kapatır, ffmpeg'in dosyayı bitirmesini bekler, sesi birleştirir.
        Yalnız bu kaydın oturumuyla çalışır; kilit tutulmaz (start() bu sürede FINALIZING görüp reddeder)."""
        s.stop_event.set()
        s.duration = time.monotonic() - s.started_at
        if s.thread is not None:
            s.thread.join(timeout=10)
        audio = self._stop_audio(s)
        proc = s.proc
        if proc is not None:
            try:
                if proc.stdin:
                    try:
                        proc.stdin.close()
                    except (OSError, ValueError):
                        pass
                    proc.stdin = None        # communicate() kapalı boruyu flush etmesin (Py3.12/macOS ValueError)
                proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                s.error = "ffmpeg zamanında kapanmadı"
        self._close_log(s)
        if proc is not None and proc.returncode not in (0, None) and not s.error:
            s.error = f"ffmpeg hata kodu {proc.returncode}: {self._log_tail(s)}"
        if audio is not None:
            self._mux(s, audio)
        elif s.video_path != s.final_path and s.video_path.exists():
            s.video_path.replace(s.final_path)      # mikrofon açılamadı: yalnız video

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

    def _stop_audio(self, s: _Session) -> AudioResult | None:
        if s.audio is None:
            return None
        try:
            s.audio_result = s.audio.stop()
        except Exception as err:  # noqa: BLE001
            s.audio_error = f"Mikrofon kapatılamadı: {err}"
            s.audio_result = None
        s.audio = None
        return s.audio_result

    def _mux(self, s: _Session, audio: AudioResult) -> None:
        """Video (kopya) + WAV -> son MP4. Birleştirme başarısızsa yalnız video dosyası sonuç olur. Birleştirme
        videoyu asla kısaltmaz (#1): eksik ses sessizlikle dolar; ara dosyalar yalnız birleşik dosyanın videonun
        tam uzunluğunda olduğu ölçülünce silinir. Mikrofon kesildiyse ya da WAV yazılamadıysa audio_error söyler."""
        exe = self._ffmpeg_exe or find_ffmpeg()
        video, out = s.video_path, s.final_path
        if audio.error:                              # WAV yazıcısı öldü (disk dolu...): o ana dek yazılan ses kalır
            s.audio_error = s.audio_error or f"Ses dosyası yazılamadı: {audio.error}"
        if not exe or audio.samples <= 0 or not audio.path.exists():
            s.audio_error = s.audio_error or "Ses kaydedilemedi (örnek yok)"
            video.replace(out)
            return
        video_s = media_duration(exe, video)         # ara videonun gerçek süresi: dolgu ve doğrulama ölçüsü
        length = video_s if video_s is not None else s.duration     # ölçülemezse duvar süresi (video ondan uzun değil)
        t0 = s.video_t0 if s.video_t0 is not None else (audio.first_sample_monotonic or 0.0)
        offset = t0 - (audio.first_sample_monotonic if audio.first_sample_monotonic is not None else t0)
        rate = audio_rate_correction(audio)
        cut = mic_cut_text(length, audio_end_in_video(audio, offset, rate))
        if cut:                                      # yazıcı hatası varsa sebep odur; yalnız yeri eklenir
            s.audio_error = f"{s.audio_error} ({cut})" if s.audio_error else f"Mikrofon kayıt sırasında kesildi ({cut})"
        args = mux_args(exe, video, audio.path, out, offset, asetrate=rate, video_s=length)
        try:
            res = subprocess.run(args, capture_output=True, timeout=max(120, int(s.duration * 2)))
        except (OSError, subprocess.SubprocessError) as err:
            s.audio_error = _joined(f"Ses birleştirilemedi: {err}", s.audio_error)
            video.replace(out)
            return
        if res.returncode != 0 or not out.exists():
            reason = res.stderr.decode("utf-8", "replace").strip()[-300:]
            s.audio_error = _joined(f"Ses birleştirilemedi: {reason}", s.audio_error)
            video.replace(out)
            return
        out_s = media_duration(exe, out)
        if video_s is None or out_s is None:         # doğrulanamayan dosya için tek tam kopyayı silme
            self._keep_raw(s, audio, "Birleştirilen kaydın süresi ölçülemedi, tam olduğu doğrulanamadı")
            return
        if out_s < video_s - min(SHORT_MUX_S, video_s / 4):
            self._keep_raw(s, audio, f"Birleştirilen kayıt videodan kısa çıktı ({clock_text(out_s)} / "
                                     f"{clock_text(video_s)})")
            return
        for p in (video, audio.path):
            try:
                p.unlink()
            except OSError:
                pass

    def _keep_raw(self, s: _Session, audio: AudioResult, why: str) -> None:
        """Birleşik dosyaya güvenilemiyor: ham video ve WAV silinmez, hata (arayüzde 'Kayıt hatası') üç dosyanın da
        yerini söyler. Birleşik dosya da kalır; öğretmen hangisini kullanacağını görür."""
        text = (f"{why}: {s.final_path}\nHam video ve ses silinmedi; kaydın tamamı bu dosyalarda:\n"
                f"{s.video_path}\n{audio.path}")
        s.error = f"{s.error}\n\n{text}" if s.error else text

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

    def _loop(self, s: _Session, rect: RecordRect, first: np.ndarray, w: int, h: int, fps: int) -> None:
        """Yazıcı iş parçacığı: sabit tempoda (fps) en yeni kareyi bu kaydın ffmpeg'ine yazar.
        Yakalama yavaşsa aynı kare tekrar yazılır; süre duvar saatiyle aynı kalır."""
        period = 1.0 / fps
        s.latest = np.ascontiguousarray(first[:h, :w]).tobytes()
        grabber = threading.Thread(target=self._grab_loop, args=(s, rect, w, h, fps), daemon=True)
        grabber.start()
        t0 = time.monotonic()
        s.video_t0 = t0
        try:
            while not s.stop_event.is_set():
                with s.latest_lock:
                    data = s.latest
                due = int((time.monotonic() - t0) * fps) - s.frames_written
                for _ in range(max(1, due)):
                    try:
                        s.proc.stdin.write(data)      # type: ignore[union-attr]
                    except (BrokenPipeError, OSError, ValueError, AttributeError):
                        s.error = "ffmpeg borusu kapandı: " + (self._log_tail(s, 200) or "ayrıntı yok")
                        s.failed = True
                        return
                    s.frames_written += 1
                delay = (t0 + s.frames_written * period) - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
        finally:
            s.stop_event.set()
            grabber.join(timeout=5)
