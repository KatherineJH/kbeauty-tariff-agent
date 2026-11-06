-- Declared relations between actions: action b is named, as a whole identifier, in a relation column of action a.
with actions as (select * from {{ ref('stg_regulatory_actions') }}),
texts as (
    select
        action_id,
        concat_ws(' ', supersedes, superseded_by, amends, ends_rule, stacking_rule, unaffected_actions, open_issues)
            as relation_text
    from actions
)
select t.action_id as from_action, a.action_id as to_action
from texts t
join actions a
  on a.action_id <> t.action_id
 and regexp_matches(t.relation_text, '(^|[^A-Za-z0-9_])' || a.action_id || '($|[^A-Za-z0-9_])')
