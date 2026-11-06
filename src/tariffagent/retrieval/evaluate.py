"""Evaluate a retriever on the dev queries (evals/dev/queries.csv).

Relevance is attached here, not in the corpus. Two qrel sets, both mapping citation_id -> relevant chunk ids:

  citation_qrels   strict: chunks from the cited file that overlap the cited quote's span. Nothing else.
  retrieval_qrels  citation_qrels plus the other locations a reviewer accepted in evals/dev/retrieval_qrels.csv
                   (same quote, same legal scope, time and claim role; e.g. a United Kingdom note with the same
                   list is rejected for a Korea question). Rows are judged by hand; nothing is added automatically.

The unit of relevance is the citation (one piece of evidence the answer needs), not the chunk: a citation counts as
found when any of its relevant chunks is ranked. A quote can span two overlapping chunks and can be accepted in
several revisions; counting chunks would reward or punish that duplication. Per answerable query:
  recall@k   found citations in the top k / distinct relevant citations of the query (the denominator)
  mrr@10     1 / rank of the first chunk relevant to any of the query's citations (0 if none in the top 10)
  ndcg@10    binary gains: a ranked chunk gains 1 if it is the first hit of a not-yet-found citation;
             ideal = min(#relevant citations, 10)
  zero       1 if the retriever returned no result
Summaries report macro recall (mean of per-query recall) and micro recall (found citations pooled over queries /
relevant citations pooled over queries), for all answerable queries and for English and Korean separately.

Unanswerable queries (no relevant citation) are summarized apart: they have no recall, and an empty result list is
the right outcome for them, while for answerable queries it is a failure. BM25 has no abstention, so for them the
report shows how often the retriever returned nothing and the top score it returned otherwise.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from tariffagent.answer.citations import CITATIONS, file_text, normalize
from tariffagent.retrieval.corpus import REPO, Chunk

DEV = REPO / "evals" / "dev"
QUERIES = DEV / "queries.csv"
RETRIEVAL_QRELS = DEV / "retrieval_qrels.csv"


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _by_file(chunks: list[Chunk]) -> dict[str, list[Chunk]]:
    out: dict[str, list[Chunk]] = {}
    for c in chunks:
        out.setdefault(c.source_file, []).append(c)
    return out


def _overlapping(by_file: dict[str, list[Chunk]], source_file: str, quote: str, root: Path, label: str) -> set[str]:
    text = file_text(root / source_file)
    pos = text.find(quote)
    if pos < 0:
        raise ValueError(f"{label}: quote not in {source_file}")
    end = pos + len(quote)
    ids = {c.chunk_id for c in by_file.get(source_file, []) if c.start < end and c.end > pos}
    if not ids:
        raise ValueError(f"{label}: no chunk covers the quote in {source_file}")
    return ids


def citation_qrels(chunks: list[Chunk], citations_csv: Path = CITATIONS, root: Path = REPO) -> dict[str, set[str]]:
    """citation_id -> chunk ids overlapping the quote in the cited file (strict)."""
    by_file = _by_file(chunks)
    return {r["citation_id"]: _overlapping(by_file, r["source_file"], normalize(r["quote"]), root, r["citation_id"])
            for r in _read(citations_csv)}


gold_chunks = citation_qrels  # name used by run_001


def retrieval_qrels(chunks: list[Chunk], qrels_csv: Path = RETRIEVAL_QRELS, citations_csv: Path = CITATIONS,
                    root: Path = REPO) -> dict[str, set[str]]:
    """citation_qrels plus the reviewer-accepted locations of the same quote."""
    out = citation_qrels(chunks, citations_csv, root)
    quotes = {r["citation_id"]: normalize(r["quote"]) for r in _read(citations_csv)}
    by_file = _by_file(chunks)
    for r in _read(qrels_csv):
        if r["decision"] not in ("accept", "reject"):
            raise ValueError(f"{r['citation_id']} {r['source_file']}: decision must be accept or reject")
        if r["decision"] == "accept":
            out[r["citation_id"]] |= _overlapping(by_file, r["source_file"], quotes[r["citation_id"]], root,
                                                  r["citation_id"])
    return out


def query_citations(q: dict) -> list[str]:
    """Distinct relevant citations of a query, in order; empty for an unanswerable query."""
    return list(dict.fromkeys(c for c in q["relevant_citation_ids"].split(";") if c))


def evaluate(search, chunks: list[Chunk], qrels: dict[str, set[str]] | None = None, queries_csv: Path = QUERIES,
             k: int = 10) -> tuple[list[dict], list[dict]]:
    qrels = citation_qrels(chunks) if qrels is None else qrels
    runs, per_query = [], []
    for q in _read(queries_csv):
        cites = query_citations(q)
        hits = search(q["text"], k)
        for h in hits:
            runs.append({"query_id": q["query_id"], "chunk_id": h.chunk.chunk_id, "rank": h.rank,
                         "bm25_score": f"{h.score:.6f}", "source_id": h.chunk.source_id,
                         "physical_page": h.chunk.physical_page, "printed_page": h.chunk.printed_page,
                         "relevant": int(any(h.chunk.chunk_id in qrels[c] for c in cites))})
        row = {"query_id": q["query_id"], "lang": q["lang"], "answerable": int(bool(cites)),
               "relevant_citations": len(cites), "zero": int(not hits),
               "top_score": hits[0].score if hits else 0.0}
        if cites:
            found_at: dict[str, int] = {}
            gains = []
            for h in hits:
                new = [c for c in cites if h.chunk.chunk_id in qrels[c] and c not in found_at]
                for c in new:
                    found_at[c] = h.rank
                gains.append(1 if new else 0)
            first = min((h.rank for h in hits if any(h.chunk.chunk_id in qrels[c] for c in cites)), default=None)
            dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
            idcg = sum(1 / math.log2(i + 2) for i in range(min(len(cites), k)))
            found5 = sum(1 for r in found_at.values() if r <= 5)
            found10 = sum(1 for r in found_at.values() if r <= 10)
            row.update({"found@5": found5, "found@10": found10, "recall@5": found5 / len(cites),
                        "recall@10": found10 / len(cites), "mrr@10": 1 / first if first else 0.0,
                        "ndcg@10": dcg / idcg})
        per_query.append(row)
    return runs, per_query


def summarize(per_query: list[dict]) -> list[dict]:
    """Answerable queries only: macro and micro recall, MRR, nDCG, zero-result rate; all / en / ko."""
    out = []
    for group in ("all", "en", "ko"):
        rows = [r for r in per_query if r["answerable"] and (group == "all" or r["lang"] == group)]
        if not rows:
            continue
        n_rel = sum(r["relevant_citations"] for r in rows)
        out.append({"group": group, "queries": len(rows), "relevant_citations": n_rel,
                    "macro_recall@5": f"{sum(r['recall@5'] for r in rows) / len(rows):.4f}",
                    "micro_recall@5": f"{sum(r['found@5'] for r in rows) / n_rel:.4f}",
                    "macro_recall@10": f"{sum(r['recall@10'] for r in rows) / len(rows):.4f}",
                    "micro_recall@10": f"{sum(r['found@10'] for r in rows) / n_rel:.4f}",
                    "mrr@10": f"{sum(r['mrr@10'] for r in rows) / len(rows):.4f}",
                    "ndcg@10": f"{sum(r['ndcg@10'] for r in rows) / len(rows):.4f}",
                    "zero_result_rate": f"{sum(r['zero'] for r in rows) / len(rows):.4f}"})
    return out


def summarize_unanswerable(per_query: list[dict]) -> list[dict]:
    """Unanswerable queries: how often nothing was returned (correct here), and the top score otherwise."""
    out = []
    for group in ("all", "en", "ko"):
        rows = [r for r in per_query if not r["answerable"] and (group == "all" or r["lang"] == group)]
        if not rows:
            continue
        returned = [r["top_score"] for r in rows if not r["zero"]]
        out.append({"group": group, "queries": len(rows),
                    "empty_result_rate": f"{sum(r['zero'] for r in rows) / len(rows):.4f}",
                    "mean_top_score_when_returned": f"{sum(returned) / len(returned):.4f}" if returned else ""})
    return out
