"""Kaydedicinin kapanışı: ffmpeg ancak ilerlemiyorsa öldürülür, durdurma borcu ödenmez, birleştirme düşerse ham
dosyalar kalır, mikrofon kapanışı sınırlı (son inceleme K1, O3, k1, k2).

Sahte ffmpeg'ler Python betiği (python_ffmpeg): kabuk betiği yalnız posix'te koşuyordu, bu testler Windows CI'da da
koşar. Yavaş kodlayıcı gerçek ffmpeg + SlowPipe ile: kare yazımı test izin verdikçe geçer (olayla, uyumadan)."""
import contextlib
import re
import subprocess
import threading
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from matematigin_mantigi.core.recorder import (MssFfmpegRecorder, RecordRect, RecorderError, RecorderState, clock_text,
                                               encoder_lag_text, ffmpeg_args, find_ffmpeg, media_duration, mux_args)
from tests.test_recorder import (FakeAudioCapture, _outcome, _raw_files, _stream_seconds, _write_test_media,
                                 capture_logged, python_ffmpeg, recorded_runs, stepping_clock, synthetic_grabber,
                                 wait_until, waiting_stop_signal, writer_blocked_in_pipe_write)

needs_ffmpeg = pytest.mark.skipif(find_ffmpeg() is None, reason="ffmpeg yok")


class SlowPipe:
    """Kayıt ffmpeg'inin stdin'i yerine geçer: gerçek zamandan yavaş kodlayan ama okuyan ffmpeg (s1'de 2816x1584 ->
    1440p libx264 17,7 kare/sn). Başta serbest; hold() sonrası her kare yazımı allow() bekler. waits: yazıcının izin
    beklemeye girdiği sayı (olayla beklemek için). Kareler gerçek ffmpeg'e gider: dosya gerçek MP4."""

    def __init__(self, pipe):
        self._pipe = pipe
        self._cond = threading.Condition()
        self._free, self._budget, self.waits = True, 0, 0

    def write(self, data):
        with self._cond:
            counted = False
            while not self._free and self._budget <= 0:
                if not counted:
                    self.waits, counted = self.waits + 1, True
                self._cond.wait(0.05)
            if not self._free:
                self._budget -= 1
        return self._pipe.write(data)

    def hold(self) -> None:
        with self._cond:
            self._free = False

    def allow(self, n: int = 1) -> None:
        with self._cond:
            self._budget += n
            self._cond.notify_all()

    def release(self) -> None:
        with self._cond:
            self._free = True
            self._cond.notify_all()

    def close(self) -> None:
        self._pipe.close()

    def __getattr__(self, name):
        return getattr(self._pipe, name)


def slow_pipes(monkeypatch) -> list:
    """Kayıt ffmpeg'inin (gerçek) stdin'ini SlowPipe ile sarar; dönüş: SlowPipe'lar (kayıt başına bir)."""
    pipes: list = []
    real = subprocess.Popen

    def popen(args, *a, **k):
        p = real(args, *a, **k)
        if isinstance(args, list) and "pipe:0" in args:
            p.stdin = SlowPipe(p.stdin)
            pipes.append(p.stdin)
        return p
    monkeypatch.setattr(subprocess, "Popen", popen)
    return pipes


def debt(rec, fps: int) -> int:
    """Duvar saatine göre yazılması gereken ama henüz yazılamamış kare sayısı (kodlayıcının birikimi)."""
    return int((time.monotonic() - rec.video_t0) * fps) - rec.frames_written


@contextlib.contextmanager
def reading_slowly(pipe: SlowPipe, every: float = 0.1):
    """Durdurma sürerken yavaş okuyan ffmpeg: her `every` sn'de bir kare geçer; çıkışta boru serbest kalır."""
    done = threading.Event()
    feeder = threading.Thread(target=lambda: [pipe.allow() for _ in iter(lambda: done.wait(every), True)],
                              daemon=True)
    feeder.start()
    try:
        yield
    finally:
        done.set()
        pipe.release()
        feeder.join(5)


def counted_kills(monkeypatch, rec) -> list:
    """Kaydedicinin ffmpeg'i öldürdüğü anlar (monotonic); öldürme yine gerçekten yapılır."""
    kills: list = []
    real = rec._kill
    monkeypatch.setattr(rec, "_kill", lambda proc: (kills.append(time.monotonic()), real(proc))[1])
    return kills


TRY_LOWER = " (30 kare/sn ya da daha düşük çözünürlük deneyin)"


# --- K1: yavaş ama okuyan ffmpeg öldürülmez; durdurma borcu ödenmez -------------------------------------------

