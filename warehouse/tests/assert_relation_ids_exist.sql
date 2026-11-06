-- Identifiers written in supersedes / superseded_by / unaffected_actions / ends_rule must name existing actions.
with refs as (
    select action_id, col, unnest(regexp_extract_all(txt, '[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+')) as ref_id
    from (
        select action_id, 'supersedes' as col, supersedes as txt from {{ ref('stg_regulatory_actions') }}
        union all select action_id, 'superseded_by', superseded_by from {{ ref('stg_regulatory_actions') }}
        union all select action_id, 'unaffected_actions', unaffected_actions from {{ ref('stg_regulatory_actions') }}
        union all select action_id, 'ends_rule', ends_rule from {{ ref('stg_regulatory_actions') }}
    )
)
select r.*
from refs r
left join {{ ref('stg_regulatory_actions') }} a on a.action_id = r.ref_id
where a.action_id is null
