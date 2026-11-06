-- Code-level overrides of a rule's resolution, and whether the code's membership in the rule's exception list was
-- checked for the rule's period (so that a later-revision list is not needed for that code).
select segment_id as rule_id, hts8, cast(list_membership_verified as boolean) as list_membership_verified,
       resolution_status, reason
from {{ ref('rule_code_resolution') }}
