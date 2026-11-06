-- Code-level overrides of a rule's resolution, and whether the code's membership in the rule's exception list was
-- checked for the rule's period (so that a later-revision list is not needed for that code), and the input condition
-- (resolved_when) under which a 'partial' code is resolved for one entry. Without that condition it is not computed.
select segment_id as rule_id, hts8, cast(list_membership_verified as boolean) as list_membership_verified,
       resolution_status, nullif(trim(resolved_when), '') as resolved_when, reason
from {{ ref('rule_code_resolution') }}
