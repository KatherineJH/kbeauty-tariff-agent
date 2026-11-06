# Retrieval baseline (BM25)

Each run is a folder that is never overwritten:

    uv run python scripts/eval_retrieval.py <run_name>

Corpus, chunking, tokenizer and parameters are described in `src/tariffagent/retrieval/`; each run folder keeps its
`manifest.json` (corpus, chunking and index logical hashes) and `inputs.sha256` (hashes of the evaluation inputs).

**These are exploratory diagnostics, not test results.** The dev set has 24 answerable queries (12 English / Korean
pairs) written by one author, plus 4 unanswerable ones added after run_001. Differences of one or two queries move
the numbers by 0.04 to 0.08; nothing here is a claim about how BM25 generalizes.

## run_001_strict_citation_qrels (2026-11-06, no tuning)

Dev set: the 24 queries of `evals/dev/queries.csv`, written before this run (not committed before it, so that order
is stated, not proven by a commit time). Corpus: 1,218 documents, 7,738 chunks of 120 words with 30 words of overlap.
BM25 k1 = 1.2, b = 0.75. Relevance: **citation qrels only** (the cited file and page; the same sentence on another
page is a miss). Recall is the mean over queries of per-query recall (macro).

| Group | Queries | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | Zero-result rate |
|---|---|---|---|---|---|---|
| all | 24 | 0.2917 | 0.5208 | 0.2214 | 0.2814 | 0.1250 |
| en | 12 | 0.5000 | 0.7917 | 0.3953 | 0.4698 | 0.0000 |
| ko | 12 | 0.0833 | 0.2500 | 0.0475 | 0.0930 | 0.2500 |

Files: `bm25_dev_runs.csv`, `bm25_dev_per_query.csv`, `bm25_dev_metrics.csv`, plus `manifest.json` and
`inputs.sha256` (copied into the folder after the run, when the run was renamed; the result files are unchanged). Rows
were appended to `queries.csv` after this run, so its whole-file hash no longer matches `inputs.sha256`; the first 24
rows still hash to the recorded value (`test_dev_queries_are_append_only_after_run_001`).

## run_002_reviewed_retrieval_qrels (2026-11-06, no tuning)

Same corpus (identical document and chunk hashes), index and parameters. The rankings of the 24 queries are
identical to run_001. What changed is the evaluation:

- **Two qrel sets.** `citation` = run_001's strict qrels. `retrieval` = strict plus the locations a reviewer accepted
  in `evals/dev/retrieval_qrels.csv`. Candidates were listed mechanically (pages that contain the cited quote
  verbatim: 53, of which 13 are the cited locations) and each was judged by legal scope, period and claim role:
  6 accepted (the same Korea-scope row or note in 2026 Rev. 3 and Rev. 4, inside the rule period), 34 rejected
  (11 United Kingdom lists, 8 aluminum lists for a steel question, 8 IEEPA stacking notes for a surcharge question,
  7 revisions before the rule period). Reviewer of record: Claude; the user's confirmation is pending.
- **Recall denominator** = distinct relevant citations of the query (not chunks). **Macro** recall = mean of
  per-query recall; **micro** recall = found citations / relevant citations, pooled over queries.
- **Unanswerable queries** (dq13, dq14; added after run_001, see `evals/dev/README.md`) are summarized separately.

Answerable queries:

| qrels | Group | Queries | Citations | macro R@5 | micro R@5 | macro R@10 | micro R@10 | MRR@10 | nDCG@10 | Zero-result |
|---|---|---|---|---|---|---|---|---|---|---|
| citation | all | 24 | 28 | 0.2917 | 0.2857 | 0.5208 | 0.5000 | 0.2214 | 0.2814 | 0.1250 |
| citation | en | 12 | 14 | 0.5000 | 0.5000 | 0.7917 | 0.7857 | 0.3953 | 0.4698 | 0.0000 |
| citation | ko | 12 | 14 | 0.0833 | 0.0714 | 0.2500 | 0.2143 | 0.0475 | 0.0930 | 0.2500 |
| retrieval | all | 24 | 28 | 0.3333 | 0.3214 | 0.5208 | 0.5000 | 0.2259 | 0.2855 | 0.1250 |
| retrieval | en | 12 | 14 | 0.5833 | 0.5714 | 0.7917 | 0.7857 | 0.4043 | 0.4779 | 0.0000 |
| retrieval | ko | 12 | 14 | 0.0833 | 0.0714 | 0.2500 | 0.2143 | 0.0475 | 0.0930 | 0.2500 |

Unanswerable queries:

| Group | Queries | Empty-result rate | Mean top score when returned |
|---|---|---|---|
| all | 4 | 0.5000 | 15.0895 |
| en | 2 | 0.0000 | 15.0895 |
| ko | 2 | 1.0000 | |

Reading:
- The reviewed qrels change one query (dq03_en: the 9903.85.08 rate row of 2026 Rev. 4 and Rev. 3 is ranked 4th and
  5th, the cited 2025 Rev. 19 row 7th; the same row in Rev. 17 and 18, rejected as before the rule period, is 6th
  and 8th, and ranks 1 to 3 are an April 2025 page). Strict qrels were not hiding many hits for this query set; most misses are real.