@needs_ffmpeg
@pytest.mark.parametrize("mic", [False, True], ids=["mikrofonsuz", "mikrofonlu"])
def test_slow_encoder_that_keeps_reading_is_not_killed_and_the_file_opens(tmp_path, monkeypatch, mic):
    """Kodlayıcı gerçek zamandan yavaşsa (s1: 17,7 kare/sn) yazıcının borcu birikir; durdurunca yazıcı bütün borcu
    yazmaya çalışıyor, WRITER_JOIN_S dolunca kapanış ffmpeg'i 'iş parçacığı hâlâ canlı' diye öldürüyordu. ffmpeg
    okuyordu (s1'de STOP->KILL arası 242->443 kare); moov yazılmadığı için videonun TAMAMI açılmıyordu. Şimdi büyük
    borç (STOP_DEBT_S'den büyük) yazılmaz, son kare en yeni ekran; okuyan ffmpeg öldürülmez, dosya açılır. Video
    duvar saatinden kısa kaldığı için birleştirme sesin ucunu kesmez (ses tam, son kare ekranda durur); kayıt hatasız
    biter. Uyarı görüntü uyarısı alanında (video_warning; ses uyarısı kanalı temiz kalır, R1) ve izleyicinin ne
    göreceğini söyler: görüntü donarak ilerledi, sesle arası açıldı, video erken bitiyor."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 1.0)                        # gerçek sınır 10 sn
    monkeypatch.setattr(r, "STOP_DEBT_S", 1.0)                          # bundan büyük borç yazılmaz (gerçekte 2 sn)
    fps = 20
    pipes = slow_pipes(monkeypatch)
    logged = capture_logged(monkeypatch)
    kw = dict(audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture) if mic else {}
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=fps, grabber=synthetic_grabber, out_height=0,
                            clock=stepping_clock(), **kw)
    kills: list = []
    real_kill = rec._kill
    monkeypatch.setattr(rec, "_kill", lambda proc: (kills.append(proc), real_kill(proc))[1])
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    pipe = pipes[0]
    pipe.hold()                                                         # kodlayıcı geride kalmaya başladı
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 2.5 * fps)    # 2,5 sn'lik borç
    for _ in range(3):                                                  # birkaç kare geçer: yazıcı borcu yazıyor
        n = pipe.waits
        pipe.allow()
        wait_until(lambda: pipe.waits > n)
    at_stop = rec.frames_written
    stopped = threading.Event()

    def feed():                                                         # durdurma sürerken ffmpeg yavaş okur
        while not stopped.wait(0.2):
            pipe.allow()
    feeder = threading.Thread(target=feed, daemon=True)
    feeder.start()
    t_stop = time.monotonic()
    try:
        outcome = _outcome(rec.stop)
    finally:
        stopped.set()
        pipe.release()
        feeder.join(5)
    path = rec.last_path
    assert outcome == ("dönüş", path), outcome
    assert kills == [], rec.error                                       # okuyan ffmpeg öldürülmedi
    assert rec.frames_written <= at_stop + 2, (at_stop, rec.frames_written)   # yazılmakta olan + son ekran
    assert rec._session.frames_skipped >= 2 * fps, rec._session.frames_skipped     # büyük borç yazılmadı
    exe = find_ffmpeg()
    video_s = rec.frames_written / fps
    assert media_duration(exe, path) is not None                         # dosya açılıyor
    assert abs(_stream_seconds(exe, path, "-an") - video_s) < 0.15
    assert rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
    behind = (r", sesle arası sona doğru (\d) sn'ye çıktı; görüntü \1 sn erken bitiyor, son kare ses bitene dek ekranda"
              r" kalıyor" if mic else r"; video (\d) sn erken bitiyor")
    m = re.fullmatch(r"Görüntü kodlayıcısı kayda yetişemedi: görüntü kayıt boyunca donarak ilerledi" + behind
                     + re.escape(TRY_LOWER), rec.video_warning or "")
    assert m and int(m.group(1)) == round(rec._session.frames_skipped / fps), rec.video_warning
    results = [str(exc) for exc, where in logged if where == "kayıt sonucu"]       # hatalar.log'daki sonuç satırı
    assert results == [f"{path.name} · görüntü: {rec.video_warning}"], results
    if mic:                                                             # ses durdurma anına dek tam
        wall = t_stop - rec.video_t0
        assert abs(_stream_seconds(exe, path, "-vn") - wall) < 0.15, wall
        assert all(p.exists() for p in _raw_files(path))  # ham dosyalar yarışsız silinemediği için kalır


@needs_ffmpeg
def test_stopped_writer_still_writing_to_a_slow_reader_is_not_killed_after_one_window(tmp_path, monkeypatch):
    """K1: öldürme ölçüsü 'yazıcı iş parçacığı hâlâ canlı' değil 'bu pencerede tek kare okunmadı'. Durdurulan yazıcı
    küçük borcu yavaş ama okuyan ffmpeg'e yazarken ilk WRITER_JOIN_S penceresi dolar (iş parçacığı canlı): ffmpeg kare
    okuduğu için öldürülmez, ikinci pencerede yazıcı biter, dosya açılır. Durdurma burada yazıcının bir yığının son
    yazımında beklediği ana denk gelir: eskiden o yoldan borç hesaba girmeden çıkılıyordu (atlanan 0, uyarı yok)."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 1.0)                        # gerçek sınır 10 sn
    fps = 20
    pipes = slow_pipes(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=fps, grabber=synthetic_grabber, out_height=0,
                            clock=stepping_clock())
    kills: list = []
    real_kill = rec._kill
    rec._kill = lambda proc: (kills.append(proc), real_kill(proc))
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    pipe = pipes[0]
    pipe.hold()
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 1.5 * fps)  # küçük borç (STOP_DEBT_S = 2 sn)
    joins: list = []
    thread = rec._session.thread
    real_join = thread.join
    thread.join = lambda timeout=None: (joins.append(timeout), real_join(timeout))[1]
    reading = threading.Event()

    def slow_reader():                                                  # ffmpeg saniyede ~10 kare okuyor
        while not reading.is_set():
            pipe.allow()
            reading.wait(0.1)
    pacer = threading.Thread(target=slow_reader, daemon=True)
    pacer.start()
    try:
        path = rec.stop()
    finally:
        reading.set()
        pacer.join(5)
    assert len(joins) >= 2, joins                                       # ilk pencere doldu, yazıcı hâlâ yazıyordu
    assert kills == [] and rec.error is None, (kills, rec.error)
    assert media_duration(find_ffmpeg(), path) is not None               # moov yazıldı, dosya açılıyor
    assert rec._session.frames_skipped > 0                              # yazılamayan borç hesapta ...
    warning = rec.video_warning or ""
    assert warning.startswith("Görüntü kodlayıcısı kayda yetişemedi"), warning      # ... ve görüntü uyarısında
    assert rec.audio_error is None, rec.audio_error


def test_encoder_lag_text_says_what_the_viewer_will_see():
    """R1 (son inceleme s8, s1f): kodlayıcı uyarısı ses uyarısı kanalından gidiyordu ('Kayıtta ses sorunu', mikrofonsuz
    kayıtta bile) ve hasarı küçümsüyordu ('görüntü takılmış olabilir'). Geride kalan yazıcı aynı kareyi art arda
    yazar: görüntü slayt gösterisi gibi donarak ilerler, sesle arası durdurmadaki borca dek açılır, video o kadar erken
    biter. Metin bunu kendi başına söyler; ses yoksa sesten söz etmez. Kodlayıcı dersin ortasında geride kalmaya
    başladıysa (ısınan MacBook Air, takılan disk) 'kayıt boyunca' demez, hangi dakikadan sonra olduğunu söyler."""
    assert encoder_lag_text(8.2, lag_from_s=0.4, sound=False, tail_kept=False) == (
        "Görüntü kodlayıcısı kayda yetişemedi: görüntü kayıt boyunca donarak ilerledi; video 8 sn erken bitiyor"
        + TRY_LOWER)
    assert encoder_lag_text(17.1, lag_from_s=2.0, sound=True, tail_kept=True) == (
        "Görüntü kodlayıcısı kayda yetişemedi: görüntü kayıt boyunca donarak ilerledi, sesle arası sona doğru 17 sn'ye"
        " çıktı; görüntü 17 sn erken bitiyor, son kare ses bitene dek ekranda kalıyor" + TRY_LOWER)
    assert encoder_lag_text(135.0, lag_from_s=1510.4, sound=True, tail_kept=False) == (
        "Görüntü kodlayıcısı kayda yetişemedi: görüntü 25:10. dakikadan sonra donarak ilerledi, sesle arası sona doğru"
        " 2 dk 15 sn'ye çıktı; video 2 dk 15 sn erken bitiyor" + TRY_LOWER)
    assert "kayıt boyunca" not in encoder_lag_text(3.0, lag_from_s=6.0, sound=False, tail_kept=False)


