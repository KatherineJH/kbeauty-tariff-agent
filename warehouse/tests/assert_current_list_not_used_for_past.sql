-- An exception list known only from a later revision must not decide membership for an earlier instant: such a
-- rule/code may only be 'uncertain', unless a code-level check for the rule's period exists.
with s as (select * from {{ ref('int_fixture_rule_states') }}),
f as (select fixture_id, cast("at" as timestamptz) as t, left(hts10, 10) as hts8 from {{ ref('boundary_fixtures') }}),
r as (select rule_id, hts_list_id from {{ ref('mart_tariff_rules') }} where hts_scope_kind = 'all_except_list'),
v as (select distinct list_id, valid_from from {{ ref('mart_tariff_rule_lists') }} where list_role = 'exclude'),
c as (select rule_id, hts8 from {{ ref('mart_rule_code_resolution') }} where list_membership_verified)
select s.fixture_id, s.rule_id, s.scope_state
from s
join f using (fixture_id)
join r using (rule_id)
join v on v.list_id = r.hts_list_id
left join c on c.rule_id = s.rule_id and c.hts8 = f.hts8
where f.t < v.valid_from
  and c.rule_id is null
  and s.time_state <> 'none'
  and s.scope_state <> 'uncertain'
