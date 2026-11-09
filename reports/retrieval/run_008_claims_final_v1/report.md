# run_008: claim-based B1/B2 comparison on run_007 (qrels = final/v1, human_assisted)

Rankings: B1 = BM25 top 10 of run_003; B2 = b2_heading_v4 top 10 of run_007. Qrels: `evals/dev/review_claims/final/v1`
only (527 items, 1,011 component rows, human_assisted). The sealed Claude judgements were not used. Claim catalog:
v1 as sealed. Script: `scripts/eval_claims_final.py`; per-query rows: `claim_per_query.csv`; paired deltas:
`claim_paired_delta.csv`; all numbers: `claim_metrics.json`; hashes: `manifest.json`. Every top-10 unit of both
systems is judged (unjudged@10 = 0).

24 answerable queries (12 pairs, 37 required claims): 14 main, 10 underspecified (time condition missing).
Macro = mean over queries.

## Official result (v1 catalog, dq07 included)

### Primary, macro

| group | system | claim_recall @1 / @3 / @5 / @10 | all_claims_covered @1 / @3 / @5 / @10 | MRR any / all | unreachable |
|---|---|---|---|---|---|
| all (24) | B1 | 0.076 / 0.194 / 0.236 / 0.340 | 0.042 / 0.125 / 0.167 / 0.292 | 0.200 / 0.109 | 16 |
| all (24) | B2 | 0.181 / 0.278 / 0.340 / 0.486 | 0.125 / 0.208 / 0.292 / 0.417 | 0.321 / 0.201 | 6 |
| main (14) | B1 | 0.131 / 0.298 / 0.298 / 0.369 | 0.071 / 0.214 / 0.214 / 0.286 | 0.293 / 0.150 | 6 |
| main (14) | B2 | 0.131 / 0.298 / 0.369 / 0.512 | 0.071 / 0.214 / 0.286 / 0.429 | 0.317 / 0.174 | 2 |
| underspecified (10) | B1 | 0.000 / 0.050 / 0.150 / 0.300 | 0.000 / 0.000 / 0.100 / 0.300 | 0.071 / 0.052 | 10 |
| underspecified (10) | B2 | 0.250 / 0.250 / 0.300 / 0.450 | 0.200 / 0.200 / 0.300 / 0.400 | 0.327 / 0.239 | 4 |
| en (12) | B1 | 0.153 / 0.333 / 0.417 / 0.542 | 0.083 / 0.250 / 0.333 / 0.500 | 0.351 / 0.210 | 7 |
| en (12) | B2 | 0.278 / 0.417 / 0.542 / 0.667 | 0.167 / 0.333 / 0.500 / 0.583 | 0.497 / 0.299 | 2 |
| ko (12) | B1 | 0.000 / 0.056 / 0.056 / 0.139 | 0.000 / 0.000 / 0.000 / 0.083 | 0.050 / 0.008 | 9 |
| ko (12) | B2 | 0.083 / 0.139 / 0.139 / 0.306 | 0.083 / 0.083 / 0.083 / 0.250 | 0.145 / 0.103 | 4 |

### Paired B2 − B1 (same query), all 24

| metric | mean delta | B2 wins / ties / losses |
|---|---|---|
| claim_recall@1 / @3 / @5 / @10 | +0.104 / +0.083 / +0.104 / +0.146 | 3/21/0, 3/20/1, 4/19/1, 5/18/1 |
| all_claims_covered@1 / @3 / @5 / @10 | +0.083 / +0.083 / +0.125 / +0.125 | 2/22/0, 3/20/1, 4/19/1, 4/19/1 |
| mrr_any_complete_claim@10 | +0.121 | 8/14/2 |
| mrr_all_claims_complete@10 | +0.092 | 7/15/2 |
| unreachable_claims | 16 → 6 | fewer for B2 in 8 queries, more in 0 |

Main (14): claim_recall@10 +0.143 (2/12/0), MRR any +0.024 (3/10/1). Underspecified (10): claim_recall@10 +0.150
(3/6/1), MRR any +0.256 (5/4/1). B2 is worse on dq03_en (claim_recall@10 1 → 0) and dq11_en (MRR any 0.50 → 0.20).
Most gains come from dq09 en/ko, dq02_en, dq11_ko and dq10_en.

### Secondary and counts

partial_claim_recall @1 / @3 / @5 / @10 (macro): all B1 0.382 / 0.458 / 0.458 / 0.583, B2 0.444 / 0.542 / 0.542 /
0.688; main B1 0.440 / 0.571 / 0.571 / 0.714, B2 0.405 / 0.571 / 0.571 / 0.714; underspecified B1 0.300 / 0.300 /
0.300 / 0.400, B2 0.500 / 0.500 / 0.500 / 0.650 (en / ko in `claim_metrics.json`). unjudged@10 = 0 for both systems;
uncertain units in the top 10: B1 10, B2 4 (all in underspecified queries).

### Language gap (matched pairs only: p01, p03, p05, p07, p09)

en − ko, primary, in `claim_metrics.json` (`language_gap_matched_pairs`); five pairs only, not a basis for a general
conclusion.

## CI-001 (dq07)

dq07_en and dq07_ko keep their v1 claims. Their c1 (one effective date for the interim final rule) has no complete
support in any judged unit (the official text separates 2026-06-24 and 2026-07-24; such units are partial), so c1
cannot be completed in the current catalog and counts as 1 unreachable claim per query for both systems. It stays in
the official result above. dq07_v2 is not created here and no qrel was changed.

## Sensitivity (diagnostic, not merged): without dq07_en / dq07_ko (22 queries)

| system | claim_recall @1 / @3 / @5 / @10 | all_claims_covered @1 / @3 / @5 / @10 | MRR any / all | unreachable |
|---|---|---|---|---|
| B1 | 0.061 / 0.189 / 0.235 / 0.348 | 0.045 / 0.136 / 0.182 / 0.318 | 0.173 / 0.119 | 14 |
| B2 | 0.174 / 0.280 / 0.348 / 0.508 | 0.136 / 0.227 / 0.318 / 0.455 | 0.305 / 0.220 | 4 |

Mean paired delta B2 − B1: claim_recall@10 +0.159, all_claims_covered@10 +0.136, MRR any +0.132.

## Diagnostics only (not comparable across systems; not used above)

system_relative_ndcg@10 uses each system's own pool IDCG; claim_novelty_dcg@10 is not nDCG. Values are in
`claim_metrics.json` (`diagnostics_only`).

## Conclusion (with limits)

On these 24 queries, B2 (heading-enriched BM25, b2_heading_v4) completes more required claims than B1 in the top 10
and leaves fewer claims unreachable in its judged pool; the paired differences are mostly ties, with a few queries
deciding the means (gains concentrated in dq09, dq02_en, dq11_ko, dq10_en; losses on dq03_en and dq11_en). In the
main set the difference at k = 1 and 3 is zero; most of the gain is at k = 5 and 10 and in underspecified queries.

Limits: a small sample (24 queries, 37 claims; one changed query moves a macro by about 0.04); the B2 configuration
(v4), the claim catalog and the scoring were fixed after earlier diagnostics of these same runs had been seen, so this
is not a pre-registered test; the qrels are human_assisted (Claude assisted the reviewer); dq07 c1 is unreachable in
the current catalog (CI-001). No significance test is claimed.
