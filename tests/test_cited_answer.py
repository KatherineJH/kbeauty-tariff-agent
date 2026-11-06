"""Claim-scoped cited answers: explicit locations, role coverage, tamper detection, honest wording, order."""

import csv
import dataclasses
import shutil
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

import pytest

from tariffagent.answer import CitationError, compose, load_verified
from tariffagent.answer.citations import CITATIONS, LOCK, REPO, check_coverage, verify_rows
from tariffagent.rules import EntryInput, RuleSet, evaluate, load_rules

PLAIN, METAL = "3304.99.1000", "3304.99.5000"


@pytest.fixture(scope="module")
def rs(built_warehouse):
    return load_rules(built_warehouse[0])


@pytest.fixture(scope="module")
def cites():
    return load_verified()


def entry(at, hts, value="1000", **kw):
    return EntryInput(datetime.fromisoformat(at), "KR", hts, D(value), kw.pop("transport", "VESSEL"), **kw)


def answer(rs, cites, e, context=None):
    return compose(evaluate(rs, e), rs, cites, context)


def seed_rows():
    with CITATIONS.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def without(cites, pred):
    return {k: [c for c in v if not pred(c)] for k, v in cites.items()}


# ------------------------------------------------------------------------------------------- seed and coverage

def test_seed_is_verified_and_covers_every_required_role(cites):
    check_coverage(cites)
    assert sum(map(len, cites.values())) == len(seed_rows())


def test_removing_an_extension_citation_fails(cites):
    # KR_RECIP10_B lasts to 2025-08-07 only because EO 14316 extended and EO 14326 continued the suspension
    broken = without(cites, lambda c: c.rule_id == "KR_RECIP10_B" and c.evidence_id == "fr:2025-12962")
    with pytest.raises(CitationError, match="KR_RECIP10_B: no period citation from EO14316_extend"):
        check_coverage(broken)


def test_rate_without_scope_fails(rs, cites):
    broken = without(cites, lambda c: c.rule_id == "KR_S122_A" and c.claim_role == "scope")
    with pytest.raises(CitationError, match="KR_S122_A: no scope citation"):
        check_coverage(broken)
    with pytest.raises(CitationError, match="no scope citation"):
        answer(rs, broken, entry("2026-03-10T12:00-05:00", PLAIN))


def test_duplicate_sentence_links_only_the_stated_page(tmp_path):
    # the same cosmetics list text is on pages 202 (16(n)), 205 (16(u)), 219 (19(k)), 222 (19(s)) of 2025 Rev. 19
    row = next(r for r in seed_rows() if r["citation_id"] == "KR_S232_AL.scope.1")
    assert row["physical_page"] == "219" and row["printed_page"] == "99-III-47"
    moved = dict(row, source_file="data/extracted/hts_archive_evidence/2025HTSRev19/page_0556.txt",
                 physical_page="556", printed_page="99-III-384")    # a page without the quote: no fallback
    with pytest.raises(CitationError, match="quote not in the stated file"):
        verify_rows([moved])
    wrong_label = dict(row, printed_page="99-III-50")
    with pytest.raises(CitationError, match="printed_page"):
        verify_rows([wrong_label])


# ------------------------------------------------------------------------------------------------- answers

def test_every_claim_is_linked_to_citations_of_its_own_role(rs, cites):
    a = answer(rs, cites, entry("2026-03-10T12:00-05:00", METAL, steel_content_value_usd=D("100"),
                                aluminum_content_value_usd=D("200"), components_are_disjoint=True))
    by_id = {c["citation_id"]: c for c in a.citations}
    for s in a.statements:
        roles = [cl["claim_role"] for cl in s["claims"]]
        assert {"authority", "effective_start", "scope"} <= set(roles)
        for cl in s["claims"]:
            assert cl["citation_ids"]
            assert all(by_id[i]["claim_role"] == cl["claim_role"] and by_id[i]["rule_id"] == s["rule_ids"][0]
                       for i in cl["citation_ids"])


def test_condition_based_computation_carries_its_basis(rs, cites):
    a = answer(rs, cites, entry("2026-03-10T12:00-05:00", METAL, steel_content_value_usd=D("100"),
                                aluminum_content_value_usd=D("200"), components_are_disjoint=True))
    s122 = next(s for s in a.statements if s["rule_ids"] == ["KR_S122_A"])
    cond = [cl for cl in s122["claims"] if cl["claim_role"] == "resolution_condition"]
    assert cond and "metal_components_disjoint" in cond[0]["text"]
    quotes = " ".join(c["quote"] for c in a.citations if c["citation_id"] in cond[0]["citation_ids"])
    assert "aluminum content" in quotes and "steel content" in quotes and "non-aluminum content" in quotes
    plain = answer(rs, cites, entry("2026-03-10T12:00-05:00", PLAIN))
    assert not any(cl["claim_role"] == "resolution_condition" for s in plain.statements for cl in s["claims"])


