"""Extract comparison outputs from the archived HTS revisions (D2a), offline.

    uv run python pipeline/extract_hts_archive.py [--out DIR] [--workers N]

For each data/raw/hts_archive/<release>/chapter_99.pdf (and change_record.pdf):
  <out>/hts_archive/<release>/pages/page_NNNN.txt   normalized page text (pypdf; same normalization as extract_hts_pdf)
  <out>/hts_archive/<release>/pages.csv             page, printed_page, chars, text_sha256
  <out>/hts_archive/<release>/change_record.txt     change record text
Across releases:
  <out>/hts_archive/heading_presence.csv  release, heading, pdf pages where the heading number appears, and whether a
                                          tariff-table row for it was seen (the number alone on a line, optionally after '1/', or followed by rate text)
  <out>/hts_archive/heading_context.csv   release, heading, pdf_page, printed_page, +-300 characters around each
                                          occurrence (target headings only)
  <out>/hts_archive/change_records.csv   release, line, item, nature, detail, effective_date, source (one-line rows
                                          of each change record; wrapped rows are left in change_record.txt)
  <out>/hts_archive/cosmetics_mentions.csv release, code (3303-3307 8-digit), pdf_page, printed_page, nearest preceding
                                          note subdivision line and heading reference on that page

Targets (docs/data_sources.md, D2a): headings 9903.01, .02, .03, .05, .82, .85 and U.S. notes 2, 16, 19, 52.
Nothing here asserts that a state held between two revisions.
"""

import argparse
import csv
import re
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "hts_archive"
DEFAULT_OUT = REPO / "data" / "extracted"

TARGET_HEADINGS = [
    "9903.01.25", "9903.01.43", "9903.01.54", "9903.01.63", "9903.01.76",
    "9903.02.01", "9903.02.56", "9903.02.79", "9903.02.80",
    "9903.03.01", "9903.03.02", "9903.03.03", "9903.03.06",
    "9903.05.70", "9903.05.71", "9903.05.90",
    "9903.82.02", "9903.82.04", "9903.85.02", "9903.85.04", "9903.85.07", "9903.85.08", "9903.85.09",
]
COSMETIC = re.compile(r"(330[3-7]\.\d{2}\.\d{2})(?=\d{4}\.\d{2}|\D|$)")
LABEL = re.compile(r"99 - ([IVX]+) - (\d+)")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
# One change-record row: item, nature (with optional detail), effective date, source. Rows that wrap across lines in
# the PDF text are not matched and stay only in change_record.txt.
CHANGE_LINE = re.compile(rf"^(?P<item>.+?) (?P<nature>Added|Deleted|Modified|Established|Discontinued|Technical "
                         rf"correction|Annotated|Restored|Suspended|Terminated)(?P<detail>.*?) "
                         rf"(?P<effective_date>(?:{MONTHS}) \d{{1,2}}, \d{{4}}) (?P<source>.+)$")
SUBDIVISION = re.compile(r"^\(?([a-z]{1,4}|[ivx]+|\d{1,2})\)\s|^\d{1,2}\.\s*$|^\d{1,2}\.\s+\(?[a-z]\)")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip("\n") + "\n"


def label(text: str) -> str:
    m = LABEL.search(text)
    return f"99-{m.group(1)}-{m.group(2)}" if m else ""


def extract_release(args: tuple[str, str]) -> str:
    release, out_root = args
    src = RAW / release
    out = Path(out_root) / "hts_archive" / release
    pages_dir = out / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, page in enumerate(PdfReader(str(src / "chapter_99.pdf")).pages, start=1):
        text = normalize(page.extract_text() or "")
        (pages_dir / f"page_{i:04d}.txt").write_bytes(text.encode("utf-8"))
        rows.append({"page": i, "printed_page": label(text), "chars": len(text),
                     "text_sha256": sha256(text.encode("utf-8")).hexdigest()})
    with (out / "pages.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    cr = "".join(normalize(p.extract_text() or "") for p in PdfReader(str(src / "change_record.pdf")).pages)
    (out / "change_record.txt").write_bytes(cr.encode("utf-8"))
    return release


def summarize(out_root: Path, releases: list[str]) -> None:
    presence, context, cosmetics = [], [], []
    for release in releases:
        base = out_root / "hts_archive" / release
        pages = sorted((base / "pages").glob("page_*.txt"))
        texts = {int(p.stem[5:]): p.read_text(encoding="utf-8") for p in pages}
        for heading in TARGET_HEADINGS:
            found, row_seen = [], False
            for n, text in texts.items():
                if heading in text:
                    found.append(n)
                    # A tariff-table row prints the heading alone on its line, usually after the footnote mark
                    # "1/", or directly followed by rate text; note sentences continue with a comma or a word.
                    if re.search(rf"^(1/)?{re.escape(heading)}(?:$|[A-Z])", text, flags=re.M):
                        row_seen = True
                    flat = re.sub(r"\s+", " ", text)
                    for m in re.finditer(re.escape(heading), flat):
                        context.append({"release": release, "heading": heading, "pdf_page": n,
                                        "printed_page": label(text),
                                        "context": flat[max(0, m.start() - 300):m.end() + 300]})
            presence.append({"release": release, "heading": heading, "pages": " ".join(map(str, found)),
                             "table_row_seen": row_seen})
        for n, text in texts.items():
            codes = sorted(set(COSMETIC.findall(text)))
            if not codes:
                continue
            last_sub, refs = "", sorted(set(re.findall(r"9903\.\d{2}\.\d{2}", text)))
            for line in text.split("\n"):
                if SUBDIVISION.match(line.strip()):
                    last_sub = line.strip()[:160]
            for code in codes:
                cosmetics.append({"release": release, "code": code, "pdf_page": n, "printed_page": label(text),
                                  "last_subdivision_line_on_page": last_sub, "headings_on_page": " ".join(refs[:12])})
    changes = []
    for release in releases:
        text = (out_root / "hts_archive" / release / "change_record.txt").read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), start=1):
            m = CHANGE_LINE.match(line.strip())
            if m:
                changes.append({"release": release, "line": n, **m.groupdict(), "raw": line.strip()})
    for name, data in (("heading_presence.csv", presence), ("heading_context.csv", context),
                       ("cosmetics_mentions.csv", cosmetics), ("change_records.csv", changes)):
        with (out_root / "hts_archive" / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--offline", action="store_true", help="accepted for symmetry; never uses the network")
    args = parser.parse_args()
    releases = sorted(p.name for p in RAW.iterdir() if (p / "chapter_99.pdf").exists())
    if not args.summary_only:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for done in pool.map(extract_release, [(r, str(args.out)) for r in releases]):
                print(f"extract  {done}")
    summarize(args.out, releases)
    print(f"summary  {len(releases)} releases")


if __name__ == "__main__":
    main()