- Korean queries against English documents stay weak: only shared tokens (HTS codes, "IEEPA", percentages) match.
  Their empty results on the unanswerable pair are a side effect of that, not a sign of abstention.
- The two English unanswerable queries return chunks with top scores of 12.4 and 17.8, while the lowest top score of
  an answerable English query is 17.2. A score threshold alone cannot tell them apart; abstention has to come from
  later steps (rule engine coverage, answer verification).

Files: `bm25_dev_runs.csv` (top 10 per query with `relevant_citation` and `relevant_retrieval`),
`bm25_dev_per_query.csv`, `bm25_dev_metrics.csv`, `bm25_dev_unanswerable.csv`, `manifest.json`, `inputs.sha256`.

Not done yet, on purpose: query translation, synonyms, Korean tokenization, parameter tuning, dense retrieval. They
will be added as separate configurations and compared with this baseline on the same dev set.

## run_003_user_reviewed_qrels (2026-11-06, no tuning) — fixed dev baseline

Same corpus, chunks, index and parameters as run_001 and run_002 (identical manifest hashes); the rankings are the
same. What changed is the dev qrel set, now fixed for BM25, dense and hybrid comparisons (`evals/dev/README.md`):

- **retrieval qrels v2** (`evals/dev/retrieval_qrels_v2.csv`): 75 (query pair, chunk) units judged by the user
  (`human_assisted`: decided in chat from Claude's neutral Korean translations; see
  `evals/dev/review/translation_notes.md`). Criterion: only the query's stated conditions and the returned chunk
  with its metadata. relevant 18, not_relevant 42, uncertain 15 (uncertain is kept, not counted as relevant).
- **time conditions** (`evals/dev/query_time_conditions.csv`): dated 2, time_invariant 12, underspecified 10.
  Underspecified queries are reported apart from the main set.
- **pair checks** (`evals/dev/query_pair_checks.csv`): 7 of 12 English/Korean pairs ask different things; only the
  5 matched pairs enter `en_paired` / `ko_paired` / `gap_en_minus_ko`. Every query keeps its individual result.
- Agreement with Claude's sealed reading (`evals/dev/review/agreement.md`): 71/75 units (0.947), Cohen's kappa
  0.909; 57/57 where neither said uncertain; time conditions 20/24. One of the four unit disagreements (u065) is
  the unit whose translation included a phrase not in the chunk. Claude's reading was not naive (it had seen the
  cited locations and its own v1), so this is consistency between two readers, not independent validation.

Answerable queries, retrieval qrels v2 (the `citation` rows in `bm25_dev_metrics.csv` keep the strict qrels for
reference):

| Set | Group | Queries | Citations | Unreachable | macro R@5 | macro R@10 | micro R@10 | MRR@10 | Zero-result |
|---|---|---|---|---|---|---|---|---|---|
| main | all | 14 | 16 | 0 | 0.3571 | 0.5714 | 0.5625 | 0.2872 | 0.1429 |
| main | en | 7 | 8 | 0 | 0.5714 | 0.7143 | 0.7500 | 0.4966 | 0.0000 |
| main | ko | 7 | 8 | 0 | 0.1429 | 0.4286 | 0.3750 | 0.0778 | 0.2857 |
| main | en_paired | 3 | 4 | 0 | 0.6667 | 0.6667 | 0.7500 | 0.4444 | 0.0000 |
| main | ko_paired | 3 | 4 | 0 | 0.0000 | 0.6667 | 0.5000 | 0.0704 | 0.3333 |
| main | gap en − ko | 3 pairs | | | 0.6667 | 0.0000 | 0.2500 | 0.3740 | −0.3333 |
| underspecified | en | 5 | 6 | 3 | 0.4000 | 0.6000 | 0.5000 | 0.1786 | 0.0000 |
| underspecified | ko | 5 | 6 | 3 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.2000 |

Unanswerable queries are unchanged from run_002 (English: something returned, top scores 12.4 and 17.8; Korean:
nothing returned).

Reading (exploratory; 14 + 10 queries, 3 matched pairs in the main set):
- **Unreachable citations: 3 of 6 in the underspecified set, in each language.** p09 (3304.99.50 on the 9903.81.91
  steel list: both its citations) and p10 (the surcharge's aluminum-content exclusion) have no chunk judged
  relevant: the chunks that carry the code list or the exclusion do not carry the heading or the duty they belong
  to, and the chunks with the heading do not carry the code. This is a retrieval-unit design failure, not a
  ranking failure: no ranker can score these citations with the current chunks.
- The paired language gap rests on 3 pairs (p01, p05, p07); Recall@10 is equal, Korean finds the evidence lower in
  the list (Recall@5 0.00 vs 0.67) and returns nothing more often. Four other pairs were left out as mismatched.
- In the main set the reviewed qrels change MRR/nDCG only slightly against the strict ones: units judged not
  relevant (e.g. the CSMS title chunk for p01) no longer count, and no new relevant location was found.

Next, on purpose as separate configurations compared on this fixed set: heading-enriched chunks (the note or heading
line prefixed to each chunk, or carried as metadata the engine returns), then dense and hybrid retrieval. Changing
the retrieval unit changes the units to be judged: chunks that did not exist in this review need their own
judgements, recorded as a new qrel version, never by editing v2.
