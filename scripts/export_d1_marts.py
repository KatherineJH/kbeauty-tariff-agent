"""Export the verified marts of the predecessor project (D1) at a pinned commit, reproducibly.

    uv run python scripts/export_d1_marts.py                 # build at UPSTREAM_SHA and export to data/raw/d1_marts
    uv run python scripts/export_d1_marts.py --out DIR       # export elsewhere (used to check a rerun)

Steps (no network except what `uv sync --frozen` needs when its cache is cold):
1. `git archive UPSTREAM_SHA` of the predecessor repository into a temporary directory (its working tree is not used,
   so local edits there cannot leak in).
2. Verify every file listed in its data/SHA256SUMS (raw API responses and extracted CSVs).
3. `uv sync --frozen` there (its own uv.lock) and `dbt build` (seeds, models, data tests) into a temporary DuckDB file;
   every node in run_results.json must have status success/pass.
4. For each mart in MARTS: `COPY (SELECT <columns, HUGEINT cast to BIGINT> FROM <mart> ORDER BY ALL)`, and a logical hash of the
   ordered rows computed from the warehouse and again from the written Parquet; the two must match.
Outputs: <mart>.parquet, marts.csv (rows, columns, hashes), schema.csv (types and glossary descriptions), SOURCE.md.

Reproducibility is defined on the logical hash (canonical serialization of the ordered rows, see logical_hash),
not on Parquet bytes.
"""

import argparse
import csv
import datetime as dt
import decimal
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from hashlib import sha256
from pathlib import Path

import duckdb

REPO = Path(__file__).resolve().parents[1]
UPSTREAM = REPO.parent / "kbeauty-us-supply-chain"
UPSTREAM_SHA = "b3faac8044b7b67b8d32bbe6287b8e2798ca0b58"
DEFAULT_OUT = REPO / "data" / "raw" / "d1_marts"
MARTS = ["dim_port", "fct_imports_hs10_mode_monthly", "mart_category_monthly", "mart_country_panel_monthly",
         "mart_mirror_monthly", "mart_monthly_summary", "mart_port_concentration_monthly",
         "mart_port_region_monthly", "mart_vessel_transit"]
EXPORT_SQL = "COPY (SELECT {select} FROM {mart} ORDER BY ALL) TO '{path}' (FORMAT parquet, COMPRESSION zstd)"
# Parquet has no 128-bit integer: HUGEINT (DuckDB's type for sums of BIGINT) is cast to BIGINT after checking that
# every value fits, so the export stays exact instead of silently becoming DOUBLE.
EXACT_CASTS = {"HUGEINT": "BIGINT"}
NULL = "\\N"


def canonical(value) -> str:
    """One value as text: NULL marker, shortest round-trip repr for floats, ISO dates."""
    if value is None:
        return NULL
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    return str(value)


def logical_hash(con: duckdb.DuckDBPyConnection, relation: str) -> tuple[str, int]:
    """SHA-256 of 'name:type' header plus rows ordered by all columns, fields joined by U+001F, rows by LF."""
    cols = con.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
    h = sha256(("\x1f".join(f"{c[0]}:{c[1]}" for c in cols) + "\n").encode("utf-8"))
    n = 0
    cur = con.execute(f"SELECT * FROM {relation} ORDER BY ALL")
    while batch := cur.fetchmany(10000):
        for row in batch:
            h.update(("\x1f".join(canonical(v) for v in row) + "\n").encode("utf-8"))
            n += 1
    return h.hexdigest(), n


