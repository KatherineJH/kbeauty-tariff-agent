"""Build the DuckDB warehouse with dbt (seeds, models, data tests) and report the result.

    uv run python scripts/build_warehouse.py                 # warehouse/tariff.duckdb
    uv run python scripts/build_warehouse.py --db PATH

Every node must end in success/pass; a dbt 'warn' also fails the run. The rule seeds are regenerated first from
their builder scripts so the warehouse never runs on stale seed files.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO / "warehouse"


def build(db: Path) -> dict:
    for script in ("_build_regulatory_actions_seed.py", "_build_rule_seeds.py"):
        subprocess.run([sys.executable, str(REPO / "scripts" / script)], check=True, capture_output=True)
    env = {**os.environ, "TARIFF_DUCKDB": str(db)}
    dbt = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    proc = subprocess.run([str(dbt), "build", "--project-dir", str(WAREHOUSE), "--profiles-dir", str(WAREHOUSE)],
                          cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8")
    results = json.loads((WAREHOUSE / "target" / "run_results.json").read_text(encoding="utf-8"))["results"]
    tests = [r for r in results if r["unique_id"].startswith("test.")]
    bad = [(r["unique_id"], r["status"]) for r in results if r["status"] not in ("success", "pass")]
    return {"returncode": proc.returncode, "nodes": len(results), "tests": len(tests),
            "tests_passed": sum(r["status"] == "pass" for r in tests), "not_passed": bad,
            "log_tail": proc.stdout[-3000:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=WAREHOUSE / "tariff.duckdb")
    args = parser.parse_args()
    s = build(args.db)
    print(f"build    {s['tests_passed']}/{s['tests']} data tests passed ({s['nodes']} nodes)")
    if s["returncode"] != 0 or s["not_passed"]:
        sys.exit(f"build failed: {s['not_passed']}\n{s['log_tail']}")


if __name__ == "__main__":
    main()
