-- A row that is not both quote_checked and resolved must say what is missing: open_issues for actions,
-- segment_resolution_note for segments, reason for code-level overrides. For resolved rows these are optional notes.
select 'action' as level, action_id as id
from {{ ref('stg_regulatory_actions') }}
where (evidence_status <> 'quote_checked' or resolution_status <> 'resolved') and open_issues is null
union all
select 'segment', segment_id
from {{ ref('stg_rule_segments') }}
where segment_resolution_status <> 'resolved' and segment_resolution_note is null
union all
select 'code', segment_id || ':' || hts8
from {{ ref('rule_code_resolution') }}
where resolution_status <> 'resolved' and coalesce(trim(reason), '') = ''
