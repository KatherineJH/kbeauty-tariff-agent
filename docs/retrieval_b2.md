# B2: heading-enriched BM25, configuration b2_heading_v1 (diagnostic)

Status of `b2_heading_v1`: **`invalid_structural_context`**: kept as a diagnostic run, not used for evaluation.
After its first run (run_004) a lead-in was found carried over 1,088 chunks of other subdivisions and notes (below).
Its code is `src/tariffagent/retrieval/structure.py` at this commit (module sha256 `e8a58235…`, config sha256
`e013ec0e…`), its first results are `reports/retrieval/run_004_b2_heading_v1/` and
`data/extracted/retrieval_b2/b2_heading_v1_manifest.json`, its unused review sheet `evals/dev/review_b2_v1/`.
The fix is a new configuration, `b2_heading_v2`. No qrels were reviewed and no B1/B2 conclusion is drawn here. Strategy and
order: [retrieval_strategy.md](retrieval_strategy.md). B1 and the fixed dev set: [architecture.md](architecture.md)
4.4, [evals/dev/README.md](../evals/dev/README.md), [reports/retrieval/README.md](../reports/retrieval/README.md).

## What changes and what does not

- Same as B1: corpus documents, chunk windows (120 words, 30 overlap), tokenizer, BM25 k1 = 1.2, b = 0.75, tie
  order. B1's corpus, chunks, index, qrels v2 and runs `run_001` to `run_003` are not touched.
- New: each B1 chunk gets a structural context; BM25 indexes `index_text` instead of the chunk text.
  `raw_text` is the B1 chunk text, unchanged; `index_text` =
  `[context] <context_text> [/context] [text] <raw_text> [/text]`.
- Configuration `b2_heading_v1`, code `src/tariffagent/retrieval/structure.py` (rules R1 to R5 in its docstring and in
  `CONFIG`), B2 chunk fields: `raw_text`, `context_text`, `index_text`, `source_id`, `source_revision`,
  `physical_page`, `printed_page`, `note`, `subdivision`, `applicable_heading`, `duty_family`, `country_scope`,
  `context_origin` (same_page / previous_page:<n> / document_metadata / none), `parent_chunk_id` (the B1 chunk),
  `chunk_id`, `config_id`.

## Enrichment rules (b2_heading_v1)

