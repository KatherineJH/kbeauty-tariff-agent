"""Make the blind review sheets for the dev qrels (v2).

    uv run python scripts/make_qrel_review_sheet.py

Relevance criterion (fixed before review; also in evals/dev/README.md):
  Relevance is judged only from the conditions stated in the query and from what the retriever actually returns:
  the chunk text and its metadata (source_id, source_file, physical_page, printed_page). Outside context, such as
  the rest of the page, the heading of a note that is not in the chunk, or the hidden period of the answer rule,
  is not used. Later context expansion (adjacent chunks) is a different retrieval unit and is not assumed here.
  Time: a query that states a date is judged at that date. A query without a date is not judged against any
  period: the same provision in a revision from another time is not not_relevant for its period alone. A query
  that cannot be answered without a date is classified underspecified in the time sheet and reported apart.

  relevant      the returned unit alone answers the query's core claim
  not_relevant  a different country, duty type or legal scope, or plainly does not answer
  uncertain     the heading, period or note context needed to judge is not in the returned unit

Review unit: (query pair, chunk). The English and Korean queries of a pair ask the same thing; if their stated
conditions differ, the time-condition sheet records it per query. Candidates: every chunk that overlaps a verbatim
occurrence of a quote the pair's answer cites (the cited location included, not marked). No retriever is used to
pick candidates, so the set does not favour BM25 or dense retrieval; evidence that is worded differently is not a
candidate (a known limit of this qrel set).

Writes, under evals/dev/review/:
  qrel_review_sheet.csv / .md   one row per unit (u001..): fill user_decision and user_reason, and reviewer_type
                                (human, or second_model_review if a model filled it)
  query_time_sheet.csv          one row per answerable query: fill time_condition (dated / time_invariant /
                                underspecified) and reason
Both are blind: no earlier decision, cited location, rule or rule period is shown. CSV files are UTF-8 with BOM.
The script refuses to overwrite a sheet that already has decisions.
"""

import csv
import sys

from tariffagent.answer.citations import CITATIONS, normalize
from tariffagent.retrieval.corpus import REPO, build_chunks, documents

DEV = REPO / "evals" / "dev"
OUT = DEV / "review"
CANDIDATES = DEV / "retrieval_qrel_candidates.csv"
SHEET = OUT / "qrel_review_sheet.csv"
TIME_SHEET = OUT / "query_time_sheet.csv"
CRITERION = (__doc__.split("Relevance criterion (fixed before review; also in evals/dev/README.md):\n")[1]
             .split("\n\nReview unit:")[0])


def _read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def pairs() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for q in _read(DEV / "queries.csv"):
        cites = [c for c in q["relevant_citation_ids"].split(";") if c]
        if not cites:
            continue
        p = out.setdefault(q["pair_id"], {"queries": {}, "citations": []})
        p["queries"][q["lang"]] = q
        p["citations"] += [c for c in cites if c not in p["citations"]]
    return out


def units() -> list[dict]:
    """(pair, chunk) units with the citations whose quote the chunk overlaps."""
    cites = {r["citation_id"]: r for r in _read(CITATIONS)}
    texts = {d.source_file: d.text for d in documents()}
    by_file: dict = {}
    for c in build_chunks():
        by_file.setdefault(c.source_file, []).append(c)
    cands = _read(CANDIDATES)
    rows: dict[tuple, dict] = {}
    for pid, p in sorted(pairs().items()):
        for cand in cands:
            if cand["citation_id"] not in p["citations"]:
                continue
            text = texts[cand["source_file"]]
            quote = normalize(cites[cand["citation_id"]]["quote"])
            pos = text.find(quote)
            for c in by_file[cand["source_file"]]:
                if c.start < pos + len(quote) and c.end > pos:
                    u = rows.setdefault((pid, c.chunk_id), {"pair_id": pid, "chunk": c, "citations": []})
                    if cand["citation_id"] not in u["citations"]:
                        u["citations"].append(cand["citation_id"])
    return sorted(rows.values(), key=lambda u: (u["pair_id"], u["chunk"].source_file, u["chunk"].start))


def build() -> tuple[list[dict], list[dict]]:
    ps = pairs()
    sheet = []
    for i, u in enumerate(units(), 1):
        c, qs = u["chunk"], ps[u["pair_id"]]["queries"]
        sheet.append({"unit_id": f"u{i:03d}", "pair_id": u["pair_id"],
                      "query_en": qs["en"]["text"], "query_ko": qs["ko"]["text"],
                      "source_id": c.source_id, "source_file": c.source_file, "physical_page": c.physical_page,
                      "printed_page": c.printed_page, "chunk_id": c.chunk_id, "chunk_text": " ".join(c.text.split()),
                      "citation_ids": ";".join(u["citations"]),
                      "user_decision": "", "user_reason": "", "reviewer_type": ""})
    time_rows = [{"query_id": q["query_id"], "pair_id": pid, "lang": lang, "text": q["text"],
                  "time_condition": "", "reason": ""}
                 for pid, p in sorted(ps.items()) for lang, q in sorted(p["queries"].items())]
    return sheet, time_rows


def write_md(rows: list[dict]) -> str:
    out = ["# Retrieval qrel review sheet (blind, v2)", "", "## Criterion (fixed before review)", "",
           "```", CRITERION, "```", "",
           "Fill `user_decision`, `user_reason` and `reviewer_type` in qrel_review_sheet.csv. "
           "`citation_ids` is bookkeeping for scoring; ignore it when judging.", ""]
    last = None
    for r in rows:
        if r["pair_id"] != last:
            last = r["pair_id"]
            out += [f"## {last}", "", f"- en: {r['query_en']}", f"- ko: {r['query_ko']}", ""]
        out += [f"### {r['unit_id']}: {r['source_id']}, page {r['physical_page'] or '-'} / {r['printed_page'] or '-'}", "",
                f"> {r['chunk_text']}", "", "decision: ____ reason: ____", ""]
    return "\n".join(out)


def main() -> None:
    for path, col in ((SHEET, "user_decision"), (TIME_SHEET, "time_condition")):
        if path.exists() and col in _read(path)[0] and any(r[col] for r in _read(path)):
            sys.exit(f"{path} already has decisions; not overwritten")
    sheet, time_rows = build()
    OUT.mkdir(parents=True, exist_ok=True)
    _write(SHEET, sheet)
    _write(TIME_SHEET, time_rows)
    (OUT / "qrel_review_sheet.md").write_text(write_md(sheet) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(sheet)} units, {len(time_rows)} queries")


if __name__ == "__main__":
    main()
