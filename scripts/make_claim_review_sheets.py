"""Claim-level review items, one sheet per system: B1 units (raw text) and B2 units (b2_heading_v4: context + raw).

    uv run python scripts/make_claim_review_sheets.py

Pools, per answerable query (union, nothing cut to top 5):
  candidate       chunks overlapping a verbatim occurrence of a quote the query's answer cites (v2 candidates)
  top10           the system's own top 10 (B1: run_003; B2: run_007_b2_heading_v4)
  cited_location  chunks overlapping the cited quote in the cited file and page
A B1 item shows only what B1 returns (raw_text and B1 metadata); a B2 item shows what B2 returns (context_text,
raw_text and B2 metadata).

Review item key = (intent, required_claim_set_hash, displayed_payload_hash):
  intent                    the pair for a matched pair (both queries ask the same thing), the query otherwise
  required_claim_set_hash   sha256 over the sorted (claim_text, required) of the query's claims
  displayed_payload_hash    sha256 over exactly the fields the reviewer sees for the unit (payload + metadata)
So a matched English/Korean pair that returns the same payload is judged once; a mismatched pair is judged per
query; B1 and B2 share an item only if their displayed payloads are identical (they never are: B2 always shows a
context).

Reuse of the earlier human_assisted pair judgements (evals/dev/review/qrel_review_sheet.csv) on a B1 item only when
all hold: the intent is a matched pair and the same pair; the gold links of the required claims' evidence
(evals/dev/claim_evidence.csv) are exactly the gold citations the earlier judgement used (the pair's
relevant_citation_ids); the displayed payload and metadata hash is identical. A reused not_relevant / uncertain item
gets support none on every component; a reused relevant item keeps its decision and reason, and its component
supports are left to fill (the earlier review recorded no claims).

Judgement structure: the item sheet holds the item decision (relevant / not_relevant / uncertain) and reason; the
item_claim_judgments sheet holds one row per (item, claim component) with support complete / partial / none
(evals/dev/claim_components.csv; a composite claim has several components and is complete when the top-k union
supports every component completely, see src/tariffagent/retrieval/claim_scoring.py).

Writes evals/dev/review_claims/:
  b1_review_sheet.csv / .md, b2_review_sheet.csv / .md   one row per review item; fill decision, reason,
                                                        reviewer_type
  b1_item_claim_judgments.csv, b2_...                    one row per (item, claim component); fill support
  item_queries.csv                                      which queries (and their claim ids) each item serves
  pools.csv                                             bookkeeping, not for the reviewer
  summary.json                                          counts: items, reused, new, per query
Refuses to overwrite a sheet that already holds a new decision.
"""

import csv
import hashlib
import json
import sys

from tariffagent.retrieval.corpus import REPO, build_chunks, documents
from tariffagent.retrieval.evaluate import citation_qrels
from tariffagent.retrieval.structure import CONFIG_V4, enrich

sys.path.insert(0, str(REPO / "scripts"))
from make_qrel_review_sheet import units  # noqa: E402

CONFIG_ID = CONFIG_V4["config_id"]
DEV = REPO / "evals" / "dev"
OUT = DEV / "review_claims"
B1_RUNS = REPO / "reports" / "retrieval" / "run_003_user_reviewed_qrels" / "bm25_dev_runs.csv"
B2_RUNS = REPO / "reports" / "retrieval" / "run_007_b2_heading_v4" / "b2_dev_runs.csv"
OLD = DEV / "review" / "qrel_review_sheet.csv"


