"""Excel şablonu: sütun doğrulama, örnek şablon üretme, soru yükleme/yazma."""
from __future__ import annotations

import contextlib
import filecmp
import os
import secrets
import shutil
from pathlib import Path
from typing import Callable, Sequence

import openpyxl
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font

from matematigin_mantigi.core.models import SAMPLE_QUESTIONS, Question

REQUIRED_COLUMNS = ("id", "konu", "sinif", "soru", "ipucu1", "ipucu2", "ipucu3", "cevap")
OPTIONAL_COLUMNS = ("ipucu4", "a", "b", "c", "d", "gorsel")
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS
_WIDTHS = {"id": 8, "konu": 16, "sinif": 8, "soru": 60, "ipucu1": 40, "ipucu2": 40, "ipucu3": 40,
           "cevap": 16, "ipucu4": 40, "a": 14, "b": 14, "c": 14, "d": 14, "gorsel": 28}
_LINE_BREAK_CONTROLS = str.maketrans({"\x0b": "\n", "\x0c": "\n"})   # Word/PowerPoint satır sonu, sayfa sonu


class QuestionTemplateError(ValueError):
    pass


class EmptyTemplateError(QuestionTemplateError):
    """Şablon okunabildi ama hiç soru yok (boş şablon): editör soruları güvenle ona yazabilir."""


def clean_text(text: str) -> str:
    """Excel hücresine yazılamayan kontrol karakterlerini temizler (openpyxl bunlarda IllegalCharacterError
    fırlatır): dikey sekme ve sayfa sonu (Word/PowerPoint'ten kopyalanan satır sonları) satır sonu olur, gerisi
    (\\x00-\\x1f) atılır. Sekme ve satır sonu korunur."""
    return ILLEGAL_CHARACTERS_RE.sub("", text.translate(_LINE_BREAK_CONTROLS))


def backup_path(path: Path) -> Path:
    """Soru dosyasının bir önceki sürümü: aynı klasörde <ad>.bak (ör. sorular_sablon.xlsx.bak)."""
    path = Path(path)
    return path.with_name(path.name + ".bak")


def _replace_atomically(target: Path, write: Callable[[Path], object]) -> None:
    """write(tmp) hedefin klasöründeki geçici bir dosyaya yazar; hedef ancak yazım tamamlanınca os.replace ile tek
    adımda değişir. Yazım yarıda kalırsa (dolu disk, çıkarılan USB) hedef eski hâlinde kalır, geçici dosya silinir.
    Windows'ta hedef başka bir programda (Excel) açıksa os.replace PermissionError verir; hedef yine değişmez."""
    tmp = target.with_name(f".{target.name}.{secrets.token_hex(4)}.tmp")
    try:
        write(tmp)
        if os.name == "posix" and target.exists():
            with contextlib.suppress(OSError):      # izinler eski dosyanınki gibi kalsın
                shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
        raise


def write_questions(path: Path, questions: Sequence[Question]) -> Path:
    """Soruları tüm sütunlarla yazar. Görsel yolu xlsx klasörüne göre göreli ise öyle bırakılır.

    Yazım dosyayı yarıda bırakmaz (#29): önce dosyanın o anki hâli <ad>.bak'a kopyalanır, sonra yeni çalışma kitabı
    aynı klasörde geçici dosyaya yazılıp os.replace ile yerine konur (yedek de aynı yolla). Herhangi bir adımda hata
    olursa soru dosyası ve önceki yedek değişmez; OSError çağırana gider."""
    path = Path(path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sorular"
    ws.append(list(ALL_COLUMNS))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for q in questions:
        hints = list(q.hints[:4]) + [""] * max(0, 4 - len(q.hints))
        opts = list(q.options[:4]) + [""] * max(0, 4 - len(q.options))
        ws.append([q.id, q.konu, q.sinif, q.soru, hints[0], hints[1], hints[2], q.cevap,
                   hints[3], *opts, q.image or ""])
    for i, col in enumerate(ALL_COLUMNS):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i + 1)].width = _WIDTHS[col]
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _replace_atomically(backup_path(path), lambda tmp: shutil.copy2(path, tmp))
    _replace_atomically(path, wb.save)
    return path


def _same_file(a: Path, b: Path) -> bool:
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


