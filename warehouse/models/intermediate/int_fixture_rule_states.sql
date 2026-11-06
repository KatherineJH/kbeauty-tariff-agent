-- Reference applicability for the hand-written fixtures: state of every rule at every fixture instant.
--   time:  none before effective_at or at/after the end; 'uncertain' inside a date-precision boundary window
--   scope: origin and transport must match (VESSEL/AIR/OTHER count as NON_POSTAL); list rules need the code in the
--          include list; exception-list rules use the list only if the instant is within the list's validity, or a
--          code-level check (list_membership_verified) exists; otherwise membership is 'uncertain'
--   state: none if time or scope is none; uncertain if either is uncertain; else applies
--   auto:  applies and the resolution (code-level if present, else the rule's) is 'resolved'
with f as (
    select fixture_id, cast("at" as timestamptz) as t, origin_country, hts10, left(hts10, 10) as hts8,
           case when transport = 'POSTAL' then 'POSTAL' else 'NON_POSTAL' end as transport_class
    from {{ ref('boundary_fixtures') }}
),
r as (select * from {{ ref('mart_tariff_rules') }}),
l as (select * from {{ ref('mart_tariff_rule_lists') }}),
c as (select * from {{ ref('mart_rule_code_resolution') }}),
pairs as (
    select f.fixture_id, f.t, f.hts8, f.hts10, r.*,
           case
               when f.t < r.effective_at then 'none'
               when r.start_uncertain_until is not null and f.t < r.start_uncertain_until then 'uncertain'
               when r.ends_at is not null and r.end_uncertain_until is null and f.t >= r.ends_at then 'none'
               when r.end_uncertain_until is not null and f.t >= r.end_uncertain_until then 'none'
               when r.end_uncertain_until is not null and f.t >= r.ends_at then 'uncertain'
               else 'applies'
           end as time_state,
           r.origin_country in (f.origin_country, 'ALL')
             and r.transport_scope in (f.transport_class, 'ALL') as origin_transport_ok
    from f cross join r
),
scoped as (
    select p.*,
           cv.list_membership_verified, cv.resolution_status as code_resolution_status,
           case
               when not p.origin_transport_ok then 'none'
               when p.hts_scope_kind = 'all' then 'applies'
               when p.hts_scope_kind = 'list' then
                   case when exists (select 1 from l where l.list_id = p.hts_list_id and l.list_role = 'include'
                                       and l.code in (p.hts8, p.hts10)) then 'applies' else 'none' end
               when coalesce(cv.list_membership_verified, false) then 'applies'
               when exists (select 1 from l where l.list_id = p.hts_list_id and l.list_role = 'exclude'
                              and l.valid_from <= p.t and (l.valid_to is null or p.t < l.valid_to)) then
                   case when exists (select 1 from l where l.list_id = p.hts_list_id and l.list_role = 'exclude'
                                       and l.code in (p.hts8, p.hts10)) then 'none' else 'applies' end
               else 'uncertain'
           end as scope_state
    from pairs p
    left join c cv on cv.rule_id = p.rule_id and cv.hts8 = p.hts8
)
select fixture_id, rule_id, duty_family, time_state, scope_state,
       case when time_state = 'none' or scope_state = 'none' then 'none'
            when time_state = 'uncertain' or scope_state = 'uncertain' then 'uncertain'
            else 'applies' end as state,
       coalesce(code_resolution_status, resolution_status) as effective_resolution_status
from scoped
