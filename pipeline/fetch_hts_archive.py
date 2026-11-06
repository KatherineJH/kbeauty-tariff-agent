"""Collect selected earlier HTS revisions (D2a) from the official USITC archive.

    uv run python pipeline/fetch_hts_archive.py

Selection rule (docs/data_sources.md, section D2a, fixed before collection): only the revisions published just before
and just after each unresolved effective-date boundary of the regulatory effect table. For each revision: the full
chapter 99 PDF and the change record PDF, saved byte-for-byte under data/raw/hts_archive/<release>/ with a manifest.

The archive page lists, for each revision, a posted date (in the link text) and a releaseDate parameter; both are kept
in revisions.csv. Interim electronic revisions are not all preserved (archive notice), so no change is inferred
between two revisions.
"""

import csv
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RAW, archive, get  # noqa: E402

BASE = "https://hts.usitc.gov/reststop/file"
ARCHIVE_PAGE = "https://hts.usitc.gov/download/archive"

# (release, posted date shown on the archive page, releaseDate parameter of the archive link, boundary)
REVISIONS = [
    ("2025HTSRev7", "2025-04-05", "2025-04-03", "2025-04-05..04-10 before"),
    ("2025HTSRev8", "2025-04-10", "2025-04-09", "2025-04-05..04-10 after"),
    ("2025HTSRev9", "2025-04-10", "2025-04-10", "2025-04-05..04-10 after"),
    ("2025HTSRev17", "2025-08-01", "2025-07-30", "2025-08-01..08-07 before"),
    ("2025HTSRev18", "2025-08-06", "2025-08-04", "2025-08-01..08-07 after"),
    ("2025HTSRev19", "2025-08-18", "2025-08-15", "2025-08-01..08-07 after"),
    ("2026HTSRev3", "2026-02-11", "2026-02-09", "2026-02-24 before"),
    ("2026HTSRev4", "2026-02-25", "2026-02-23", "2026-02-24 after"),
    ("2026HTSRev5", "2026-04-08", "2026-04-03", "2026-04-09 before"),
    ("2026HTSRev6", "2026-04-23", "2026-04-22", "2026-04-09 after"),
    ("2026HTSRev12", "2026-07-21", "2026-07-16", "2026-07-24 before"),
    ("2026HTSRev13", "2026-07-28", "2026-07-22", "2026-07-24 after"),
]
FILES = {"chapter_99.pdf": "Chapter 99", "change_record.pdf": "Change Record"}


def main() -> None:
    out = RAW / "hts_archive"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "revisions.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["release", "posted_date", "release_date_param", "boundary", "source_page"])
        for release, posted, param, boundary in REVISIONS:
            w.writerow([release, posted, param, boundary, ARCHIVE_PAGE])
    for release, *_ in REVISIONS:
        for name, title in FILES.items():
            url = f"{BASE}?release={release}&filename={quote(title)}"
            body = get(url)
            if not body.startswith(b"%PDF"):
                sys.exit(f"not a PDF: {url}")
            archive(f"hts_archive/{release}", name, url, body)


if __name__ == "__main__":
    main()
