"""Rule engine: agreement with the dbt reference states, the first-scope cases, and input / output contracts."""

import dataclasses
import re
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

import duckdb
import pytest

from tariffagent.rules import EntryInput, RuleSet, evaluate, load_rules, select_rules

REPO = Path(__file__).resolve().parents[1]
PLAIN, METAL = "3304.99.1000", "3304.99.5000"   # not a 232 derivative / in the 232 derivative lists


@pytest.fixture(scope="module")
def db(built_warehouse):
    path, s = built_warehouse
    assert not s["not_passed"], s["log_tail"]
    return path


@pytest.fixture(scope="module")
def rs(db):
    return load_rules(db)


def entry(at: str, hts: str, value="1000", **kw) -> EntryInput:
    return EntryInput(entry_at=datetime.fromisoformat(at), origin_country="KR", hts_code=hts,
                      customs_value_usd=D(value), transport_mode=kw.pop("transport", "VESSEL"), **kw)


def duties(r):
    return {d["rule_id"]: d for d in r.computed_duties}


def test_selection_agrees_with_dbt_reference_on_every_fixture(db, rs):
    con = duckdb.connect(str(db), read_only=True)
    fixtures = con.execute("select fixture_id, \"at\", hts10, transport from boundary_fixtures").fetchall()
    ref = {(f, r): s for f, r, s in con.execute(
        "select fixture_id, rule_id, state from int_fixture_rule_states").fetchall()}
    for fid, at, hts, transport in fixtures:
        e = entry(at, hts, transport=transport, is_postal=(transport == "POSTAL"))
        for s in select_rules(rs, e):
            expected = {"none": "not_applicable"}.get(ref[(fid, s.rule.rule_id)], ref[(fid, s.rule.rule_id)])
            assert s.state == expected, (fid, s.rule.rule_id, s.reason)


# ----------------------------------------------------------------------------------------------- the six cases

def test_case1_plain_cosmetic_under_surcharge(rs):
    r = evaluate(rs, entry("2026-03-10T12:00-05:00", PLAIN))
    assert r.status == "computed_modelled_only" and r.coverage == "modelled_families_only"
    assert r.not_modelled_families == ["mfn"]
    assert r.modelled_additional_duty == D("100")
    assert list(duties(r)) == ["KR_S122_A"]
    assert "fr:2026-03824" in r.evidence_ids


def test_case2_metal_derivative_with_disjoint_contents(rs):
    r = evaluate(rs, entry("2026-03-10T12:00-05:00", METAL, steel_content_value_usd=D("100"),
                           aluminum_content_value_usd=D("200"), components_are_disjoint=True))
    assert r.status == "computed_modelled_only"
    d = duties(r)
    assert d["KR_S232_AL"]["duty_usd"] == D("100") and d["KR_S232_ST"]["duty_usd"] == D("50")
    assert d["KR_S122_A"]["base_usd"] == D("700") and d["KR_S122_A"]["duty_usd"] == D("70")
    assert r.modelled_additional_duty == D("220")
    assert [x["rule_id"] for x in r.computed_duties] == ["KR_S232_AL", "KR_S232_ST", "KR_S122_A"]


def test_case2_metal_contents_not_declared_disjoint_is_not_computed(rs):
    r = evaluate(rs, entry("2026-03-10T12:00-05:00", METAL, steel_content_value_usd=D("100"),
                           aluminum_content_value_usd=D("200")))
    assert r.status == "incomplete" and r.modelled_additional_duty is None
    assert "KR_S122_A" not in duties(r)
    partial = [x for x in r.unresolved_components if x["kind"] == "partial_rule"]
    assert [x["rule_id"] for x in partial] == ["KR_S122_A"]
    assert "components_are_disjoint" in partial[0]["needed"]


def test_case3_metal_derivative_without_content(rs):
    r = evaluate(rs, entry("2026-03-10T12:00-05:00", METAL))
    assert r.status == "incomplete" and r.modelled_additional_duty is None and r.computed_duties == []
    kinds = {(x["kind"], x.get("rule_id")) for x in r.unresolved_components}
    assert ("missing_input", "KR_S232_AL") in kinds and ("missing_input", "KR_S232_ST") in kinds
    assert ("partial_rule", "KR_S122_A") in kinds          # never computed on the full value as a fallback


def test_case4_date_precision_boundary_is_refused(rs):
    r = evaluate(rs, entry("2026-04-06T15:00-04:00", PLAIN))
    assert r.status == "refused_uncertain" and r.modelled_additional_duty is None
    unc = {x["rule_id"]: x for x in r.unresolved_components if x["kind"] == "uncertain"}
    assert set(unc) == {"KR_S122_A", "KR_S122_B"} and "exact time" in unc["KR_S122_B"]["needed"]
    assert evaluate(rs, entry("2026-04-07T15:00-04:00", PLAIN)).status == "computed_modelled_only"


def test_case5_one_minute_gap_is_not_zero_total_duty(rs):
    gap = evaluate(rs, entry("2026-02-24T00:00-05:00", PLAIN))
    assert gap.status == "computed_modelled_only" and gap.modelled_additional_duty == D("0")
    assert gap.not_modelled_families == ["mfn"] and gap.coverage == "modelled_families_only"
    assert gap.applied_rule_ids == ["ALL_DEMIN_EO"] and gap.computed_duties == []
    before = evaluate(rs, entry("2026-02-23T23:59-05:00", PLAIN, column1_rate_pct=D("0")))
    after = evaluate(rs, entry("2026-02-24T00:01-05:00", PLAIN))
    assert list(duties(before)) == ["KR_DEAL15"] and list(duties(after)) == ["KR_S122_A"]