def save_question_image(image_path: Path, images_dir: Path) -> str:
    """Görseli images_dir içine kopyalar, ad çakışması varsa '_1' gibi ekle çözer.
    xlsx klasörüne göre göreli posix yol döndürür: 'sorular_gorsel/<ad>'."""
    image_path = Path(image_path)
    images_dir = Path(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    target = images_dir / image_path.name
    if target.exists() and not _same_file(image_path, target):
        stem, suffix = image_path.stem, image_path.suffix
        i = 1
        while True:
            target = images_dir / f"{stem}_{i}{suffix}"
            if not target.exists() or _same_file(image_path, target):
                break
            i += 1
    if not target.exists():
        shutil.copyfile(image_path, target)
    return f"{images_dir.name}/{target.name}"


def write_template(path: Path, with_samples: bool = True) -> Path:
    return write_questions(path, SAMPLE_QUESTIONS if with_samples else [])


def ensure_template(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        write_template(path)
    return path


def _text(v) -> str:
    return "" if v is None else str(v).strip()


def _read_rows(source) -> list[tuple]:
    """Etkin sayfanın satırları (yalnız değerler). source bir yol ya da ikili kipte açık dosya: openpyxl yolu uzantısına
    bakıp .bak/.tmp adlı dosyayı reddeder, dosya nesnesinde bakmaz."""
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        # Satırlar önce belleğe alınır, kitap hemen kapanır: read_only kitap dosyayı açık tutar ve doğrulama hatası
        # wb.close()'dan önce fırlayınca tutamak çöp toplayıcıya dek kalıyordu. Windows'ta açık tutamak dosyayı
        # kilitler: öğretmen Excel'den kaydedemez, editörün atomik yazımı (os.replace) da düşer.
        return list(wb.active.iter_rows(values_only=True))
    finally:
        wb.close()


def load_questions(path: Path) -> list[Question]:
    path = Path(path)
    if not path.exists():
        raise QuestionTemplateError(f"Şablon bulunamadı: {path}")
    return _questions_from_rows(_read_rows(path), path.parent)


def load_backup(path: Path) -> list[Question]:
    """Soru dosyasının önceki sürümündeki (<ad>.bak) sorular; görsel yolları soru dosyasının klasörüne göre çözülür.
    Yedek dosya nesnesi olarak açılır (openpyxl .bak uzantısını reddeder). Yedek yoksa OSError."""
    path = Path(path)
    with open(backup_path(path), "rb") as fh:
        return _questions_from_rows(_read_rows(fh), path.parent)


def _questions_from_rows(all_rows: list[tuple], folder: Path) -> list[Question]:
    """Sayfa satırlarından sorular; göreli görsel yolu folder'a (xlsx'in klasörü) göre çözülür."""
    rows = iter(all_rows)
    header = [_text(c).lower() for c in (next(rows, None) or [])]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise QuestionTemplateError("Eksik sütun(lar): " + ", ".join(missing))
    idx = {c: header.index(c) for c in ALL_COLUMNS if c in header}

    def cell(cells, key) -> str:
        return _text(cells[idx[key]]) if key in idx else ""

    questions: list[Question] = []
    for row_no, row in enumerate(rows, start=2):
        cells = list(row) + [None] * (len(header) - len(row))
        if all(_text(c) == "" for c in cells):
            continue
        soru = cell(cells, "soru")
        if not soru:
            raise QuestionTemplateError(f"Satır {row_no}: 'soru' boş")
        qid = cell(cells, "id") or f"S{len(questions) + 1}"
        sinif_raw = cell(cells, "sinif")
        try:
            sinif: int | None = int(float(sinif_raw)) if sinif_raw else None
        except ValueError:
            sinif = None
        hints = tuple(h for h in (cell(cells, k) for k in ("ipucu1", "ipucu2", "ipucu3", "ipucu4")) if h)
        options = tuple(o for o in (cell(cells, k) for k in ("a", "b", "c", "d")) if o)
        image_raw = cell(cells, "gorsel")
        image: str | None = None
        if image_raw:
            p = Path(image_raw)
            image = str(p if p.is_absolute() else (folder / p))
        questions.append(Question(qid, cell(cells, "konu"), sinif, soru, hints, cell(cells, "cevap"),
                                  options, image))
    if not questions:
        raise EmptyTemplateError("Şablonda hiç soru yok")
    return questions