def git_archive(src: Path, sha: str, dest: Path) -> None:
    data = subprocess.run(["git", "-C", str(src), "archive", "--format=tar", sha], check=True,
                          capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(dest, filter="data")


def verify_sums(root: Path) -> int:
    lines = [l for l in (root / "data" / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if l]
    bad = [rel for digest, rel in (l.split("  ", 1) for l in lines)
           if sha256((root / rel).read_bytes()).hexdigest() != digest]
    if bad:
        sys.exit(f"upstream hash mismatch: {bad}")
    return len(lines)


def build(root: Path, db: Path) -> dict:
    env = {**os.environ, "KBEAUTY_DUCKDB": str(db)}
    env.pop("VIRTUAL_ENV", None)
    subprocess.run(["uv", "sync", "--frozen", "--no-dev"], cwd=root, check=True, capture_output=True)
    dbt = root / ".venv" / ("Scripts/dbt.exe" if os.name == "nt" else "bin/dbt")
    result = subprocess.run([str(dbt), "build", "--project-dir", "warehouse", "--profiles-dir", "warehouse"],
                            cwd=root, env=env, capture_output=True, text=True, encoding="utf-8")
    results = json.loads((root / "warehouse" / "target" / "run_results.json").read_text(encoding="utf-8"))["results"]
    bad = [r["unique_id"] for r in results if r["status"] not in ("success", "pass")]
    if result.returncode != 0 or bad:
        sys.exit(f"dbt build failed: {bad}\n{result.stdout[-2000:]}")
    tests = [r for r in results if r["unique_id"].startswith("test.")]
    return {"nodes": len(results), "tests": len(tests)}


def glossary(root: Path) -> dict:
    """Column descriptions from the predecessor's warehouse/column_glossary.yml (simple 'name: text' entries)."""
    out, text = {}, (root / "warehouse" / "column_glossary.yml").read_text(encoding="utf-8")
    for line in text.splitlines():
        s = line.strip()
        if ":" in s and not s.startswith("#") and line.startswith("  ") and not line.startswith("    "):
            k, v = s.split(":", 1)
            out[k.strip()] = v.strip().strip("'\"")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--upstream", type=Path, default=UPSTREAM)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "upstream"
        git_archive(args.upstream, UPSTREAM_SHA, root)
        n_sums = verify_sums(root)
        db = Path(tmp) / "kbeauty.duckdb"
        built = build(root, db)
        sums_hash = sha256((root / "data" / "SHA256SUMS").read_bytes()).hexdigest()
        desc = glossary(root)
        con = duckdb.connect(str(db))
        con.execute("SET threads = 1")
        marts, schema = [], []
        for mart in MARTS:
            path = args.out / f"{mart}.parquet"
            source_cols = con.execute(f"DESCRIBE {mart}").fetchall()
            select, casts = [], {}
            for name, typ, *_ in source_cols:
                if typ in EXACT_CASTS:
                    target = EXACT_CASTS[typ]
                    lossy = con.execute(f'SELECT count(*) FROM {mart} WHERE TRY_CAST("{name}" AS {target}) IS NULL '
                                        f'AND "{name}" IS NOT NULL').fetchone()[0]
                    if lossy:
                        sys.exit(f"{mart}.{name}: {lossy} values do not fit {target}")
                    select.append(f'CAST("{name}" AS {target}) AS "{name}"')
                    casts[name] = f"{typ}->{target}"
                else:
                    select.append(f'"{name}"')
            view = f"export_{mart}"
            con.execute(f"CREATE OR REPLACE TEMP VIEW {view} AS SELECT {', '.join(select)} FROM {mart}")
            con.execute(EXPORT_SQL.format(select=", ".join(select), mart=mart, path=path.as_posix()))
            db_hash, rows = logical_hash(con, view)
            pq_hash, pq_rows = logical_hash(con, f"read_parquet('{path.as_posix()}')")
            if (db_hash, rows) != (pq_hash, pq_rows):
                a = con.execute(f"DESCRIBE {view}").fetchall()
                b = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path.as_posix()}')").fetchall()
                diff = [(x[0], x[1], y[1]) for x, y in zip(a, b) if x[:2] != y[:2]]
                sys.exit(f"parquet round trip differs for {mart}: rows {rows}/{pq_rows}, types {diff}")
            cols = con.execute(f"DESCRIBE {view}").fetchall()
            marts.append({"mart": mart, "rows": rows, "columns": len(cols), "order_by": "ALL",
                          "logical_sha256": db_hash, "parquet_bytes": path.stat().st_size,
                          "parquet_sha256": sha256(path.read_bytes()).hexdigest()})
            schema += [{"mart": mart, "ordinal": i + 1, "column": c[0], "type": c[1], "nullable": c[2],
                        "cast": casts.get(c[0], ""), "description": desc.get(c[0], "")} for i, c in enumerate(cols)]
        con.close()
    for name, rows in (("marts.csv", marts), ("schema.csv", schema)):
        with (args.out / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    (args.out / "SOURCE.md").write_bytes((
        "# D1 source (generated by scripts/export_d1_marts.py; do not edit)\n\n"
        f"- upstream repository: kbeauty-us-supply-chain, commit `{UPSTREAM_SHA}` (git archive, not the working tree)\n"
        f"- upstream data/SHA256SUMS: {n_sums} files verified; SHA-256 of that file `{sums_hash}`\n"
        f"- dbt build: {built['nodes']} nodes, {built['tests']} data tests, all success/pass; DuckDB settings threads=1\n"
        f"- export SQL per mart: `{EXPORT_SQL}`\n"
        f"- duckdb (export side) {duckdb.__version__}\n"
    ).encode("utf-8"))
    print(f"export   {len(marts)} marts, {sum(m['rows'] for m in marts)} rows -> {args.out}")


if __name__ == "__main__":
    main()
