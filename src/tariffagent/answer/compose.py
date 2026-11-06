"""Structured cited answer from a rule-engine result (deterministic; no LLM, no retrieval).

engine result -> rule ids -> claims (rate, period, scope, exclusion, stacking, resolution condition)
             -> claim-scoped verified citations (warehouse/seeds/rule_citations.csv)

Rules:
- The engine's status, amounts and unresolved components are carried over unchanged. incomplete and
  refused_uncertain never produce a figure or a definite sentence about the duty.
- computed_modelled_only is worded as the modelled additional duty of the modelled families, never a total duty.
- Every claim is linked to the citations of its own role; a claim whose role has no citation fails composition.
- A duty computed through a resolution condition carries a resolution_condition claim with its citations.
- Order is fixed by the engine's computation order, a fixed claim order and citation ids.
- Retrieved context, if given, goes to `background` only; it cannot change any statement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tariffagent.answer.citations import Citation, CitationError
from tariffagent.rules.engine import Result, RuleSet


@dataclass
class CitedAnswer:
    status: str
    coverage: str
    not_modelled_families: list[str]
    modelled_additional_duty: str | None
    headline: str
    statements: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    caveats: list[dict] = field(default_factory=list)
    excluded_rules: list[dict] = field(default_factory=list)
    background: list[dict] = field(default_factory=list)


def _needed(result: Result) -> list[str]:
    seen = []
    for u in result.unresolved_components:
        if u["kind"] == "not_modelled" and "rule_id" not in u:
            continue
        need = u.get("needed") or u["detail"]
        if need not in seen:
            seen.append(need)
    return seen


def compose(result: Result, rules: RuleSet, citations: dict[str, list[Citation]],
            context: list[dict] | None = None) -> CitedAnswer:
    by_rule = {r.rule_id: r for r in rules.rules}
    not_modelled = ", ".join(result.not_modelled_families) or "none"
    if result.status == "computed_modelled_only":
        families = sorted({d["duty_family"] for d in result.computed_duties})
        headline = (f"Modelled additional duty: {result.modelled_additional_duty} USD "
                    f"(modelled duty families: {', '.join(families) or 'none applying'}; not modelled: "
                    f"{not_modelled}). This is not the total duty.")
    elif result.status == "incomplete":
        headline = "No modelled additional duty is stated: the inputs are not sufficient. Needed: " + \
            "; ".join(_needed(result))
    elif result.status == "refused_uncertain":
        headline = "Not determinable from the sources at this instant. Needed: " + "; ".join(_needed(result))
    else:
        raise ValueError(f"unknown engine status {result.status}")

    answer = CitedAnswer(status=result.status, coverage=result.coverage,
                         not_modelled_families=list(result.not_modelled_families),
                         modelled_additional_duty=(str(result.modelled_additional_duty)
                                                   if result.status == "computed_modelled_only" else None),
                         headline=headline, excluded_rules=list(result.excluded_rule_ids))
    used: dict[str, Citation] = {}

    def claim(rule_id: str, role: str, text: str) -> dict:
        cites = [c for c in citations.get(rule_id, []) if c.claim_role == role]
        if not cites:
            raise CitationError(f"rule {rule_id}: no {role} citation for the claim {text!r}")
        for c in cites:
            used.setdefault(c.citation_id, c)
        return {"claim_role": role, "text": text, "citation_ids": [c.citation_id for c in cites]}

    def period_claims(rule) -> list[dict]:
        out = [claim(rule.rule_id, "effective_start",
                     f"in force from {rule.effective_at.isoformat()} ({rule.effective_precision} precision)")]
        if rule.ends_at is not None:
            out.append(claim(rule.rule_id, "effective_end",
                             f"ends at {rule.ends_at.isoformat()} ({rule.ends_precision} precision)"))
        return out

    computed = {d["rule_id"]: d for d in result.computed_duties}
    not_computed = {u["rule_id"]: u for u in result.unresolved_components
                    if u.get("rule_id") and u["kind"] in ("missing_input", "partial_rule", "not_modelled")}
    order = [d["rule_id"] for d in result.computed_duties] + \
        [r for r in result.applied_rule_ids if r not in computed]
    for n, rule_id in enumerate(order, start=1):
        rule = by_rule[rule_id]
        claims = [claim(rule_id, "authority", f"legal authority of {rule.action_id}")]
        if rule_id in computed:
            d = computed[rule_id]
            kind = "computed_duty"
            text = (f"{rule_id} ({rule.duty_family}): {d['rate_pct_applied']}% ({d['rate_kind']}) of "
                    f"{d['value_component']} {d['base_usd']} USD = {d['duty_usd']} USD")
            claims.append(claim(rule_id, "rate", f"rate {rule.rate_pct}% ({rule.rate_kind})"))
        elif rule.effect_kind != "duty":
            kind = "effect"
            text = f"{rule_id} ({rule.duty_family}): {rule.effect_kind.replace('_', ' ')} (no duty amount)"
        else:
            kind = "not_computed"
            u = not_computed.get(rule_id, {})
            text = f"{rule_id} ({rule.duty_family}) applies but was not computed: {u.get('detail', 'not computed')}"
            if rule.rate_kind != "none":
                claims.append(claim(rule_id, "rate", f"rate {rule.rate_pct}% ({rule.rate_kind})"))
        claims += period_claims(rule)
        claims.append(claim(rule_id, "scope", f"origin {rule.origin_country}, HTS scope {rule.hts_scope_kind}, "
                                              f"transport {rule.transport_scope}"))
        if rule.hts_scope_kind == "all_except_list":
            claims.append(claim(rule_id, "exclusion", f"except codes in list {rule.hts_list_id}"))
        if rule.value_component != "FULL_VALUE" and rule.value_component != "NA" or rule.rate_kind == "total_with_column1":
            claims.append(claim(rule_id, "stacking", f"value component {rule.value_component}; rate kind "
                                                     f"{rule.rate_kind}"))
        if rule_id in computed and computed[rule_id].get("resolved_by_condition"):
            claims.append(claim(rule_id, "resolution_condition",
                                f"computed because {computed[rule_id]['resolved_by_condition']} holds for this "
                                f"entry (declared steel and aluminum values, disjoint)"))
        answer.statements.append({"statement_id": f"S{n}", "kind": kind, "rule_ids": [rule_id], "text": text,
                                  "claims": claims})
    for u in result.unresolved_components:
        caveat = {"kind": u["kind"], "detail": u["detail"]}
        for k in ("needed", "rule_id", "duty_family"):
            if k in u:
                caveat[k] = u[k]
        if u["kind"] == "uncertain":
            rule = by_rule[u["rule_id"]]
            caveat["claims"] = period_claims(rule)
        answer.caveats.append(caveat)
    answer.citations = [{"citation_id": c.citation_id, "rule_id": c.rule_id, "claim_role": c.claim_role,
                         "evidence_id": c.evidence_id, "source_file": c.source_file,
                         "physical_page": c.physical_page, "printed_page": c.printed_page, "quote": c.quote,
                         "file_sha256": c.file_sha256}
                        for c in sorted(used.values(), key=lambda c: c.citation_id)]
    if context:
        answer.background = [{"source": p.get("source"), "text": p.get("text"),
                              "role": "background only; does not change any statement"} for p in context]
    return answer
