# Claim review consistency check v1 (human_assisted final/v1 vs sealed Claude judgements)

This is a **consistency check, not independent validation**. Claude wrote the sealed judgements before the review (commit 72e9124) after seeing the runs and the earlier judgements, and Claude then assisted the reviewer (translations and suggested decisions) during the human_assisted review. The two sets are not independent; agreement rates and kappa below are reference diagnostics only. Neither set was changed. No retrieval metric (B1/B2) is computed here.

Inputs: `final/v1/` (commit 937ef95) and `claude_sealed/` (commit 72e9124). Rows are compared only where system and item id (and claim/component) are identical. Sealed file hashes were checked against `claude_sealed/manifest.json` and the final outputs against `final/v1/manifest.json` before comparison.

## Item decisions (527)

All: n=527, 일치 499 (94.69%), 참고 κ=0.9011

| human_assisted \ Claude | relevant | not_relevant | uncertain | 합계 |
|---|---|---|---|---|
| relevant | 184 | 0 | 0 | 184 |
| not_relevant | 23 | 285 | 0 | 308 |
| uncertain | 0 | 5 | 30 | 35 |
| 합계 | 207 | 290 | 30 | 527 |

### B1 (266)

n=266, 일치 246 (92.48%), 참고 κ=0.863

| human_assisted \ Claude | relevant | not_relevant | uncertain | 합계 |
|---|---|---|---|---|
| relevant | 76 | 0 | 0 | 76 |
| not_relevant | 15 | 146 | 0 | 161 |
| uncertain | 0 | 5 | 24 | 29 |
| 합계 | 91 | 151 | 24 | 266 |

### B2 (261)

n=261, 일치 253 (96.93%), 참고 κ=0.9406

| human_assisted \ Claude | relevant | not_relevant | uncertain | 합계 |
|---|---|---|---|---|
| relevant | 108 | 0 | 0 | 108 |
| not_relevant | 8 | 139 | 0 | 147 |
| uncertain | 0 | 0 | 6 | 6 |
| 합계 | 116 | 139 | 6 | 261 |

### new stage 1 items (484)

n=484, 일치 465 (96.07%), 참고 κ=0.9247

| human_assisted \ Claude | relevant | not_relevant | uncertain | 합계 |
|---|---|---|---|---|
| relevant | 178 | 0 | 0 | 178 |
| not_relevant | 14 | 269 | 0 | 283 |
| uncertain | 0 | 5 | 18 | 23 |
| 합계 | 192 | 274 | 18 | 484 |

### reused items (43)

n=43, 일치 34 (79.07%), 참고 κ=0.6815

| human_assisted \ Claude | relevant | not_relevant | uncertain | 합계 |
|---|---|---|---|---|
| relevant | 6 | 0 | 0 | 6 |
| not_relevant | 9 | 16 | 0 | 25 |
| uncertain | 0 | 0 | 12 | 12 |
| 합계 | 15 | 16 | 12 | 43 |

Reused items carry decisions from the earlier qrel review (different, pre-claim criteria); the sealed Claude judgements judged them afresh under the claim criteria.

## Component support (1,011)

All: n=1011, 일치 967 (95.65%), 참고 κ=0.8949

| human_assisted \ Claude | complete | partial | none | 합계 |
|---|---|---|---|---|
| complete | 106 | 4 | 0 | 110 |
| partial | 10 | 124 | 5 | 139 |
| none | 13 | 12 | 737 | 762 |
| 합계 | 129 | 140 | 742 | 1011 |

### Judged by the reviewer in stage 2 (324)

n=324, 일치 303 (93.52%), 참고 κ=0.9004

| human_assisted \ Claude | complete | partial | none | 합계 |
|---|---|---|---|---|
| complete | 106 | 4 | 0 | 110 |
| partial | 10 | 124 | 5 | 139 |
| none | 0 | 2 | 73 | 75 |
| 합계 | 116 | 130 | 78 | 324 |

### Filled `none` by finalize for not_relevant / uncertain items (687)

n=687, 일치 664 (96.65%), 참고 κ=0.0 (degenerate: the human side is all none, so kappa is not meaningful)

| human_assisted \ Claude | complete | partial | none | 합계 |
|---|---|---|---|---|
| complete | 0 | 0 | 0 | 0 |
| partial | 0 | 0 | 0 | 0 |
| none | 13 | 10 | 664 | 687 |
| 합계 | 13 | 10 | 664 | 687 |

By system: b1_human_stage2: n=130, 일치 118 (90.77%), 참고 κ=0.85; b1_auto_none: n=381, 일치 366 (96.06%), 참고 κ=0.0; b2_human_stage2: n=194, 일치 185 (95.36%), 참고 κ=0.9297; b2_auto_none: n=306, 일치 298 (97.39%), 참고 κ=0.0

Note: CI-001 (dq07 c1) was decided during the review, after the sealed judgements were written; dq07 c1 differences on units showing both dates reflect that rule.

## Mismatches

Items: 28 rows in `item_mismatches.csv`; components: 44 rows in `component_mismatches.csv` (system, item id, intent, query ids, segment, both values). No judgement was changed.

