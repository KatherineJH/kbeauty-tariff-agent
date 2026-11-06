"""Build the committed evidence snapshot from the full archived-revision page texts (offline).

    uv run python pipeline/build_hts_archive_evidence.py [--src DIR] [--out DIR]

Input : <src>/hts_archive/<release>/pages/page_NNNN.txt   (full page texts; git-ignored, rebuilt by rehydrate)
Output: <out>/hts_archive_evidence/<release>/page_NNNN.txt  canonical text of the pages used for determinations
        <out>/hts_archive_evidence/evidence_index.csv       release, pdf_page, printed_page, reasons, text_sha256

A page is kept when it
  - holds a tariff-table row of a target heading (extract_hts_archive.TARGET_HEADINGS or EXTRA_ROW_HEADINGS),
  - mentions a chapter 33 cosmetics subheading (3303-3307),
  - starts one of the note subdivisions the regulatory table cites (EVIDENCE_HEADERS), or
  - is the following page of such a subdivision start (lists continue across pages).
The page texts are byte-identical copies of the normalized extraction, so text_sha256 must equal the hash in
<src>/hts_archive/<release>/pages.csv; tests check this.
"""

import argparse
import csv
import re
import shutil
from hashlib import sha256
from pathlib import Path

import extract_hts_archive as x

REPO = Path(__file__).resolve().parents[1]
DEFAULT = REPO / "data" / "extracted"

EVIDENCE_HEADERS = {
    "note 2(v)(xiii) country list": re.compile(r"^\(xiii\)"),
    "note 2(aa)(v) surcharge 232 exceptions": re.compile(r"^\(v\) As provided in heading 9903\.03\.06"),
    "note 16(n) steel derivatives 9903.81.91": re.compile(r"^\(n\) The rates of duty in heading 9903\.81\.91"),
    "note 19(k) aluminum derivatives 9903.85.08": re.compile(r"^\(k\) The rates of duty in heading 9903\.85\.08"),
    "note 19(h) aluminum derivative stacking": re.compile(r"^\(h\) Except as provided in heading 9903\.96\.02"),
    "note 52(a) section 301": re.compile(r"^\(a\) Except as provided in headings 9903\.05\.85"),
}
# Headings whose tariff rows the regulatory table cites, beyond extract_hts_archive.TARGET_HEADINGS.
EXTRA_ROW_HEADINGS = ["9903.81.91"]
ROW = {h: re.compile(rf"^(1/)?{re.escape(h)}(?:$|[A-Z])", re.M) for h in [*x.TARGET_HEADINGS, *EXTRA_ROW_HEADINGS]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=DEFAULT)
    parser.add_argument("--out", type=Path, default=DEFAULT)
    args = parser.parse_args()
    root = args.out / "hts_archive_evidence"
    if root.exists():
        shutil.rmtree(root)
    index = []
    for rel_dir in sorted((args.src / "hts_archive").iterdir()):
        pages_dir = rel_dir / "pages"
        if not pages_dir.is_dir():
            continue
        texts = {int(p.stem[5:]): p.read_text(encoding="utf-8") for p in sorted(pages_dir.glob("page_*.txt"))}
        reasons: dict[int, set[str]] = {}
        for n, text in texts.items():
            for h, rx in ROW.items():
                if rx.search(text):
                    reasons.setdefault(n, set()).add(f"row {h}")
            if x.COSMETIC.search(text):
                reasons.setdefault(n, set()).add("cosmetics code")
            lines = [ln.strip() for ln in text.split("\n")]
            for label, rx in EVIDENCE_HEADERS.items():
                if any(rx.match(ln) for ln in lines):
                    reasons.setdefault(n, set()).add(label)
                    if n + 1 in texts:
                        reasons.setdefault(n + 1, set()).add(f"{label} (continued)")
        out = root / rel_dir.name
        out.mkdir(parents=True, exist_ok=True)
        for n in sorted(reasons):
            data = texts[n].encode("utf-8")
            (out / f"page_{n:04d}.txt").write_bytes(data)
            index.append({"release": rel_dir.name, "pdf_page": n, "printed_page": x.label(texts[n]),
                          "reasons": "; ".join(sorted(reasons[n])), "text_sha256": sha256(data).hexdigest()})
    with (root / "evidence_index.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(index)
    print(f"evidence {len(index)} pages")


if __name__ == "__main__":
    main()
