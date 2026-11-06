# Dev retrieval set

`queries.csv`: queries in English / Korean pairs, each pair asking the same thing in both languages. The first 24
(dq01 to dq12) were written by hand on 2026-11-06 **before the first BM25 run** (run_001), from the scenarios in
docs/architecture.md. Rows are only appended, never edited or removed; every change is logged below with whether it
was made before or after a run. A test checks that the first 24 rows are byte-identical to run_001's input hash.

- `relevant_citation_ids`: citations of `warehouse/seeds/rule_citations.csv` that answer the query, `;`-separated.
  Empty means the query is **unanswerable** from the corpus; `author_note` says why.
- The corpus is built without reading the citations; relevance is attached only at evaluation time.
- This is a dev set for the baseline. It is small and was written by the author; it is not a test set, and the
  numbers it gives are exploratory diagnostics.

## Qrels

Two relevance sets, both at the citation level (a citation is found when any of its relevant chunks is ranked):

- **citation qrels** (strict, derived from the citation seed): chunks that overlap the cited quote in the cited file
  and page only.
- **retrieval qrels** (reviewed): the strict set plus other locations of the same quote that a reviewer accepted.
  - `retrieval_qrel_candidates.csv` is produced by `scripts/list_qrel_candidates.py`: every page whose normalized
    text contains the citation's normalized quote verbatim, with the heading that governs the passage. Candidates are
    not judgements, and paraphrased or reworded later versions are not listed.
  - `retrieval_qrels.csv` has one row per candidate: `decision` (accept / reject), `reason_code`, `reason`,
    `reviewer`. Accepted only when the location has the same legal scope (Korea, the same heading), the same period
    (a revision in force inside the rule period) and the same claim role. Rejected examples: the same cosmetics list
    under the United Kingdom heading 9903.81.98 (note 16(u)) or 9903.85.15 (note 19(s)); the same words in note
    2(v)(ix), which governs IEEPA reciprocal duties, for a question about the section 122 surcharge.
  - Tests fail if a candidate has no decision, a decision has no candidate, or a cited location is not accepted.
  - `qrels_meta.json` records the document, chunk and chunking-rule hashes the candidates were listed on. If the
    corpus or chunking changes, evaluation stops until candidates are listed and reviewed again.
  - First review (v1), 2026-11-06: 53 candidates; 13 cited locations, 6 more accepted, 34 rejected, by Claude. It
    used criteria later ruled out (see below); it is kept only as the record of run_002.

## Relevance criterion for v2 (fixed before the review)

Relevance is judged only from the conditions stated in the query and from what the retriever actually returns: the
chunk text and its metadata (`source_id`, `source_file`, `physical_page`, `printed_page`). Outside context, such as
the rest of the page, the heading of a note that is not in the chunk, or the hidden period of the answer rule, is
not used.

- `relevant`: the returned unit alone answers the query's core claim.
- `not_relevant`: a different country, duty type or legal scope, or plainly does not answer.
- `uncertain`: the heading, period or note context needed to judge is not in the returned unit. Kept in the file,
  left out of the qrels.
- Time: a query that states a date is judged at that date. A query without a date is not judged against any period;
  the same provision in a revision from another time is not `not_relevant` for its period alone. A query that cannot
  be answered without a date is classified `underspecified` and reported apart from the main metrics. To evaluate a
  date-specific answer, the date has to be written in the query.
- Retrieval unit: the chunk as BM25 returns it now (120 words, 30 overlap) with the metadata above. Adjacent-chunk
  expansion, if added later, is a different unit and gets its own judgements; it is not assumed for this baseline.

Claude's v1 decisions (`retrieval_qrels.csv`, used by run_002) applied the rule period to queries without a date
and used page context outside the chunk. Both are against this criterion, so v1 stays only as the record of run_002.

## User review (v2) and freeze

