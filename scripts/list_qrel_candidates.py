"""List every corpus location that contains the quote of a dev-set citation, for human review.

    uv run python scripts/list_qrel_candidates.py

Writes evals/dev/retrieval_qrel_candidates.csv and evals/dev/qrels_meta.json (the corpus and chunking hashes the
candidates were listed on; evaluation refuses to run when the corpus no longer matches them).

The candidate rule is mechanical and narrow: a location is a candidate when its normalized page text contains the
citation's normalized quote verbatim. Paraphrases and reworded later
versions are not candidates. Candidates are not relevance judgements: each one must get a decision (accept / reject)
and a reason in evals/dev/retrieval_qrels.csv, written by a reviewer; tests fail if a candidate has no decision or a
decision has no candidate.
"""

import csv
import json
import re

from tariffagent.answer.citations import CITATIONS, normalize
from tariffagent.retrieval.corpus import REPO, build_chunks, corpus_hashes, documents

QUERIES = REPO / "evals" / "dev" / "queries.csv"
OUT = REPO / "evals" / "dev" / "retrieval_qrel_candidates.csv"
META = REPO / "evals" / "dev" / "qrels_meta.json"
RULE = ("a location is a candidate when its normalized page text contains the citation's normalized quote verbatim; "
        "every candidate gets a reviewer decision in retrieval_qrels.csv")
HEADING = re.compile(r"heading (9903\.\d\d\.\d\d)")


def _read(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def candidates() -> list[dict]:
    cites = {r["citation_id"]: r for r in _read(CITATIONS)}
    wanted = sorted({c for q in _read(QUERIES) for c in q["relevant_citation_ids"].split(";") if c})
    docs = documents()
    rows = []
    for cid in wanted:
        quote = normalize(cites[cid]["quote"])
        for d in docs:
            pos = d.text.find(quote)
            if pos < 0:
                continue
            last = HEADING.findall(d.text[:pos])
            rows.append({"citation_id": cid, "source_file": d.source_file, "physical_page": d.physical_page,
                         "printed_page": d.printed_page,
                         "is_cited_location": int(d.source_file == cites[cid]["source_file"]),
                         "preceding_heading": last[-1] if last else "",
                         "context_before": " ".join(d.text[max(0, pos - 160):pos].split())})
    return sorted(rows, key=lambda r: (r["citation_id"], r["source_file"]))


def main() -> None:
    rows = candidates()
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    h = corpus_hashes(documents(), build_chunks())
    meta = {k: h[k] for k in ("documents", "documents_sha256", "chunks", "chunks_sha256", "chunk_config_sha256")}
    meta["candidate_rule"] = RULE
    META.write_bytes((json.dumps(meta, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(f"{len(rows)} candidates, {sum(1 for r in rows if not r['is_cited_location'])} outside the cited location")


if __name__ == "__main__":
    main()
