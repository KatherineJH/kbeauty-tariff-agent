"""Record the claim review in two stages over one sealed, mixed queue, and finalize it into a new version.

    uv run python scripts/record_claim_review.py build-queue          (once; refuses if the queue exists)
    uv run python scripts/record_claim_review.py status
    uv run python scripts/record_claim_review.py next-stage1 [N]
    uv run python scripts/record_claim_review.py decide <review_id> <relevant|not_relevant|uncertain> "<reason>"
    uv run python scripts/record_claim_review.py next-stage2 [N]
    uv run python scripts/record_claim_review.py support <review_id> <c1.e1>=<complete|partial|none> ...
    uv run python scripts/record_claim_review.py finalize <version>   (refuses if final/<version>/ exists)

Queue: B1 and B2 items in one order (seed QUEUE_SEED in src/tariffagent/retrieval/claim_review.py) under opaque
review ids. queue.csv (review_id, position, stage) is what the session walks through; queue_map.csv (review_id ->
system, item_id) is internal, never shown; queue_manifest.json records both hashes. The reviewer sees review ids, the
queries, claims, source metadata, the raw text and, for B2 units, the extracted context; never a system name or an
internal item id. The context and the B2-only revision field can still reveal the system (documented limit).

Stage 1 asks a decision and a non-empty reason only for new items (484). Stage 2 asks component levels only for
relevant items: the new items decided relevant and the 6 reused relevant items. not_relevant and uncertain items and
components a relevant item does not name become none at finalize. Answers are appended to
evals/dev/review_claims/responses/ by review id; finalize writes evals/dev/review_claims/final/<version>/ and stops if
that directory exists. A corrected review is a new version; nothing is overwritten.
"""

import csv
import hashlib
import json
import sys
from pathlib import Path

from tariffagent.retrieval.claim_review import (DECISION_HELP_KO, DECISIONS, LEVEL_HELP_KO, LEVELS, QUEUE_SEED,
                                                TRANSLATION_RULES_KO, Item, ReviewInputError, build_queue,
                                                check_reason, finalize, stage2_items)
from tariffagent.retrieval.corpus import REPO

OUT = REPO / "evals" / "dev" / "review_claims"
QUEUE_DIR = OUT / "queue"
QUEUE_CSV = QUEUE_DIR / "queue.csv"
QUEUE_MAP = QUEUE_DIR / "queue_map.csv"
QUEUE_MANIFEST = QUEUE_DIR / "queue_manifest.json"
RESP = OUT / "responses"
DECISIONS_CSV = RESP / "item_decisions.csv"
SUPPORTS_CSV = RESP / "component_supports.csv"
FINAL = OUT / "final"
SYSTEMS = ("b1", "b2")
REVIEWER_TYPE = "human_assisted"


def _read(path: Path, bom: bool = False) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row), lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow(row)


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_sheet(system: str):
    sheet = _read(OUT / f"{system}_review_sheet.csv", bom=True)
    items = [Item(r["item_id"], r["status"], r["decision"], r["reason"]) for r in sheet]
    comps: dict[str, list[str]] = {}
    texts: dict[tuple[str, str], str] = {}
    for c in _read(OUT / f"{system}_item_claim_judgments.csv", bom=True):
        key = f"{c['claim']}.{c['component']}"
        comps.setdefault(c["item_id"], []).append(key)
        texts[(c["item_id"], key)] = c["component_text"] + ("" if c["required"] == "true" else " (not required)")
    return sheet, items, comps, texts


def load_queue() -> tuple[list[dict], dict[str, tuple[str, str]]]:
    m = json.loads(QUEUE_MANIFEST.read_text("utf-8"))
    if (_sha(QUEUE_CSV), _sha(QUEUE_MAP)) != (m["queue_sha256"], m["queue_map_sha256"]):
        sys.exit("the sealed queue files do not match their manifest")
    mapping = {r["review_id"]: (r["system"], r["item_id"]) for r in _read(QUEUE_MAP)}
    return _read(QUEUE_CSV), mapping


def responses(mapping):
    """Answers by (system, item id)."""
    decisions = {s: {} for s in SYSTEMS}
    supports = {s: {} for s in SYSTEMS}
    for r in _read(DECISIONS_CSV):
        s, iid = mapping[r["review_id"]]
        decisions[s][iid] = (r["decision"], r["reason"])
    for r in _read(SUPPORTS_CSV):
        s, iid = mapping[r["review_id"]]
        supports[s].setdefault(iid, {})[r["component"]] = r["support"]
    return decisions, supports


def build_queue_files() -> None:
    if QUEUE_DIR.exists() and any(QUEUE_DIR.iterdir()):
        sys.exit(f"{QUEUE_DIR} exists; the queue is sealed and is not rebuilt")
    rows = build_queue({s: load_sheet(s)[1] for s in SYSTEMS})
    _write(QUEUE_CSV, [{"review_id": r["review_id"], "position": r["position"], "stage": r["stage"]} for r in rows])
    _write(QUEUE_MAP, [{"review_id": r["review_id"], "system": r["system"], "item_id": r["item_id"]} for r in rows])
    QUEUE_MANIFEST.write_text(json.dumps({"seed": QUEUE_SEED, "rows": len(rows), "queue_sha256": _sha(QUEUE_CSV),
                                          "queue_map_sha256": _sha(QUEUE_MAP)}, indent=2) + "\n",
                              encoding="utf-8", newline="\n")
    print(f"{len(rows)} queue rows")


