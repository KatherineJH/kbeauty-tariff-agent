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
  - First review, 2026-11-06: 53 candidates; 13 cited locations, 6 more accepted, 34 rejected. Reviewer of record:
    Claude. The user's confirmation is pending; a changed decision is a new commit and a new run, not an edit of a
    past run.

## Change log

| Date | Change | Relative to runs | Reason |
|---|---|---|---|
| 2026-11-06 | dq01 to dq12 (24 queries) written | before run_001 | first dev set |
| 2026-11-06 | dq13, dq14 (4 unanswerable queries) appended | after run_001, first evaluated in run_002 | unanswerable queries are evaluated apart from the zero-result rate; the answers (a Japanese consumption tax, a Korean export voucher) are not in the corpus, checked by searching the corpus for "consumption tax" and "export voucher" (0 pages) |
| 2026-11-06 | `retrieval_qrels.csv`, `retrieval_qrel_candidates.csv`, `qrels_meta.json` added | after run_001, first used in run_002 | strict qrels count the same accepted evidence on another page as a miss |
