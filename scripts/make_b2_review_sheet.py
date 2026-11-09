"""Candidates and the blind review sheet for B2 (b2_heading_v1) units.

    uv run python scripts/make_b2_review_sheet.py

Candidates: the B2 children of the B1 review units (every chunk overlapping a verbatim occurrence of a quote the
pair's answer cites; scripts/make_qrel_review_sheet.py:units). Same retriever-independent rule as v2; nothing is
marked relevant. Each B2 unit is new (context added) and is judged again with the v2 criterion
(evals/dev/README.md), from what B2 returns: context_text, raw_text and metadata.

Writes:
  evals/dev/b2_qrel_candidates.csv          pair_id, b2_chunk_id, parent_chunk_id, citation_ids, config_id
  evals/dev/review_b2/qrel_review_sheet.csv one row per unit (b001..): fill user_decision, user_reason, reviewer_type
  evals/dev/review_b2/qrel_review_sheet.md  the same, readable
The sheet shows no B1 decision, no cited location and no rule. It is not overwritten once a decision is filled.
"""

import csv
import sys

from tariffagent.retrieval.corpus import REPO, build_chunks, documents
from tariffagent.retrieval.structure import CONFIG_ID, enrich

sys.path.insert(0, str(REPO / "scripts"))
from make_qrel_review_sheet import pairs, units  # noqa: E402

DEV = REPO / "evals" / "dev"
OUT = DEV / "review_b2"
SHEET = OUT / "qrel_review_sheet.csv"


def _write(path, rows, bom=False):
    with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build() -> tuple[list[dict], list[dict]]:
    b2 = {b.parent_chunk_id: b for b in enrich(documents(), build_chunks())}
    ps = pairs()
    cands, sheet = [], []
    for i, u in enumerate(units(), 1):
        b = b2[u["chunk"].chunk_id]
        q = ps[u["pair_id"]]["queries"]
        cands.append({"pair_id": u["pair_id"], "b2_chunk_id": b.chunk_id, "parent_chunk_id": b.parent_chunk_id,
                      "citation_ids": ";".join(u["citations"]), "config_id": CONFIG_ID})
        sheet.append({"unit_id": f"b{i:03d}", "pair_id": u["pair_id"], "query_en": q["en"]["text"],
                      "query_ko": q["ko"]["text"], "source_id": b.source_id, "source_file": b.source_file,
                      "source_revision": b.source_revision, "physical_page": b.physical_page,
                      "printed_page": b.printed_page, "chunk_id": b.chunk_id, "context_text": b.context_text,
                      "raw_text": b.raw_text, "user_decision": "", "user_reason": "", "reviewer_type": ""})
    return cands, sheet


def write_md(rows: list[dict]) -> str:
    out = ["# B2 qrel review sheet (blind, b2_heading_v1)", "",
           "Criterion: the v2 criterion in evals/dev/README.md, applied to what B2 returns: the extracted context, "
           "the raw text and the metadata. The context is extracted by rules, not part of the source text.", ""]
    last = None
    for r in rows:
        if r["pair_id"] != last:
            last = r["pair_id"]
            out += [f"## {last}", "", f"- en: {r['query_en']}", f"- ko: {r['query_ko']}", ""]
        out += [f"### {r['unit_id']}: {r['source_id']}, page {r['physical_page'] or '-'} / "
                f"{r['printed_page'] or '-'}", "", f"- context (extracted): {r['context_text']}", "",
                f"> {r['raw_text']}", "", "decision: ____ reason: ____", ""]
    return "\n".join(out)


def main() -> None:
    if SHEET.exists() and any(r["user_decision"] for r in csv.DictReader(SHEET.open(encoding="utf-8-sig"))):
        sys.exit(f"{SHEET} already has decisions; not overwritten")
    cands, sheet = build()
    OUT.mkdir(parents=True, exist_ok=True)
    _write(DEV / "b2_qrel_candidates.csv", cands)
    _write(SHEET, sheet, bom=True)
    (OUT / "qrel_review_sheet.md").write_text(write_md(sheet) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(sheet)} units")


if __name__ == "__main__":
    main()
