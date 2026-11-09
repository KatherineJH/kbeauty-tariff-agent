"""run_008: the claim-based B1/B2 comparison is reproduced from the raw rankings and final/v1 only."""

import csv
import hashlib
import json
import sys

import pytest

from tariffagent.retrieval.claim_scoring import Judgement, score_query
from tariffagent.retrieval.corpus import REPO

sys.path.insert(0, str(REPO / "scripts"))
import eval_claims_final as e  # noqa: E402

RUN = REPO / "reports" / "retrieval" / "run_008_claims_final_v1"


@pytest.fixture(scope="module")
def computed():
    return e.compute()


def _csv(path):
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_outputs_are_reproduced_from_raw_rankings_and_final_judgements(computed):
    rows, deltas, metrics = computed
    assert _csv(RUN / "claim_per_query.csv") == [{k: str(v) for k, v in e._fmt(r).items()} for r in rows]
    assert _csv(RUN / "claim_paired_delta.csv") == [{k: str(v) for k, v in e._fmt(r).items()} for r in deltas]
    assert json.loads((RUN / "claim_metrics.json").read_text("utf-8")) == json.loads(json.dumps(metrics))


def test_manifest_hashes_match_inputs_and_outputs():
    m = json.loads((RUN / "manifest.json").read_text("utf-8"))
    for rel, digest in m["inputs_sha256"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    for name, digest in m["outputs_sha256"].items():
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest, name
    assert m["claude_sealed_read"] is False
    assert not any("claude_sealed" in rel for rel in m["inputs_sha256"])


def test_group_macros_are_means_of_the_per_query_rows(computed):
    rows, _, metrics = computed
    for s in ("B1", "B2"):
        for g, sel in (("all", lambda r: True), ("main", lambda r: not r["underspecified"]),
                       ("underspecified", lambda r: r["underspecified"]), ("en", lambda r: r["lang"] == "en"),
                       ("ko", lambda r: r["lang"] == "ko")):
            rs = [r for r in rows if r["system"] == s and sel(r)]
            got = metrics["official"]["systems"][s][g]
            assert got["queries"] == len(rs)
            for m in e.PRIMARY:
                assert got["primary_macro"][m] == round(sum(r[m] for r in rs) / len(rs), 4)


def test_every_top10_unit_is_judged_and_query_sets_are_fixed(computed):
    rows, _, metrics = computed
    assert len(rows) == 48 and all(r["unjudged@10"] == 0 for r in rows)
    assert metrics["official"]["systems"]["B1"]["main"]["queries"] == 14
    assert metrics["official"]["systems"]["B1"]["underspecified"]["queries"] == 10
    assert metrics["sensitivity_without_dq07"]["systems"]["B1"]["all"]["queries"] == 22


def test_dq07_c1_cannot_be_completed_and_stays_in_the_official_result(computed):
    rows, _, metrics = computed
    assert metrics["official"]["systems"]["B1"]["all"]["queries"] == 24
    for q in e.CI001_QUERIES:
        for s in ("B1", "B2"):
            assert metrics["ci001"]["unreachable_required_claims"][q][s] == 1
            r = next(r for r in rows if r["system"] == s and r["query_id"] == q)
            assert r["ci001_query"] == 1


def test_diagnostics_are_kept_out_of_the_primary_tables(computed):
    _, _, metrics = computed
    for s in ("B1", "B2"):
        for g in metrics["official"]["systems"][s].values():
            assert not set(g["primary_macro"]) & set(e.DIAGNOSTIC)
    gap = metrics["official"]["language_gap_matched_pairs"]["B1"]["en_minus_ko"]
    assert not set(gap) & set(e.DIAGNOSTIC)


def test_score_query_at_k1_and_k3():
    claims = {"q.c1": ["q.c1.e1"]}
    judged = {"a": Judgement("not_relevant", {}), "b": Judgement("relevant", {"q.c1.e1": "complete"})}
    row = score_query(claims, {"q.c1"}, ["a", "b"], judged, {"a", "b"}, k_values=(1, 3))
    assert row["claim_recall@1"] == 0.0 and row["claim_recall@3"] == 1.0
    assert row["mrr_any_complete_claim@10"] == 0.5
