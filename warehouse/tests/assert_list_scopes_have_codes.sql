-- Every list named by a rule scope has codes with the matching role.
select r.rule_id, r.hts_scope
from {{ ref('mart_tariff_rules') }} r
where r.hts_scope_kind <> 'all'
  and not exists (
      select 1 from {{ ref('mart_tariff_rule_lists') }} l
      where l.list_id = r.hts_list_id
        and l.list_role = case r.hts_scope_kind when 'list' then 'include' else 'exclude' end
  )
