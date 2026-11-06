"""Build the corpus and the BM25 index offline, run the dev queries, write one run folder.

    uv run python scripts/eval_retrieval.py run_002_reviewed_retrieval_qrels

A run folder is never overwritten (the script stops if it exists). It holds:
  bm25_dev_runs.csv          top 10 per query: rank, score, source, pages, relevant_citation, relevant_retrieval
  bm25_dev_per_query.csv     per query and qrel set
  bm25_dev_metrics.csv       answerable queries: macro/micro recall@5/10, MRR@10, nDCG@10, zero-result rate,
                             per qrel set (citation = strict, retrieval = reviewed) and group (all / en / ko)
  bm25_dev_unanswerable.csv  unanswerable queries: empty-result rate, top score when something was returned
  manifest.json              corpus, chunking and index logical hashes, parameters
  inputs.sha256              sha256 of the evaluation inputs (queries, citation seed, retrieval qrels, qrel meta)
The corpus manifest is also written to data/extracted/retrieval/bm25_manifest.json.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

from tariffagent.answer.citations import CITATIONS
from tariffagent.retrieval.bm25 import B, K1, BM25Index
from tariffagent.retrieval.corpus import REPO, build_chunks, corpus_hashes, documents
from tariffagent.retrieval.evaluate import (QUERIES, RETRIEVAL_QRELS, citation_qrels, evaluate, retrieval_qrels,
                                            summarize, summarize_unanswerable)

OUT = REPO / "reports" / "retrieval"
MANIFEST = REPO / "data" / "extracted" / "retrieval" / "bm25_manifest.json"
QRELS_META = REPO / "evals" / "dev" / "qrels_meta.json"


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _fmt(row: dict) -> dict:
    return {k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()}


def main(run: str) -> None:
    out = OUT / run
    if out.exists():
        sys.exit(f"{out} exists; runs are not overwritten")
    docs = documents()
    chunks = build_chunks()
    manifest = {**corpus_hashes(docs, chunks)}
    meta = json.loads(QRELS_META.read_text("utf-8"))
    for key in ("documents_sha256", "chunks_sha256", "chunk_config_sha256"):
        if meta[key] != manifest[key]:
            sys.exit(f"corpus changed since the qrels were reviewed ({key}); list and review the candidates again")
    index = BM25Index(chunks)
    manifest.update({"index_terms": len(index.idf), "index_sha256": index.logical_hash(), "k1": K1, "b": B})

    qrel_sets = {"citation": citation_qrels(chunks), "retrieval": retrieval_qrels(chunks)}
    runs, per_query, metrics, unanswerable = None, [], [], []
    for name, qrels in qrel_sets.items():
        r, pq = evaluate(index.search, chunks, qrels)
        if runs is None:
            runs = [{**{k: v for k, v in row.items() if k != "relevant"}, "relevant_citation": row["relevant"]}
                    for row in r]
        else:
            for row, other in zip(runs, r, strict=True):
                assert row["chunk_id"] == other["chunk_id"]
                row["relevant_retrieval"] = other["relevant"]
        per_query += [_fmt({"qrels": name, **row}) for row in pq]
        metrics += [{"qrels": name, **row} for row in summarize(pq)]
        if name == "citation":
            unanswerable = summarize_unanswerable(pq)

    out.mkdir(parents=True)
    write(out / "bm25_dev_runs.csv", runs)
    write(out / "bm25_dev_per_query.csv", per_query)
    write(out / "bm25_dev_metrics.csv", metrics)
    write(out / "bm25_dev_unanswerable.csv", unanswerable)
    body = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (out / "manifest.json").write_bytes(body)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_bytes(body)
    lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(REPO).as_posix()}"
             for p in (QUERIES, CITATIONS, RETRIEVAL_QRELS, QRELS_META)]
    (out / "inputs.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    for m in metrics + unanswerable:
        print(m)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
