"""The committed evidence snapshot of the archived HTS revisions is self-consistent (offline).

The full PDFs and page texts are not committed; scripts/rehydrate_hts_archive.py rebuilds and verifies them.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import rehydrate_hts_archive as r  # noqa: E402


def test_committed_evidence_matches_logical_sums_and_page_hashes():
    assert r.check_committed() == []


def test_every_archived_file_has_a_manifest_row_with_url_size_and_hash():
    import csv
    rows = []
    for manifest in sorted(r.RAW.glob("*/manifest.csv")):
        with manifest.open(encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    assert len(rows) == 24
    for row in rows:
        assert row["url"].startswith("https://hts.usitc.gov/reststop/file?release=")
        assert int(row["bytes"]) > 0 and len(row["sha256"]) == 64