@needs_ffmpeg
def test_lag_that_starts_mid_lesson_says_from_which_minute(tmp_path, monkeypatch):
    """R1: yazıcı tempodayken (kodlayıcı yetişirken) geçen süre ölçülür; kodlayıcı ancak ders ilerledikten sonra geride
    kaldıysa uyarı 'kayıt boyunca' değil o dakikayı söyler: öncesi sağlam. Ölçü yazıcının tempoda olduğu son an."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 1.0)
    monkeypatch.setattr(r, "STOP_DEBT_S", 1.0)
    monkeypatch.setattr(r, "LAG_START_S", 0.5)                          # gerçekte 5 sn: test kısa sürsün
    fps = 20
    pipes = slow_pipes(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=fps, grabber=synthetic_grabber, out_height=0,
                            clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 1.2 * fps)                 # 1,2 sn kodlayıcı yetişiyor
    pipe = pipes[0]
    held = time.monotonic()
    pipe.hold()                                                         # sonra geride kaldı
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 2.5 * fps)
    with reading_slowly(pipe):
        rec.stop()
    lag_from = rec._session.on_time_at - rec.video_t0
    assert 0.5 < lag_from and abs(lag_from - (held - rec.video_t0)) < 0.3, (lag_from, held - rec.video_t0)
    assert rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
    assert re.fullmatch(r"Görüntü kodlayıcısı kayda yetişemedi: görüntü " + re.escape(clock_text(lag_from))
                        + r"\. dakikadan sonra donarak ilerledi; video \d sn erken bitiyor" + re.escape(TRY_LOWER),
                        rec.video_warning or ""), rec.video_warning


@needs_ffmpeg
def test_short_encoder_hiccup_is_still_written_and_the_video_reaches_the_stop(tmp_path, monkeypatch):
    """Kısa takılmada (borç STOP_DEBT_S'den az: kodlayıcı bir an geride kaldı, ffmpeg yeni açıldı) durdurma borcu
    yazılır: video düğmeye basılan ana dek sürer, birleştirme her zamanki -shortest yolundan geçer, uyarı yok. Borcun
    tamamını bırakmak her kısa kayıtta sesin ucunu kesip videoyu kısaltırdı."""
    fps = 20
    pipes = slow_pipes(monkeypatch)
    runs = recorded_runs(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=fps, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    pipe = pipes[0]
    pipe.hold()
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 0.5 * fps)     # yarım saniyelik borç
    for _ in range(3):                                                  # yazıcı borcu yazmaya başladı
        n = pipe.waits
        pipe.allow()
        wait_until(lambda: pipe.waits > n)
    t_stop = time.monotonic()
    pipe.release()                                                      # kodlayıcı yine yetişiyor
    path = rec.stop()
    assert rec.error is None and rec.audio_error is None, (rec.error, rec.audio_error)
    assert rec._session.frames_skipped == 0
    exe = find_ffmpeg()
    assert abs(_stream_seconds(exe, path, "-an") - (t_stop - rec.video_t0)) < 0.15     # video durdurmaya dek
    mux = [a for a in runs if "-c:a" in a]
    assert len(mux) == 1 and "-shortest" in mux[0] and "-t" not in mux[0], mux


@needs_ffmpeg
def test_ffmpeg_that_reads_a_little_after_stop_then_hangs_is_killed(tmp_path, monkeypatch):
    """K1'in öbür yüzü: öldürme ölçüsü PENCERE BAŞINA ilerleme. ffmpeg durdurmadan sonra birkaç kare okuyup takılırsa
    (kodlayıcı dondu) bir pencere sonra öldürülür, stop() döner. Ölçü toplam ilerleme olsaydı (durdurmadan beri hiç
    kare okundu mu) bir kez ilerleyen ffmpeg hiç öldürülmez, kaydedici sonsuza dek 'kaydediliyor'da kalırdı."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 0.5)                        # gerçek sınır 10 sn
    fps = 20
    pipes = slow_pipes(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=fps, grabber=synthetic_grabber, out_height=0,
                            clock=stepping_clock())
    kills = counted_kills(monkeypatch, rec)
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    pipe = pipes[0]
    pipe.hold()
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 0.5 * fps)  # küçük borç: durdurmada yazılır
    joins: list = []
    thread = rec._session.thread
    real_join = thread.join
    thread.join = lambda timeout=None: (joins.append(timeout), real_join(timeout))[1]
    done: list = []
    stopper = threading.Thread(target=lambda: done.append(_outcome(rec.stop)), daemon=True)
    stopper.start()
    wait_until(lambda: joins)                                           # kapanış ilk pencereyi bekliyor
    for _ in range(3):                                                  # durdurmadan sonra 3 kare okur ...
        n = pipe.waits
        pipe.allow()
        wait_until(lambda: pipe.waits > n)
    stopper.join(10)                                                    # ... sonra takılır
    alive, error = stopper.is_alive(), rec.error
    pipe.release()                       # (bırakılan yazıcı ölü boruya yazıp hatayı ezer: hata önce okundu)
    stopper.join(10)
    assert not alive, "ilerleyip takılan ffmpeg öldürülmedi: stop() dönmüyor"
    assert len(kills) == 1 and (error or "").startswith("ffmpeg yanıt vermedi"), (kills, error)


GROWS_ONCE = """
with open(out, "wb") as f:
    while stdin.read(65536):
        pass
    while not os.path.exists(out + ".olculdu"):     # kaydedici EOF'tan sonraki ilk boyu ölçtü
        time.sleep(0.01)
    f.write(b"\\0" * 4096); f.flush()               # bir kez yazdı ...
    time.sleep(300)                                 # ... sonra takıldı
"""

GROWS_FOREVER = """
with open(out, "wb") as f:
    while stdin.read(65536):
        pass
    while True:                                     # EOF'tan sonra durmadan yazıyor (bitmeyen döngü)
        f.write(b"\\0" * 4096); f.flush()
        time.sleep(0.05)
"""


@pytest.mark.parametrize("body, cap, limit", [(GROWS_ONCE, 30.0, 6.0), (GROWS_FOREVER, 3.0, 9.0)],
                         ids=["bir-kez", "hep"])
