"""Extract text from the archived HTS PDFs, page by page (offline).

    uv run python pipeline/extract_hts_pdf.py [--out DIR]

For each PDF in data/raw/hts/*.pdf:
  <out>/hts_pdf/<stem>/page_0001.txt ...   text of each page (1-based PDF page index), normalized
  <out>/hts_pdf/<stem>/full.txt            all pages joined, each preceded by a '=== page N ===' marker
  <out>/hts_pdf/pages.csv                  stem, page, chars, text_sha256

pypdf's text order can differ from the visual order on pages with tables or columns; any value used as a gold
answer must be checked against the rendered page (see docs/architecture.md, section 4).
The pypdf version is pinned in pyproject.toml / uv.lock because text extraction output depends on it.
"""

import argparse
import csv
import unicodedata
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "hts"
DEFAULT_OUT = REPO / "data" / "extracted"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--offline", action="store_true", help="accepted for symmetry; never uses the network")
    parser.add_argument("--only", nargs="*", help="PDF file names to extract (default: all); used by the tests")
    args = parser.parse_args()
    root = args.out / "hts_pdf"
    root.mkdir(parents=True, exist_ok=True)
    index = []
    for pdf in sorted(RAW.glob("*.pdf")):
        if args.only and pdf.name not in args.only:
            continue
        out = root / pdf.stem
        out.mkdir(exist_ok=True)
        reader = PdfReader(str(pdf))
        parts = []
        for i, page in enumerate(reader.pages, start=1):
            text = normalize(page.extract_text() or "")
            (out / f"page_{i:04d}.txt").write_bytes(text.encode("utf-8"))
            parts.append(f"=== page {i} ===\n{text}")
            index.append({"stem": pdf.stem, "page": i, "chars": len(text),
                          "text_sha256": sha256(text.encode("utf-8")).hexdigest()})
        (out / "full.txt").write_bytes("".join(parts).encode("utf-8"))
        print(f"extract  {pdf.name}: {len(reader.pages)} pages")
    with (root / "pages.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["stem", "page", "chars", "text_sha256"], lineterminator="\n")
        w.writeheader()
        w.writerows(index)


if __name__ == "__main__":
    main()
