-- The hand-written fixtures (warehouse/seeds/boundary_fixtures.csv) must match the reference applicability exactly:
-- the set of applying rules, the set of uncertain rules, and the set of applying rules that may be auto-computed.
with s as (select * from {{ ref('int_fixture_rule_states') }}),
actual as (
    select fixture_id,
           coalesce(string_agg(rule_id, ';' order by rule_id) filter (where state = 'applies'), '') as applies,
           coalesce(string_agg(rule_id, ';' order by rule_id) filter (where state = 'uncertain'), '') as uncertain,
           coalesce(string_agg(rule_id, ';' order by rule_id)
                    filter (where state = 'applies' and effective_resolution_status = 'resolved'), '') as auto
    from s group by fixture_id
),
expected as (
    select fixture_id, coalesce(expected_applies, '') as applies, coalesce(expected_uncertain, '') as uncertain,
           coalesce(expected_auto, '') as auto
    from {{ ref('boundary_fixtures') }}
)
select e.fixture_id, e.applies as exp_applies, a.applies, e.uncertain as exp_uncertain, a.uncertain,
       e.auto as exp_auto, a.auto
from expected e
left join actual a using (fixture_id)
where a.fixture_id is null or e.applies <> a.applies or e.uncertain <> a.uncertain or e.auto <> a.auto
