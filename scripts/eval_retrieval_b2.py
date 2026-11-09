"""First B2 (heading-enriched BM25) run, compared with B1 on the same queries, offline.

    uv run python scripts/eval_retrieval_b2.py run_004_b2_heading_v1 b2_heading_v1   (diagnostic, invalid)
    uv run python scripts/eval_retrieval_b2.py run_005_b2_heading_v2 b2_heading_v2

Relevance here is only the strict citation qrels (the cited file and page; mechanical, identical for B1 and B2,
because B2 keeps B1's windows and offsets). B2 needs its own reviewed qrels (evals/dev/review_b2v2/); until they exist
there is no reviewed B1/B2 comparison and no unreachable-citation count for B2.
Time conditions and pair checks are run_003's (evals/dev/query_time_conditions.csv, query_pair_checks.csv).

Writes reports/retrieval/<run>/ (never overwritten):
  b2_dev_runs.csv            top 10 per query for B2: rank, score, chunk, parent B1 chunk, context origin, relevant
  dev_per_query.csv          per system (B1, B2) and query, strict citation qrels
  dev_metrics.csv            per system, query set (main / underspecified) and group, incl. paired rows and gap
  dev_unanswerable.csv       per system
  unit_stats.csv             chunks, mean raw / index tokens, index terms and postings, build and search time
  manifest.json              B1 and B2 corpus, chunk, config and index hashes, B2 structure statistics
  inputs.sha256
and data/extracted/retrieval_b2/<config>_manifest.json. B1's manifest and runs are not written.
Timings are wall-clock on this machine (not reproducible, not hashed).
"""

import csv
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

from tariffagent.answer.citations import CITATIONS
from tariffagent.retrieval.bm25 import B, K1, BM25Index, tokenize
from tariffagent.retrieval.corpus import REPO, build_chunks, corpus_hashes, documents
from tariffagent.retrieval.evaluate import (QUERIES, citation_qrels, evaluate, matched_pairs, summarize,
                                            summarize_unanswerable, time_conditions)
from tariffagent.retrieval.structure import CONFIGS, b2_hashes, enrich, structure_stats

OUT = REPO / "reports" / "retrieval"
B1_MANIFEST = REPO / "data" / "extracted" / "retrieval" / "bm25_manifest.json"
B2_DIR = REPO / "data" / "extracted" / "retrieval_b2"
DEV = REPO / "evals" / "dev"
TIME_CONDITIONS = DEV / "query_time_conditions.csv"
PAIR_CHECKS = DEV / "query_pair_checks.csv"
MODULE = REPO / "src" / "tariffagent" / "retrieval" / "structure.py"


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _fmt(row: dict) -> dict:
    return {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()}


def timed_search(index: BM25Index, repeats: int = 5):
    queries = list(csv.DictReader(QUERIES.open(encoding="utf-8")))
    per_round = []
    for _ in range(repeats):
        t = time.perf_counter()
        for q in queries:
            index.search(q["text"], 10)
        per_round.append((time.perf_counter() - t) / len(queries))
    return statistics.median(per_round)


def main(run: str, config_id: str) -> None:
    if config_id not in CONFIGS:
        sys.exit(f"unknown configuration {config_id}")
    out = OUT / run
    if out.exists():
        sys.exit(f"{out} exists; runs are not overwritten")
    docs = documents()
    b1 = build_chunks()
    h1 = corpus_hashes(docs, b1)
    m1 = json.loads(B1_MANIFEST.read_text("utf-8"))
    for key in ("documents_sha256", "chunks_sha256", "chunk_config_sha256"):
        if h1[key] != m1[key]:
            sys.exit(f"B1 corpus differs from its manifest ({key}); B1 must stay as run_003 used it")
    b2 = enrich(docs, b1, config_id=config_id)
    stats, indexes = [], {}
    for name, chunks in (("B1", b1), ("B2", b2)):
        t = time.perf_counter()
        idx = BM25Index(chunks)
        build = time.perf_counter() - t
        indexes[name] = idx
        stats.append({"system": name, "chunks": len(chunks),
                      "mean_raw_tokens": f"{statistics.mean(len(tokenize(c.text if name == 'B1' else c.raw_text)) for c in chunks):.1f}",
                      "mean_index_tokens": f"{statistics.mean(idx.lengths):.1f}",
                      "index_terms": len(idx.idf), "postings": sum(len(p) for p in idx.postings.values()),
                      "index_build_seconds": f"{build:.2f}",
                      "search_ms_per_query_median_of_5": f"{1000 * timed_search(idx):.2f}"})
    if indexes["B1"].logical_hash() != m1["index_sha256"]:
        sys.exit("B1 index differs from its manifest")

    conditions, pairs_ok = time_conditions(TIME_CONDITIONS), matched_pairs(PAIR_CHECKS)
    per_query, metrics, unanswerable, runs = [], [], [], []
    for name, chunks in (("B1", b1), ("B2", b2)):
        r, pq = evaluate(indexes[name].search, chunks, citation_qrels(chunks), conditions=conditions)
        per_query += [_fmt({"system": name, "qrels": "citation", **row}) for row in pq]
        for qset, under in (("main", False), ("underspecified", True)):
            metrics += [{"system": name, "qrels": "citation", "queries_set": qset, **row}
                        for row in summarize(pq, underspecified=under, matched_pairs=pairs_ok)]
        unanswerable += [{"system": name, **row} for row in summarize_unanswerable(pq)]
        if name == "B2":
            by_id = {b.chunk_id: b for b in b2}
            runs = [{**row, "parent_chunk_id": by_id[row["chunk_id"]].parent_chunk_id,
                     "context_origin": by_id[row["chunk_id"]].context_origin,
                     "applicable_heading": by_id[row["chunk_id"]].applicable_heading} for row in r]

    manifest = {"b1": {k: h1[k] for k in ("documents_sha256", "chunks", "chunks_sha256", "chunk_config_sha256")}
                | {"index_sha256": indexes["B1"].logical_hash()},
                "b2": b2_hashes(b2) | {"index_sha256": indexes["B2"].logical_hash(),
                                       "index_terms": len(indexes["B2"].idf),
                                       "structure_module_sha256": hashlib.sha256(MODULE.read_bytes()).hexdigest(),
                                       "structure_stats": structure_stats(b2)},
                "k1": K1, "b": B, "config_id": config_id, "qrels": "citation (strict) only; B2 review pending"}
    out.mkdir(parents=True)
    write(out / "b2_dev_runs.csv", runs)
    write(out / "dev_per_query.csv", per_query)
    write(out / "dev_metrics.csv", metrics)
    write(out / "dev_unanswerable.csv", unanswerable)
    write(out / "unit_stats.csv", stats)
    body = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (out / "manifest.json").write_bytes(body)
    B2_DIR.mkdir(parents=True, exist_ok=True)
    (B2_DIR / f"{config_id}_manifest.json").write_bytes((json.dumps(manifest["b2"], indent=2, sort_keys=True) + "\n").encode("utf-8"))
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(REPO).as_posix()}"
             for p in (QUERIES, CITATIONS, TIME_CONDITIONS, PAIR_CHECKS, MODULE)]
    (out / "inputs.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for row in stats + [m for m in metrics if m["group"] in ("all", "en", "ko", "gap_en_minus_ko")] + unanswerable:
        print(row)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
