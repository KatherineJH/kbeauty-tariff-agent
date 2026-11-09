"""Two-stage claim review input: automatic none, refused input, composite claims across items, empty sheets."""

import hashlib

import pytest

from tariffagent.retrieval.claim_review import (LEVEL_HELP_KO, QUEUE_SEED, Item, ReviewInputError, build_queue,
                                                finalize, stage2_items)
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
    ({"n1": ("not_relevant", "r")}, {"n1": {"c1.e1": "none"}}),        # stage 2 answer for a non-relevant item
    ({"n1": ("relevant", "r")}, {"n1": {"c9.e1": "complete"}}),        # unknown component
    ({"n1": ("relevant", "r")}, {"n1": {"c1.e1": "mostly"}}),          # unknown level
    ({"n1": ("maybe", "r")}, {}),                                      # unknown decision
    ({"zz": ("relevant", "r")}, {}),                                   # unknown item
])
def test_inconsistent_input_is_refused(decisions, supports):
    with pytest.raises(ReviewInputError):
        finalize(_items(("n1", "new")), COMPS, decisions, supports)


def test_composite_claim_completed_by_two_items_in_the_top_k():
    comps = {"a": ["c1.e1", "c1.e2"], "b": ["c1.e1", "c1.e2"], "c": ["c1.e1", "c1.e2"]}
    items = _items(("a", "new"), ("b", "new"), ("c", "new"))
    _, cells = finalize(items, comps, {"a": ("relevant", "r"), "b": ("not_relevant", "r"), "c": ("relevant", "r")},
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


@pytest.mark.parametrize("reason", ["", "   ", "\t\n"])
def test_empty_reason_is_refused(reason):
    with pytest.raises(ReviewInputError):
        finalize(_items(("n1", "new")), COMPS, {"n1": ("not_relevant", reason)}, {})


def test_reused_item_without_its_reason_is_refused():
    with pytest.raises(ReviewInputError):
        finalize(_items(("old", "reused", "not_relevant", "  ")), COMPS, {}, {})
    items, _ = finalize(_items(("old", "reused", "not_relevant", "kept reason")), COMPS, {}, {})
    assert items[0]["reason"] == "kept reason"


def test_queue_is_deterministic_mixed_and_opaque():
    items = {"b1": [Item(f"b1-{i:04d}", "new") for i in range(1, 40)] + [Item("b1-0099", "reused")],
             "b2": [Item(f"b2-{i:04d}", "new") for i in range(1, 40)]}
    a, b = build_queue(items), build_queue(items)
    assert a == b and len(a) == 78                                   # the reused item is not queued
    assert [r["review_id"] for r in build_queue(items, seed="other")] != [r["review_id"] for r in a]
    assert all(r["review_id"].startswith("R-") and "b1" not in r["review_id"] and "b2" not in r["review_id"]
               for r in a)
    assert {r["system"] for r in a[:20]} == {"b1", "b2"}


def _rec(tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    import record_claim_review as rec
    monkeypatch.setattr(rec, "DECISIONS_CSV", tmp_path / "item_decisions.csv")
    monkeypatch.setattr(rec, "SUPPORTS_CSV", tmp_path / "component_supports.csv")
    monkeypatch.setattr(rec, "FINAL", tmp_path / "final")
    return rec


def test_sealed_queue_matches_its_manifest_and_the_seed():
    import csv
    import json
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    import record_claim_review as rec
    m = json.loads(rec.QUEUE_MANIFEST.read_text("utf-8"))
    assert m["seed"] == QUEUE_SEED and m["queue_sha256"] == rec._sha(rec.QUEUE_CSV)
    assert m["queue_map_sha256"] == rec._sha(rec.QUEUE_MAP)
    rebuilt = build_queue({s: rec.load_sheet(s)[1] for s in rec.SYSTEMS})
    with rec.QUEUE_MAP.open(encoding="utf-8", newline="") as f:
        sealed = list(csv.DictReader(f))
    assert [(r["review_id"], r["system"], r["item_id"]) for r in rebuilt] == \
        [(r["review_id"], r["system"], r["item_id"]) for r in sealed]
    with rec.QUEUE_CSV.open(encoding="utf-8", newline="") as f:
        visible = list(csv.DictReader(f))
    assert list(visible[0]) == ["review_id", "position", "stage"] and len(visible) == m["rows"]


def test_recording_uses_review_ids_and_leaves_the_sheets_empty(tmp_path, monkeypatch, capsys):
    rec = _rec(tmp_path, monkeypatch)
    sheets = [rec.OUT / f"{s}_{k}.csv" for s in rec.SYSTEMS for k in ("review_sheet", "item_claim_judgments")]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sheets]
    queue, mapping = rec.load_queue()
    s1 = next(q["review_id"] for q in queue if q["stage"] == "stage1")
    s2 = next(q["review_id"] for q in queue if q["stage"] == "stage2_only")
    with pytest.raises(SystemExit):
        rec.decide(s1, "not_relevant", "   ")                       # empty reason
    with pytest.raises(SystemExit):
        rec.decide(s2, "relevant", "asked again")                   # reused item
    rec.decide(s1, "not_relevant", "different heading")
    with pytest.raises(SystemExit):
        rec.decide(s1, "relevant", "twice")
    comps = rec.load_sheet(mapping[s2][0])[2][mapping[s2][1]]
    with pytest.raises(SystemExit):
        rec.support(s2, [f"{comps[0]}=none"])
    rec.support(s2, [f"{comps[0]}=complete"])
    rec.next_stage1(1)
    shown = capsys.readouterr().out
    assert "b1-" not in shown and "b2-" not in shown and " b1 " not in shown and " b2 " not in shown
    with pytest.raises(SystemExit):                                  # most items still undecided
        rec.finalize_all("v1")
    assert not (tmp_path / "final" / "v1").exists()
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in sheets] == before


def test_finalize_never_overwrites_a_version(tmp_path, monkeypatch):
    rec = _rec(tmp_path, monkeypatch)
    (tmp_path / "final" / "v1").mkdir(parents=True)
    (tmp_path / "final" / "v1" / "b1_items.csv").write_text("kept\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        rec.finalize_all("v1")
    assert "never overwritten" in str(e.value)
    assert (tmp_path / "final" / "v1" / "b1_items.csv").read_text("utf-8") == "kept\n"
    for bad in ("", "../v1", "a/b", ".hidden"):
        with pytest.raises(SystemExit):
            rec.finalize_all(bad)
    src = (REPO / "scripts" / "record_claim_review.py").read_text("utf-8")
    assert "--force" not in src and "overwrite=True" not in src
