-- Every period is half-open [start, end): the end, when present, must be strictly after the start.
select 'segment' as kind, segment_id as id, starts_at, ends_at
from {{ ref('stg_rule_segments') }}
where ends_at is not null and ends_at <= starts_at
union all
select 'action', action_id, effective_at, ends_at
from {{ ref('stg_regulatory_actions') }}
where effective_at is not null and ends_at is not null and ends_at <= effective_at
