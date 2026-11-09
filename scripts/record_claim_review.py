"""Record the claim review in two stages and finalize it. The review sheets themselves stay empty.

    uv run python scripts/record_claim_review.py status
    uv run python scripts/record_claim_review.py next-stage1 [N]
    uv run python scripts/record_claim_review.py decide <b1|b2> <item_id> <relevant|not_relevant|uncertain> "<reason>"
    uv run python scripts/record_claim_review.py next-stage2 [N]
    uv run python scripts/record_claim_review.py support <b1|b2> <item_id> <c1.e1>=<complete|partial|none> ...
    uv run python scripts/record_claim_review.py finalize

Stage 1 asks a decision only for new items (484). Stage 2 asks component levels only for relevant items: the new
items decided relevant and the reused relevant items whose claims were never mapped. not_relevant and uncertain
items, and components a relevant item does not name, become none at finalize. Answers are appended to
evals/dev/review_claims/responses/ (item_decisions.csv, component_supports.csv); finalize writes
evals/dev/review_claims/final/ and refuses incomplete or inconsistent input (src/tariffagent/retrieval/claim_review.py).
"""

import csv
import sys
from pathlib import Path

from tariffagent.retrieval.claim_review import (DECISION_HELP_KO, DECISIONS, LEVEL_HELP_KO, LEVELS, Item,
                                                ReviewInputError, finalize, stage2_items)
from tariffagent.retrieval.corpus import REPO

OUT = REPO / "evals" / "dev" / "review_claims"
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


def load(system: str):
    sheet = _read(OUT / f"{system}_review_sheet.csv", bom=True)
    items = [Item(r["item_id"], r["status"], r["decision"], r["reason"]) for r in sheet]
    comps: dict[str, list[str]] = {}
    texts: dict[tuple[str, str], str] = {}
    for c in _read(OUT / f"{system}_item_claim_judgments.csv", bom=True):
        key = f"{c['claim']}.{c['component']}"
        comps.setdefault(c["item_id"], []).append(key)
        texts[(c["item_id"], key)] = c["component_text"] + ("" if c["required"] == "true" else " (not required)")
    decisions = {r["item_id"]: (r["decision"], r["reason"]) for r in _read(DECISIONS_CSV) if r["system"] == system}
    supports: dict[str, dict[str, str]] = {}
    for r in _read(SUPPORTS_CSV):
        if r["system"] == system:
            supports.setdefault(r["item_id"], {})[r["component"]] = r["support"]
    return sheet, items, comps, texts, decisions, supports


def status() -> None:
    for system in SYSTEMS:
        _, items, _, _, decisions, supports = load(system)
        new = [it for it in items if it.status == "new"]
        rel = stage2_items(items, decisions)
        print(f"{system}: stage 1 {sum(1 for it in new if it.item_id in decisions)}/{len(new)} decided; "
              f"stage 2 {sum(1 for i in rel if i in supports)}/{len(rel)} relevant items mapped "
              f"(reused relevant: {sum(1 for it in items if it.status == 'reused_needs_claim_mapping')})")


def next_stage1(n: int) -> None:
    print("판정 기준:", "; ".join(f"{k} = {v}" for k, v in DECISION_HELP_KO.items()))
    shown = 0
    for system in SYSTEMS:
        sheet, _, _, _, decisions, _ = load(system)
        for r in sheet:
            if r["status"] == "new" and r["item_id"] not in decisions and shown < n:
                shown += 1
                print(f"\n[{system} {r['item_id']}] queries: {r['queries']}\n  claims: {r['claims']}\n"
                      f"  source: {r['source_id']} page {r['physical_page'] or '-'} / {r['printed_page'] or '-'}")
                if system == "b2":
                    print(f"  context: {r['context_text']}")
                print(f"  text: {r['raw_text']}")


def next_stage2(n: int) -> None:
    print("수준 설명:", "; ".join(f"{k} = {v}" for k, v in LEVEL_HELP_KO.items()))
    shown = 0
    for system in SYSTEMS:
        sheet, items, comps, texts, decisions, supports = load(system)
        rows = {r["item_id"]: r for r in sheet}
        for iid in stage2_items(items, decisions):
            if iid in supports or shown >= n:
                continue
            shown += 1
            r = rows[iid]
            print(f"\n[{system} {iid}] queries: {r['queries']}\n  text: {r['raw_text']}")
            if system == "b2":
                print(f"  context: {r['context_text']}")
            for k in comps[iid]:
                print(f"  {k}: {texts[(iid, k)]}")


def decide(system: str, item_id: str, decision: str, reason: str) -> None:
    _, items, _, _, decisions, _ = load(system)
    it = {i.item_id: i for i in items}.get(item_id)
    if it is None or it.status != "new":
        sys.exit(f"{system} {item_id}: not a new item; reused items are not asked again")
    if decision not in DECISIONS:
        sys.exit(f"decision must be one of {DECISIONS}")
    if item_id in decisions:
        sys.exit(f"{system} {item_id}: already decided")
    _append(DECISIONS_CSV, {"system": system, "item_id": item_id, "decision": decision, "reason": reason,
                            "reviewer_type": REVIEWER_TYPE})


def support(system: str, item_id: str, pairs: list[str]) -> None:
    _, items, comps, _, decisions, supports = load(system)
    if item_id not in stage2_items(items, decisions):
        sys.exit(f"{system} {item_id}: not a relevant item; component levels are only asked for relevant items")
    if item_id in supports:
        sys.exit(f"{system} {item_id}: already mapped")
    given = dict(p.split("=", 1) for p in pairs)
    if set(given) - set(comps[item_id]) or set(given.values()) - set(LEVELS):
        sys.exit(f"components must be among {comps[item_id]} and levels among {LEVELS}")
    if not any(v in ("complete", "partial") for v in given.values()):
        sys.exit("a relevant item needs at least one complete or partial component")
    for k, v in given.items():
        _append(SUPPORTS_CSV, {"system": system, "item_id": item_id, "component": k, "support": v})


def finalize_all() -> None:
    for system in SYSTEMS:
        _, items, comps, _, decisions, supports = load(system)
        try:
            final_items, final_cells = finalize(items, comps, decisions, supports)
        except ReviewInputError as e:
            sys.exit(f"{system}: {e}")
        _write(FINAL / f"{system}_items.csv", final_items)
        _write(FINAL / f"{system}_item_claim_judgments.csv", final_cells)
        print(f"{system}: {len(final_items)} items, {len(final_cells)} component rows finalized")


def main(argv: list[str]) -> None:
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    if cmd == "status":
        status()
    elif cmd == "next-stage1":
        next_stage1(int(args[0]) if args else 5)
    elif cmd == "next-stage2":
        next_stage2(int(args[0]) if args else 5)
    elif cmd == "decide" and len(args) == 4:
        decide(*args)
    elif cmd == "support" and len(args) >= 3:
        support(args[0], args[1], args[2:])
    elif cmd == "finalize":
        finalize_all()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
