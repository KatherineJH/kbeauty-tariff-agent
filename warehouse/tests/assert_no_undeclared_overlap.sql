-- Two rule segments that can apply to the same entry at the same instant, with the same legal basis and kind of
-- effect, must belong to the same action or to actions with a declared relation (int_action_relations).
with p as (select * from {{ ref('int_regulatory_action_periods') }}),
lists as (select * from {{ ref('mart_tariff_rule_lists') }} where list_role = 'include'),
pairs as (
    select a.segment_id as seg_a, b.segment_id as seg_b, a.action_id as act_a, b.action_id as act_b,
           a.hts_scope_kind as kind_a, b.hts_scope_kind as kind_b, a.hts_list_id as list_a, b.hts_list_id as list_b
    from p a
    join p b on a.segment_id < b.segment_id
    where a.effect_kind = b.effect_kind
      and a.legal_basis_key = b.legal_basis_key
      and (a.origin_country = b.origin_country or 'ALL' in (a.origin_country, b.origin_country))
      and (a.transport_scope = b.transport_scope or 'ALL' in (a.transport_scope, b.transport_scope))
      and a.starts_at < coalesce(b.ends_at, 'infinity'::timestamptz)
      and b.starts_at < coalesce(a.ends_at, 'infinity'::timestamptz)
)
select pr.*
from pairs pr
where pr.act_a <> pr.act_b
  -- two include lists overlap only if they share a code
  and not (pr.kind_a = 'list' and pr.kind_b = 'list' and not exists (
      select 1 from lists la join lists lb on la.code = lb.code
      where la.list_id = pr.list_a and lb.list_id = pr.list_b))
  and not exists (
      select 1 from {{ ref('int_action_relations') }} r
      where (r.from_action = pr.act_a and r.to_action = pr.act_b)
         or (r.from_action = pr.act_b and r.to_action = pr.act_a))
