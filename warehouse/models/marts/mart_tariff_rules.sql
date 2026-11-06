-- Minimal input for the rule engine; one row per rule segment over [effective_at, ends_at).
-- No duty totals are computed here. Resolution is per segment (resolution_status) and may be overridden per HTS code
-- (mart_rule_code_resolution); only 'resolved' may be auto-computed. A date-precision boundary is not a cut-off:
-- between effective_at and start_uncertain_until (and between ends_at and end_uncertain_until) applicability is
-- uncertain and must not be computed.
select
    p.segment_id                                                      as rule_id,
    p.action_id,
    p.duty_family,
    p.effective_at_source,
    p.starts_at                                                       as effective_at,
    p.starts_precision                                                as effective_precision,
    p.starts_on                                                       as effective_on,
    p.start_uncertain_until,
    p.ends_at_source,
    p.ends_at,
    p.ends_precision,
    p.ends_on,
    p.end_uncertain_until,
    p.origin_country,
    p.hts_scope,
    p.hts_scope_kind,
    p.hts_list_id,
    p.transport_scope,
    p.effect_kind,
    p.rate_kind,
    p.rate_pct,
    p.value_component,
    p.stacking_rule,
    p.evidence_status,
    p.resolution_status,
    p.resolution_status = 'resolved'                                  as auto_compute_allowed_default,
    p.segment_resolution_note,
    e.evidence_ids
from (
    select *, starts_at_source as effective_at_source from {{ ref('int_regulatory_action_periods') }}
) p
left join (
    select action_id, string_agg(evidence_id, ';' order by evidence_id) as evidence_ids
    from {{ ref('action_evidence') }}
    group by action_id
) e using (action_id)
