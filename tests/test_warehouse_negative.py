"""Negative tests: a corrupted seed must make the specific dbt data test fail.

Each case copies warehouse/ to a temporary directory, changes one seed, runs `dbt build` against the copy (from the
repository root, so data/extracted resolves) and checks that the named test failed.
"""

import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DBT = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")


def rewrite(path: Path, change) -> None:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0])
    change(rows)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def failed_tests(tmp: Path, mutate) -> set[str]:
    project = tmp / "warehouse"
    shutil.copytree(REPO / "warehouse", project, ignore=shutil.ignore_patterns("target", "logs", "*.duckdb*"))
    mutate(project / "seeds")
    env = {**os.environ, "TARIFF_DUCKDB": str(tmp / "t.duckdb")}
    subprocess.run([str(DBT), "build", "--project-dir", str(project), "--profiles-dir", str(project)],
                   cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")
    results = json.loads((project / "target" / "run_results.json").read_text(encoding="utf-8"))["results"]
    return {r["unique_id"].split(".")[2] for r in results if r["status"] in ("fail", "error")}


def wrong_boundary_expectation(seeds: Path) -> None:
    def change(rows):
        for r in rows:
            if r["fixture_id"] == "2026-02-24_exact_plain":
                r["expected_applies"] = "ALL_DEMIN_EO;KR_DEAL15"  # claims the deal still applies at the cut-off
    rewrite(seeds / "boundary_fixtures.csv", change)


def drop_metal_relation(seeds: Path) -> None:
    def change(rows):
        for r in rows:
            if r["action_id"] in ("S232_AL_derivative_19k", "S232_ST_derivative_16n"):
                r["stacking_rule"] = "applies to the metal content"
    rewrite(seeds / "regulatory_actions.csv", change)


def drop_supersession(seeds: Path) -> None:
    def change(rows):
        for r in rows:
            if r["action_id"] == "KORdeal_15allin":
                r["supersedes"] = ""
            if r["action_id"] == "EO14326_KR15":
                r["superseded_by"] = ""
                r["ends_rule"] = "IEEPA duties ended by EO14389_end_ieepa"
    def stretch(rows):  # make the two Korea segments overlap so the relation is required
        for r in rows:
            if r["segment_id"] == "KR_RECIP15":
                r["ends_at"] = "2025-12-01T00:01-05:00"
    rewrite(seeds / "regulatory_actions.csv", change)
    rewrite(seeds / "rule_segments.csv", stretch)


def backdate_current_list(seeds: Path) -> None:
    def change(rows):
        for r in rows:
            if r["list_id"] == "s301_korea":
                r["valid_from"] = "2024-01-01"  # pretends the Rev. 22 list was evidence for 2026-08
    rewrite(seeds / "list_versions.csv", change)


def wrong_family_expectation(seeds: Path) -> None:
    def change(rows):
        for r in rows:
            if r["fixture_id"] == "2026-02-24_exact_plain" and r["duty_family"] == "de_minimis":
                r["expected_state"] = "none"  # reads the one-minute gap as "no rule of any kind"
    rewrite(seeds / "family_fixtures.csv", change)


@pytest.mark.slow
@pytest.mark.parametrize("mutate, must_fail", [
    (wrong_boundary_expectation, "assert_boundary_fixtures"),
    (drop_metal_relation, "assert_no_undeclared_overlap"),
    (drop_supersession, "assert_no_undeclared_overlap"),
    (backdate_current_list, "assert_boundary_fixtures"),
    (wrong_family_expectation, "assert_family_fixtures"),
], ids=lambda x: getattr(x, "__name__", x))
def test_corruption_is_caught(tmp_path, mutate, must_fail):
    assert must_fail in failed_tests(tmp_path, mutate)
