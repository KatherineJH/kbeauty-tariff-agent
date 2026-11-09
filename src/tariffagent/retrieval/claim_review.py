"""Two-stage input for the claim review, the sealed review queue, and the finalize step that fills the rest.

The review sheets in evals/dev/review_claims/ stay empty; answers are recorded in responses/ and combined here.

Stage 1  every new item: decision relevant / not_relevant / uncertain and a non-empty reason. Reused items are not
         asked again (their earlier reason must exist).
Stage 2  only items whose decision is relevant (new relevant items and the reused relevant items that still need
         their claims): for the components of the item's claims, complete / partial / none. Components the reviewer
         does not name are none; at least one must be complete or partial.
Finalize not_relevant and uncertain items get none on every component without asking; relevant items get the levels
         given in stage 2 and none elsewhere. It refuses: a new item without a decision or with an empty reason, a
         reused item without its reason, a decision recorded for a reused item, a stage 2 answer for an item that is
         not relevant, a relevant item with no complete or partial component, an unknown component or level.
Queue    B1 and B2 items are reviewed in one queue, shuffled with a fixed seed, under opaque review ids; the mapping
         from review id to (system, item id) is a separate file whose hash is recorded (build_queue).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

DECISIONS = ("relevant", "not_relevant", "uncertain")
LEVELS = ("complete", "partial", "none")
QUEUE_SEED = "claim-review-queue-2026-11-09"
# the explanations shown to the reviewer (fixed wording)
LEVEL_HELP_KO = {
    "complete": "이 청크만으로 해당 근거 요소를 명확히 확인할 수 있음",
    "partial": "관련 정보는 있지만 해당 근거 요소를 완전히 확정하기에는 부족함",
    "none": "해당 근거 요소를 지원하지 않음",
}
DECISION_HELP_KO = {
    "relevant": "반환 단위만으로 질문의 claim 하나 이상을 완전히 또는 부분적으로 뒷받침함",
    "not_relevant": "국가·관세 종류·법적 범위가 다르거나 질문에 답하지 못함",
    "uncertain": "판단에 필요한 heading·기간·주 문맥이 반환 단위에 없어 판단할 수 없음",
}
# how Claude assists the reviewer in chat (fixed)
TRANSLATION_RULES_KO = (
    "1. 원문 청크의 한국어 번역, 질문, claim만 설명한다.",
    "2. 원문에 없는 주어·heading·연도·앞 문장을 복원해 번역에 넣지 않는다. 잘린 곳은 [끊김]으로 표시한다.",
    "3. 불가피한 보충 설명은 '청크 밖 설명'으로 분리하고, relevance 판단에는 쓰지 않는다.",
    "4. Claude가 판정을 제안하면 사용자가 '동의'하거나 직접 고친다. 기록은 사용자의 최종 답을 그대로 쓴다.",
    "5. reviewer_type은 human_assisted로 기록한다.",
    "6. 시스템 이름(B1/B2)과 내부 item id는 보여주지 않고 review id만 쓴다.",
)


class ReviewInputError(ValueError):
    pass


@dataclass(frozen=True)
class Item:
    item_id: str
    status: str            # new / reused / reused_needs_claim_mapping / same_as:<id>
    decision: str = ""     # prefilled for reused items
    reason: str = ""


def build_queue(items_by_system: dict[str, list[Item]], seed: str = QUEUE_SEED) -> list[dict]:
    """One queue for both systems: the new items (stage 1) and the reused relevant items (stage 2 only), ordered
    by sha256(seed|system|item_id), each with an opaque review id. Deterministic for a given seed."""
    rows = []
    for system, items in items_by_system.items():
        for it in items:
            if it.status not in ("new", "reused_needs_claim_mapping"):
                continue
            key = hashlib.sha256(f"{seed}|order|{system}|{it.item_id}".encode()).hexdigest()
            # digits only, so an id never reads like a system name ("b1", "b2")
            rid = "R-%010d" % (int(hashlib.sha256(f"{seed}|id|{system}|{it.item_id}".encode()).hexdigest(), 16)
                               % 10 ** 10)
            rows.append({"order_key": key, "review_id": rid, "system": system, "item_id": it.item_id,
                         "stage": "stage1" if it.status == "new" else "stage2_only"})
    rows.sort(key=lambda r: r["order_key"])
    if len({r["review_id"] for r in rows}) != len(rows):
        raise ReviewInputError("review id collision; change the seed")
    for i, r in enumerate(rows, 1):
        r["position"] = i
    return rows


def stage2_items(items: list[Item], decisions: dict[str, tuple[str, str]]) -> list[str]:
    """Items that need component levels: relevant by the stage 1 decision or by reuse."""
    out = []
    for it in items:
        d = decisions.get(it.item_id, (it.decision, ""))[0] if it.status == "new" else it.decision
        if d == "relevant":
            out.append(it.item_id)
    return out


def check_reason(reason: str) -> str:
    if not reason or not reason.strip():
        raise ReviewInputError("a reason is required")
    return reason.strip()


def finalize(items: list[Item], components: dict[str, list[str]], decisions: dict[str, tuple[str, str]],
             supports: dict[str, dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """items: sheet rows; components: item_id -> its component keys ('c1.e1', ...);
    decisions: stage 1 answers, item_id -> (decision, reason); supports: stage 2 answers, item_id -> {key: level}.
    Returns (final item rows, final item-component rows)."""
    by_id = {it.item_id: it for it in items}
    for iid in decisions:
        if iid not in by_id:
            raise ReviewInputError(f"{iid}: unknown item")
        if by_id[iid].status != "new":
            raise ReviewInputError(f"{iid}: reused or shared item, its decision is not asked again")
    for iid in supports:
        if iid not in by_id:
            raise ReviewInputError(f"{iid}: unknown item")
    final_items, final_cells = [], []
    for it in items:
        if it.status.startswith("same_as:"):
            final_items.append({"item_id": it.item_id, "decision": "", "reason": "", "source": it.status})
            continue
        if it.status == "new":
            if it.item_id not in decisions:
                raise ReviewInputError(f"{it.item_id}: no stage 1 decision")
            decision, reason = decisions[it.item_id]
            source = "stage1"
        else:
            decision, reason, source = it.decision, it.reason, "reused"
        try:
            reason = check_reason(reason)
        except ReviewInputError:
            raise ReviewInputError(f"{it.item_id}: a reason is required") from None
        if decision not in DECISIONS:
            raise ReviewInputError(f"{it.item_id}: decision {decision!r}")
        given = supports.get(it.item_id, {})
        keys = components[it.item_id]
        unknown = set(given) - set(keys)
        if unknown:
            raise ReviewInputError(f"{it.item_id}: components {sorted(unknown)} are not this item's")
        bad = {v for v in given.values() if v not in LEVELS}
        if bad:
            raise ReviewInputError(f"{it.item_id}: levels {sorted(bad)}")
        if decision != "relevant":
            if given:
                raise ReviewInputError(f"{it.item_id}: {decision} item, component levels are not asked")
            levels = {k: "none" for k in keys}
            fill = "auto_none"
        else:
            levels = {k: given.get(k, "none") for k in keys}
            if not any(v in ("complete", "partial") for v in levels.values()):
                raise ReviewInputError(f"{it.item_id}: relevant item with no complete or partial component")
            fill = "stage2"
        final_items.append({"item_id": it.item_id, "decision": decision, "reason": reason, "source": source})
        for k in keys:
            final_cells.append({"item_id": it.item_id, "claim": k.split(".")[0], "component": k.split(".")[1],
                                "support": levels[k],
                                "filled_by": fill if (fill == "auto_none" or k in given) else "default_none"})
    return final_items, final_cells