def test_ffmpeg_that_writes_after_eof_but_never_exits_is_killed(tmp_path, monkeypatch, body, cap, limit):
    """EOF'tan sonraki bekleme ilerlemeye bağlı ama sınırlı. Dosyaya bir kez yazıp takılan ffmpeg bir pencere sonra
    öldürülür: ölçü her pencerede yenilenmese (ilk boya göre) ilk yazımdan sonra hep 'büyüdü' görünür, FFMPEG_EXIT_MAX_S
    (gerçekte 10 dk) beklenirdi. Dosyayı durmadan büyüten (bitmeyen döngü) ffmpeg o tavanda öldürülür: tavan olmasa
    stop() hiç dönmezdi. Sahte ffmpeg ilk boy ölçülünce yazar (olayla): ölçümden önce yazsa fark görünmezdi."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "FFMPEG_EXIT_S", 1.0)                        # gerçek pencere 60 sn
    monkeypatch.setattr(r, "FFMPEG_EXIT_MAX_S", cap)
    real_size = r._file_size

    def file_size(path):
        n = real_size(path)
        Path(str(path) + ".olculdu").touch()
        return n
    monkeypatch.setattr(r, "_file_size", file_size)
    procs = python_ffmpeg(monkeypatch, tmp_path, body)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            ffmpeg_exe="sahte-ffmpeg", clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 3)
    done: list = []
    stopper = threading.Thread(target=lambda: done.append(_outcome(rec.stop)), daemon=True)
    t = time.monotonic()
    stopper.start()
    stopper.join(limit + 2)
    took = time.monotonic() - t
    for p in procs:
        if p.poll() is None:
            p.kill()                                                    # (düzeltmesiz kodda takılı stop()'u çöz)
    stopper.join(10)
    assert done and took < limit, f"stop() {took:.1f} sn'de döndü (sınır {limit})"
    assert (rec.error or "").startswith("ffmpeg yanıt vermedi"), rec.error
    assert len(procs) == 1 and procs[0].returncode is not None          # öldürüldü ve toplandı


@needs_ffmpeg
def test_last_frame_of_a_lagging_recording_is_the_newest_screen(tmp_path, monkeypatch):
    """K1: kodlayıcı geride kalınca büyük borç yazılmaz; son kare durdurma anının ekranıdır (tahtanın son hâli, çoğu
    derste çözümün kendisi) ve sesin ucu boyunca ekranda kalır. Son kare yazılmasa video yazıcının elindeki bayat
    kareyle (borç yığınının başındaki ekran) biterdi."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 1.0)
    monkeypatch.setattr(r, "STOP_DEBT_S", 1.0)
    fps, marker = 20, {"v": 0}

    def grabber(rect):                                                  # ekranın tamamı tek renk: o anki işaret
        return np.full((rect.height, rect.width, 4), (marker["v"], marker["v"], marker["v"], 255), np.uint8)
    pipes = slow_pipes(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=fps, grabber=grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    pipe = pipes[0]
    pipe.hold()
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 2.5 * fps)
    marker["v"] = 250                                                   # durdurmadan hemen önce ekran beyaz
    wait_until(lambda: rec._session.latest[:1] == bytes([250]))
    with reading_slowly(pipe):
        path = rec.stop()
    raw = subprocess.run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-an", "-f",
                          "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    size = 160 * 120
    first, last = raw[:size], raw[-size:]
    assert rec.error is None and "son kare ses bitene dek ekranda kalıyor" in (rec.video_warning or ""), \
        (rec.error, rec.video_warning)
    assert len(raw) >= 2 * size and first[size // 2] < 50, len(raw)    # baştaki kareler siyah ...
    assert last[size // 2] > 200, last[size // 2]                       # ... son kare durdurma anının ekranı


@needs_ffmpeg
def test_audio_tail_ends_at_the_stop_even_when_the_writer_and_the_microphone_stop_later(tmp_path, monkeypatch):
    """K1: video erken bittiyse birleştirme sesin ucunu korur, ama en çok durdurma anına dek. Yazıcı durdurmayı bir kare
    yazımının içinde geç görebilir (kodlayıcı o kareyi geç okudu), ses sürücüsü de akışı geç kapatabilir: ikisi de
    düğmeden sonraki sesi birleşik dosyaya taşırdı. Dosya durdurma anında biter."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 5.0)                        # geç kalan yazıcı öldürülmesin
    monkeypatch.setattr(r, "STOP_DEBT_S", 1.0)
    fps, late = 20, 1.5
    mic_go = threading.Event()

    class LateMic(FakeAudioCapture):                                    # akış geç kapandı: ses o ana dek sürdü
        def stop(self):
            assert mic_go.wait(30)
            return super().stop()
    pipes = slow_pipes(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=fps, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=LateMic, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    pipe = pipes[0]
    pipe.hold()
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 2.5 * fps)
    done: list = []
    stopper = threading.Thread(target=lambda: done.append(_outcome(rec.stop)), daemon=True)
    stopper.start()
    try:
        wait_until(lambda: rec._session.stopped_at > 0)                 # durdurma anı ölçüldü
        time.sleep(late)                                                # yazıcı ve mikrofon durdurmayı geç görüyor
    finally:
        pipe.release()                                                  # yazıcı bekleyen kareyi yazıp durur
        mic_go.set()
        stopper.join(30)
    s = rec._session
    stop_s = s.stopped_at - s.video_t0
    assert done == [("dönüş", rec.last_path)] and rec.error is None, (done, rec.error)
    assert s.tail_kept and rec.audio_result.duration > stop_s + late - 0.3     # ses durdurmadan sonra da sürdü
    assert media_duration(find_ffmpeg(), rec.last_path) == pytest.approx(stop_s, abs=0.25)    # dosya durdurmada biter


@needs_ffmpeg
def test_mux_that_drops_the_audio_tail_keeps_the_raw_files(tmp_path, monkeypatch):
    """K1: video erken bittiyse birleşik dosyanın olması gereken süresi sesin ucu (end_s), videonun süresi değil.
    Birleştirme ucu kaybederse (ileride ffmpeg -t'yi başka işlerse, komut değişirse) dosya videonun boyunda çıkar:
    doğrulama yalnız videoya bakarsa bu 'tam' sayılıp ham WAV silinir, dersin son sözleri kaybolurdu. Şimdi ham
    dosyalar kalır, hata ikisinin yerini söyler."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 1.0)
    monkeypatch.setattr(r, "STOP_DEBT_S", 1.0)
    real_mux_args = r.mux_args
    monkeypatch.setattr(r, "mux_args", lambda *a, **k: real_mux_args(*a, **{**k, "end_s": None}))  # uç kaybolur
    fps = 20
    pipes = slow_pipes(monkeypatch)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=fps, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 5)
    pipe = pipes[0]
    pipe.hold()                                                         # kodlayıcı geride kaldı: 2,5 sn'lik borç
    wait_until(lambda: pipe.waits >= 1 and debt(rec, fps) >= 2.5 * fps)
    with reading_slowly(pipe):
        path = rec.stop()
    video, wav = _raw_files(path)
    assert video.exists() and wav.exists(), rec.error                   # sesin ucu ham dosyada
    err = rec.error or ""
    assert "kısa çıktı" in err and str(video) in err and str(wav) in err, err


@pytest.mark.parametrize("fake", ["okumayi-birakan", "eofta-kapanmayan"])
@pytest.mark.parametrize("mic", [False, True], ids=["mikrofonsuz", "mikrofonlu"])
def test_unresponsive_ffmpeg_is_killed_and_stop_returns(tmp_path, monkeypatch, fake, mic):
    """ffmpeg stdin'i okumayı bırakıp ölmezse (donan kodlayıcı, takılan disk) yazıcı iş parçacığı write()'ta borunun
    kilidini tutarak bekler. Kapanıştaki stdin.close() aynı kilidi beklediği için join ve communicate zaman aşımları
    hiç işlemiyordu: stop() dönmüyor, kaydedici FINALIZING'de kalıyordu. Şimdi WRITER_JOIN_S boyunca tek kare okunmazsa
    ffmpeg öldürülür; EOF'tan sonra FFMPEG_EXIT_S boyunca dosyaya tek bayt yazmayan ffmpeg de. stop() döner,
    kaydedici IDLE; birleştirme denenmez, hiçbir dosya silinmez, hata videonun büyük olasılıkla açılmayacağını ve
    dosyaların yerini söyler. Kapanışı bekleyen ikinci stop() aynı hatayı RecorderError ile görür."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 0.5)                        # gerçek sınır 10 sn; test kısa sürsün
    if fake == "eofta-kapanmayan":
        monkeypatch.setattr(r, "FFMPEG_EXIT_S", 0.5)                    # (okumayan ffmpeg bu sınıra hiç varmamalı)
    body = {"okumayi-birakan": "open(out, 'wb').close()\ntime.sleep(300)\n",
            "eofta-kapanmayan": "open(out, 'wb').close()\nwhile stdin.read(65536):\n    pass\ntime.sleep(300)\n"}[fake]
    procs = python_ffmpeg(monkeypatch, tmp_path, body)
    calls = recorded_runs(monkeypatch)
    kw = dict(audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture) if mic else {}
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            ffmpeg_exe="sahte-ffmpeg", clock=stepping_clock(), **kw)
    waiter_in = waiting_stop_signal(monkeypatch)
    real_kill = rec._kill

    def kill_once_the_second_stop_waits(proc):
        assert waiter_in.wait(15), "ikinci stop() kapanışı beklemeye girmedi"
        real_kill(proc)
    monkeypatch.setattr(rec, "_kill", kill_once_the_second_stop_waits)
    rec.start(RecordRect(0, 0, 160, 120))                               # kare 76,8 KB > boru tamponu
    if fake == "okumayi-birakan":
        wait_until(lambda: writer_blocked_in_pipe_write(rec))           # yazıcı borunun kilidini tutarak bekliyor
    else:
        wait_until(lambda: rec.frames_written >= 3)                     # ffmpeg okuyor, kayıt sürüyor
    outcomes: list = [None, None]
    stoppers = [threading.Thread(target=lambda i=i: outcomes.__setitem__(i, _outcome(rec.stop)), daemon=True)
                for i in range(2)]
    try:
        stoppers[0].start()
        wait_until(lambda: rec.state is RecorderState.FINALIZING)
        stoppers[1].start()                                             # pencere kapatma + işçi gibi ikinci stop()
        for t in stoppers:
            t.join(15)
        assert not any(t.is_alive() for t in stoppers), "stop() takılı kaldı"
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()                                                # (düzeltmesiz kodda takılı stop()'u çöz)
        for t in stoppers:
            t.join(10)
    assert outcomes[0] == ("dönüş", rec.last_path), outcomes
    assert outcomes[1][0] == "istisna" and isinstance(outcomes[1][1], RecorderError), outcomes
    assert rec.state is RecorderState.IDLE and rec.error is not None
    assert rec.error.startswith("ffmpeg yanıt vermedi; kayıt zorla kapatıldı"), rec.error
    assert "büyük olasılıkla" in rec.error and "açılmaz" in rec.error, rec.error
    assert str(outcomes[1][1]) == rec.error
    assert len(procs) == 1 and procs[0].returncode is not None          # öldürüldü ve toplandı (zombi değil)
    assert calls == [], calls                                           # birleştirme / süre ölçümü denenmedi
    kept = list(_raw_files(rec.last_path)) if mic else [rec.last_path]
    for f in kept:                                                      # ara dosyalar silinmedi, yerleri hatada
        assert f.exists() and str(f) in rec.error, (f, rec.error)


def test_ffmpeg_that_finishes_slowly_after_eof_is_not_killed(tmp_path, monkeypatch):
    """EOF'tan sonra ffmpeg dosyayı bitirirken (kalan kareler, moov; yavaş disk) sabit FFMPEG_EXIT_S dolunca
    öldürülüyordu: dosyayı yazmaya devam etse de. Şimdi dosya büyüdükçe beklenir; ffmpeg kendisi çıkar."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "FFMPEG_EXIT_S", 0.5)
    body = """
        with open(out, "wb") as f:
            while stdin.read(65536):
                pass
            for _ in range(40):                     # EOF'tan sonra 2 sn: dosya her 50 ms'de büyüyor
                f.write(b"\\0" * 4096)
                f.flush()
                time.sleep(0.05)
        open(out + ".bitti", "wb").close()
        """
    procs = python_ffmpeg(monkeypatch, tmp_path, body)
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            ffmpeg_exe="sahte-ffmpeg", clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 3)
    try:
        outcome = _outcome(rec.stop)
    finally:
        for p in procs:
            if p.poll() is None:
                p.kill()
    path = rec.last_path
    assert outcome == ("dönüş", path) and rec.error is None, (outcome, rec.error)
    assert procs[0].returncode == 0 and Path(str(path) + ".bitti").exists()     # kendisi bitirdi


def test_recording_ffmpeg_writes_moov_at_the_end_and_only_the_final_mux_uses_faststart(tmp_path):
    """Ara videoda +faststart vardı: ffmpeg EOF'tan sonra bütün dosyayı yeniden yazar (moov'u başa taşımak için 7 GB
    oku + yaz, dakikalar); bu sırada kare sayısı artmaz, dosya boyu da değişmez (yerinde kaydırma), kapanış onu
    'yanıt vermiyor' sayıp bütün dersi kaybettirebilirdi. Kayıt ffmpeg'i moov'u sona yazar (EOF'tan sonra saniyeler);
    faststart yalnız birleşik dosyada (birleştirmenin zaman aşımı kayıt süresiyle ölçeklenir)."""
    out = tmp_path / "k.mp4"
    for enc in ("libx264", "h264_videotoolbox"):
        assert "+faststart" not in " ".join(ffmpeg_args("ffmpeg", 640, 480, 60, out, encoder=enc))
    args = mux_args("ffmpeg", tmp_path / "v.mp4", tmp_path / "a.wav", out, 0.0, video_s=10.0)
    assert args[args.index("-movflags") + 1] == "+faststart"


def test_mux_args_keep_the_audio_tail_when_the_video_ends_early(tmp_path):
    """Video durdurma anından erken bittiyse (kodlayıcı yetişemedi, borç yazılmadı) -shortest sesin ucunu keserdi:
    dersin son sözleri birleşik dosyada yok, ara WAV da siliniyordu. end_s verilince çıktı -t ile sesin ucunda biter
    (video izi kısa kalır, oynatıcı son kareyi tutar); apad yine sınırlı. end_s yoksa eskisi gibi -shortest."""
    v, a, out = tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4"
    tail = mux_args("ffmpeg", v, a, out, 0.25, video_s=3.0, end_s=4.5)
    assert "-shortest" not in tail and tail[tail.index("-t") + 1] == "4.500" and tail[-1] == str(out)
    assert tail[tail.index("-af") + 1].split(",")[-1] == "apad=whole_dur=5.500"
    assert tail.index("-t") > tail.index("-af")                         # çıkış seçeneği (girişi kırpmaz)
    plain = mux_args("ffmpeg", v, a, out, 0.25, video_s=3.0)
    assert "-shortest" in plain and "-t" not in plain


@needs_ffmpeg
@pytest.mark.parametrize("offset, rate", [(0.25, None), (-0.1, None), (0.0, 48480)])
def test_mux_with_the_audio_tail_keeps_video_and_audio_whole(tmp_path, offset, rate):
    """Gerçek ffmpeg: 3 sn video + 5 sn ses, end_s=4,5: video izi 3 sn (kopya), ses 4,5 sn, dosya 4,5 sn."""
    exe = find_ffmpeg()
    video, wav, out = tmp_path / "v.mp4", tmp_path / "a.wav", tmp_path / "o.mp4"
    _write_test_media(exe, video, wav, 3.0, 5.0)
    res = subprocess.run(mux_args(exe, video, wav, out, offset, asetrate=rate, video_s=3.0, end_s=4.5),
                         capture_output=True, timeout=60)
    assert res.returncode == 0, res.stderr[-300:]
    assert abs(_stream_seconds(exe, out, "-an") - 3.0) < 0.06
    assert abs(_stream_seconds(exe, out, "-vn") - 4.5) < 0.06
    assert media_duration(exe, out) == pytest.approx(4.5, abs=0.06)


# --- O3: kayıt ortasında ölen ffmpeg, düşen birleştirme -------------------------------------------------------

@needs_ffmpeg
def test_ffmpeg_that_dies_mid_lesson_keeps_the_raw_files_and_says_what_happened(tmp_path):
    """O3 (son inceleme s4): kayıt ortasında ffmpeg ölünce (kodlayıcı çöktü, bellek bitti) birleştirme düşüyor, BOZUK
    ara video son dosya adına taşınıyordu (48 B, 'moov atom not found'); hata yalnız 'ffmpeg borusu kapandı: ayrıntı
    yok' diyordu, sağlam WAV'ın yeri hiçbir yerde yoktu (sebep durum satırına bile gitmeyen audio_error'daydı). Şimdi
    ara video son ada taşınmaz, açılmayan videoyla birleştirme denenmez; hata kendi başına anlaşılır: ne oldu, video
    ve ses ne durumda, dosyalar nerede."""
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 40)                        # 2 sn video
    rec._session.proc.kill()                                            # kodlayıcı çöktü (moov yazılmadı)
    wait_until(lambda: rec.failed)                                      # yazıcı kırık boruyu gördü
    path = rec.stop()
    video, wav = _raw_files(path)
    assert not path.exists()                                            # bozuk video son ada taşınmadı
    assert video.exists() and wav.exists()
    err = rec.error or ""
    assert re.match(r"ffmpeg kayıt sırasında durdu \(0:0\d\. dakikada, çıkış kodu -?\d+\)\.", err), err
    assert "ffmpeg dosyayı bitiremediği için video büyük olasılıkla hiç açılmaz" in err, err
    assert f"{video} (video okunamadı)" in err, err
    assert re.search(re.escape(f"{wav} (ses sağlam, ") + r"0:0\d\)", err), err
    assert "ayrıntı yok" not in err and "birleştirilemedi" not in (rec.audio_error or ""), (err, rec.audio_error)
    assert media_duration(find_ffmpeg(), wav) >= 2.0                    # ses sağlam