| system | item | intent | queries | source | human_assisted | Claude |
|---|---|---|---|---|---|---|
| b1 | b1-0003 | p01 | dq01_en | stage1 | not_relevant | relevant |
| b1 | b1-0008 | p01 | dq01_en | stage1 | not_relevant | relevant |
| b1 | b1-0106 | p07 | dq07_en;dq07_ko | reused | not_relevant | relevant |
| b1 | b1-0140 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0142 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0144 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0151 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0153 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0155 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0161 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0168 | p09 | dq09_en;dq09_ko | reused | not_relevant | relevant |
| b1 | b1-0181 | p09 | dq09_ko | stage1 | uncertain | not_relevant |
| b1 | b1-0182 | p09 | dq09_ko | stage1 | uncertain | not_relevant |
| b1 | b1-0183 | p09 | dq09_ko | stage1 | uncertain | not_relevant |
| b1 | b1-0187 | p09 | dq09_ko | stage1 | uncertain | not_relevant |
| b1 | b1-0188 | p09 | dq09_ko | stage1 | uncertain | not_relevant |
| b1 | b1-0226 | dq11_en | dq11_en | stage1 | not_relevant | relevant |
| b1 | b1-0227 | dq11_en | dq11_en | stage1 | not_relevant | relevant |
| b1 | b1-0238 | dq11_ko | dq11_ko | stage1 | not_relevant | relevant |
| b1 | b1-0239 | dq11_ko | dq11_ko | stage1 | not_relevant | relevant |
| b2 | b2-0003 | p01 | dq01_en | stage1 | not_relevant | relevant |
| b2 | b2-0008 | p01 | dq01_en | stage1 | not_relevant | relevant |
| b2 | b2-0222 | dq11_en | dq11_en | stage1 | not_relevant | relevant |
| b2 | b2-0223 | dq11_en | dq11_en | stage1 | not_relevant | relevant |
| b2 | b2-0225 | dq11_en | dq11_en | stage1 | not_relevant | relevant |
| b2 | b2-0233 | dq11_ko | dq11_ko | stage1 | not_relevant | relevant |
| b2 | b2-0234 | dq11_ko | dq11_ko | stage1 | not_relevant | relevant |
| b2 | b2-0236 | dq11_ko | dq11_ko | stage1 | not_relevant | relevant |

| system | item | intent | component | segment | human_assisted | Claude |
|---|---|---|---|---|---|---|
| b1 | b1-0003 | p01 | c1.e1 | finalize_auto_none | none | partial |
| b1 | b1-0008 | p01 | c1.e1 | finalize_auto_none | none | partial |
| b1 | b1-0024 | dq02_en | c1.e1 | human_stage2 | partial | complete |
| b1 | b1-0035 | dq02_ko | c1.e1 | human_stage2 | partial | complete |
| b1 | b1-0085 | p05 | c2.e1 | human_stage2 | none | partial |
| b1 | b1-0106 | p07 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0107 | p07 | c1.e1 | human_stage2 | partial | complete |
| b1 | b1-0109 | p07 | c2.e1 | human_stage2 | complete | partial |
| b1 | b1-0113 | p07 | c2.e1 | human_stage2 | complete | partial |
| b1 | b1-0114 | p07 | c1.e1 | human_stage2 | partial | complete |
| b1 | b1-0140 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0142 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0144 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0151 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0153 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0155 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0161 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0168 | p09 | c2.e1 | finalize_auto_none | none | complete |
| b1 | b1-0226 | dq11_en | c1.e1 | finalize_auto_none | none | partial |
| b1 | b1-0227 | dq11_en | c1.e1 | finalize_auto_none | none | complete |
| b1 | b1-0233 | dq11_en | c1.e1 | human_stage2 | partial | complete |
| b1 | b1-0236 | dq11_ko | c1.e2 | human_stage2 | partial | none |
| b1 | b1-0237 | dq11_ko | c1.e2 | human_stage2 | partial | none |
| b1 | b1-0238 | dq11_ko | c1.e1 | finalize_auto_none | none | complete |
| b1 | b1-0239 | dq11_ko | c1.e1 | finalize_auto_none | none | partial |
| b1 | b1-0244 | dq11_ko | c1.e1 | human_stage2 | partial | complete |
| b1 | b1-0250 | dq12_en | c1.e1 | human_stage2 | partial | complete |
| b2 | b2-0003 | p01 | c1.e1 | finalize_auto_none | none | partial |
| b2 | b2-0008 | p01 | c1.e1 | finalize_auto_none | none | partial |
| b2 | b2-0086 | p05 | c2.e1 | human_stage2 | none | partial |
| b2 | b2-0107 | p07 | c1.e1 | human_stage2 | partial | complete |
| b2 | b2-0110 | p07 | c2.e1 | human_stage2 | complete | partial |
| b2 | b2-0114 | p07 | c2.e1 | human_stage2 | complete | partial |
| b2 | b2-0116 | p07 | c1.e1 | human_stage2 | partial | complete |
| b2 | b2-0221 | dq11_en | c1.e2 | human_stage2 | partial | none |
| b2 | b2-0222 | dq11_en | c1.e1 | finalize_auto_none | none | complete |
| b2 | b2-0223 | dq11_en | c1.e1 | finalize_auto_none | none | partial |
| b2 | b2-0225 | dq11_en | c1.e1 | finalize_auto_none | none | partial |
| b2 | b2-0231 | dq11_ko | c1.e2 | human_stage2 | partial | none |
| b2 | b2-0232 | dq11_ko | c1.e2 | human_stage2 | partial | none |
| b2 | b2-0233 | dq11_ko | c1.e1 | finalize_auto_none | none | complete |
| b2 | b2-0234 | dq11_ko | c1.e1 | finalize_auto_none | none | partial |
| b2 | b2-0236 | dq11_ko | c1.e1 | finalize_auto_none | none | partial |
| b2 | b2-0242 | dq12_en | c1.e1 | human_stage2 | partial | complete |
