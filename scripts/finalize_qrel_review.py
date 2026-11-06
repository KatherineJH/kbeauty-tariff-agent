"""After the review sheets are filled: agreement report, retrieval_qrels v2 and query time conditions.

    uv run python scripts/finalize_qrel_review.py

Reads evals/dev/review/qrel_review_sheet.csv (user_decision relevant / not_relevant / uncertain, user_reason,
reviewer_type human / human_assisted / second_model_review) and evals/dev/review/query_time_sheet.csv (time_condition dated /
time_invariant / underspecified). If evals/dev/review/claude_review.csv exists (Claude's independent reading of the
same units under the same criterion, sealed before the user's review), it reports agreement against it; likewise
claude_time_review.csv for the time conditions.

Writes:
  evals/dev/retrieval_qrels_v2.csv        pair_id, chunk_id, citation_ids, decision, reason, reviewer_type
  evals/dev/query_time_conditions.csv     query_id, pair_id, time_condition, reason
  evals/dev/review/agreement.md           counts; with claude_review.csv: raw agreement, Cohen's kappa, confusion
  evals/dev/review/disagreements.csv      units where the two readings differ, with both reasons
The sheet's decisions are final in v2. Stops if anything is undecided or unknown, if reviewer_type is mixed, and
never overwrites an existing v2 file.
"""

import csv
import sys
from collections import Counter

from tariffagent.retrieval.corpus import REPO

DEV = REPO / "evals" / "dev"
REVIEW = DEV / "review"
SHEET = REVIEW / "qrel_review_sheet.csv"
TIME_SHEET = REVIEW / "query_time_sheet.csv"
SECOND = REVIEW / "claude_review.csv"
SECOND_TIME = REVIEW / "claude_time_review.csv"
V2 = DEV / "retrieval_qrels_v2.csv"
CONDITIONS = DEV / "query_time_conditions.csv"
VALUES = ("relevant", "not_relevant", "uncertain")
TIME_VALUES = ("dated", "time_invariant", "underspecified")
REVIEWER_TYPES = ("human", "human_assisted", "second_model_review")
KIND_NOTE = {"human": "",
             "human_assisted": " (a person decided every row, reading Claude's neutral Korean translations of the "
                               "queries and chunks; the translation is a possible influence)",
             "second_model_review": " (a model, not a human review)"}


def _read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[v] * cb[v] for v in VALUES) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main() -> None:
    if V2.exists():
        sys.exit(f"{V2} exists; a new review is a new version")
    sheet, times = _read(SHEET), _read(TIME_SHEET)
    bad = [r["unit_id"] for r in sheet if r["user_decision"].strip() not in VALUES]
    bad += [r["query_id"] for r in times if r["time_condition"].strip() not in TIME_VALUES]
    if bad:
        sys.exit(f"undecided or unknown value in {', '.join(bad)}")
    kinds = {r["reviewer_type"].strip() for r in sheet}
    if len(kinds) != 1 or not kinds <= set(REVIEWER_TYPES):
        sys.exit(f"reviewer_type must be one of {REVIEWER_TYPES} on every row, got {sorted(kinds)}")
    kind = kinds.pop()

    users = {r["unit_id"]: r["user_decision"].strip() for r in sheet}
    lines = ["# Qrel review agreement", "",
             f"Reviewer of the sheet: {kind}" + KIND_NOTE[kind] + ".",
             f"Units (query pair x chunk): {len(sheet)}. Decisions: "
             + ", ".join(f"{v} {sum(d == v for d in users.values())}" for v in VALUES) + ".",
             "Query time conditions: "
             + ", ".join(f"{v} {sum(r['time_condition'].strip() == v for r in times)}" for v in TIME_VALUES) + ".", ""]
    if SECOND.exists():
        second = {r["unit_id"]: r for r in _read(SECOND)}
        if set(second) != set(users):
            sys.exit("claude_review.csv does not cover the same units")
        pairs = [(users[u], second[u]["decision"]) for u in sorted(users)]
        decided = [(a, b) for a, b in pairs if "uncertain" not in (a, b)]
        conf = Counter(pairs)
        lines += [f"Against Claude's sealed reading (claude_review.csv), same units and criterion:", "",
                  f"- Raw agreement: {sum(a == b for a, b in pairs)}/{len(pairs)} = "
                  f"{sum(a == b for a, b in pairs) / len(pairs):.3f}",
                  f"- Raw agreement where neither said uncertain: {sum(a == b for a, b in decided)}/{len(decided)}"
                  + (f" = {sum(a == b for a, b in decided) / len(decided):.3f}" if decided else ""),
                  f"- Cohen's kappa: {kappa(pairs):.3f} (one corpus, few units: a description, not an estimate)", "",
                  "| sheet \\ Claude | relevant | not_relevant | uncertain |", "|---|---|---|---|"]
        lines += [f"| {u} | " + " | ".join(str(conf[(u, c)]) for c in VALUES) + " |" for u in VALUES]
        dis = [{"unit_id": u, "pair_id": r["pair_id"], "source_id": r["source_id"], "chunk_id": r["chunk_id"],
                "sheet_decision": users[u], "sheet_reason": r["user_reason"],
                "claude_decision": second[u]["decision"], "claude_reason": second[u]["reason"]}
               for u, r in ((r["unit_id"], r) for r in sheet) if users[u] != second[u]["decision"]]
        lines += ["", f"Disagreements: {len(dis)} (disagreements.csv). The sheet's decision is final in v2."]
        if dis:
            _write(REVIEW / "disagreements.csv", dis)
    else:
        lines += ["No second reading (claude_review.csv); no agreement computed."]
    if SECOND_TIME.exists():
        theirs = {r["query_id"]: r["time_condition"] for r in _read(SECOND_TIME)}
        mine = {r["query_id"]: r["time_condition"].strip() for r in times}
        same = sum(mine[q] == theirs.get(q) for q in mine)
        lines += ["", f"Query time conditions, agreement with claude_time_review.csv: {same}/{len(mine)}; differing: "
                  + (", ".join(f"{q} ({mine[q]} vs {theirs.get(q)})" for q in sorted(mine) if mine[q] != theirs.get(q))
                     or "none")]
    (REVIEW / "agreement.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    _write(V2, [{"pair_id": r["pair_id"], "chunk_id": r["chunk_id"], "citation_ids": r["citation_ids"],
                 "decision": r["user_decision"].strip(), "reason": r["user_reason"].strip(), "reviewer_type": kind}
                for r in sheet])
    _write(CONDITIONS, [{"query_id": r["query_id"], "pair_id": r["pair_id"],
                         "time_condition": r["time_condition"].strip(), "reason": r["reason"].strip()} for r in times])
    print("\n".join(lines))


if __name__ == "__main__":
    main()
