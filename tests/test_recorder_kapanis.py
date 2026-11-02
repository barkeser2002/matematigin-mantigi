"""Kaydedicinin kapanışı: ffmpeg ancak ilerlemiyorsa öldürülür, durdurma borcu ödenmez, birleştirme düşerse ham
dosyalar kalır, mikrofon kapanışı sınırlı (son inceleme K1, O3, k1, k2).

Sahte ffmpeg'ler Python betiği (python_ffmpeg): kabuk betiği yalnız posix'te koşuyordu, bu testler Windows CI'da da
koşar. Yavaş kodlayıcı gerçek ffmpeg + SlowPipe ile: kare yazımı test izin verdikçe geçer (olayla, uyumadan)."""
import re
import subprocess
import threading
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from matematigin_mantigi.core.recorder import (MssFfmpegRecorder, RecordRect, RecorderError, RecorderState,
                                               ffmpeg_args, find_ffmpeg, media_duration, mux_args)
from tests.test_recorder import (FakeAudioCapture, _outcome, _raw_files, _stream_seconds, _write_test_media,
                                 python_ffmpeg, recorded_runs, stepping_clock, synthetic_grabber, wait_until,
                                 waiting_stop_signal, writer_blocked_in_pipe_write)

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


# --- K1: yavaş ama okuyan ffmpeg öldürülmez; durdurma borcu ödenmez -------------------------------------------

@needs_ffmpeg
@pytest.mark.parametrize("mic", [False, True], ids=["mikrofonsuz", "mikrofonlu"])
def test_slow_encoder_that_keeps_reading_is_not_killed_and_the_file_opens(tmp_path, monkeypatch, mic):
    """Kodlayıcı gerçek zamandan yavaşsa (s1: 17,7 kare/sn) yazıcının borcu birikir; durdurunca yazıcı bütün borcu
    yazmaya çalışıyor, WRITER_JOIN_S dolunca kapanış ffmpeg'i 'iş parçacığı hâlâ canlı' diye öldürüyordu. ffmpeg
    okuyordu (s1'de STOP->KILL arası 242->443 kare); moov yazılmadığı için videonun TAMAMI açılmıyordu. Şimdi büyük
    borç (STOP_DEBT_S'den büyük) yazılmaz, son kare en yeni ekran; okuyan ffmpeg öldürülmez, dosya açılır. Video
    duvar saatinden kısa kaldığı için birleştirme sesin ucunu kesmez (ses tam, son kare ekranda durur); kayıt hatasız
    biter, uyarı (durum satırı) kodlayıcının yetişemediğini söyler."""
    from matematigin_mantigi.core import recorder as r
    monkeypatch.setattr(r, "WRITER_JOIN_S", 1.0)                        # gerçek sınır 10 sn
    monkeypatch.setattr(r, "STOP_DEBT_S", 1.0)                          # bundan büyük borç yazılmaz (gerçekte 2 sn)
    fps = 20
    pipes = slow_pipes(monkeypatch)
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
    assert rec.error is None, rec.error
    assert re.match(r"Görüntü kodlayıcısı kayda yetişemedi: video \d sn erken bitiyor", rec.audio_error or ""), \
        rec.audio_error
    if mic:                                                             # ses durdurma anına dek tam
        wall = t_stop - rec.video_t0
        assert abs(_stream_seconds(exe, path, "-vn") - wall) < 0.15, wall
        assert "son kare ses bitene dek duruyor" in rec.audio_error, rec.audio_error
        assert not any(p.exists() for p in _raw_files(path))            # birleşik dosya doğrulandı


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
