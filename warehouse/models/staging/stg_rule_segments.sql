-- Machine-readable rule segments: one action applied to one origin / HTS scope / transport / value component over
-- the half-open period [starts_at, ends_at). ends_at NULL = open-ended. rate_pct NULL = not a rate (rate_kind 'none').
-- A boundary with precision 'date' is known only by its day: starts_at / ends_at hold 00:00 America/New_York of that
-- day for ordering only, and the whole day [day, day + 1) is a boundary-uncertain window.
select
    segment_id,
    action_id,
    duty_family,
    origin_country,
    hts_scope,
    case when hts_scope like 'LIST:%' then 'list'
         when hts_scope like 'ALL_EXCEPT_LIST:%' then 'all_except_list'
         else 'all' end                                               as hts_scope_kind,
    nullif(split_part(hts_scope, ':', 2), '')                         as hts_list_id,
    transport_scope,
    effect_kind,
    value_component,
    nullif(trim(starts_at), '')                                       as starts_at_source,
    {{ parse_ts('starts_at') }}                                       as starts_at,
    starts_precision,
    case when starts_precision = 'date' then cast(trim(starts_at) as date) end as starts_on,
    nullif(trim(ends_at), '')                                         as ends_at_source,
    {{ parse_ts('ends_at') }}                                         as ends_at,
    nullif(ends_precision, '')                                        as ends_precision,
    case when ends_precision = 'date' then cast(trim(ends_at) as date) end as ends_on,
    rate_kind,
    cast(nullif(trim(rate_pct), '') as decimal(6, 3))                 as rate_pct,
    segment_resolution_status,
    nullif(trim(segment_resolution_note), '')                         as segment_resolution_note,
    segment_note
from {{ ref('rule_segments') }}
