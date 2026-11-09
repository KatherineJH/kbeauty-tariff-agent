"""Claim-based B1/B2 comparison on run_007, with the finalized human_assisted judgements (final/v1) as the only qrels.

    uv run python scripts/eval_claims_final.py run_008_claims_final_v1

Inputs (hashed in the manifest):
  rankings     B1: reports/retrieval/run_003_user_reviewed_qrels/bm25_dev_runs.csv (the B1 top 10 that run_007
               compared against); B2: reports/retrieval/run_007_b2_heading_v4/b2_dev_runs.csv
  judgements   evals/dev/review_claims/final/v1/{b1,b2}_items.csv and _item_claim_judgments.csv (human_assisted)
  unit -> item evals/dev/review_claims/pools.csv (system, query, unit chunk -> displayed payload hash) and the review
               sheets (item id, intent, queries, payload hash)
  claims       evals/dev/claims.csv, claim_components.csv (v1 catalog, sealed; not changed here)
  query sets   evals/dev/queries.csv, query_time_conditions.csv (underspecified), query_pair_checks.csv (matched)
The sealed Claude judgements are not read.

Scoring: src/tariffagent/retrieval/claim_scoring.py score_query with k in (1, 3, 5, 10). A ranked unit is judged when
it is in the system's pool for that query; its item's decision and component levels apply to the query's own claim
component ids (pair items serve both languages with the same claim text).

Official result: the v1 claim catalog as sealed. dq07 c1 (single effective date) cannot be completed by any judged
unit under CI-001 (evals/dev/review_claims/claim_open_issues.md); it stays in the official result. A sensitivity
view without dq07_en / dq07_ko is reported separately and never merged into the official tables.

Writes reports/retrieval/<run>/ (never overwritten):
  claim_per_query.csv     one row per system and query (all metrics)
  claim_paired_delta.csv  one row per query: B2 - B1 for the primary metrics and unreachable_claims
  claim_metrics.json      official groups, paired summary (mean delta, wins/ties/losses), diagnostics apart,
                          sensitivity (without dq07) apart
  manifest.json           input and output hashes
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

from tariffagent.retrieval.claim_scoring import Judgement, score_query
from tariffagent.retrieval.corpus import REPO
from tariffagent.retrieval.evaluate import matched_pairs, time_conditions

DEV = REPO / "evals" / "dev"
RC = DEV / "review_claims"
FINAL = RC / "final" / "v1"
RUNS = {"B1": REPO / "reports" / "retrieval" / "run_003_user_reviewed_qrels" / "bm25_dev_runs.csv",
        "B2": REPO / "reports" / "retrieval" / "run_007_b2_heading_v4" / "b2_dev_runs.csv"}
OUT = REPO / "reports" / "retrieval"
K = (1, 3, 5, 10)
PRIMARY = ([f"claim_recall@{k}" for k in K] + [f"all_claims_covered@{k}" for k in K]
           + ["mrr_any_complete_claim@10", "mrr_all_claims_complete@10"])
SECONDARY = [f"partial_claim_recall@{k}" for k in K]
DIAGNOSTIC = ["system_relative_ndcg@10", "claim_novelty_dcg@10"]
COUNTS = ["unreachable_claims", "unjudged@10", "uncertain@10"]
CI001_QUERIES = ("dq07_en", "dq07_ko")


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs() -> list[Path]:
    return ([RUNS["B1"], RUNS["B2"], RC / "pools.csv", DEV / "claims.csv", DEV / "claim_components.csv",
             DEV / "queries.csv", DEV / "query_time_conditions.csv", DEV / "query_pair_checks.csv",
             FINAL / "manifest.json", RC / "claim_open_issues.md"]
            + sorted(FINAL.glob("*.csv")) + [RC / f"{s}_review_sheet.csv" for s in ("b1", "b2")])


def load():
    queries = {q["query_id"]: q for q in _read(DEV / "queries.csv")}
    cond = time_conditions(DEV / "query_time_conditions.csv")
    claims: dict[str, dict[str, list[str]]] = {}
    required: dict[str, set[str]] = {}
    for c in _read(DEV / "claims.csv"):
        claims.setdefault(c["query_id"], {})[c["claim_id"]] = []
        if c["required"] == "true":
            required.setdefault(c["query_id"], set()).add(c["claim_id"])
    for c in _read(DEV / "claim_components.csv"):
        claims[c["claim_id"].split(".")[0]][c["claim_id"]].append(c["component_id"])
    judgements: dict[str, dict[str, tuple[str, dict]]] = {}   # system -> item -> (decision, {c1.e1: level})
    by_payload: dict[tuple, str] = {}                          # (system, query, payload) -> item
    for s, sysname in (("b1", "B1"), ("b2", "B2")):
        items = {r["item_id"]: (r["decision"], {}) for r in _read(FINAL / f"{s}_items.csv")}
        for c in _read(FINAL / f"{s}_item_claim_judgments.csv"):
            items[c["item_id"]][1][f"{c['claim']}.{c['component']}"] = c["support"]
        judgements[sysname] = items
        for r in _read(RC / f"{s}_review_sheet.csv"):
            for q in r["query_ids"].split(";"):
                key = (sysname, q, r["payload_sha256"])
                if key in by_payload:
                    raise ValueError(f"two items for {key}")
                by_payload[key] = r["item_id"]
    pools: dict[tuple, dict[str, str]] = {}                    # (system, query) -> unit -> item
    for p in _read(RC / "pools.csv"):
        item = by_payload[(p["system"], p["query_id"], p["payload_sha256"])]
        pools.setdefault((p["system"], p["query_id"]), {})[p["unit_chunk_id"]] = item
    rankings: dict[tuple, list[str]] = {}
    for sysname, path in RUNS.items():
        rows = sorted(_read(path), key=lambda r: (r["query_id"], int(r["rank"])))
        for r in rows:
            if int(r["rank"]) <= 10:
                rankings.setdefault((sysname, r["query_id"]), []).append(r["chunk_id"])
    return queries, cond, claims, required, judgements, pools, rankings


def per_query_rows() -> list[dict]:
    queries, cond, claims, required, judgements, pools, rankings = load()
    rows = []
    for sysname in ("B1", "B2"):
        for qid in sorted(required):
            pool_items = pools.get((sysname, qid), {})
            judged = {}
            for unit, item in pool_items.items():
                decision, levels = judgements[sysname][item]
                judged[unit] = Judgement(decision, {f"{qid}.{k}": v for k, v in levels.items()})
            ranking = rankings.get((sysname, qid), [])
            row = score_query(claims[qid], required[qid], ranking, judged, set(pool_items), k_values=K)
            q = queries[qid]
            rows.append({"system": sysname, "query_id": qid, "pair_id": q["pair_id"], "lang": q["lang"],
                         "underspecified": int(cond.get(qid) == "underspecified"),
                         "ci001_query": int(qid in CI001_QUERIES), **row})
    return rows


def macro(rows: list[dict], names: list[str]) -> dict:
    return {m: round(sum(r[m] for r in rows) / len(rows), 4) for m in names} if rows else {}


def groups(rows: list[dict]) -> dict:
    sel = {"all": rows, "main": [r for r in rows if not r["underspecified"]],
           "underspecified": [r for r in rows if r["underspecified"]],
           "en": [r for r in rows if r["lang"] == "en"], "ko": [r for r in rows if r["lang"] == "ko"]}
    out = {}
    for g, rs in sel.items():
        out[g] = {"queries": len(rs), "required_claims": sum(r["required_claims"] for r in rs),
                  "unreachable_claims": sum(r["unreachable_claims"] for r in rs),
                  "unjudged@10": sum(r["unjudged@10"] for r in rs), "uncertain@10": sum(r["uncertain@10"] for r in rs),
                  "primary_macro": macro(rs, PRIMARY), "secondary_macro": macro(rs, SECONDARY)}
    return out


def paired(rows: list[dict], query_ids: list[str]) -> tuple[list[dict], dict]:
    b = {(r["system"], r["query_id"]): r for r in rows}
    deltas = []
    for q in query_ids:
        d = {"query_id": q, "pair_id": b[("B1", q)]["pair_id"], "lang": b[("B1", q)]["lang"],
             "underspecified": b[("B1", q)]["underspecified"], "ci001_query": b[("B1", q)]["ci001_query"]}
        for m in PRIMARY + ["unreachable_claims"]:
            d[f"B1_{m}"] = b[("B1", q)][m]
            d[f"B2_{m}"] = b[("B2", q)][m]
            d[f"delta_{m}"] = round(b[("B2", q)][m] - b[("B1", q)][m], 4)
        deltas.append(d)
    summary = {}
    for m in PRIMARY:
        ds = [d[f"delta_{m}"] for d in deltas]
        summary[m] = {"mean_delta_B2_minus_B1": round(sum(ds) / len(ds), 4) if ds else 0.0,
                      "wins_B2": sum(x > 0 for x in ds), "ties": sum(x == 0 for x in ds),
                      "losses_B2": sum(x < 0 for x in ds)}
    ds = [d["delta_unreachable_claims"] for d in deltas]
    summary["unreachable_claims"] = {"total_B1": sum(d["B1_unreachable_claims"] for d in deltas),
                                     "total_B2": sum(d["B2_unreachable_claims"] for d in deltas),
                                     "fewer_unreachable_B2": sum(x < 0 for x in ds), "ties": sum(x == 0 for x in ds),
                                     "more_unreachable_B2": sum(x > 0 for x in ds)}
    return deltas, summary


def view(rows: list[dict], query_ids: list[str]) -> dict:
    sel = [r for r in rows if r["query_id"] in query_ids]
    _, pair_all = paired(sel, query_ids)
    _, pair_main = paired(sel, [q for q in query_ids if not next(r for r in sel if r["query_id"] == q)["underspecified"]])
    _, pair_under = paired(sel, [q for q in query_ids if next(r for r in sel if r["query_id"] == q)["underspecified"]])
    pairs = matched_pairs(DEV / "query_pair_checks.csv")
    out = {"systems": {s: groups([r for r in sel if r["system"] == s]) for s in ("B1", "B2")},
           "paired": {"all": pair_all, "main": pair_main, "underspecified": pair_under}}
    gap = {}
    for s in ("B1", "B2"):
        both = {r["pair_id"] for r in sel if r["system"] == s and r["pair_id"] in pairs}
        both = {p for p in both if {r["lang"] for r in sel if r["system"] == s and r["pair_id"] == p} >= {"en", "ko"}}
        en = macro([r for r in sel if r["system"] == s and r["pair_id"] in both and r["lang"] == "en"], PRIMARY)
        ko = macro([r for r in sel if r["system"] == s and r["pair_id"] in both and r["lang"] == "ko"], PRIMARY)
        gap[s] = {"matched_pairs": sorted(both), "en_minus_ko": {m: round(en[m] - ko[m], 4) for m in PRIMARY}}
    out["language_gap_matched_pairs"] = gap
    return out


def compute() -> tuple[list[dict], list[dict], dict]:
    rows = per_query_rows()
    qids = sorted({r["query_id"] for r in rows})
    deltas, _ = paired(rows, qids)
    ci = {q: {s: next(r for r in rows if r["system"] == s and r["query_id"] == q)["unreachable_claims"]
              for s in ("B1", "B2")} for q in CI001_QUERIES}
    metrics = {
        "qrels": "evals/dev/review_claims/final/v1 (human_assisted)",
        "claim_catalog": "v1 (sealed); dq07 c1 unchanged",
        "k": list(K), "primary": PRIMARY, "secondary": SECONDARY, "diagnostic_only": DIAGNOSTIC,
        "official": view(rows, qids),
        "diagnostics_only": {s: {g: macro(rs, DIAGNOSTIC) for g, rs in
                                 (("all", [r for r in rows if r["system"] == s]),
                                  ("main", [r for r in rows if r["system"] == s and not r["underspecified"]]),
                                  ("underspecified", [r for r in rows if r["system"] == s and r["underspecified"]]))}
                             for s in ("B1", "B2")},
        "ci001": {"queries": list(CI001_QUERIES), "unreachable_required_claims": ci,
                  "note": "dq07 c1 (single effective date) has no complete support in any judged unit under CI-001; "
                          "it cannot be completed in the current catalog"},
        "sensitivity_without_dq07": view(rows, [q for q in qids if q not in CI001_QUERIES]),
    }
    return rows, deltas, metrics


def _fmt(row: dict) -> dict:
    return {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()}


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(_fmt(r) for r in rows)


def main(run: str) -> None:
    out = OUT / run
    if out.exists():
        sys.exit(f"{out} exists; runs are not overwritten")
    rows, deltas, metrics = compute()
    out.mkdir(parents=True)
    write(out / "claim_per_query.csv", rows)
    write(out / "claim_paired_delta.csv", deltas)
    (out / "claim_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8", newline="\n")
    manifest = {"run": run, "script": "scripts/eval_claims_final.py",
                "inputs_sha256": {str(p.relative_to(REPO)).replace("\\", "/"): _sha(p) for p in inputs()},
                "outputs_sha256": {p.name: _sha(p) for p in sorted(out.iterdir())},
                "claude_sealed_read": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
