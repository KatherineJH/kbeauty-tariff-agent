"""Extract Federal Register documents from the archived raw responses (offline; no network).

    uv run python pipeline/extract_federal_register.py [--out DIR]

Inputs : data/raw/federal_register/doc_<number>.json and doc_<number>.html (only the numbers listed in
         pipeline/fr_documents.csv, in that order).
Outputs: <out>/fr_documents.csv   one row per document: identifiers, dates, notes, text hash
         <out>/fr_text/<number>.txt   the <pre> body of the GPO HTML, normalized (see normalize_text)

Reproducibility is defined on normalized content, not file bytes: normalize_text() fixes Unicode form (NFC),
line endings (LF) and trailing whitespace, and text_sha256 is computed on the normalized text.
"""

import argparse
import csv
import html
import json
import re
import sys
import unicodedata
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw" / "federal_register"
LIST = Path(__file__).resolve().parent / "fr_documents.csv"
DEFAULT_OUT = REPO / "data" / "extracted"

FIELDS = ["document_number", "group", "type", "subtype", "title", "executive_order_number", "proclamation_number",
          "signing_date", "publication_date", "effective_on", "citation", "start_page", "end_page", "agencies",
          "disposition_notes", "text_chars", "text_sha256"]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip("\n") + "\n"


def body_text(raw_html: str) -> str:
    match = re.search(r"<pre>(.*?)</pre>", raw_html, flags=re.S | re.I)
    if not match:
        raise ValueError("no <pre> block")
    return normalize_text(html.unescape(re.sub(r"<[^>]+>", "", match.group(1))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--offline", action="store_true", help="accepted for symmetry; this step never uses the network")
    args = parser.parse_args()
    text_dir = args.out / "fr_text"
    text_dir.mkdir(parents=True, exist_ok=True)

    with LIST.open(encoding="utf-8", newline="") as f:
        selected = list(csv.DictReader(f))
    rows = []
    for item in selected:
        num = item["document_number"]
        meta = json.loads((RAW / f"doc_{num}.json").read_text(encoding="utf-8"))
        text = body_text((RAW / f"doc_{num}.html").read_text(encoding="utf-8"))
        (text_dir / f"{num}.txt").write_bytes(text.encode("utf-8"))
        rows.append({
            "document_number": num,
            "group": item["group"],
            "type": meta.get("type"),
            "subtype": meta.get("subtype"),
            "title": meta.get("title"),
            "executive_order_number": meta.get("executive_order_number"),
            "proclamation_number": meta.get("proclamation_number"),
            "signing_date": meta.get("signing_date"),
            "publication_date": meta.get("publication_date"),
            "effective_on": meta.get("effective_on"),
            "citation": meta.get("citation"),
            "start_page": meta.get("start_page"),
            "end_page": meta.get("end_page"),
            "agencies": "; ".join(a.get("name") or a.get("raw_name") or "" for a in meta.get("agencies") or []),
            "disposition_notes": meta.get("disposition_notes"),
            "text_chars": len(text),
            "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
        })
    with (args.out / "fr_documents.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"extract  {len(rows)} Federal Register documents -> {args.out.relative_to(REPO) if args.out.is_relative_to(REPO) else args.out}")


if __name__ == "__main__":
    sys.exit(main())
