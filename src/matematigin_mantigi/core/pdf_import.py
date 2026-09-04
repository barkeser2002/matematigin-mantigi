"""PDF (yatay, sayfa başına 1 soru + 'AKILLI İPUÇLARI' kartları) -> Question listesi.

Sayfa düzeni varsayımı: sol yarıda kırmızı numara, soru metni ve A) B) C) D) seçenekleri;
sağ yarıda 'AKILLI İPUÇLARI' başlığı ve her biri ayrı metin bloğu olan ipucu kartları.
Sol yarıda uzun metin içermeyen çizim/resim bölgesi soru görseli olarak PNG'ye alınır.
"""
from __future__ import annotations

import re
from pathlib import Path

from matematigin_mantigi.core.models import Question


class PdfImportError(RuntimeError):
    pass


_OPTION = re.compile(r"([A-D])\)\s*(.*?)(?=\s+[A-D]\)|$)")
_NUMBER = re.compile(r"^(\d+)\.\s*(.*)$", re.S)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_questions(pdf_path: Path, image_dir: Path | None = None, id_prefix: str = "S") -> list[Question]:
    try:
        import pymupdf
    except ImportError as err:  # pragma: no cover - ortam bağımlı
        raise PdfImportError("pymupdf kurulu değil: python -m pip install pymupdf") from err

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise PdfImportError(f"PDF bulunamadı: {pdf_path}")
    doc = pymupdf.open(str(pdf_path))
    questions: list[Question] = []
    for pno, page in enumerate(doc, start=1):
        width = page.rect.width
        blocks = [(b[0], b[1], b[2], b[3], _clean(b[4])) for b in page.get_text("blocks") if b[4].strip()]
        left = sorted((b for b in blocks if b[0] < width / 2), key=lambda b: (round(b[1] / 20), b[0]))
        right = sorted((b for b in blocks if b[0] >= width / 2), key=lambda b: b[1])
        if not left:
            continue
        number_block = next((b for b in left if re.fullmatch(r"\d+\.", b[4])), None)
        option_blocks = [b for b in left if re.match(r"^[A-D]\)", b[4])]
        hints = tuple(b[4] for b in right if "AKILLI" not in b[4].upper())
        q_blocks = [b for b in left if b is not number_block and b not in option_blocks]

        image: str | None = None
        if image_dir is not None:
            rects = []
            for img in page.get_images(full=True):
                rects += [r for r in page.get_image_rects(img[0]) if r.x1 < width / 2 and r.width > 60]
            rects += [d["rect"] for d in page.get_drawings()
                      if d["rect"].x1 < width / 2 and d["rect"].width > 60 and d["rect"].height > 30]
            if rects:
                union = rects[0]
                for r in rects[1:]:
                    union |= r
                inside = [b for b in q_blocks if pymupdf.Rect(b[:4]).intersects(union)]
                if not any(len(b[4]) > 8 for b in inside):          # uzun metin yoksa bu bir şekil
                    image_dir = Path(image_dir)
                    image_dir.mkdir(parents=True, exist_ok=True)
                    target = image_dir / f"{id_prefix}{pno:02d}.png"
                    page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=union + (-8, -8, 8, 8)).save(str(target))
                    image = str(target)
                    q_blocks = [b for b in q_blocks if b not in inside]

        text = " ".join(b[4] for b in q_blocks)
        if number_block is None:
            m = _NUMBER.match(text)
            if m:
                text = m.group(2)
        if not text:
            continue
        pairs = _OPTION.findall(" ".join(b[4] for b in option_blocks))
        options = tuple(v.strip() for _, v in sorted(pairs))
        questions.append(Question(f"{id_prefix}{pno:02d}", "", None, text, hints, "", options, image))
    doc.close()
    if not questions:
        raise PdfImportError("PDF'de soru bulunamadı")
    return questions