def encoder_dies_after(seconds: float, fps: int = 20, w: int = 160, h: int = 120) -> str:
    """python_ffmpeg gövdesi: seconds kadar kare okur, gerçek ffmpeg'le o uzunlukta açılan bir MP4 yazar (dosyayı
    bitirmiş kodlayıcı), sonra hatayla çıkar: kayıt ortasında kodlayıcı hatasıyla duran ffmpeg."""
    return (f"import subprocess\nfor _ in range({round(seconds * fps)}):\n    stdin.read({w * h * 4})\n"
            f"subprocess.run([{find_ffmpeg()!r}, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', "
            f"'testsrc=s={w}x{h}:r={fps}:d={seconds}', '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', "
            f"'yuv420p', out], check=True)\nsys.stderr.write('Error while encoding\\n')\nsys.exit(1)\n")


@needs_ffmpeg
def test_ffmpeg_that_stops_mid_lesson_but_finishes_the_file_still_gets_its_sound(tmp_path, monkeypatch):
    """ffmpeg kayıt ortasında hatayla çıktı ama dosyayı bitirdi (kodlayıcı hatası; moov yazıldı): video o ana dek
    açılır. Ses yine birleştirilir (o ana dek kaydedilen tek dosyada); kayıt hatayla bittiği için ham dosyalar
    silinmez, hata ne olduğunu, birleşik dosyayı ve ham dosyaların yerini söyler."""
    python_ffmpeg(monkeypatch, tmp_path, encoder_dies_after(2.0))
    rec = MssFfmpegRecorder(lambda: tmp_path / "rec", fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.failed, timeout=30)
    path = rec.stop()
    video, wav = _raw_files(path)
    exe = find_ffmpeg()
    assert media_duration(exe, video) == pytest.approx(2.0, abs=0.1) and wav.exists()
    err = rec.error or ""
    assert re.match(r"ffmpeg kayıt sırasında durdu \(0:0\d\. dakikada, çıkış kodu 1\)\. Video o ana dek "
                    r"kaydedildi \(0:02\)\. Ses birleştirildi: ", err), err
    assert f"Ses birleştirildi: {path}\nDosyalar silinmedi:\n{video} (video 0:02)\n{wav} (ses sağlam, 0:0" in err, err
    assert err.endswith("ffmpeg çıktısı: Error while encoding"), err
    assert _stream_seconds(exe, path, "-an") == pytest.approx(2.0, abs=0.15)      # birleşik dosya videonun tamamı
    assert _stream_seconds(exe, path, "-vn") == pytest.approx(2.0, abs=0.15)      # ... sesiyle


