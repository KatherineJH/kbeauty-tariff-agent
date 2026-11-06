-- Per duty family at a fixture instant: applies if any rule of the family applies, uncertain if none applies and one
-- is uncertain, none otherwise; not_modelled for families without rules (MFN). Keeps "no surcharge in the
-- one-minute gap" from being read as "no duty of any kind".
with s as (select * from {{ ref('int_fixture_rule_states') }}),
fam as (select duty_family, cast(modelled as boolean) as modelled from {{ ref('duty_families') }}),
actual as (
    select ff.fixture_id, ff.duty_family,
           case when not fam.modelled then 'not_modelled'
                when bool_or(s.state = 'applies') then 'applies'
                when bool_or(s.state = 'uncertain') then 'uncertain'
                else 'none' end as state
    from {{ ref('family_fixtures') }} ff
    join fam using (duty_family)
    left join s on s.fixture_id = ff.fixture_id and s.duty_family = ff.duty_family
    group by ff.fixture_id, ff.duty_family, fam.modelled
)
select ff.fixture_id, ff.duty_family, ff.expected_state, a.state
from {{ ref('family_fixtures') }} ff
join actual a using (fixture_id, duty_family)
where ff.expected_state <> a.state