def _show(review_id, row, system, comps=None, texts=None, iid=None):
    print(f"\n[{review_id}] queries: {row['queries']}\n  claims: {row['claims']}\n"
          f"  source: {row['source_id']} page {row['physical_page'] or '-'} / {row['printed_page'] or '-'}")
    if row.get("context_text"):
        print(f"  context (extracted): {row['context_text']}")
    print(f"  text: {row['raw_text']}")
    for k in comps or []:
        print(f"  {k}: {texts[(iid, k)]}")


def status() -> None:
    queue, mapping = load_queue()
    decisions, supports = responses(mapping)
    s1 = [q for q in queue if q["stage"] == "stage1"]
    done1 = sum(1 for q in s1 if mapping[q["review_id"]][1] in decisions[mapping[q["review_id"]][0]])
    rel = [(s, i) for s in SYSTEMS for i in stage2_items(load_sheet(s)[1], decisions[s])]
    print(f"stage 1: {done1}/{len(s1)} decided; stage 2: {sum(1 for s, i in rel if i in supports[s])}/{len(rel)} "
          f"relevant items mapped so far")


def next_stage1(n: int) -> None:
    queue, mapping = load_queue()
    decisions, _ = responses(mapping)
    print("번역 보조 규칙:", " ".join(TRANSLATION_RULES_KO))
    print("판정 기준:", "; ".join(f"{k} = {v}" for k, v in DECISION_HELP_KO.items()))
    sheets = {s: {r["item_id"]: r for r in load_sheet(s)[0]} for s in SYSTEMS}
    shown = 0
    for q in queue:
        s, iid = mapping[q["review_id"]]
        if q["stage"] == "stage1" and iid not in decisions[s] and shown < n:
            shown += 1
            _show(q["review_id"], sheets[s][iid], s)


def next_stage2(n: int) -> None:
    queue, mapping = load_queue()
    decisions, supports = responses(mapping)
    print("수준 설명:", "; ".join(f"{k} = {v}" for k, v in LEVEL_HELP_KO.items()))
    loaded = {s: load_sheet(s) for s in SYSTEMS}
    relevant = {(s, i) for s in SYSTEMS for i in stage2_items(loaded[s][1], decisions[s])}
    shown = 0
    for q in queue:
        s, iid = mapping[q["review_id"]]
        if (s, iid) in relevant and iid not in supports[s] and shown < n:
            shown += 1
            sheet, _, comps, texts = loaded[s]
            _show(q["review_id"], {r["item_id"]: r for r in sheet}[iid], s, comps[iid], texts, iid)


def decide(review_id: str, decision: str, reason: str) -> None:
    queue, mapping = load_queue()
    stage = {q["review_id"]: q["stage"] for q in queue}.get(review_id)
    if stage != "stage1":
        sys.exit(f"{review_id}: not a stage 1 item; reused items are not asked again")
    if decision not in DECISIONS:
        sys.exit(f"decision must be one of {DECISIONS}")
    try:
        reason = check_reason(reason)
    except ReviewInputError as e:
        sys.exit(f"{review_id}: {e}")
    s, iid = mapping[review_id]
    if iid in responses(mapping)[0][s]:
        sys.exit(f"{review_id}: already decided")
    _append(DECISIONS_CSV, {"review_id": review_id, "decision": decision, "reason": reason,
                            "reviewer_type": REVIEWER_TYPE})


def support(review_id: str, pairs: list[str]) -> None:
    queue, mapping = load_queue()
    if review_id not in mapping:
        sys.exit(f"{review_id}: unknown review id")
    s, iid = mapping[review_id]
    decisions, supports = responses(mapping)
    _, items, comps, _ = load_sheet(s)
    if iid not in stage2_items(items, decisions[s]):
        sys.exit(f"{review_id}: not a relevant item; component levels are only asked for relevant items")
    if iid in supports[s]:
        sys.exit(f"{review_id}: already mapped")
    given = dict(p.split("=", 1) for p in pairs)
    if set(given) - set(comps[iid]) or set(given.values()) - set(LEVELS):
        sys.exit(f"components must be among {comps[iid]} and levels among {LEVELS}")
    if not any(v in ("complete", "partial") for v in given.values()):
        sys.exit("a relevant item needs at least one complete or partial component")
    for k, v in given.items():
        _append(SUPPORTS_CSV, {"review_id": review_id, "component": k, "support": v})


def finalize_all(version: str) -> None:
    if not version or "/" in version or "\\" in version or version.startswith("."):
        sys.exit("finalize needs a plain version name, e.g. v1")
    target = FINAL / version
    if target.exists():
        sys.exit(f"{target} exists; finalized results are never overwritten, use a new version")
    _, mapping = load_queue()
    decisions, supports = responses(mapping)
    out = {}
    for s in SYSTEMS:
        _, items, comps, _ = load_sheet(s)
        try:
            out[s] = finalize(items, comps, decisions[s], supports[s])
        except ReviewInputError as e:
            sys.exit(f"{s}: {e}")
    for s, (final_items, final_cells) in out.items():
        _write(target / f"{s}_items.csv", final_items)
        _write(target / f"{s}_item_claim_judgments.csv", final_cells)
        print(f"{s}: {len(final_items)} items, {len(final_cells)} component rows finalized into {target}")


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    if cmd == "build-queue":
        build_queue_files()
    elif cmd == "status":
        status()
    elif cmd == "next-stage1":
        next_stage1(int(args[0]) if args else 5)
    elif cmd == "next-stage2":
        next_stage2(int(args[0]) if args else 5)
    elif cmd == "decide" and len(args) == 3:
        decide(*args)
    elif cmd == "support" and len(args) >= 2:
        support(args[0], args[1:])
    elif cmd == "finalize" and len(args) == 1:
        finalize_all(args[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
