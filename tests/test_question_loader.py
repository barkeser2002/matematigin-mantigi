import errno
import json
import os
import subprocess
import sys
import textwrap
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
    os.replace ile yerine konur; hatada geçici dosya silinir, soru dosyası eski hâliyle kalır."""
    p = tmp_path / "sorular.xlsx"
    write_questions(p, SAMPLE_QUESTIONS)
    before = p.read_bytes()

    def half_written(self, filename):
        Path(filename).write_bytes(b"PK\x03\x04 yarim kalan zip")
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(openpyxl.Workbook, "save", half_written)
    with pytest.raises(OSError):
        write_questions(p, SAMPLE_QUESTIONS[:1])
    assert p.read_bytes() == before and len(load_questions(p)) == 3
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
    write_questions(path, SAMPLE_QUESTIONS)
    write_questions(path, SAMPLE_QUESTIONS[:2])
    v2, old_bak = path.read_bytes(), bak.read_bytes()
    rnd = random.Random(0)
    big = [Question(f"S{i}", "Konu", 7, "".join(rnd.choice(string.ascii_letters) for _ in range(3000)), (), "", ())
           for i in range(5)]
    res = {}
    # 1) yedek kopyası yarıda kalır: ne soru dosyası ne önceki yedek bozulur
    res["yedekte_hata"] = limited(len(v2) // 2, lambda: write_questions(path, big))
    res["yedekte_dosya_ayni"], res["yedekte_onceki_yedek_ayni"] = path.read_bytes() == v2, bak.read_bytes() == old_bak
    # 2) yeni çalışma kitabının yazımı yarıda kalır (yedek sığar, büyük yeni dosya sığmaz)
    res["yazimda_hata"] = limited(max(len(v2), len(old_bak)) + 1000, lambda: write_questions(path, big))
    res["yazimda_dosya_ayni"], res["yazimda_yuklenen"] = path.read_bytes() == v2, loads(path)
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
    dosyası ya da önceki yedek bozulur; geçici dosya kalmaz."""
    res = _run_script(tmp_path, _DISK_FULL)
    assert res["yedekte_hata"] == errno.EFBIG and res["yazimda_hata"] == errno.EFBIG, res
    assert res["yedekte_dosya_ayni"] and res["yedekte_onceki_yedek_ayni"], res
    assert res["yazimda_dosya_ayni"] and res["yazimda_yuklenen"] == 2, res
    assert res["dosyalar"] == ["calistir.py", "sorular.xlsx", "sorular.xlsx.bak"], res
