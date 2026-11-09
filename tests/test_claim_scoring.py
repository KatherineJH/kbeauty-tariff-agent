"""Claim-based scoring on synthetic judgements (no reviewed data exists yet), the claim catalog and the review items."""

import csv
import math

import pytest

from tariffagent.retrieval.claim_scoring import Judgement, score_query, summarize_claims
from tariffagent.retrieval.corpus import REPO

# a query with two single-component claims and one composite claim
CLAIMS = {"q.c1": ["q.c1.e1"], "q.c2": ["q.c2.e1"], "q.c3": ["q.c3.e1", "q.c3.e2"]}
J = lambda decision, **levels: Judgement(decision, {k.replace("_", "."): v for k, v in levels.items()})


def test_one_unit_complete_for_c1_and_partial_for_c2():
    required = {"q.c1", "q.c2"}
    claims = {k: CLAIMS[k] for k in required}
    judged = {"u": J("relevant", q_c1_e1="complete", q_c2_e1="partial")}
    row = score_query(claims, required, ["u"], judged, {"u"})
    assert row["claim_recall@10"] == 0.5                 # c1 counts, c2 is only partly supported
    assert row["partial_claim_recall@10"] == 1.0
    assert row["all_claims_covered@10"] == 0 and row["mrr_all_claims_complete@10"] == 0.0
    assert row["mrr_any_complete_claim@10"] == 1.0
    assert row["unreachable_claims"] == 1               # nothing in the pool completes c2
    assert row["claim_novelty_dcg@10"] == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_a_later_unit_completes_the_partly_supported_claim():
    required = {"q.c1", "q.c2"}
    claims = {k: CLAIMS[k] for k in required}
    judged = {"u": J("relevant", q_c1_e1="complete", q_c2_e1="partial"),
              "x": J("not_relevant"),
              "v": J("relevant", q_c2_e1="complete")}
    row = score_query(claims, required, ["u", "x", "v"], judged, set(judged))
    assert (row["claim_recall@5"], row["all_claims_covered@5"]) == (1.0, 1)
    assert row["mrr_any_complete_claim@10"] == 1.0 and row["mrr_all_claims_complete@10"] == 1 / 3
    assert row["unreachable_claims"] == 0
    nov = (1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3))
    assert row["claim_novelty_dcg@10"] == pytest.approx(nov)


def test_composite_claim_is_completed_by_the_union_of_units():
    required = {"q.c3"}
    claims = {"q.c3": CLAIMS["q.c3"]}
    judged = {"a": J("relevant", q_c3_e1="complete"), "b": J("relevant", q_c3_e2="complete"),
              "p": J("relevant", q_c3_e2="partial")}
    row = score_query(claims, required, ["a", "p", "b"], judged, set(judged))
    assert row["mrr_any_complete_claim@10"] == 1 / 3 and row["claim_recall@5"] == 1.0
    row = score_query(claims, required, ["a", "p"], judged, {"a", "p"})
    assert row["claim_recall@10"] == 0.0 and row["partial_claim_recall@10"] == 1.0
    assert row["unreachable_claims"] == 1
    row = score_query(claims, required, ["a"], judged, set(judged))     # reachable through b in the pool
    assert row["claim_recall@10"] == 0.0 and row["unreachable_claims"] == 0


def test_ndcg_grade_is_fixed_per_unit():
    required = {"q.c1"}
    claims = {"q.c1": CLAIMS["q.c1"], "q.c2": CLAIMS["q.c2"]}
    judged = {"a": J("relevant", q_c1_e1="complete"), "b": J("relevant", q_c1_e1="complete"),
              "c": J("relevant", q_c2_e1="complete"), "d": J("uncertain")}
    row = score_query(claims, required, ["c", "d", "a", "b"], judged, set(judged))
    grades = [1, 0, 2, 2]                              # c supports only a non-required claim
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades))
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(sorted(grades, reverse=True)))
    assert row["system_relative_ndcg@10"] == pytest.approx(dcg / idcg)
    assert row["uncertain@10"] == 1 and row["claim_recall@10"] == 1.0


def test_unjudged_units_get_no_credit_and_are_counted():
    row = score_query({"q.c1": ["q.c1.e1"]}, {"q.c1"}, ["x", "y"], {}, set())
    assert row["claim_recall@10"] == 0.0 and row["unjudged@10"] == 2 and row["unreachable_claims"] == 1


@pytest.mark.parametrize("bad", [J("relevant"),                                    # relevant, nothing supported
                                 J("relevant", q_c1_e1="none"),
                                 J("not_relevant", q_c1_e1="partial"),
                                 J("uncertain", q_c1_e1="complete"),
                                 J("relevant", q_c1_e1="mostly"),
                                 J("relevant", other_c1_e1="complete"),
                                 J("maybe")])
