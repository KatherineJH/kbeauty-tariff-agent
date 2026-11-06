"""Deterministic tariff rule engine.

The engine reads the rule marts built by dbt (warehouse/) and does two things only:

1. select_rules: decide, for one entry, the state of every rule (applies / uncertain / not_applicable) from the mart
   fields alone. The decision mirrors the dbt reference model int_fixture_rule_states, and tests require the two to
   agree on every fixture; no legal text is interpreted here.
2. evaluate: compute the modelled additional duties of the applying rules with Decimal arithmetic, keeping every
   missing input, uncertain rule and unmodelled component visible instead of guessing.

Scope of the result: only the duty families present in the marts. Column 1 (MFN / FTA) duty is not modelled, so the
result reports `modelled_additional_duty`, never a total duty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import re

import duckdb

# --------------------------------------------------------------------------------------------------- loading


@dataclass(frozen=True)
class Rule:
    rule_id: str
    action_id: str
    duty_family: str
    effective_at: datetime
    effective_precision: str
    start_uncertain_until: datetime | None
    ends_at: datetime | None
    ends_precision: str | None
    end_uncertain_until: datetime | None
    origin_country: str
    hts_scope_kind: str
    hts_list_id: str | None
    transport_scope: str
    effect_kind: str
    rate_kind: str
    rate_pct: Decimal | None
    value_component: str
    resolution_status: str
    resolution_note: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ListEntry:
    list_id: str
    list_role: str
    code: str
    valid_from: datetime
    valid_to: datetime | None


@dataclass(frozen=True)
class CodeResolution:
    rule_id: str
    hts8: str
    list_membership_verified: bool
    resolution_status: str
    resolved_when: str | None
    reason: str


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[Rule, ...]
    lists: tuple[ListEntry, ...]
    code_resolution: tuple[CodeResolution, ...]
    modelled_families: frozenset[str]
    unmodelled_families: frozenset[str]


def _ts(text: str | None) -> datetime | None:
    return None if text is None else datetime.fromisoformat(text)


def load_rules(db_path: Path | str) -> RuleSet:
    """Read the marts; instants are rendered in UTC as ISO text so no timezone library is needed in Python."""
    con = duckdb.connect(str(db_path), read_only=True)
    con.execute("SET TimeZone = 'UTC'")
    iso = "strftime({c}, '%Y-%m-%dT%H:%M:%S+00:00')"
    rules = con.execute(f"""
        select rule_id, action_id, duty_family, {iso.format(c='effective_at')}, effective_precision,
               {iso.format(c='start_uncertain_until')}, {iso.format(c='ends_at')}, ends_precision,
               {iso.format(c='end_uncertain_until')}, origin_country, hts_scope_kind, hts_list_id, transport_scope,
               effect_kind, rate_kind, cast(rate_pct as varchar), value_component, resolution_status,
               segment_resolution_note, evidence_ids
        from mart_tariff_rules order by rule_id""").fetchall()
    lists = con.execute(f"""
        select list_id, list_role, code, {iso.format(c='valid_from')}, {iso.format(c='valid_to')}
        from mart_tariff_rule_lists order by list_id, list_role, code""").fetchall()
    codes = con.execute("""
        select rule_id, hts8, list_membership_verified, resolution_status, resolved_when, reason
        from mart_rule_code_resolution order by rule_id, hts8""").fetchall()
    families = con.execute("select duty_family, cast(modelled as boolean) from duty_families").fetchall()
    con.close()
    return RuleSet(
        rules=tuple(Rule(r[0], r[1], r[2], _ts(r[3]), r[4], _ts(r[5]), _ts(r[6]), r[7], _ts(r[8]), r[9], r[10], r[11],
                         r[12], r[13], r[14], None if r[15] is None else Decimal(r[15]), r[16], r[17], r[18],
                         tuple(r[19].split(";")) if r[19] else ()) for r in rules),
        lists=tuple(ListEntry(l[0], l[1], l[2], _ts(l[3]), _ts(l[4])) for l in lists),
        code_resolution=tuple(CodeResolution(*c) for c in codes),
        modelled_families=frozenset(f for f, m in families if m),
        unmodelled_families=frozenset(f for f, m in families if not m),
    )


# --------------------------------------------------------------------------------------------------- selection

HTS_FORMAT = re.compile(r"\d{4}\.\d{2}\.\d{2}(\d{2})?")


@dataclass(frozen=True)
class EntryInput:
    entry_at: datetime                      # timezone-aware instant of entry for consumption
    origin_country: str                     # ISO 3166-1 alpha-2, e.g. "KR"
    hts_code: str                           # "3304.99.5000" (10-digit with dots) or "3304.99.50"
    customs_value_usd: Decimal
    transport_mode: str                     # VESSEL / AIR / OTHER / POSTAL
    is_postal: bool = False
    steel_content_value_usd: Decimal | None = None      # None = not provided (never assumed)
    aluminum_content_value_usd: Decimal | None = None   # None = not provided (never assumed)
    column1_rate_pct: Decimal | None = None             # column 1 rate, needed by total_with_column1 rules only
    components_are_disjoint: bool | None = None         # True = steel and aluminum values are disjoint parts of
                                                        # the customs value (declared by the user, never assumed)

    def __post_init__(self):
        if self.entry_at.tzinfo is None:
            raise ValueError("entry_at must be timezone-aware")
        if not HTS_FORMAT.fullmatch(self.hts_code):
            raise ValueError(f"unsupported HTS code format {self.hts_code!r}; use 'NNNN.NN.NN' or 'NNNN.NN.NNNN'")
        for name in ("customs_value_usd", "steel_content_value_usd", "aluminum_content_value_usd",
                     "column1_rate_pct"):
            v = getattr(self, name)
            if v is not None and not isinstance(v, Decimal):
                raise TypeError(f"{name} must be Decimal, not {type(v).__name__}")
            if v is not None and (not v.is_finite() or v < 0):
                raise ValueError(f"{name} must be a finite non-negative amount")
        metal = [v for v in (self.steel_content_value_usd, self.aluminum_content_value_usd) if v is not None]
        if sum(metal, Decimal("0")) > self.customs_value_usd:
            raise ValueError("steel + aluminum content value exceeds the customs value")


@dataclass(frozen=True)
class RuleState:
    rule: Rule
    state: str                  # applies | uncertain | not_applicable
    reason: str                 # why (time / scope / list)
    resolution_status: str      # code-level if present, else the rule's (before any entry condition)
    resolution_reason: str | None
    resolved_when: str | None   # input condition that resolves a 'partial' code for one entry


def _hts8(code: str) -> str:
    return code[:10]


def select_rules(rs: RuleSet, e: EntryInput) -> list[RuleState]:
    t = e.entry_at
    transport = "POSTAL" if (e.is_postal or e.transport_mode == "POSTAL") else "NON_POSTAL"
    hts8, hts10 = _hts8(e.hts_code), e.hts_code
    codes = {(c.rule_id, c.hts8): c for c in rs.code_resolution}
    out = []
    for r in rs.rules:
        # time (half-open; a date-precision boundary day is uncertain as a whole)
        if t < r.effective_at:
            time_state, time_reason = "not_applicable", "before effective_at"
        elif r.start_uncertain_until is not None and t < r.start_uncertain_until:
            time_state, time_reason = "uncertain", f"start known only by day ({r.effective_at.date()} ET day)"
        elif r.ends_at is not None and r.end_uncertain_until is None and t >= r.ends_at:
            time_state, time_reason = "not_applicable", "at or after ends_at"
        elif r.end_uncertain_until is not None and t >= r.end_uncertain_until:
            time_state, time_reason = "not_applicable", "after the end day"
        elif r.end_uncertain_until is not None and t >= r.ends_at:
            time_state, time_reason = "uncertain", "end known only by day"
        else:
            time_state, time_reason = "applies", "within period"
        # scope
        cr = codes.get((r.rule_id, hts8))
        if r.origin_country not in (e.origin_country, "ALL"):
            scope_state, scope_reason = "not_applicable", f"origin {e.origin_country} not in {r.origin_country}"
        elif r.transport_scope not in (transport, "ALL"):
            scope_state, scope_reason = "not_applicable", f"transport {transport} not in {r.transport_scope}"
        elif r.hts_scope_kind == "all":
            scope_state, scope_reason = "applies", "all HTS codes"
        elif r.hts_scope_kind == "list":
            hit = any(l.list_id == r.hts_list_id and l.list_role == "include" and l.code in (hts8, hts10)
                      for l in rs.lists)
            scope_state, scope_reason = ("applies", f"in list {r.hts_list_id}") if hit else \
                ("not_applicable", f"not in list {r.hts_list_id}")
        elif cr is not None and cr.list_membership_verified:
            scope_state, scope_reason = "applies", f"not excepted (code checked for the period: {cr.reason})"
        else:
            valid = [l for l in rs.lists if l.list_id == r.hts_list_id and l.list_role == "exclude"
                     and l.valid_from <= t and (l.valid_to is None or t < l.valid_to)]
            if valid:
                listed = any(l.code in (hts8, hts10) for l in valid)
                scope_state, scope_reason = ("not_applicable", f"excepted by list {r.hts_list_id}") if listed else \
                    ("applies", f"not in exception list {r.hts_list_id}")
            else:
                scope_state, scope_reason = "uncertain", (f"exception list {r.hts_list_id} is known only from a later "
                                                          f"revision; membership at this instant unverified")
        if "not_applicable" in (time_state, scope_state):
            state = "not_applicable"
            reason = time_reason if time_state == "not_applicable" else scope_reason
        elif "uncertain" in (time_state, scope_state):
            state = "uncertain"
            reason = time_reason if time_state == "uncertain" else scope_reason
        else:
            state, reason = "applies", f"{time_reason}; {scope_reason}"
        out.append(RuleState(r, state, reason, cr.resolution_status if cr else r.resolution_status,
                             cr.reason if cr else r.resolution_note, cr.resolved_when if cr else None))
    return out


# --------------------------------------------------------------------------------------------------- computation

FAMILY_ORDER = {"s232_derivative": 0, "ieepa_reciprocal": 1, "s122_surcharge": 2, "s301": 3, "de_minimis": 9}

# Status of a result. "computed_modelled_only" means every applying rule of the MODELLED duty families was computed;
# it says nothing about families that are not modelled (listed in not_modelled_families, e.g. MFN).
STATUSES = ("computed_modelled_only", "incomplete", "refused_uncertain")


@dataclass
class Result:
    status: str
    coverage: str                                 # always "modelled_families_only"
    not_modelled_families: list[str]
    base_value: Decimal
    computed_duties: list[dict] = field(default_factory=list)
    modelled_additional_duty: Decimal | None = None     # raw Decimal, no rounding (no rounding rule is modelled)
    unresolved_components: list[dict] = field(default_factory=list)
    applied_rule_ids: list[str] = field(default_factory=list)
    excluded_rule_ids: list[dict] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


def _metal_value(e: EntryInput, component: str) -> Decimal | None:
    return e.aluminum_content_value_usd if component == "ALUMINUM_CONTENT" else e.steel_content_value_usd


def _condition_met(condition: str | None, e: EntryInput) -> bool:
    """Input conditions that make a 'partial' code resolved for one entry (rule_code_resolution.resolved_when)."""
    if condition == "metal_components_disjoint":
        return (e.components_are_disjoint is True and e.steel_content_value_usd is not None
                and e.aluminum_content_value_usd is not None)
    return False


def evaluate(rs: RuleSet, e: EntryInput) -> Result:
    states = select_rules(rs, e)
    res = Result(status="computed_modelled_only", coverage="modelled_families_only",
                 not_modelled_families=sorted(rs.unmodelled_families), base_value=e.customs_value_usd)
    applying = sorted((s for s in states if s.state == "applies"),
                      key=lambda s: (FAMILY_ORDER.get(s.rule.duty_family, 5), s.rule.rule_id))
    uncertain = sorted((s for s in states if s.state == "uncertain"), key=lambda s: s.rule.rule_id)
    res.excluded_rule_ids = sorted(({"rule_id": s.rule.rule_id, "state": s.state, "reason": s.reason}
                                    for s in states if s.state != "applies"), key=lambda x: x["rule_id"])
    for fam in sorted(rs.unmodelled_families):
        res.unresolved_components.append({"kind": "not_modelled", "duty_family": fam,
                                          "detail": "this duty family is not in the rule marts; excluded from "
                                                    "modelled_additional_duty"})
    res.applied_rule_ids = [s.rule.rule_id for s in applying]
    if uncertain:
        res.status = "refused_uncertain"
        for s in uncertain:
            needed = ("the exact time the change took effect on that day (the sources give only the date)"
                      if "known only by day" in s.reason else
                      "the exception list in force at the entry instant (an HTS revision of that period)")
            res.unresolved_components.append({"kind": "uncertain", "rule_id": s.rule.rule_id,
                                              "duty_family": s.rule.duty_family, "detail": s.reason,
                                              "needed": needed})
        res.trace.append(f"refused: {len(uncertain)} rule(s) uncertain at {e.entry_at.isoformat()}; no duty computed")
        return res

    metal_rules = [s for s in applying if s.rule.value_component in ("ALUMINUM_CONTENT", "STEEL_CONTENT")]
    total = Decimal("0")
    incomplete = False
    for s in applying:
        r = s.rule
        for x in r.evidence_ids:
            if x not in res.evidence_ids:
                res.evidence_ids.append(x)
        if r.effect_kind != "duty":
            res.trace.append(f"{r.rule_id}: effect {r.effect_kind} (no duty amount)")
            continue
        # resolution: only 'resolved' is computed; a 'partial' code is resolved only when its input condition holds
        if s.resolution_status != "resolved" and not _condition_met(s.resolved_when, e):
            incomplete = True
            res.unresolved_components.append({
                "kind": "partial_rule", "rule_id": r.rule_id, "detail": s.resolution_reason or "partial",
                "needed": ("declared steel and aluminum content values and components_are_disjoint=True"
                           if s.resolved_when == "metal_components_disjoint" else "not resolvable from the inputs")})
            res.trace.append(f"{r.rule_id}: not computed, resolution '{s.resolution_status}'")
            continue
        # base
        if r.value_component == "FULL_VALUE":
            base = e.customs_value_usd
        elif r.value_component in ("ALUMINUM_CONTENT", "STEEL_CONTENT"):
            base = _metal_value(e, r.value_component)
            if base is None:
                incomplete = True
                res.unresolved_components.append({"kind": "missing_input", "rule_id": r.rule_id,
                                                  "detail": f"{r.value_component.lower()} value required; the "
                                                            f"customs value is not used as a substitute"})
                res.trace.append(f"{r.rule_id}: not computed, {r.value_component} value missing")
                continue
        elif r.value_component == "FULL_VALUE_LESS_232_METAL_CONTENT":
            values = [_metal_value(e, m.rule.value_component) for m in metal_rules]
            if any(v is None for v in values):
                incomplete = True
                res.unresolved_components.append({"kind": "missing_input", "rule_id": r.rule_id,
                                                  "detail": "base is the value less the 232 metal content; metal "
                                                            "content value missing"})
                res.trace.append(f"{r.rule_id}: not computed, metal content needed to reduce the base")
                continue
            if len(metal_rules) > 1 and e.components_are_disjoint is not True:
                incomplete = True
                res.unresolved_components.append({"kind": "missing_input", "rule_id": r.rule_id,
                                                  "detail": "two metal contents are deducted; components_are_disjoint "
                                                            "must be declared True"})
                res.trace.append(f"{r.rule_id}: not computed, metal components not declared disjoint")
                continue
            base = e.customs_value_usd - sum(values, Decimal("0"))
        else:
            raise ValueError(f"unknown value component {r.value_component}")
        # rate
        if r.rate_kind == "additional_ad_valorem":
            pct = r.rate_pct
        elif r.rate_kind == "total_with_column1":
            if e.column1_rate_pct is None:
                incomplete = True
                res.unresolved_components.append({"kind": "not_modelled", "rule_id": r.rule_id,
                                                  "duty_family": "mfn",
                                                  "detail": f"rule sets column 1 + this duty to {r.rate_pct}%; the "
                                                            f"column 1 rate is not modelled and was not given"})
                res.trace.append(f"{r.rule_id}: not computed, column 1 rate needed ({r.rate_kind})")
                continue
            # floor at zero: both sources say the added duty is zero when column 1 is at or above the cap
            pct = max(r.rate_pct - e.column1_rate_pct, Decimal("0"))
        else:
            raise ValueError(f"unexpected rate kind {r.rate_kind} for a duty")
        duty = base * pct / Decimal("100")
        total += duty
        res.computed_duties.append({"rule_id": r.rule_id, "duty_family": r.duty_family,
                                    "order": len(res.computed_duties) + 1, "value_component": r.value_component,
                                    "base_usd": base, "rate_kind": r.rate_kind, "rate_pct_applied": pct,
                                    "duty_usd": duty, "evidence_ids": list(r.evidence_ids),
                                    "resolved_by_condition": (s.resolved_when if s.resolution_status != "resolved"
                                                              else None)})
        res.trace.append(f"{r.rule_id}: {r.rate_kind} {pct}% x {r.value_component} {base} = {duty}")
    if incomplete:
        res.status = "incomplete"
        res.trace.append("incomplete: some applying rules were not computed; no modelled total reported")
    else:
        res.modelled_additional_duty = total
        res.trace.append(f"modelled additional duty {total} (not modelled: {', '.join(res.not_modelled_families)})")
    return res