MUX_FAILS = {    # birleştirme ffmpeg'i yerine: yarım çıktı yazıp düşer (hata kodu) ya da takılır (zaman aşımı)
    "hata kodu": "sys.stderr.write('Conversion failed!\\n'); sys.exit(1)",
    "zaman aşımı": "time.sleep(30)",
}


@needs_ffmpeg
@pytest.mark.parametrize("fail", list(MUX_FAILS))
def test_failed_mux_does_not_move_the_raw_video_and_names_both_files(tmp_path, monkeypatch, fail):
    """O3: birleştirme düşerse (hata kodu, zaman aşımı) ara video son ada taşınıyor, WAV'ın yeri söylenmiyordu;
    'Ses birleştirilemedi' yalnız durum satırındaydı, kayıt 'kaydedildi' görünüyordu. Şimdi ham video ve ses yerinde
    kalır, yarım birleşik dosya silinir, hata ne olduğunu, iki dosyanın durumunu ve yerini söyler."""
    import sys
    from matematigin_mantigi.core import recorder as r
    script = "import sys, time; open(sys.argv[-1], 'wb').write(b'yarim'); " + MUX_FAILS[fail]
    monkeypatch.setattr(r, "mux_args", lambda exe, video, wav, out, *a, **k: [sys.executable, "-c", script, str(out)])
    monkeypatch.setattr(r, "_mux_timeout", lambda duration: 1.0)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=FakeAudioCapture, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 20)
    path = rec.stop()
    video, wav = _raw_files(path)
    assert path.read_bytes() == b"yarim" and video.exists() and wav.exists()  # kuşkulu çıktı da korunur
    err = rec.error or ""
    assert err.startswith("Ses ile görüntü birleştirilemedi"), err
    assert ("Conversion failed!" in err) if fail == "hata kodu" else ("zaman aşımı" in err), err
    assert re.search(re.escape(f"{video} (video ") + r"0:0\d\)", err), err
    assert re.search(re.escape(f"{wav} (ses sağlam, ") + r"0:0\d\)", err), err
    assert abs(_stream_seconds(find_ffmpeg(), video, "-an") - rec.frames_written / 20) < 0.15    # video tam


