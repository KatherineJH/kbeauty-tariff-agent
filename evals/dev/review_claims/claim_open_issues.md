# Claim open issues (found during the claim review)

The claim catalog (`evals/dev/claims.csv`, `claim_components.csv`) and the sealed queue are not changed while the
review is running. Issues found during the review are recorded here and resolved after it, in a new query/claim
version; earlier runs and judgements are never overwritten.

## CI-001 dq07 c1: one effective date does not describe the rule's effective structure

- Found: 2026-11-09, stage 1 review, `R-1503327472` (dq07_en, compliance-extension notice fr:2026-21600).
- Chunk: "The suspension of the de minimis administrative exemption took effect on June 24, 2026. The remainder of
  the interim final rule was effective on July 24, 2026."
- Problem: `dq07_en.c1` / `dq07_ko.c1` state a single date ("The interim final rule suspending the de minimis
  exemption for mail shipments is effective on July 24, 2026"). The official text separates two dates:
  - the de minimis suspension (amendatory instruction for 19 CFR 145.31): 2026-06-24
  - the remainder of the interim final rule: 2026-07-24
  An exact answer must distinguish both.
- Handling in the current review (v1 catalog, unchanged):
  - stage 1: `R-1503327472` recorded as relevant, with the reason above.
  - stage 2: units that state the July 24 date for the remainder of the rule while also stating the June 24
    suspension date (or the "except amendatory instruction 4" carve-out) support the current c1 as `partial`, not
    `complete`. `R-1503327472` c1 = partial.
- After the review: create `dq07_v2` as a new query/claim version with the two dates as separate components
  (suspension effective 2026-06-24; remainder of the interim final rule effective 2026-07-24), and evaluate it as a
  new run. The v1 claims, the sealed queue, the v1 judgements and existing runs stay as they are.