1. `scripts/make_qrel_review_sheet.py` writes `review/qrel_review_sheet.csv` (fill) and `.md` (read): one row per
   (query pair, chunk), 75 units: every chunk overlapping a verbatim occurrence of a quote the pair's answer cites,
   the cited locations included and not marked. Candidates are picked without any retriever, so they do not favour
   BM25 or dense retrieval; evidence worded differently is not a candidate (a known limit). The sheet is blind: no
   earlier decision, cited location, rule or rule period. `review/query_time_sheet.csv`: one row per answerable
   query, `time_condition` = `dated` / `time_invariant` / `underspecified`.
2. The reviewer fills `user_decision`, `user_reason` and `reviewer_type`. `human` only when a person judged every
   row from the sheet itself; `human_assisted` when a person decided every row in chat after Claude translated the
   query and the chunk into plain Korean, neutrally and without giving a judgement first (the translation can still
   influence the decision, and the report says so); `second_model_review` if a model filled the sheet, and then it
   is not called a human review anywhere.
3. `scripts/finalize_qrel_review.py` writes `retrieval_qrels_v2.csv`, `query_time_conditions.csv`,
   `review/agreement.md` and `review/disagreements.csv`. Agreement is computed against `review/claude_review.csv`
   when it exists: Claude's reading of the same units under the same criterion, whose sha256 is recorded here before
   the user's review starts. The sheet's decision is final.
   Claude's sealed reading, written 2026-11-06 before the user's review (do not open these two files before your own
   review is done):

   | file | sha256 |
   |---|---|
   | `review/claude_review.csv` | `5ecc87d9eec7406bd094473de71bd00116043fa17ae1b3617b5c4176e8234dd9` |
   | `review/claude_time_review.csv` | `4e6ec075e2574a05643663215650eafabdbc78457662778f9bb034b060fdc1d9` |

   It is a model's reading, not a human one, and it is not naive: Claude had already seen the cited locations, the
   rules and its own v1 decisions. Agreement with it is a consistency check between two readers, not independent
   validation. A test fails if either file changes.
4. `run_003_user_reviewed_qrels` is run with v2. From then on v2 is the fixed dev qrel set for BM25, dense and
   hybrid; a later change is a v3 with its own run, logged below.

## Change log

| Date | Change | Relative to runs | Reason |
|---|---|---|---|
| 2026-11-06 | dq01 to dq12 (24 queries) written | before run_001 | first dev set |
| 2026-11-06 | dq13, dq14 (4 unanswerable queries) appended | after run_001, first evaluated in run_002 | unanswerable queries are evaluated apart from the zero-result rate; the answers (a Japanese consumption tax, a Korean export voucher) are not in the corpus, checked by searching the corpus for "consumption tax" and "export voucher" (0 pages) |
| 2026-11-06 | `retrieval_qrels.csv`, `retrieval_qrel_candidates.csv`, `qrels_meta.json` added | after run_001, first used in run_002 | strict qrels count the same accepted evidence on another page as a miss |
| 2026-11-06 | v2 relevance criterion fixed; blind sheets for 75 (pair, chunk) units and 24 query time conditions | after run_002, before any v2 decision | v1 used the hidden rule period and context outside the returned chunk |
| 2026-11-06 | Claude's reading of the 75 units and 24 time conditions sealed (`review/claude_review.csv`, `review/claude_time_review.csv`, sha256 above), committed before the user's review with the empty sheets | before any user decision | the commit time proves the model reading came first; `reports/retrieval/run_001_strict_citation_qrels` and `run_002_reviewed_retrieval_qrels` were not changed (no diff against the previous commit) |
| 2026-11-06 | `reviewer_type` value `human_assisted` added | after the seal commit, before any user decision | the user reviews in chat from neutral Korean translations of the English chunks; Claude records the answers verbatim |
| 2026-11-06 | user review recorded: 75 units, 24 time conditions, 12 pair checks (`human_assisted`), with `review/translation_notes.md`; hashes in `review/user_review.sha256` | committed before the sealed Claude files are opened and before finalize | the commit order proves the user decisions were fixed before the agreement was computed |