def test_mux_timeout_grows_with_the_lesson():
    """Birleştirmenin zaman aşımı kayıt süresiyle büyür: 60 dk'lık derste 7 GB'ın kopyası + faststart yavaş harici
    diskte dakikalar sürer. Sabit (en kısa) sınır uzun dersin birleştirmesini düşürürdü: ham dosyalar kalır ama ders
    tek dosya olmaz, 'Kayıt hatası' çıkar. Kısa kayıtta en az MUX_MIN_S."""
    from matematigin_mantigi.core.recorder import MUX_MIN_S, _mux_timeout
    assert _mux_timeout(3600) == 7200
    assert _mux_timeout(30) == MUX_MIN_S == 120


# --- k1/k2: mikrofonun kapanışı sınırlı, yarım açılan mikrofon iz bırakmaz -----------------------------------

@needs_ffmpeg
def test_microphone_that_never_closes_does_not_hold_the_video_and_its_file_is_named(tmp_path, monkeypatch):
    """k1 (son inceleme s5): mikrofonun kapanması kapanışın tek sınırsız adımıydı ve ffmpeg'e EOF'tan ÖNCE koşuyordu:
    ses sürücüsü stop()'ta takılınca kaydedici sonsuza dek 'kaydediliyor'da kalıyor, ffmpeg EOF almadığı için video
    bitmiyordu (moov yok). Şimdi mikrofon yardımcı iş parçacığında kapanır, ffmpeg beklemeden EOF alır; mikrofon
    AUDIO_STOP_S içinde kapanmazsa video sessiz kaydedilir, hata sesin ayrı dosyada durduğunu ve yerini söyler."""
    from matematigin_mantigi.core import recorder as r
    release, entered = threading.Event(), threading.Event()

    class StuckMic(FakeAudioCapture):
        def start(self, path):                                          # gerçek yakalayıcı gibi WAV başta açılır
            super().start(path)
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(bytes(9600))

        def stop(self):
            entered.set()
            release.wait(60)                                            # sürücü takıldı (test sonunda bırakılır)
            return super().stop()
    monkeypatch.setattr(r, "AUDIO_STOP_S", 1.0)                         # gerçek sınır 25 sn
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="Sahte Mikrofon", audio_factory=StuckMic, clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    wait_until(lambda: rec.frames_written >= 20)
    try:
        path = rec.stop()
        assert entered.is_set() and not release.is_set()                # mikrofon hâlâ takılı, kapanış bitti
    finally:
        release.set()
    assert rec.state is RecorderState.IDLE
    exe = find_ffmpeg()
    assert abs(_stream_seconds(exe, path, "-an") - rec.frames_written / 20) < 0.15    # video bitti (EOF aldı)
    _, wav = _raw_files(path)
    err = rec.error or ""
    assert re.match(r"Mikrofon \d+ sn içinde kapanmadı \(ses sürücüsü yanıt vermedi\); ses videoya eklenemedi\. "
                    r"Video sessiz kaydedildi: ", err), err
    assert f"{path}\nSes ayrı dosyada (silinmedi): {wav}" in err, err


@needs_ffmpeg
def test_driver_that_hangs_closing_the_stream_still_gives_a_recording_with_sound(tmp_path, monkeypatch):
    """k1, gerçek AudioCapture: sürücü akışı kapatırken takılırsa (s5) AudioCapture STREAM_STOP_S sonra o ana dek gelen
    sesi WAV'a yazıp kapatır; kayıt sesiyle birleştirilir, ses uyarısı mikrofonun düzgün kapanmadığını söyler."""
    from matematigin_mantigi.core import audio_capture as ac
    from tests.test_audio_capture import FakeSoundDevice
    release = threading.Event()
    sd = FakeSoundDevice(blocks=50)                                     # 1 sn ses
    sd.InputStream.stop = lambda stream: release.wait(60)
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    monkeypatch.setattr(ac.AudioCapture, "STREAM_STOP_S", 0.5)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="USB Mikrofon", clock=stepping_clock())
    rec.start(RecordRect(0, 0, 160, 120))
    assert sd.fed.wait(10)
    wait_until(lambda: rec.frames_written >= 20)
    try:
        path = rec.stop()
    finally:
        release.set()
    assert rec.error is None, rec.error
    assert rec.audio_result.samples == 50 * 960
    assert "Mikrofon düzgün kapanmadı (ses sürücüsü akışı kapatamadı (0,5 sn içinde yanıt vermedi))" in (
        rec.audio_error or ""), rec.audio_error
    assert _stream_seconds(find_ffmpeg(), path, "-vn") >= 0.9            # ses birleşik dosyada


@needs_ffmpeg
def test_microphone_that_cannot_open_leaks_no_writer_and_leaves_no_wav(tmp_path, monkeypatch):
    """k2 (son inceleme s6): InputStream açılamayınca her denemede bir yazıcı iş parçacığı ve açık 0 B'lık WAV
    kalıyordu (Windows'ta kilitli). Şimdi kayıt sessiz sürer, iz kalmaz."""
    from matematigin_mantigi.core import audio_capture as ac
    from tests.test_audio_capture import FakeSoundDevice
    sd = FakeSoundDevice(blocks=0)

    class Busy:
        def __init__(self, *a, **k):
            raise RuntimeError("Error opening InputStream: Device unavailable [PaErrorCode -9985]")
    sd.InputStream = Busy
    monkeypatch.setattr(ac, "_sd", lambda: sd)

    def writers() -> int:
        return sum(1 for t in threading.enumerate() if getattr(getattr(t, "_target", None), "__name__", "") ==
                   "_write_loop")
    before = writers()
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="USB Mikrofon", clock=stepping_clock())
    for _ in range(2):
        rec.start(RecordRect(0, 0, 160, 120))
        wait_until(lambda: rec.frames_written >= 5)
        path = rec.stop()
        assert rec.audio_error == "Mikrofon açılamadı: Error opening InputStream: Device unavailable [PaErrorCode " \
                                  "-9985]", rec.audio_error
        assert path.exists() and rec.error is None, rec.error
    assert writers() == before
    assert len(list(tmp_path.glob("*.wav"))) == 2  # Değiştirilmiş bir yolu silmemek için ham WAV'lar kalır.


MIC_STILL_CLOSING = "Mikrofon açılmadı: önceki kaydın mikrofonu hâlâ kapanmadı (uygulamayı yeniden başlatın)"
NEXT_ONES_SILENT = "ikrofon kapanana dek yeni kayıtlar mikrofonsuz başlar (uygulamayı yeniden başlatın)"


