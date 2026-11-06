# Qrel review agreement

Reviewer of the sheet: human_assisted (a person decided every row, reading Claude's neutral Korean translations of the queries and chunks; the translation is a possible influence).
Units (query pair x chunk): 75. Decisions: relevant 18, not_relevant 42, uncertain 15.
Translation assistance and its possible influence: review/translation_notes.md.
Query time conditions: dated 2, time_invariant 12, underspecified 10.

Against Claude's sealed reading (claude_review.csv), same units and criterion:

- Raw agreement: 71/75 = 0.947
- Raw agreement where neither said uncertain: 57/57 = 1.000
- Cohen's kappa: 0.909 (one corpus, few units: a description, not an estimate)

| sheet \ Claude | relevant | not_relevant | uncertain |
|---|---|---|---|
| relevant | 15 | 0 | 3 |
| not_relevant | 0 | 42 | 0 |
| uncertain | 0 | 1 | 14 |

Disagreements: 4 (disagreements.csv). The sheet's decision is final in v2.

Query time conditions, agreement with claude_time_review.csv: 20/24; differing: dq04_en (underspecified vs time_invariant), dq06_en (dated vs time_invariant), dq08_en (dated vs time_invariant), dq08_ko (underspecified vs time_invariant)