def _read(path, bom=False):
    with path.open(encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write(path, rows, bom=False):
    with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def payload(system: str, **fields) -> dict:
    keys = ("source_id", "source_file", "physical_page", "printed_page", "chunk_id", "raw_text") if system == "B1" \
        else ("source_id", "source_file", "source_revision", "physical_page", "printed_page", "chunk_id",
              "context_text", "raw_text")
    return {k: fields[k] for k in keys}


payload_hash = lambda p: _h(p)


def claim_set_hash(claims: list[dict]) -> str:
    return _h(sorted((c["claim_text"], c["required"]) for c in claims))


def build():
    docs, chunks = documents(), build_chunks()
    b1 = {c.chunk_id: c for c in chunks}
    b2 = {b.parent_chunk_id: b for b in enrich(docs, chunks, config_id=CONFIG_ID)}
    queries = [q for q in _read(DEV / "queries.csv") if q["relevant_citation_ids"]]
    comps = {}
    for c in _read(DEV / "claim_components.csv"):
        comps.setdefault(c["claim_id"], []).append(c)
    claims = {}
    for c in _read(DEV / "claims.csv"):
        claims.setdefault(c["query_id"], []).append(c)
    matched = {r["pair_id"] for r in _read(DEV / "query_pair_checks.csv") if r["pair_mismatch"] == "false"}
    strict = citation_qrels(chunks)
    cand = {}
    for u in units():
        cand.setdefault(u["pair_id"], set()).add(u["chunk"].chunk_id)
    top = {"B1": {}, "B2": {}}
    for r in _read(B1_RUNS):
        top["B1"].setdefault(r["query_id"], []).append(r["chunk_id"])
    for r in _read(B2_RUNS):
        top["B2"].setdefault(r["query_id"], []).append(r["parent_chunk_id"])
    old = {(r["pair_id"], payload_hash(payload("B1", raw_text=r["chunk_text"], **r))): r for r in _read(OLD, bom=True)}

    items = {"B1": {}, "B2": {}}
    links, pools = [], []
    for q in queries:
        qid, pid = q["query_id"], q["pair_id"]
        intent = pid if pid in matched else qid
        qclaims = claims[qid]
        chash = claim_set_hash(qclaims)
        gold = set(q["relevant_citation_ids"].split(";"))
        required_links = {g for c in qclaims if c["required"] == "true" for g in c["gold_links"].split(";")}
        same_basis = required_links == gold
        cited = {c for cid in gold for c in strict[cid]}
        for system in ("B1", "B2"):
            parents = {}
            for parent in cand.get(pid, set()):
                parents.setdefault(parent, set()).add("candidate")
            for parent in top[system].get(qid, []):
                parents.setdefault(parent, set()).add("top10")
            for parent in cited:
                parents.setdefault(parent, set()).add("cited_location")
            for parent in sorted(parents, key=lambda p: (b1[p].source_file, b1[p].start)):
                c = b1[parent]
                if system == "B1":
                    p = payload("B1", source_id=c.source_id, source_file=c.source_file, physical_page=c.physical_page,
                                printed_page=c.printed_page, chunk_id=c.chunk_id, raw_text=c.text)
                else:
                    b = b2[parent]
                    p = payload("B2", source_id=b.source_id, source_file=b.source_file,
                                source_revision=b.source_revision, physical_page=b.physical_page,
                                printed_page=b.printed_page, chunk_id=b.chunk_id, context_text=b.context_text,
                                raw_text=b.raw_text)
                ph = payload_hash(p)
                key = (intent, chash, ph)
                item = items[system].get(key)
                if item is None:
                    item = {"intent": intent, "claim_set_sha256": chash, "payload_sha256": ph, "payload": p,
                            "queries": [], "claims": qclaims, "reuse": None}
                    prev = old.get((pid, ph)) if system == "B1" and pid in matched and same_basis else None
                    item["reuse"] = prev
                    items[system][key] = item
                item["queries"].append(q)
                links.append({"system": system, "query_id": qid, "intent": intent, "claim_set_sha256": chash,
                              "payload_sha256": ph, "claim_ids": ";".join(c["claim_id"] for c in qclaims)})
                pools.append({"system": system, "query_id": qid, "payload_sha256": ph, "parent_chunk_id": parent,
                              "unit_chunk_id": p["chunk_id"], **{s: int(s in parents[parent])
                                                                 for s in ("candidate", "top10", "cited_location")},
                              "config_id": CONFIG_ID if system == "B2" else "B1"})

    sheets, summary, claim_cells = {}, {}, {}
    b1_ids = {key: f"b1-{i:04d}" for i, key in enumerate(items["B1"], 1)}
    for system, by_key in items.items():
        rows = []
        for i, (key, it) in enumerate(by_key.items(), 1):
            prev = it["reuse"]
            qs = it["queries"]
            status = "new" if not prev else ("reused_needs_claim_mapping" if prev["user_decision"] == "relevant"
                                             else "reused")
            if system == "B2" and key in b1_ids:      # identical displayed payload, intent and claims: judged once
                status = f"same_as:{b1_ids[key]}"
            rows.append({"item_id": f"{system.lower()}-{i:04d}", "intent": it["intent"],
                         "query_ids": ";".join(q["query_id"] for q in qs),
                         "queries": " | ".join(f"{q['query_id']}: {q['text']}" for q in qs),
                         "claims": " | ".join(f"{c['claim_id'].split('.')[1]}{'' if c['required'] == 'true' else ' (not required)'}:"
                                              f" {c['claim_text']}" for c in it["claims"]),
                         **it["payload"], "claim_set_sha256": it["claim_set_sha256"],
                         "payload_sha256": it["payload_sha256"],
                         "decision": prev["user_decision"] if prev else "",
                         "reason": prev["user_reason"] if prev else "",
                         "reviewer_type": prev["reviewer_type"] if prev else "",
                         "reused_from": f"evals/dev/review/qrel_review_sheet.csv:{prev['unit_id']}" if prev else "",
                         "status": status})
        sheets[system] = rows
        cells = []
        for r, it in zip(rows, by_key.values()):
            if r["status"].startswith("same_as:"):
                continue                               # judged on the B1 item it equals
            for c in it["claims"]:
                for comp in comps[c["claim_id"]]:
                    prefilled = r["status"] == "reused" and r["decision"] in ("not_relevant", "uncertain")
                    cells.append({"item_id": r["item_id"], "claim": c["claim_id"].split(".")[1],
                                  "component": comp["component_id"].split(".")[-1],
                                  "required": c["required"], "composite": comp["composite"],
                                  "component_text": comp["component_text"],
                                  "support": "none" if prefilled else "",
                                  "status": "prefilled_none_from_reuse" if prefilled else "to_fill"})
        claim_cells[system] = cells
        per_q = {}
        for r in rows:
            for qid in r["query_ids"].split(";"):
                d = per_q.setdefault(qid, {"items": 0, "reused": 0, "reused_needs_claim_mapping": 0, "new": 0,
                                           "same_as_b1": 0})
                d["items"] += 1
                d["same_as_b1" if r["status"].startswith("same_as:") else r["status"]] += 1
        summary[system] = {"items": len(rows), **{s: sum(1 for r in rows if r["status"] == s)
                                                  for s in ("reused", "reused_needs_claim_mapping", "new")},
                           "same_as_b1": sum(1 for r in rows if r["status"].startswith("same_as:")),
                           "merged_matched_pair_items": sum(1 for r in rows if ";" in r["query_ids"]),
                           "query_units_before_dedup": sum(1 for l in links if l["system"] == system),
                           "claim_component_cells": len(claim_cells[system]),
                           "claim_component_cells_to_fill": sum(1 for c in claim_cells[system]
                                                                if c["status"] == "to_fill"),
                           "per_query": per_q}
    return sheets, claim_cells, links, pools, summary


def write_md(system: str, rows: list[dict], cells: list[dict]) -> str:
    by_item = {}
    for c in cells:
        by_item.setdefault(c["item_id"], []).append(c)
    shows = "raw text and B1 metadata" if system == "B1" else "extracted context, raw text and B2 metadata"
    out = [f"# {system} claim review items", "",
           f"Each item shows what {system} returns: {shows}. Decide relevant / not_relevant / uncertain with the v2 "
           "criterion (evals/dev/README.md), then for every claim component mark complete / partial / none in the "
           "item_claim_judgments sheet (relevant needs at least one complete or partial; not_relevant and uncertain "
           "mean none everywhere). A composite claim is complete when the top-k units together cover all its "
           "components. One item can serve both queries of a matched pair.", ""]
    for r in rows:
        meta = f"{r['source_id']}, page {r['physical_page'] or '-'} / {r['printed_page'] or '-'}"
        out += [f"## {r['item_id']} ({r['status']}): {meta}", "", f"- queries: {r['queries']}",
                f"- claims: {r['claims']}", ""]
        if system == "B2":
            out += [f"- context (extracted): {r['context_text']}", ""]
        out += [f"> {r['raw_text']}", "", f"decision: {r['decision'] or '____'} reason: {r['reason'] or '____'}", ""]
        out += [f"- {c['claim']}.{c['component']}{' (composite part)' if c['composite'] == 'true' else ''}"
                f"{'' if c['required'] == 'true' else ' (not required)'}: {c['component_text']} -> "
                f"{c['support'] or '____'}" for c in by_item.get(r["item_id"], [])]
        out += [""]
    return "\n".join(out)


def main() -> None:
    for name in ("b1_review_sheet.csv", "b2_review_sheet.csv"):
        path = OUT / name
        if path.exists() and any(r.get("decision") and r.get("status") == "new" for r in _read(path, bom=True)):
            sys.exit(f"{path} already has new decisions; not overwritten")
    sheets, claim_cells, links, pools, summary = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for old_name in ("b1_review_sheet.md", "b2_review_sheet.md"):
        (OUT / old_name).unlink(missing_ok=True)
    for system, rows in sheets.items():
        _write(OUT / f"{system.lower()}_review_sheet.csv", rows, bom=True)
        _write(OUT / f"{system.lower()}_item_claim_judgments.csv", claim_cells[system], bom=True)
        (OUT / f"{system.lower()}_review_sheet.md").write_text(write_md(system, rows, claim_cells[system]) + "\n",
                                                                encoding="utf-8", newline="\n")
    _write(OUT / "item_queries.csv", links)
    _write(OUT / "pools.csv", pools)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                                      newline="\n")
    print(json.dumps({s: {k: v for k, v in d.items() if k != "per_query"} for s, d in summary.items()}))


if __name__ == "__main__":
    main()
