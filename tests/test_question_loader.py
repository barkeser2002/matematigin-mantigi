import errno
import json
import os
import struct
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path

import openpyxl
import pytest

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question
from matematigin_mantigi.core.question_loader import (ALL_COLUMNS, REQUIRED_COLUMNS, QuestionTemplateError,
                                                      ensure_template, load_questions, write_questions,
                                                      write_template)


def test_write_then_load_round_trip(tmp_path):
    p = write_template(tmp_path / "sorular_sablon.xlsx")
    qs = load_questions(p)
    assert [q.id for q in qs] == ["S1", "S2", "S3"]
    assert qs[0].soru == "3x + 5 = 20 ise x kaçtır?" and qs[0].sinif == 7
    assert qs[2].hints == ("Paydaları eşitle: 6 ortak payda.", "2/3 = 4/6 olur; 4/6 + 1/6.", "Cevap: 5/6.")
    assert qs[0].options == ("3", "4", "5", "6") and qs[0].image is None
    wb = openpyxl.load_workbook(p)
    assert [c.value for c in wb.active[1]] == list(ALL_COLUMNS)
    assert wb.active["A1"].font.bold


def test_optional_columns_round_trip(tmp_path):
    q = Question("S9", "Konu", 8, "Soru?", ("h1", "h2", "h3", "h4"), "42", ("1", "2", "3", "4"), "img/s9.png")
    p = write_questions(tmp_path / "q.xlsx", [q])
    (tmp_path / "img").mkdir()
    loaded = load_questions(p)[0]
    assert loaded.hints == ("h1", "h2", "h3", "h4") and loaded.options == ("1", "2", "3", "4")
    assert loaded.image == str(tmp_path / "img" / "s9.png")         # xlsx klasörüne göre çözülür


def test_ensure_template_creates_once(tmp_path):
    p = tmp_path / "s.xlsx"
    assert not p.exists()
    ensure_template(p); mtime = p.stat().st_mtime
    ensure_template(p)
    assert p.stat().st_mtime == mtime