def test_invalid_judgements_are_refused(bad):
    with pytest.raises(ValueError):
        score_query({"q.c1": ["q.c1.e1"]}, {"q.c1"}, ["u"], {"u": bad}, {"u"})


def test_not_relevant_with_explicit_none_is_valid():
    j = J("not_relevant", q_c1_e1="none")
    row = score_query({"q.c1": ["q.c1.e1"]}, {"q.c1"}, ["u"], {"u": j}, {"u"})
    assert row["claim_recall@10"] == 0.0


def test_claim_metric_names_never_reuse_citation_metric_names():
    from tariffagent.retrieval import claim_scoring as cs
    code = (REPO / "src" / "tariffagent" / "retrieval" / "claim_scoring.py").read_text("utf-8")
    body = code.split('"""', 2)[2]
    for legacy in ("relevant_citations", "unreachable_citations", '"mrr@10"', '"ndcg@10"', '"recall@', '"found@'):
        assert legacy not in body, legacy
    row = score_query({"q.c1": ["q.c1.e1"]}, {"q.c1"}, ["u"], {"u": J("relevant", q_c1_e1="complete")}, {"u"})
    assert not {"recall@10", "mrr@10", "ndcg@10", "relevant_citations"} & set(row)
    rows = [{**row, "query_id": "q_en", "pair_id": "p", "lang": "en", "underspecified": 0},
            {**row, "query_id": "q_ko", "pair_id": "p", "lang": "ko", "underspecified": 0}]
    out = {r["group"]: r for r in summarize_claims(rows, matched_pairs={"p"})}
    assert out["all"]["macro_claim_recall@10"] == 1.0 and out["all"]["micro_claim_recall@10"] == 1.0
    assert out["gap_en_minus_ko"]["macro_claim_recall@10"] == 0.0
    assert not any(k.endswith("ndcg@10") for k in out["gap_en_minus_ko"])
    assert "system_relative_ndcg@10" not in cs.PRIMARY