def test_case6_column1_is_not_modelled(rs):
    r = evaluate(rs, entry("2025-12-01T12:00-05:00", PLAIN))
    assert r.status == "incomplete"
    assert any(x["kind"] == "not_modelled" and x.get("rule_id") == "KR_DEAL15" for x in r.unresolved_components)
    assert evaluate(rs, entry("2025-12-01T12:00-05:00", PLAIN, column1_rate_pct=D("4"))
                    ).modelled_additional_duty == D("110")


# ------------------------------------------------------------------------------------------------ contracts

def test_total_with_column1_floor_at_zero_is_what_the_sources_say(rs):
    fr = lambda n: re.sub(r"\s+", " ", (REPO / "data" / "extracted" / "fr_text" / f"{n}.txt").read_text("utf-8"))
    assert "is at least 15 percent, the additional ad valorem rate of duty pursuant to Executive Order 14257, " \
           "as amended, will be zero percent" in fr("2025-21940")
    assert "greater than or equal to 12.5 percent, the Section 301 tariff applied shall be zero" in fr("2026-15181")
    deal = evaluate(rs, entry("2025-12-01T12:00-05:00", PLAIN, column1_rate_pct=D("20")))
    s301 = evaluate(rs, entry("2026-08-10T12:00-04:00", PLAIN, column1_rate_pct=D("15")))
    assert deal.modelled_additional_duty == D("0") and duties(deal)["KR_DEAL15"]["rate_pct_applied"] == D("0")
    assert s301.modelled_additional_duty == D("0") and duties(s301)["KR_S301"]["rate_pct_applied"] == D("0")
    at_cap = evaluate(rs, entry("2026-08-10T12:00-04:00", PLAIN, column1_rate_pct=D("12.5")))
    assert at_cap.modelled_additional_duty == D("0")


@pytest.mark.parametrize("kw, err", [
    ({"value": "-1"}, ValueError),
    ({"steel_content_value_usd": D("-5")}, ValueError),
    ({"steel_content_value_usd": D("600"), "aluminum_content_value_usd": D("500")}, ValueError),
    ({"hts": "33049910"}, ValueError),
    ({"hts": "3304.99"}, ValueError),
    ({"hts": "3304.99.10.00"}, ValueError),
    ({"value": 1000.0}, TypeError),
])
def test_invalid_inputs_are_rejected(kw, err):
    kw = dict(kw)
    hts = kw.pop("hts", PLAIN)
    value = kw.pop("value", "1000")
    with pytest.raises(err):
        EntryInput(datetime.fromisoformat("2026-03-10T12:00-05:00"), "KR", hts,
                   value if isinstance(value, float) else D(value), "VESSEL", **kw)
    with pytest.raises(ValueError):
        EntryInput(datetime(2026, 3, 10, 12), "KR", PLAIN, D("1000"), "VESSEL")


@pytest.mark.parametrize("at, expected", [
    ("2026-07-24T04:00:59+00:00", "KR_S122_B"),   # 00:00:59 EDT
    ("2026-07-24T04:01:00+00:00", "KR_S301"),     # 00:01 EDT (UTC-4 in summer)
    ("2026-07-24T13:01:00+09:00", "KR_S301"),     # the same instant written in Korea time
    ("2026-02-24T04:59:00+00:00", "KR_DEAL15"),   # 23:59 EST
    ("2026-02-24T05:00:00+00:00", None),          # 00:00 EST (UTC-5 in winter): the cut-off, no reciprocal duty
    ("2025-11-14T04:30:00+00:00", "KR_RECIP15"),  # 23:30 EST on 11-13; would be 00:30 EDT if DST were misapplied
    ("2025-11-14T05:01:00+00:00", "KR_DEAL15"),   # 00:01 EST
])
def test_instants_are_compared_in_utc_across_dst(rs, at, expected):
    r = evaluate(rs, entry(at, PLAIN, column1_rate_pct=D("0")))
    got = [x["rule_id"] for x in r.computed_duties if x["duty_family"] in ("ieepa_reciprocal", "s122_surcharge",
                                                                          "s301")]
    assert got == ([expected] if expected else [])


def test_result_order_does_not_depend_on_mart_row_order(rs):
    shuffled = RuleSet(rules=tuple(reversed(rs.rules)), lists=tuple(reversed(rs.lists)),
                       code_resolution=tuple(reversed(rs.code_resolution)), modelled_families=rs.modelled_families,
                       unmodelled_families=rs.unmodelled_families)
    e = entry("2026-03-10T12:00-05:00", METAL, steel_content_value_usd=D("100"),
              aluminum_content_value_usd=D("200"), components_are_disjoint=True)
    assert dataclasses.asdict(evaluate(rs, e)) == dataclasses.asdict(evaluate(shuffled, e))


def test_amounts_are_raw_decimal_without_rounding(rs):
    r = evaluate(rs, entry("2026-03-10T12:00-05:00", PLAIN, value="1234.567"))
    assert r.modelled_additional_duty == D("123.4567")
    assert isinstance(r.modelled_additional_duty, D)


def test_excluded_rules_are_traceable(rs):
    r = evaluate(rs, entry("2026-03-10T12:00-05:00", PLAIN))
    excluded = {x["rule_id"]: x for x in r.excluded_rule_ids}
    assert excluded["KR_S301"]["reason"] == "before effective_at"
    assert excluded["KR_S232_AL"]["reason"].startswith("not in list")
    assert [x["rule_id"] for x in r.excluded_rule_ids] == sorted(excluded)
