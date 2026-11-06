-- HTS codes of list-scoped rules (role 'include', LIST:...) and of exception lists (role 'exclude',
-- ALL_EXCEPT_LIST:...), each with the revision it was read from and the period it is valid evidence for.
-- temporal_status 'current_revision_only': the list may decide membership only for instants >= valid_from.
-- Matching is by exact 8-digit subheading or exact 10-digit line, never by prefix.
with versions as (
    select list_id, list_role, source_revision,
           {{ parse_ts('valid_from') }} as valid_from, {{ parse_ts('valid_to') }} as valid_to, temporal_status
    from {{ ref('list_versions') }}
),
codes as (
    select list_id, 'include' as list_role, hts8 as code, 8 as digits, source from {{ ref('rule_hts_lists') }}
    union all
    select list_id, 'exclude', code, digits,
           'HTS Rev. 22 ' || subdivision || ' (PDF p. ' || pdf_page || ', ' || printed_page || ')'
    from {{ ref('stg_hts_exception_codes') }}
)
select c.list_id, c.list_role, c.code, c.digits, c.source,
       v.source_revision, v.valid_from, v.valid_to, v.temporal_status
from codes c
join versions v using (list_id, list_role)
