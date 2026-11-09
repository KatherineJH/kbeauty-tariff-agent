"""Two-stage claim review input: automatic none, refused input, composite claims across items, empty sheets."""

import hashlib

import pytest

from tariffagent.retrieval.claim_review import (LEVEL_HELP_KO, Item, ReviewInputError, finalize, stage2_items)
from tariffagent.retrieval.claim_scoring import Judgement, score_query
from tariffagent.retrieval.corpus import REPO

COMPS = {"n1": ["c1.e1", "c2.e1"], "r1": ["c1.e1", "c2.e1"], "u1": ["c1.e1", "c2.e1"], "old": ["c1.e1", "c2.e1"]}


def _items(*specs):
    return [Item(*s) for s in specs]


def _cells(cells, item):
    return {f"{c['claim']}.{c['component']}": (c["support"], c["filled_by"]) for c in cells if c["item_id"] == item}


def test_not_relevant_with_no_component_input_becomes_all_none():
    items, cells = finalize(_items(("n1", "new")), COMPS, {"n1": ("not_relevant", "other heading")}, {})
    assert items[0]["decision"] == "not_relevant"
    assert _cells(cells, "n1") == {"c1.e1": ("none", "auto_none"), "c2.e1": ("none", "auto_none")}


def test_uncertain_with_no_component_input_becomes_all_none():
    _, cells = finalize(_items(("u1", "new")), COMPS, {"u1": ("uncertain", "heading missing")}, {})
    assert _cells(cells, "u1") == {"c1.e1": ("none", "auto_none"), "c2.e1": ("none", "auto_none")}


@pytest.mark.parametrize("given", [{}, {"c1.e1": "none"}, {"c1.e1": "none", "c2.e1": "none"}])
def test_relevant_without_any_supported_component_is_refused(given):
    with pytest.raises(ReviewInputError):
        finalize(_items(("r1", "new")), COMPS, {"r1": ("relevant", "x")}, {"r1": given} if given else {})


def test_relevant_with_some_components_named_gets_none_for_the_rest():
    _, cells = finalize(_items(("r1", "new")), COMPS, {"r1": ("relevant", "x")}, {"r1": {"c1.e1": "complete"}})
    assert _cells(cells, "r1") == {"c1.e1": ("complete", "stage2"), "c2.e1": ("none", "default_none")}


def test_reused_relevant_item_needs_only_its_components():
    items = _items(("old", "reused_needs_claim_mapping", "relevant", "earlier reason"))
    assert stage2_items(items, {}) == ["old"]
    with pytest.raises(ReviewInputError):                         # no mapping yet
        finalize(items, COMPS, {}, {})
    with pytest.raises(ReviewInputError):                         # its decision is not asked again
        finalize(items, COMPS, {"old": ("relevant", "again")}, {"old": {"c1.e1": "partial"}})
    final, cells = finalize(items, COMPS, {}, {"old": {"c1.e1": "partial"}})
    assert final[0]["source"] == "reused" and final[0]["reason"] == "earlier reason"
    assert _cells(cells, "old")["c1.e1"] == ("partial", "stage2")


@pytest.mark.parametrize("decisions,supports", [
    ({}, {}),                                                         # new item not decided
    ({"n1": ("not_relevant", "")}, {"n1": {"c1.e1": "none"}}),        # stage 2 answer for a non-relevant item
    ({"n1": ("relevant", "")}, {"n1": {"c9.e1": "complete"}}),        # unknown component
    ({"n1": ("relevant", "")}, {"n1": {"c1.e1": "mostly"}}),          # unknown level
    ({"n1": ("maybe", "")}, {}),                                      # unknown decision
    ({"zz": ("relevant", "")}, {}),                                   # unknown item
])
def test_inconsistent_input_is_refused(decisions, supports):
    with pytest.raises(ReviewInputError):
        finalize(_items(("n1", "new")), COMPS, decisions, supports)


def test_composite_claim_completed_by_two_items_in_the_top_k():
    comps = {"a": ["c1.e1", "c1.e2"], "b": ["c1.e1", "c1.e2"], "c": ["c1.e1", "c1.e2"]}
    items = _items(("a", "new"), ("b", "new"), ("c", "new"))
    _, cells = finalize(items, comps, {"a": ("relevant", ""), "b": ("not_relevant", ""), "c": ("relevant", "")},
                        {"a": {"c1.e1": "complete"}, "c": {"c1.e2": "complete"}})
    judged = {}
    for it in ("a", "b", "c"):
        levels = {f"q.{k}": v[0] for k, v in _cells(cells, it).items()}
        decision = "relevant" if any(v != "none" for v in levels.values()) else "not_relevant"
        judged[it] = Judgement(decision, levels)
    claims = {"q.c1": ["q.c1.e1", "q.c1.e2"]}
    row = score_query(claims, {"q.c1"}, ["a", "b", "c"], judged, set(judged))
    assert row["claim_recall@5"] == 1.0 and row["mrr_any_complete_claim@10"] == 1 / 3
    row = score_query(claims, {"q.c1"}, ["a", "b"], judged, {"a", "b"})
    assert row["claim_recall@10"] == 0.0 and row["partial_claim_recall@10"] == 1.0


def test_korean_level_explanations_are_fixed():
    assert LEVEL_HELP_KO == {
        "complete": "이 청크만으로 해당 근거 요소를 명확히 확인할 수 있음",
        "partial": "관련 정보는 있지만 해당 근거 요소를 완전히 확정하기에는 부족함",
        "none": "해당 근거 요소를 지원하지 않음",
    }


def test_recording_writes_responses_and_leaves_the_sheets_empty(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    import record_claim_review as rec
    sheets = [rec.OUT / f"{s}_{k}.csv" for s in rec.SYSTEMS for k in ("review_sheet", "item_claim_judgments")]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sheets]
    monkeypatch.setattr(rec, "DECISIONS_CSV", tmp_path / "item_decisions.csv")
    monkeypatch.setattr(rec, "SUPPORTS_CSV", tmp_path / "component_supports.csv")
    monkeypatch.setattr(rec, "FINAL", tmp_path / "final")
    sheet, items, comps, *_ = rec.load("b1")
    new = next(it for it in items if it.status == "new")
    reused = next(it for it in items if it.status == "reused")
    mapping = next(it for it in items if it.status == "reused_needs_claim_mapping")
    with pytest.raises(SystemExit):
        rec.decide("b1", reused.item_id, "relevant", "asked again")
    rec.decide("b1", new.item_id, "not_relevant", "test")
    with pytest.raises(SystemExit):
        rec.support("b1", new.item_id, [f"{comps[new.item_id][0]}=complete"])     # not relevant
    with pytest.raises(SystemExit):
        rec.support("b1", mapping.item_id, [f"{comps[mapping.item_id][0]}=none"])  # nothing supported
    rec.support("b1", mapping.item_id, [f"{comps[mapping.item_id][0]}=complete"])
    assert (tmp_path / "item_decisions.csv").read_text("utf-8").count("\n") == 2
    with pytest.raises(SystemExit):                                                 # most items still undecided
        rec.finalize_all()
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in sheets] == before
    assert all(not r["decision"] for r in sheet if r["status"] == "new")
