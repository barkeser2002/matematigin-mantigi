"""Komut satırı: python -m matematigin_mantigi.pdf_import <pdf> [--cikti sorular_sablon.xlsx] [--gorsel sorular_gorsel]"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from matematigin_mantigi.core.pdf_import import PdfImportError, extract_questions
from matematigin_mantigi.core.question_loader import write_questions


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    p = argparse.ArgumentParser(prog="matematigin-mantigi-pdf",
                                description="Yatay soru PDF'ini Excel şablonuna aktarır.")
    p.add_argument("pdf", help="Kaynak PDF")
    p.add_argument("--cikti", default="sorular_sablon.xlsx", help="Hedef .xlsx (varsayılan: ./sorular_sablon.xlsx)")
    p.add_argument("--gorsel", default="sorular_gorsel", help="Şekil PNG klasörü (varsayılan: ./sorular_gorsel)")
    args = p.parse_args(argv[1:])
    out = Path(args.cikti)
    try:
        questions = extract_questions(Path(args.pdf), Path(args.gorsel))
    except PdfImportError as err:
        print(f"Hata: {err}", file=sys.stderr)
        return 1
    base = out.resolve().parent
    rows = []
    for q in questions:
        if q.image:
            try:                                  # xlsx klasörüne göre göreli yol yaz
                q = replace(q, image=Path(q.image).resolve().relative_to(base).as_posix())
            except ValueError:
                pass
        rows.append(q)
    write_questions(out, rows)
    figs = sum(1 for q in rows if q.image)
    print(f"{len(rows)} soru yazıldı: {out} ({figs} görsel, klasör: {args.gorsel})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
