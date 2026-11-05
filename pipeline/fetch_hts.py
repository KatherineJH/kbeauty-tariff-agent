"""Collect the US Harmonized Tariff Schedule parts this project needs (D2), from the official USITC endpoints.

    uv run python pipeline/fetch_hts.py

- JSON exports (the site's own Export function): chapter 33 and the chapter 99 headings for the reciprocal
  tariffs (9903.01-9903.02).
- PDFs (the site's own Download links): chapter 33, chapter 99, General Rules of Interpretation, General Note 33
  (United States-Korea FTA), General Statistical Notes, Change Record.

The release is "currentRelease"; the revision seen at collection time is written to data/raw/hts/RELEASE.txt.
"""

import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import archive, get  # noqa: E402

BASE = "https://hts.usitc.gov/reststop"
REVISION_SEEN = "2026 HTS Revision 22 (shown on hts.usitc.gov, 2026-11-05)"

EXPORTS = [  # (file name, from, to)
    ("export_ch33.json", "3301", "3308"),
    ("export_9903_01-02.json", "9903.01.01", "9903.02.99"),
]
PDFS = ["Chapter 33", "Chapter 99", "General Rules of Interpretation", "General Note 33",
        "General Statistical Notes", "Change Record"]


def main() -> None:
    for name, start, end in EXPORTS:
        url = f"{BASE}/exportList?from={start}&to={end}&format=JSON&styles=false"
        archive("hts", name, url, get(url))
    for title in PDFS:
        url = f"{BASE}/file?release=currentRelease&filename={quote(title)}"
        body = get(url)
        if not body.startswith(b"%PDF"):
            sys.exit(f"not a PDF: {url}")
        archive("hts", title.lower().replace(" ", "_") + ".pdf", url, body)
    (Path(__file__).resolve().parents[1] / "data/raw/hts/RELEASE.txt").write_text(REVISION_SEEN + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