- **R1, chapter 99 notes pages.** A lead-in is a subdivision line (`(x) ...` at the start of a raw line) whose first
  sentence names a 9903 heading as the source of a duty ("rates of duty (set forth) in heading X", "duty imposed by
  heading(s) X"). It governs until another lead-in, the next sibling label (n -> o; v -> w or vi; aa -> bb) or a new
  note line `N. `. A chunk takes the lead-in governing its start (the running header `U.S. Notes (con.)` is
  skipped) and copies from it only: subdivision, applicable_heading (headings of the duty-source phrase),
  governing_text (the lead-in sentence), duty_family (a statute named in the sentence, else the product class named
  in it, else `unknown`), country_scope (`products|articles|goods of [the] Name` in the sentence, else empty), note
  (last note number seen).
- **Page boundary.** The state at the end of physical page n is carried to page n + 1 only if page n + 1 of the same
  source is in the corpus. Archive revisions hold only some pages, so most archive pages start empty.
- **R2, chapter 99 rate-table pages.** No heading is inherited (a description precedes its heading number, so the
  previous heading would be wrong). Context: revision and page.
- **R3, Federal Register.** Title, document type and number, publication date from the API metadata. Effective
  dates, abstracts and the author's own document notes are not used.
- **R4, CSMS.** The message subject (first line). **R5, others.** Revision and document kind.
- Nothing is guessed: a field that cannot be read from these sources stays empty or `unknown`.
- The enrichment code reads only the corpus documents, their raw page files, `data/raw/hts/RELEASE.txt` and
  `data/raw/federal_register/doc_*.json`. It never reads the citation seed, qrels, queries or evaluation output
  (tests check the code and the files actually opened).

## When the rules were fixed (honest order)

- 2026-11-09, before the first B2 search run: config hash
  `e013ec0e175cd8c1b7af15540deb4db5a01526daaf407c799f9ece96d383bc73`, module sha256
  `e8a582358c199711cf918dc9810accfc7dd5bc622b5f81a426eba0d7c6b8099b` (before tests were added; later changes are
  listed below). Not committed before the run, so the order is stated, not proven by a commit time.
- The rules were corrected once before that, after printing the context of the 75 B1 review units (no search had
  been run): items that mention headings were taken for lead-ins (`(a) products ... provided for in headings ...`
  overrode `(v) ... duty imposed by heading 9903.03.01`), the page header made a page-top chunk inherit the previous
  page's subdivision, and labels longer than four letters (`(xxxvi)`) were not read. These are general parsing
  errors, but they were found on pages the dev set uses, which is recorded here.
- Any change after the first run gets a new configuration id and a new run; the first run is kept.

## Known gaps at freeze

- A lead-in phrased "Heading X shall not apply to articles the product of the following countries" (the reciprocal
  country list, e.g. 2025 Rev. 7 page 184, subdivision (xiii)) is not a lead-in under R1, so the country list gets no
  heading context. Left as is: adding the phrasing now would be a change made after seeing a dev case.
- The HTS notes rarely name the statute; `duty_family` is mostly `unknown` or a product class. The surcharge
  exclusion (2026 Rev. 4 note 2 (aa)(v)) now carries `applicable_heading: 9903.03.01`, but "section 122" or
  "surcharge" is not on the page, so whether a reader can judge it from the unit alone is open.
- `note` is empty on archive pages whose note line is on a page outside the corpus.
- The context describes the subdivision governing the chunk start; a lead-in that begins inside the chunk is only in
  `raw_text`.

## Structural error found after the first run (not fixed in b2_heading_v1)

- In the HTS Rev. 22 PDF text the note numbers ("21.") are not at the start of a line, so the "new note closes the
  lead-in" rule never fires there. A lead-in then stays open until its sibling label appears. `(gg) For purposes of
  heading 9903.88.28, the additional duties imposed by heading 9903.88.15 ...` (page 365) is carried to page 501,
  into other notes (e.g. the aircraft-dispute subheadings 9903.89.xx): 1,008 chunks.
- In total 15 lead-ins are carried over three or more pages, 1,088 of the 1,649 chunks that have a governing
  context; some of the shorter carries may be legitimate long lists, they have not been checked one by one.
- Effect on run_004: 3 of 230 top-10 rows carry such a context (dq04_en, dq14_en). None of the 75 review units is
  affected (their contexts come from the same page).
- Fixing it changes the rules after the first run, so it would be a new configuration (`b2_heading_v2`) and a new
  run; `b2_heading_v1` and run_004 stay as they are. Not started: waiting for the user's decision.

## First run: run_004_b2_heading_v1 (exploratory, strict citation qrels only)

Same 24 answerable queries, time conditions and matched pairs as run_003. Strict citation qrels count only the cited
file and page, so they are not the reviewed comparison; B1 rows reproduce run_003's `citation` rows exactly.

| Set | Group | B1 macro R@5 | B2 macro R@5 | B1 macro R@10 | B2 macro R@10 | B1 MRR@10 | B2 MRR@10 |
|---|---|---|---|---|---|---|---|
| main (14) | all | 0.3571 | 0.4286 | 0.5714 | 0.5714 | 0.2890 | 0.3750 |
| main | en | 0.5714 | 0.7143 | 0.7143 | 0.7143 | 0.4966 | 0.6429 |
| main | ko | 0.1429 | 0.1429 | 0.4286 | 0.4286 | 0.0813 | 0.1071 |
| underspecified (10) | en | 0.4000 | 0.7000 | 0.9000 | 0.7000 | 0.2536 | 0.5667 |
| underspecified | ko | 0.0000 | 0.1000 | 0.0000 | 0.1000 | 0.0000 | 0.2000 |

Micro recall, nDCG, zero-result rate, paired rows and gaps are in `dev_metrics.csv`. Main-set paired gap (3 pairs)
on Recall@10 is 0.00 for both; unanswerable: English returns something in both (mean top score 15.09 B1, 12.81 B2),
Korean returns nothing in both.

Per query (strict): better in B2 for dq02_en, dq04_en, dq07_en, dq09_en, dq09_ko, dq10_en (cited unit moved into
the top 5 or to rank 1), dq05_ko and dq11_ko (MRR only); worse for **dq03_en**: the cited 9903.85.08 rate-table row
drops out of the top 10, displaced by notes-page list chunks whose context now names heading 9903.85.08. Adding a
heading to every chunk under it can crowd out the chunk that states the rate ("context flooding"); this is a cost of
the design, not only of v1.

Units, size, time (wall clock, this machine, median of 5 rounds over the 28 queries):

| System | Chunks | Mean raw tokens | Mean indexed tokens | Index terms | Postings | Build s | Search ms/query |
|---|---|---|---|---|---|---|---|
| B1 | 7,738 | 121.9 | 121.9 | 35,479 | 559,758 | 0.83 | 10.80 |
| B2 | 7,738 | 121.9 | 146.6 | 35,678 | 684,717 | 1.40 | 11.25 |

Context origin of the 7,738 B2 chunks: document metadata 1,542, same page 549, previous page 1,100 (mostly the
error above), none 4,547.

## Evaluation (pending review)

- B2 is a new retrieval unit: qrels v2 are not reused. Candidates are the B2 children of the 75 B1 review units
  (same quote-overlap rule, retriever-independent), reviewed blind with the v2 criterion; `uncertain` stays out of
  the qrels; time conditions and the 7 mismatched pairs follow run_003.
- First run `reports/retrieval/run_004_b2_heading_v1/`: strict citation qrels only (mechanical, the same for B1 and
  B2), plus chunk, length, index and timing statistics. The B1/B2 comparison on reviewed qrels waits for the review.