def test_missing_column_is_reported(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3"])   # cevap yok
    p = tmp_path / "bad.xlsx"; wb.save(p)
    with pytest.raises(QuestionTemplateError, match="cevap"):
        load_questions(p)


def test_required_only_header_still_loads(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S1", "Konu", "7", "Eski şablon sorusu", "a", "b", "c", "d"])
    p = tmp_path / "old.xlsx"; wb.save(p)
    q = load_questions(p)[0]
    assert q.options == () and q.image is None and q.hints == ("a", "b", "c")


def test_blank_rows_skipped_and_missing_hints_dropped(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S9", "Konu", "8", "Soru metni", "ipucu a", None, "", "42"])
    ws.append([None] * 8)
    ws.append(["S10", "Konu", None, "İkinci soru", None, None, None, "x"])
    p = tmp_path / "ok.xlsx"; wb.save(p)
    qs = load_questions(p)
    assert len(qs) == 2
    assert qs[0].hints == ("ipucu a",) and qs[0].sinif == 8
    assert qs[1].hints == () and qs[1].sinif is None


def test_missing_question_text_names_the_row(tmp_path):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(list(REQUIRED_COLUMNS))
    ws.append(["S1", "Konu", "7", None, "a", "b", "c", "d"])
    p = tmp_path / "row.xlsx"; wb.save(p)
    with pytest.raises(QuestionTemplateError, match="2"):
        load_questions(p)


def test_empty_file_raises(tmp_path):
    p = write_template(tmp_path / "empty.xlsx", with_samples=False)
    with pytest.raises(QuestionTemplateError, match="hiç soru"):
        load_questions(p)


# --- Excel'in saklayamadığı metin dosyayı okunamaz yapmaz (Q2) ------------------------------------------------
def test_clean_text_drops_characters_xml_cannot_hold():
    """Q2: clean_text yalnız C0 denetim karakterlerini atıyordu; U+FFFE, U+FFFF ve tek başına vekil (U+D800-U+DFFF)
    Kaydet'ten geçip dosyayı okunamaz kılıyordu (ParseError; sonraki açılış örnek sorularla). Hepsi atılır; sekme,
    satır sonu ve geçerli BMP dışı karakterler (𝑥, emoji) korunur."""
    from matematigin_mantigi.core.question_loader import clean_text
    assert clean_text("a\ufffeb\uffffc\ud800d\udfffe\x03f") == "abcdef"
    assert clean_text("x\ty\nz \U0001d465 \U0001f600") == "x\ty\nz \U0001d465 \U0001f600"
    assert clean_text("Word\x0bsatırı") == "Word\nsatırı"


def test_text_starting_with_equals_or_error_code_stays_text(tmp_path):
    """'=' ile başlayan metni openpyxl formül olarak yazıyordu: okurken boş geliyordu (ipucu ve şık sessizce
    kayboluyor, soru metni 'soru boş' hatasıyla dosyayı okunamaz yapıyordu); '#N/A' gibi metin hata hücresi oluyordu.
    Hepsi metin olarak yazılır ve aynen geri okunur."""
    q = Question("S1", "Konu", 7, "=2+3 kaçtır?", ("= 5 olur", "#DIV/0! değil"), "#N/A", ("=A", "b"), None)
    p = write_questions(tmp_path / "sorular.xlsx", [q])
    back = load_questions(p)[0]
    assert (back.soru, back.hints, back.cevap, back.options) == (q.soru, q.hints, q.cevap, q.options)


@pytest.mark.parametrize("bad", ["\uffff", "\ufffe", "\ud800"], ids=["FFFF", "FFFE", "vekil"])
def test_write_that_cannot_be_read_back_changes_nothing(tmp_path, bad):
    """Q2: yeni sürüm geçici dosyaya yazılıp geri okunur; okunamazsa (temizlenmemiş metin, başka bir çağıran) yerine
    konmaz: soru dosyası da önceki yedek de bayt bayt aynı kalır, geçici dosya kalmaz, hata çağırana gider."""
    from matematigin_mantigi.core.question_loader import UnreadableWriteError
    p = tmp_path / "sorular.xlsx"
    write_questions(p, SAMPLE_QUESTIONS)
    write_questions(p, SAMPLE_QUESTIONS[:2])
    before, bak_before = p.read_bytes(), _bak(p).read_bytes()
    with pytest.raises(UnreadableWriteError):
        write_questions(p, [Question("S1", "K", 7, f"Kopyalanan metin {bad} devam", (), "c", ())])
    assert p.read_bytes() == before and _bak(p).read_bytes() == bak_before
    assert _leftovers(tmp_path, "sorular.xlsx", "sorular.xlsx.bak") == []


# --- yazım yarıda kalırsa soru dosyası bozulmaz; önceki sürüm .bak'ta (#29, B-2) ------------------------------
def _bak(p: Path) -> Path:
    return p.with_name(p.name + ".bak")


def _leftovers(folder: Path, *keep: str) -> list[str]:
    return sorted(x.name for x in folder.iterdir() if x.name not in keep)


def test_write_keeps_the_previous_version_as_bak(tmp_path):
    """Her yazımdan önce dosyanın o anki hâli aynı klasörde <ad>.bak olarak saklanır; ilk yazımda yedek yok."""
    p = tmp_path / "sorular.xlsx"
    write_questions(p, SAMPLE_QUESTIONS)
    assert not _bak(p).exists()
    v1 = p.read_bytes()
    write_questions(p, SAMPLE_QUESTIONS[:2])
    assert _bak(p).read_bytes() == v1 and len(load_questions(p)) == 2
    assert _leftovers(tmp_path, "sorular.xlsx", "sorular.xlsx.bak") == []


def test_failed_write_leaves_the_question_file_intact_and_no_temp_file(tmp_path, monkeypatch):
    """B-2: wb.save doğrudan hedefe yazıyordu; yazımın ortasındaki hata (dolu disk, çıkarılan USB) dosyayı yarım
    bırakıyordu (5575 -> 2289 bayt, açılışta KeyError). Yazım aynı klasörde geçici dosyaya yapılır, yalnız tamamlanınca
    os.replace ile yerine konur; hatada geçici dosya silinir, soru dosyası eski hâliyle kalır. Yeni sürüm yazılamadıysa
    önceki yedeğe de dokunulmaz (Q2: yedek yeni sürüm sağlam çıktıktan sonra alınır)."""
    p = tmp_path / "sorular.xlsx"
    write_questions(p, SAMPLE_QUESTIONS[:2])
    write_questions(p, SAMPLE_QUESTIONS)
    before, bak_before = p.read_bytes(), _bak(p).read_bytes()

    def half_written(self, filename):
        Path(filename).write_bytes(b"PK\x03\x04 yarim kalan zip")
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(openpyxl.Workbook, "save", half_written)
    with pytest.raises(OSError):
        write_questions(p, SAMPLE_QUESTIONS[:1])
    assert p.read_bytes() == before and len(load_questions(p)) == 3 and _bak(p).read_bytes() == bak_before
    assert _leftovers(tmp_path, "sorular.xlsx", "sorular.xlsx.bak") == []


def test_file_locked_by_excel_is_not_replaced_and_no_temp_file_is_left(tmp_path, monkeypatch):
    """Windows'ta dosya Excel'de açıkken yerine koyma (os.replace) PermissionError verir: soru dosyası değişmez,
    geçici dosya kalmaz, hata çağırana (editörün mesajına) ulaşır."""
    p = tmp_path / "sorular.xlsx"
    write_questions(p, SAMPLE_QUESTIONS)
    before = p.read_bytes()
    real_replace = os.replace

    def locked(src, dst, *a, **k):
        if Path(dst) == p:
            raise PermissionError(errno.EACCES, "The process cannot access the file", str(dst))
        return real_replace(src, dst, *a, **k)
    monkeypatch.setattr(os, "replace", locked)
    with pytest.raises(PermissionError):
        write_questions(p, SAMPLE_QUESTIONS[:1])
    assert p.read_bytes() == before
    assert _leftovers(tmp_path, "sorular.xlsx", "sorular.xlsx.bak") == []


# Gerçek bir işletim sistemi hatası, yazımın ORTASINDA: RLIMIT_FSIZE yumuşak sınırı (Python SIGXFSZ'yi yok sayar,
# write() EFBIG döner). Ayrı süreçte: sınır o süreçteki her dosya yazımını etkiler.
_DISK_FULL = textwrap.dedent('''
    import json, random, resource, string
    from pathlib import Path
    from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question
    from matematigin_mantigi.core.question_loader import load_questions, write_questions

    def limited(nbytes, fn):
        soft, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
        resource.setrlimit(resource.RLIMIT_FSIZE, (nbytes, hard))
        try:
            fn()
            return None
        except OSError as err:
            return err.errno
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, (soft, hard))

    def loads(p):
        try:
            return len(load_questions(p))
        except Exception as err:
            return type(err).__name__

    path, bak = Path("sorular.xlsx"), Path("sorular.xlsx.bak")
    rnd = random.Random(0)

    def big(n):
        return [Question(f"S{i}", "Konu", 7, "".join(rnd.choice(string.ascii_letters) for _ in range(3000)), (), "",
                         ()) for i in range(n)]
    write_questions(path, big(5))
    write_questions(path, big(5))
    v2, old_bak = path.read_bytes(), bak.read_bytes()
    small = SAMPLE_QUESTIONS[:2]
    probe = Path("olcu.xlsx")
    write_questions(probe, small)
    small_size = probe.stat().st_size
    probe.unlink()
    res = {}
    # 1) yeni (küçük) sürüm yazılıp doğrulanır, ardından alınan yedek kopyası (büyük dosya) yarıda kalır: ne soru
    #    dosyası ne önceki yedek bozulur
    limit = (small_size + len(v2)) // 2
    res["olculer"] = [small_size, limit, len(v2)]
    res["yedekte_hata"] = limited(limit, lambda: write_questions(path, small))
    res["yedekte_dosya_ayni"], res["yedekte_onceki_yedek_ayni"] = path.read_bytes() == v2, bak.read_bytes() == old_bak
    # 2) yeni (büyük) çalışma kitabının yazımı yarıda kalır: yedek o sürüm sağlam yazılmadan alınmadığı için o da aynı
    res["yazimda_hata"] = limited(len(v2) + 1000, lambda: write_questions(path, big(8)))
    res["yazimda_dosya_ayni"], res["yazimda_yuklenen"] = path.read_bytes() == v2, loads(path)
    res["yazimda_onceki_yedek_ayni"] = bak.read_bytes() == old_bak
    res["dosyalar"] = sorted(p.name for p in Path(".").iterdir())
    print("SONUC " + json.dumps(res))
''')


def _run_script(tmp_path, source: str) -> dict:
    script = tmp_path / "calistir.py"
    script.write_text(source, encoding="utf-8")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", XDG_CONFIG_HOME=str(tmp_path / "cfg"))
    r = subprocess.run([sys.executable, str(script)], cwd=tmp_path, env=env, capture_output=True, text=True,
                       timeout=120)
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("SONUC ")), None)
    assert r.returncode == 0 and line is not None, f"çıkış {r.returncode}:\n{r.stdout}\n{r.stderr[-2000:]}"
    return json.loads(line[len("SONUC "):])


@pytest.mark.skipif(sys.platform == "win32", reason="RLIMIT_FSIZE yalnız POSIX'te")
def test_disk_full_in_the_middle_of_a_write_keeps_the_file_and_the_backup(tmp_path):
    """B-2'nin gerçek hâli (yazım ortasında EFBIG): ne yedek kopyası ne yeni çalışma kitabı yarıda kalınca soru
    dosyası ya da önceki yedek bozulur; geçici dosya kalmaz. Q2: yedek yeni sürüm yazılıp geri okunduktan sonra
    alındığı için yeni sürüm yarıda kalınca önceki yedek de değişmez."""
    res = _run_script(tmp_path, _DISK_FULL)
    assert res["yedekte_hata"] == errno.EFBIG and res["yazimda_hata"] == errno.EFBIG, res
    assert res["olculer"][0] < res["olculer"][1] < res["olculer"][2], res
    assert res["yedekte_dosya_ayni"] and res["yedekte_onceki_yedek_ayni"], res
    assert res["yazimda_dosya_ayni"] and res["yazimda_yuklenen"] == 5 and res["yazimda_onceki_yedek_ayni"], res
    assert res["dosyalar"] == ["calistir.py", "sorular.xlsx", "sorular.xlsx.bak"], res


# --- açılış: soru dosyası okunamazsa uygulama örnek sorularla açılır (#17) -----------------------------------
CORRUPT = "dosya bozuk ya da yazımı yarıda kalmış"
SHEET = "xl/worksheets/sheet1.xml"


def _rewrite_sheet(p: Path, change) -> None:
    """xlsx'i sayfa XML'i change(bayt) ile değişmiş olarak yeniden paketler (diğer üyeler aynen)."""
    with zipfile.ZipFile(p) as z:
        items = [(info, z.read(info.filename)) for info in z.infolist()]
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in items:
            z.writestr(info, change(data) if info.filename == SHEET else data)


def _flip_compressed_sheet_bytes(p: Path) -> None:
    """Sayfanın sıkıştırılmış verisinin ortasındaki baytları bozar (diskte/eşitlemede bozulma): zlib.error."""
    data = bytearray(p.read_bytes())
    with zipfile.ZipFile(p) as z:
        info = z.getinfo(SHEET)
    name_len, extra_len = struct.unpack("<HH", data[info.header_offset + 26: info.header_offset + 30])
    start = info.header_offset + 30 + name_len + extra_len + info.compress_size // 3
    for k in range(start, start + 40):
        data[k] ^= 0x5A
    p.write_bytes(bytes(data))


def _broken(kind: str, p: Path) -> None:
    if kind == "yarim":                          # yazımı yarıda kalmış xlsx (s03: 5575 -> 2289 bayt)
        write_questions(p, SAMPLE_QUESTIONS)
        p.write_bytes(p.read_bytes()[:2289])
    elif kind == "metin":                        # adı xlsx, içi değil
        p.write_text("bu bir Excel dosyası değil", encoding="utf-8")
    elif kind == "klasor":                       # okunamayan yol
        p.mkdir()
    elif kind == "sutun":                        # başka bir çizelge: zorunlu sütun eksik
        wb = openpyxl.Workbook(); wb.active.append(["id", "soru"]); wb.save(p)
    elif kind == "yarim-sayfa":                  # sayfa XML'i yarıda kesilmiş (yarım kopya/eşitleme): ParseError
        write_questions(p, SAMPLE_QUESTIONS * 20)
        _rewrite_sheet(p, lambda xml: xml[: len(xml) // 2])
    elif kind == "bozuk-sikistirma":             # sıkıştırılmış veri bozuk: zlib.error
        write_questions(p, SAMPLE_QUESTIONS * 20)
        _flip_compressed_sheet_bytes(p)


@pytest.mark.parametrize("kind", ["yarim", "metin", "klasor", "sutun", "yarim-sayfa", "bozuk-sikistirma"])
def test_unreadable_question_file_opens_with_samples_and_names_the_file(tmp_path, monkeypatch, kind):
    """#17: açılış yalnız QuestionTemplateError'ı yakalıyordu; yarım kalmış xlsx (KeyError), xlsx olmayan dosya
    (BadZipFile) ya da okunamayan yol uygulamayı açılmaz yapıyordu (çıkış 1, pencere yok). Her hatada dosya adı ve
    sebep söylenir, uygulama örnek sorularla açılır; yedek varsa nerede olduğu da söylenir. Sorular dosyadan
    okunmadığı da söylenir (Q1): editör örnekleri o dosyanın üzerine yazmasın. Q4: yarım sayfa XML'i (ParseError) ve
    bozuk sıkıştırma (zlib.error) da 'ParseError: unclosed token…' gibi ham metinle değil, dosyanın bozuk olduğuyla
    söylenir."""
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi import app as app_mod
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda _p, title, text, *a, **k: shown.append(
        (title, text))))
    p = tmp_path / "sorular.xlsx"
    _broken(kind, p)
    _bak(p).write_bytes(b"onceki")
    assert app_mod.load_questions_or_samples(p) == (list(SAMPLE_QUESTIONS), False)
    assert len(shown) == 1 and "sorular.xlsx" in shown[0][1] and "Sebep:" in shown[0][1]
    assert "sorular.xlsx.bak" in shown[0][1] and "Örnek sorularla" in shown[0][1]
    if kind in ("yarim", "metin", "yarim-sayfa", "bozuk-sikistirma"):
        assert CORRUPT in shown[0][1], shown[0][1]
    elif kind == "sutun":
        assert "Eksik sütun" in shown[0][1], shown[0][1]


@pytest.mark.parametrize("kind", ["var", "yok"])
def test_readable_question_file_opens_from_the_file(tmp_path, monkeypatch, kind):
    """Okunabilen (ya da yokken örnek şablonla yazılan) soru dosyası: sorular dosyadan, uyarı yok."""
    from PyQt6.QtWidgets import QMessageBox
    from matematigin_mantigi import app as app_mod
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    p = tmp_path / "sorular.xlsx"
    if kind == "var":
        write_questions(p, SAMPLE_QUESTIONS[:2])
    questions, from_file = app_mod.load_questions_or_samples(p)
    assert from_file is True and shown == [] and len(questions) == (2 if kind == "var" else 3)


def test_load_backup_reads_the_previous_version(tmp_path):
    """Yedek (<ad>.bak) okunabilir: openpyxl .bak uzantısını reddeder, yedek akış olarak açılır; görsel yolları soru
    dosyasının klasörüne göre çözülür."""
    from matematigin_mantigi.core.question_loader import load_backup
    p = tmp_path / "sorular.xlsx"
    old = [Question("S1", "K", 7, "Eski soru?", (), "c", (), "sorular_gorsel/s1.png")]
    write_questions(p, old)
    write_questions(p, SAMPLE_QUESTIONS)
    loaded = load_backup(p)
    assert [q.soru for q in loaded] == ["Eski soru?"]
    assert loaded[0].image == str(tmp_path / "sorular_gorsel" / "s1.png")


def _assert_not_held_open(path: Path) -> None:
    """Süreç dosyayı açık tutmuyor. Linux'ta /proc/self/fd'den bakılır; Windows'ta açık tutamak dosyayı kilitler,
    yeniden adlandırma PermissionError (WinError 32) verir: ikisi de denenir."""
    fd_dir = Path("/proc/self/fd")
    if fd_dir.is_dir():
        target = str(path.resolve())
        held = []
        for fd in fd_dir.iterdir():
            try:
                if os.readlink(fd) == target:
                    held.append(fd.name)
            except OSError:
                pass
        assert not held, f"{path.name} açık tutamakta: fd {held}"
    moved = path.with_name("tasindi-" + path.name)
    os.replace(path, moved)
    os.replace(moved, path)


@pytest.mark.parametrize("kind", ["sutun", "bos-soru", "gecerli"])
def test_load_lets_go_of_the_file_on_every_path(tmp_path, kind):
    """read_only çalışma kitabı dosyayı açık tutar; hata wb.close()'dan önce fırlayınca (eksik sütun, boş soru)
    tutamak çöp toplayıcıya dek kalıyordu. Windows'ta bu sürede dosya yeniden adlandırılamaz, Excel'den
    kaydedilemez, editörün atomik yazımı (os.replace) da düşer (CI: WinError 32). Her yolda dosya bırakılır."""
    import gc
    path = tmp_path / "sorular_sablon.xlsx"
    if kind == "gecerli":
        write_questions(path, SAMPLE_QUESTIONS)
    else:
        wb = openpyxl.Workbook()
        wb.active.append(["id", "metin"] if kind == "sutun" else ["id", "soru"])
        wb.active.append(["S1", "Gerçek soru"] if kind == "sutun" else ["S1", None])
        wb.active.append(["S2", "İkinci"])
        wb.save(path)
    gc.disable()                                # tutamak çöp toplayıcının şansına bırakılmasın
    try:
        if kind == "gecerli":
            assert load_questions(path)
        else:
            with pytest.raises(QuestionTemplateError):
                load_questions(path)
        _assert_not_held_open(path)
    finally:
        gc.enable()