def _has_audio_stream(path: Path) -> bool:
    return b"Audio:" in subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True).stderr


def _start_in_thread(rec, rect) -> tuple[threading.Thread, threading.Event]:
    """start()'ı pencerede olduğu gibi (R: arayüz iş parçacığı) ayrı iş parçacığında çağırır: takılırsa test donmaz,
    olay kurulmaz."""
    started = threading.Event()
    starter = threading.Thread(target=lambda: (rec.start(rect), started.set()), daemon=True)
    starter.start()
    return starter, started


@needs_ffmpeg
def test_next_recording_does_not_open_a_microphone_that_has_not_closed_yet(tmp_path, monkeypatch):
    """R4 (son inceleme s11): mikrofonun kapanışı takılınca (k1) kaydedici AUDIO_STOP_S sonra IDLE'a dönüyor ama
    kapanış iş parçacığı ses sürücüsünde yaşıyor. Sonraki kayıt aynı aygıtı arayüz iş parçacığında ve kaydedicinin
    kilidi altında açıyordu: sürücü aygıtı kilitli tutuyorsa start() dönmüyor, arayüz donuyordu. Şimdi önceki kaydın
    mikrofonu hâlâ kapanıyorsa yeni kayıt mikrofonu hiç açmaz: sessiz başlar, uyarı sebebini söyler. Sürücü kendine
    gelince (kapanış bitti) sonraki kayıt mikrofonu yine açar. Takılan kaydın kendi hatası da bunu önceden söyler:
    arayüz sonraki kaydın uyarısını ancak o kayıt bitince gösterir, öğretmen bütün dersi sessiz kaydetmesin."""
    from matematigin_mantigi.core import recorder as r
    driver, release = threading.Lock(), threading.Event()             # ses sürücüsünün aygıt kilidi (varsayım)
    opened: list = []

    class StuckDriverMic(FakeAudioCapture):
        def start(self, path):
            opened.append(self)
            with driver:                                                # Pa_OpenStream sürücüye girer
                super().start(path)

        def stop(self):
            with driver:                                                # Pa_StopStream sürücüde takıldı
                release.wait(60)
            return super().stop()
    monkeypatch.setattr(r, "AUDIO_STOP_S", 0.5)                         # gerçek sınır 25 sn
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="USB Mikrofon", audio_factory=StuckDriverMic, clock=stepping_clock())
    rect = RecordRect(0, 0, 160, 120)
    rec.start(rect)
    wait_until(lambda: rec.frames_written >= 10)
    rec.stop()                                                          # mikrofon kapanmadı: video sessiz kaydedildi
    assert rec.state is RecorderState.IDLE and "kapanmadı" in (rec.error or ""), rec.error
    assert (rec.error or "").endswith(f"\nM{NEXT_ONES_SILENT}."), rec.error
    starter, started = _start_in_thread(rec, rect)
    try:
        assert started.wait(10), "ikinci start() ses sürücüsünü bekliyor: arayüz donardı"
        assert len(opened) == 1                                         # mikrofon açılmadı
        wait_until(lambda: rec.frames_written >= 10)
        path = rec.stop()
    finally:
        release.set()                                                   # sürücü kendine geldi
        starter.join(10)
        if rec.state is RecorderState.RECORDING:                        # (düzeltmesiz kodda ikinci kayıt açık kalmasın)
            rec.stop()
    assert rec.audio_error == MIC_STILL_CLOSING and rec.error is None, (rec.audio_error, rec.error)
    assert rec.audio_result is None and not _has_audio_stream(path) and not path.with_suffix(".wav").exists()
    assert abs(_stream_seconds(find_ffmpeg(), path, "-an") - rec.frames_written / 20) < 0.15      # video tam
    wait_until(lambda: not rec._mic_still_closing())                    # önceki kaydın kapanışı bitti
    rec.start(rect)
    wait_until(lambda: rec.frames_written >= 10)
    path = rec.stop()
    assert len(opened) == 2 and rec.audio_error is None and rec.error is None, (rec.audio_error, rec.error)
    assert _has_audio_stream(path)                                      # mikrofon yine açıldı


@needs_ffmpeg
def test_next_recording_does_not_reopen_a_stream_the_driver_is_still_closing(tmp_path, monkeypatch):
    """R4, gerçek AudioCapture: sürücü akışı kapatırken takılınca (s5) AudioCapture STREAM_STOP_S sonra o ana dek gelen
    sesle döner (kayıt sesiyle kaydedilir), ama akışı kapatan iş parçacığı sürücüde kalır. Sonraki kayıt aynı sürücüde
    akış açmaz (Pa_OpenStream da takılabilir, arayüz donardı): sessiz başlar, uyarı sebebini söyler."""
    from matematigin_mantigi.core import audio_capture as ac
    from tests.test_audio_capture import FakeSoundDevice
    driver, release = threading.Lock(), threading.Event()
    sd = FakeSoundDevice(blocks=50)                                     # 1 sn ses
    real_open = sd.InputStream.__init__
    opened: list = []

    def open_stream(stream, *a, **k):                                   # Pa_OpenStream: aynı sürücü kilidi
        opened.append(stream)
        with driver:
            real_open(stream, *a, **k)

    def stuck_stop(stream):                                             # Pa_StopStream sürücüde takıldı
        with driver:
            release.wait(60)
    sd.InputStream.__init__, sd.InputStream.stop = open_stream, stuck_stop
    monkeypatch.setattr(ac, "_sd", lambda: sd)
    monkeypatch.setattr(ac.AudioCapture, "STREAM_STOP_S", 0.3)
    rec = MssFfmpegRecorder(lambda: tmp_path, fps=20, grabber=synthetic_grabber, out_height=0,
                            audio_device="USB Mikrofon", clock=stepping_clock())
    rect = RecordRect(0, 0, 160, 120)
    rec.start(rect)
    assert sd.fed.wait(10)
    wait_until(lambda: rec.frames_written >= 20)
    first = rec.stop()
    assert rec.error is None and "Mikrofon düzgün kapanmadı" in (rec.audio_error or ""), (rec.error, rec.audio_error)
    assert f"; o ana dek gelen ses kayıtta; m{NEXT_ONES_SILENT}" in (rec.audio_error or ""), rec.audio_error
    assert _has_audio_stream(first)                                     # o ana dek gelen sesle kaydedildi
    starter, started = _start_in_thread(rec, rect)
    try:
        assert started.wait(10), "ikinci start() ses sürücüsünü bekliyor: arayüz donardı"
        assert len(opened) == 1                                         # yeni akış açılmadı
        wait_until(lambda: rec.frames_written >= 10)
        path = rec.stop()
    finally:
        release.set()
        starter.join(10)
        if rec.state is RecorderState.RECORDING:
            rec.stop()
    assert rec.audio_error == MIC_STILL_CLOSING and rec.error is None, (rec.audio_error, rec.error)
    assert rec.audio_result is None and not _has_audio_stream(path)