def _claims():
    with (REPO / "evals" / "dev" / "claims.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_every_claim_rests_on_exact_official_sentences():
    from pathlib import Path
    from tariffagent.answer.citations import file_text, normalize
    with (REPO / "evals" / "dev" / "claim_evidence.csv").open(encoding="utf-8", newline="") as f:
        ev = {r["evidence_id"]: r for r in csv.DictReader(f)}
    with (REPO / "warehouse" / "seeds" / "rule_citations.csv").open(encoding="utf-8", newline="") as f:
        cite_ids = {r["citation_id"] for r in csv.DictReader(f)}
    with (REPO / "warehouse" / "seeds" / "regulatory_actions.csv").open(encoding="utf-8", newline="") as f:
        action_ids = {r["action_id"] for r in csv.DictReader(f)}
    for e in ev.values():
        path = REPO / e["source_file"]
        assert path.exists() and "warehouse" not in e["source_file"], e["evidence_id"]
        assert file_text(path).count(normalize(e["quote"])) == 1, e["evidence_id"]
        for g in e["gold_link"].split(";"):
            assert g in cite_ids or g in action_ids, (e["evidence_id"], g)
    used = set()
    for c in _claims():
        ids = c["evidence_ids"].split(";")
        assert ids and all(i in ev for i in ids), c["claim_id"]
        used |= set(ids)
    assert used == set(ev)                      # no unused evidence rows


def test_claim_sets_per_query():
    claims = _claims()
    with (REPO / "evals" / "dev" / "queries.csv").open(encoding="utf-8", newline="") as f:
        queries = {q["query_id"]: q for q in csv.DictReader(f)}
    assert {c["query_id"] for c in claims} == {q for q, v in queries.items() if v["relevant_citation_ids"]}
    assert len({c["claim_id"] for c in claims}) == len(claims)
    sets = {}
    for c in claims:
        assert c["pair_id"] == queries[c["query_id"]]["pair_id"] and c["required"] in ("true", "false")
        sets.setdefault(c["query_id"], []).append((c["claim_text"], c["required"], c["evidence_ids"]))
    assert all(any(r == "true" for _, r, _ in v) for v in sets.values())
    text = lambda q: sorted(t for t, _, _ in sets[q])
    assert text("dq01_en") != text("dq11_en")                       # p01 and p11 are separate claims
    assert text("dq11_en") != text("dq11_ko") and text("dq12_en") != text("dq12_ko")
    for same in ("p01", "p02", "p03", "p04", "p05", "p06", "p07", "p08", "p09", "p10"):
        assert sets[f"dq{same[1:]}_en"] == sets[f"dq{same[1:]}_ko"], same
    assert len(sets["dq05_en"]) == 3 and len(sets["dq10_en"]) == 2 and len(sets["dq04_en"]) == 2
    assert "EV.ieepa_end.csms" in sets["dq01_en"][0][2]             # its own evidence id, not a deal-rule citation


# --- claim review items ----------------------------------------------------------------------------------------------

def _sheet(name, bom=True):
    with (REPO / "evals" / "dev" / "review_claims" / name).open(encoding="utf-8-sig" if bom else "utf-8",
                                                                    newline="") as f:
        return list(csv.DictReader(f))


def _script():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    import make_claim_review_sheets as m
    return m


def test_b1_items_show_only_b1_payload_and_b2_items_the_b2_payload():
    m = _script()
    from tariffagent.retrieval.corpus import build_chunks, documents
    from tariffagent.retrieval.structure import enrich
    chunks = {c.chunk_id: c for c in build_chunks()}
    b2 = {b.chunk_id: b for b in enrich(documents(), list(chunks.values()), config_id="b2_heading_v4")}
    b1_rows, b2_rows = _sheet("b1_review_sheet.csv"), _sheet("b2_review_sheet.csv")
    assert "context_text" not in b1_rows[0] and "source_revision" not in b1_rows[0]
    for r in b1_rows:
        assert r["raw_text"] == chunks[r["chunk_id"]].text
        assert r["payload_sha256"] == m.payload_hash(m.payload("B1", **r))
    for r in b2_rows:
        b = b2[r["chunk_id"]]
        assert (r["context_text"], r["raw_text"]) == (b.context_text, b.raw_text)
        assert r["payload_sha256"] == m.payload_hash(m.payload("B2", **r))
    for rows in (b1_rows, b2_rows):
        keys = [(r["intent"], r["claim_set_sha256"], r["payload_sha256"]) for r in rows]
        assert len(keys) == len(set(keys))
    assert not {r["payload_sha256"] for r in b1_rows} & {r["payload_sha256"] for r in b2_rows}


def test_items_merge_only_matched_pairs_with_the_same_claims():
    with (REPO / "evals" / "dev" / "query_pair_checks.csv").open(encoding="utf-8", newline="") as f:
        matched = {r["pair_id"] for r in csv.DictReader(f) if r["pair_mismatch"] == "false"}
    for name in ("b1_review_sheet.csv", "b2_review_sheet.csv"):
        for r in _sheet(name):
            qids = r["query_ids"].split(";")
            if len(qids) > 1:
                assert r["intent"] in matched and len({q.split("_")[0] for q in qids}) == 1
            else:
                assert r["intent"] in (qids[0], qids[0].split("_")[0].replace("dq", "p"))


def test_reuse_only_with_same_intent_claims_payload_and_metadata():
    m = _script()
    with (REPO / "evals" / "dev" / "query_pair_checks.csv").open(encoding="utf-8", newline="") as f:
        matched = {r["pair_id"] for r in csv.DictReader(f) if r["pair_mismatch"] == "false"}
    with (REPO / "evals" / "dev" / "review" / "qrel_review_sheet.csv").open(encoding="utf-8-sig", newline="") as f:
        old = {r["unit_id"]: r for r in csv.DictReader(f)}
    with (REPO / "evals" / "dev" / "queries.csv").open(encoding="utf-8", newline="") as f:
        gold = {q["query_id"]: set(q["relevant_citation_ids"].split(";")) for q in csv.DictReader(f)}
    with (REPO / "evals" / "dev" / "claims.csv").open(encoding="utf-8", newline="") as f:
        claims = list(csv.DictReader(f))
    for r in _sheet("b2_review_sheet.csv"):
        assert r["status"] == "new" and not r["decision"] and not r["reused_from"]
    reused = 0
    for r in _sheet("b1_review_sheet.csv"):
        if r["status"] == "new":
            assert not r["decision"] and not r["reused_from"]
            continue
        reused += 1
        prev = old[r["reused_from"].rsplit(":", 1)[1]]
        assert r["intent"] == prev["pair_id"] and r["intent"] in matched
        old_payload = m.payload("B1", raw_text=prev["chunk_text"], **prev)
        assert m.payload_hash(old_payload) == r["payload_sha256"]
        for q in r["query_ids"].split(";"):
            req = {g for c in claims if c["query_id"] == q and c["required"] == "true"
                   for g in c["gold_links"].split(";")}
            assert req == gold[q]
        assert r["decision"] == prev["user_decision"] and "supports_claim_ids" not in r
        assert r["status"] == ("reused_needs_claim_mapping" if r["decision"] == "relevant" else "reused")
    assert reused > 0


def test_each_system_top10_is_fully_pooled():
    links = {(l["system"], l["query_id"]) for l in _sheet("item_queries.csv", bom=False)}
    pooled = {(p["system"], p["query_id"], p["parent_chunk_id"]) for p in _sheet("pools.csv", bom=False)}
    runs = {"B1": REPO / "reports" / "retrieval" / "run_003_user_reviewed_qrels" / "bm25_dev_runs.csv",
            "B2": REPO / "reports" / "retrieval" / "run_007_b2_heading_v4" / "b2_dev_runs.csv"}
    with (REPO / "evals" / "dev" / "queries.csv").open(encoding="utf-8", newline="") as f:
        answerable = {q["query_id"] for q in csv.DictReader(f) if q["relevant_citation_ids"]}
    for system, path in runs.items():
        with path.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["query_id"] in answerable:
                    parent = r["chunk_id"] if system == "B1" else r["parent_chunk_id"]
                    assert (system, r["query_id"], parent) in pooled
    assert {q for s, q in links} == answerable


def test_identical_payloads_are_judged_once_across_systems():
    b1 = {(r["intent"], r["claim_set_sha256"], r["payload_sha256"]): r["item_id"] for r in _sheet("b1_review_sheet.csv")}
    for r in _sheet("b2_review_sheet.csv"):
        key = (r["intent"], r["claim_set_sha256"], r["payload_sha256"])
        if key in b1:
            assert r["status"] == f"same_as:{b1[key]}"
        else:
            assert not r["status"].startswith("same_as:")


def test_claim_components_and_composites():
    with (REPO / "evals" / "dev" / "claim_components.csv").open(encoding="utf-8", newline="") as f:
        comps = list(csv.DictReader(f))
    with (REPO / "evals" / "dev" / "claim_evidence.csv").open(encoding="utf-8", newline="") as f:
        ev = {r["evidence_id"]: r for r in csv.DictReader(f)}
    claims = {c["claim_id"]: c for c in _claims()}
    by_claim = {}
    for c in comps:
        by_claim.setdefault(c["claim_id"], []).append(c)
    assert set(by_claim) == set(claims)
    for cid, cs in by_claim.items():
        assert [c["evidence_id"] for c in cs] == claims[cid]["evidence_ids"].split(";")
        assert all(c["composite"] == ("true" if len(cs) > 1 else "false") for c in cs)
        assert all(c["component_id"] == f"{cid}.e{i}" for i, c in enumerate(cs, 1))
    composite = sorted(cid for cid, cs in by_claim.items() if len(cs) > 1)
    assert composite == ["dq10_en.c1", "dq10_ko.c1", "dq11_en.c1", "dq11_ko.c1", "dq12_ko.c2"]
    assert ev["EV.demin.eo"]["quote"].endswith("August 29, 2025")
    for c in _claims():                          # a year named in the claim is in its evidence
        years = set(__import__("re").findall(r"\b20\d\d\b", c["claim_text"]))
        text = " ".join(ev[e]["quote"] for e in c["evidence_ids"].split(";"))
        assert all(y in text for y in years), (c["claim_id"], years)


def test_every_item_has_one_row_per_claim_component():
    with (REPO / "evals" / "dev" / "claim_components.csv").open(encoding="utf-8", newline="") as f:
        comps = {}
        for c in csv.DictReader(f):
            comps.setdefault(c["claim_id"], []).append(c["component_id"].split(".")[-1])
    links = _sheet("item_queries.csv", bom=False)
    for system in ("b1", "b2"):
        items = _sheet(f"{system}_review_sheet.csv")
        cells = _sheet(f"{system}_item_claim_judgments.csv")
        got = {}
        for c in cells:
            got.setdefault(c["item_id"], set()).add((c["claim"], c["component"]))
            assert c["support"] in ("", "none")
        for it in items:
            q = it["query_ids"].split(";")[0]
            want = {(cid.split(".")[1], e) for cid in next(l["claim_ids"] for l in links
                                                          if l["system"] == system.upper() and l["query_id"] == q
                                                          and l["payload_sha256"] == it["payload_sha256"]).split(";")
                    for e in comps[cid]}
            assert got[it["item_id"]] == want, it["item_id"]
            rows = [c for c in cells if c["item_id"] == it["item_id"]]
            if it["status"] == "reused" and it["decision"] in ("not_relevant", "uncertain"):
                assert all(c["support"] == "none" and c["status"] == "prefilled_none_from_reuse" for c in rows)
            else:
                assert all(c["support"] == "" and c["status"] == "to_fill" for c in rows)
