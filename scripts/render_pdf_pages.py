"""Render selected PDF pages to PNG for visual comparison with the pypdf text (review aid, not part of run_all).

    uv run python scripts/render_pdf_pages.py data/raw/hts/chapter_99.pdf 224 227 658 --out reports/review/pages

Pages are 1-based PDF page indexes. Output files: <stem>_p<page>.png. pypdfium2 and pillow are dev dependencies.
"""

import argparse
from pathlib import Path

import pypdfium2 as pdfium


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("pages", type=int, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1.6)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(str(args.pdf))
    for p in args.pages:
        image = doc[p - 1].render(scale=args.scale).to_pil()
        path = args.out / f"{args.pdf.stem}_p{p:04d}.png"
        image.save(path)
        print(path)


if __name__ == "__main__":
    main()
