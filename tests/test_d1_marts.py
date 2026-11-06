"""The committed D1 Parquet files match the logical hashes and row counts recorded at export (offline)."""

import csv
import sys
from pathlib import Path

import duckdb
import pytest

REPO = Path(__file__).resolve().parents[1]
D1 = REPO / "data" / "raw" / "d1_marts"
sys.path.insert(0, str(REPO / "scripts"))

import export_d1_marts as export  # noqa: E402

with (D1 / "marts.csv").open(encoding="utf-8") as f:
    MARTS = list(csv.DictReader(f))


@pytest.mark.parametrize("mart", MARTS, ids=lambda m: m["mart"])
def test_parquet_logical_hash_and_rows(mart):
    con = duckdb.connect()
    digest, rows = export.logical_hash(con, f"read_parquet('{(D1 / (mart['mart'] + '.parquet')).as_posix()}')")
    assert rows == int(mart["rows"])
    assert digest == mart["logical_sha256"]


def test_schema_matches_parquet_columns():
    with (D1 / "schema.csv").open(encoding="utf-8") as f:
        schema = list(csv.DictReader(f))
    con = duckdb.connect()
    for mart in MARTS:
        cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{(D1 / (mart['mart'] + '.parquet')).as_posix()}')"
                           ).fetchall()
        expected = [(s["column"], s["type"]) for s in schema if s["mart"] == mart["mart"]]
        assert [(c[0], c[1]) for c in cols] == expected


def test_source_is_pinned_to_the_upstream_commit():
    source = (D1 / "SOURCE.md").read_text(encoding="utf-8")
    assert export.UPSTREAM_SHA in source and len(export.UPSTREAM_SHA) == 40
