"""dbt build of the rule warehouse: all data tests pass, evidence paths exist, partial rules are not auto-computed."""

import csv
import sys
from pathlib import Path

import duckdb
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import build_warehouse  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    db = tmp_path_factory.mktemp("wh") / "tariff.duckdb"
    summary = build_warehouse.build(db)
    return db, summary


def test_dbt_build_passes_every_node(built):
    _, s = built
    assert s["returncode"] == 0 and not s["not_passed"], s["log_tail"]
    assert s["tests"] >= 48 and s["tests_passed"] == s["tests"]


def test_boundary_fixtures_cover_every_requested_boundary():
    with (REPO / "warehouse" / "seeds" / "boundary_fixtures.csv").open(encoding="utf-8") as f:
        ids = {r["fixture_id"] for r in csv.DictReader(f)}
    for day in ("2025-04-09", "2025-04-10", "2025-08-07", "2025-08-18", "2026-02-24", "2026-04-06", "2026-07-24"):
        for edge in ("before", "exact", "after"):
            assert f"{day}_{edge}_plain" in ids and f"{day}_{edge}_al" in ids
    assert {"2025-08-01_00:00_plain", "2025-08-01_00:01_plain", "2025-08-01_00:02_plain"} <= ids


def test_evidence_catalog_paths_exist():
    with (REPO / "warehouse" / "seeds" / "evidence_catalog.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            assert (REPO / row["path"]).exists(), row


def test_resolution_is_per_segment_and_code(built):
    db, _ = built
    con = duckdb.connect(str(db), read_only=True)
    rows = con.execute("select rule_id, resolution_status, auto_compute_allowed_default, segment_resolution_note "
                       "from mart_tariff_rules").fetchall()
    for rule_id, status, allowed, note in rows:
        assert allowed == (status == "resolved"), rule_id
        if status != "resolved":
            assert note, rule_id
    # the same rule can be resolved for one code and partial for another
    mixed = con.execute("select count(distinct resolution_status) from mart_rule_code_resolution "
                        "where rule_id = 'KR_S122_A'").fetchone()[0]
    assert mixed == 2


def test_fixtures_are_static_not_generated():
    builder = (REPO / "scripts" / "_build_rule_seeds.py").read_text(encoding="utf-8")
    assert 'write("boundary_fixtures.csv"' not in builder and 'write("family_fixtures.csv"' not in builder


def test_rule_times_are_timestamptz_with_source_text_kept(built):
    db, _ = built
    con = duckdb.connect(str(db), read_only=True)
    types = dict(con.execute("select column_name, data_type from information_schema.columns "
                             "where table_name = 'mart_tariff_rules'").fetchall())
    assert types["effective_at"].startswith("TIMESTAMP WITH TIME ZONE")
    assert types["ends_at"].startswith("TIMESTAMP WITH TIME ZONE")
    con.execute("SET TimeZone = 'UTC'")  # render instants in UTC regardless of the machine's zone
    src = con.execute("select starts_at_source, cast(starts_at as varchar) from stg_rule_segments "
                      "where segment_id = 'KR_RECIP25'").fetchone()
    assert src[0] == "2025-04-09T00:01-04:00" and src[1].startswith("2025-04-09 04:01:00")