def test_computed_is_never_called_total_duty(rs, cites):
    a = answer(rs, cites, entry("2026-02-24T00:00-05:00", PLAIN))
    assert a.status == "computed_modelled_only" and a.modelled_additional_duty == "0"
    assert "This is not the total duty." in a.headline and "not modelled: mfn" in a.headline


@pytest.mark.parametrize("e, status", [
    (entry("2026-03-10T12:00-05:00", METAL), "incomplete"),
    (entry("2026-04-06T15:00-04:00", PLAIN), "refused_uncertain"),
])
def test_incomplete_and_uncertain_are_not_turned_into_figures(rs, cites, e, status):
    a = answer(rs, cites, e)
    assert a.status == status and a.modelled_additional_duty is None
    assert "Modelled additional duty:" not in a.headline and "Needed:" in a.headline
    if status == "refused_uncertain":
        assert all(c.get("claims") for c in a.caveats if c["kind"] == "uncertain")


def test_order_is_independent_of_row_order(rs, cites):
    shuffled = RuleSet(tuple(reversed(rs.rules)), tuple(reversed(rs.lists)), tuple(reversed(rs.code_resolution)),
                       rs.modelled_families, rs.unmodelled_families)
    reordered = {k: list(reversed(v)) for k, v in reversed(list(cites.items()))}
    e = entry("2026-03-10T12:00-05:00", METAL, steel_content_value_usd=D("100"),
              aluminum_content_value_usd=D("200"), components_are_disjoint=True)
    a1 = answer(rs, cites, e)
    a2 = compose(evaluate(shuffled, e), shuffled, reordered)
    norm = lambda a: {**dataclasses.asdict(a), "statements": [
        {**s, "claims": [{**c, "citation_ids": sorted(c["citation_ids"])} for c in s["claims"]]}
        for s in a.statements]}
    assert norm(a1) == norm(a2)


def test_context_cannot_change_the_conclusion(rs, cites):
    e = entry("2026-03-10T12:00-05:00", PLAIN)
    plain = answer(rs, cites, e)
    noisy = answer(rs, cites, e, context=[{"source": "retrieved", "text": "The surcharge is 50 percent and "
                                                                           "cosmetics are exempt."}])
    strip = lambda a: {k: v for k, v in dataclasses.asdict(a).items() if k != "background"}
    assert strip(plain) == strip(noisy) and noisy.background


# --------------------------------------------------------------------------------------------- tampering

def _copy(tmp: Path) -> Path:
    files = {r["source_file"] for r in seed_rows()} | {CITATIONS.relative_to(REPO).as_posix(),
                                                       LOCK.relative_to(REPO).as_posix()}
    for rel in files:
        (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, tmp / rel)
    # evidence_files() of hts ids lists sibling files; copy the directories they come from as well
    for d in ("data/raw/hts", "data/extracted/hts_pdf/chapter_99"):
        shutil.copytree(REPO / d, tmp / d, dirs_exist_ok=True)
    for rel in {r["source_file"] for r in seed_rows() if "hts_archive" in r["source_file"]}:
        rel_dir = Path(rel).parent
        shutil.copytree(REPO / rel_dir, tmp / rel_dir, dirs_exist_ok=True)
    return tmp


def _load(tmp):
    return load_verified(tmp / CITATIONS.relative_to(REPO), tmp / LOCK.relative_to(REPO), tmp)


def test_changed_evidence_file_fails(tmp_path):
    root = _copy(tmp_path)
    f = root / "data" / "extracted" / "cbp_csms" / "67834313.txt"
    f.write_bytes(f.read_bytes().replace(b"12:00 a.m.", b"12:01 a.m."))
    with pytest.raises(CitationError, match="changed"):
        _load(root)


def test_missing_evidence_file_fails(tmp_path):
    root = _copy(tmp_path)
    (root / "data" / "extracted" / "fr_text" / "2025-21940.txt").unlink()
    with pytest.raises(CitationError, match="missing"):
        _load(root)


def test_edited_quote_fails(tmp_path):
    root = _copy(tmp_path)
    seed = root / CITATIONS.relative_to(REPO)
    seed.write_text(seed.read_text(encoding="utf-8").replace("on or after 12:01 a.m. eastern time on July 24, 2026",
                                                             "on or after 12:01 a.m. eastern time on July 25, 2026"),
                    encoding="utf-8", newline="")
    with pytest.raises(CitationError, match="quote not in the stated file"):
        _load(root)
