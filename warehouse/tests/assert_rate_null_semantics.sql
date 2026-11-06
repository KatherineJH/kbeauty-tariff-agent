-- rate_pct is NULL exactly when rate_kind = 'none' (not a rate); a rate row needs a value.
select segment_id, rate_kind, rate_pct
from {{ ref('stg_rule_segments') }}
where (rate_kind = 'none') <> (rate_pct is null)
