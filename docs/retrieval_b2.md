# B2: heading-enriched BM25

| Configuration | Status | Run | Code |
|---|---|---|---|
| `b2_heading_v1` | `invalid_structural_context`, diagnostic only | `run_004_b2_heading_v1` | commit `cbfc98b`, module sha256 `e8a58235…`, config sha256 `e013ec0e…` |
| `b2_heading_v2` | `invalid_structural_context` (3 boundary errors found in the review of its long contexts); run_005 is `exploratory_unreviewed` diagnostic | `run_005_b2_heading_v2` | commit `5347361`, module `6fac43ca…`, config `ca5f5d91…` |
| `b2_heading_v3` | superseded: heading lists cut at the printed line (65 contexts, 101 chunks) and product class read from exclusion sentences (22 chunks); run_006 is `exploratory_unreviewed` diagnostic | `run_006_b2_heading_v3` | see "Configuration b2_heading_v3" |
| `b2_heading_v4` | `post-diagnostic review checkpoint`: rules changed after looking at run_005/run_006 results; not reviewed; the review items use it | `run_007_b2_heading_v4` | see "Configuration b2_heading_v4" |

Only v2 was frozen by a commit before its first run (`5347361`). v3 and v4 were written after earlier runs' results
had been seen and are recorded as post-diagnostic changes, not as pre-run freezes.

`b2_heading_v1`: after its first run a lead-in was found carried over 1,088 chunks of other subdivisions and notes
(below). Its results stay in `reports/retrieval/run_004_b2_heading_v1/` and
`data/extracted/retrieval_b2/b2_heading_v1_manifest.json`, its unused review sheet in `evals/dev/review_b2_v1/`.
The current module still produces v1 output exactly with `config_id="b2_heading_v1"` (tested against the v1
manifest hash). No qrels were reviewed and no B1/B2 conclusion is drawn here. Strategy and
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

## Configuration b2_heading_v2 (fixed 2026-11-09, before its first search run)

Only the closing of a lead-in changes; everything else is v1 (lead-in definition, fields, duty_family and country
rules, rate-table pages, Federal Register and CSMS context, `index_text`, `chunk_id` formula). The p12 country-list
phrasing stays unrecognized (`unknown`), and `duty_family` stays `unknown` unless the governing sentence names it.

- **Note boundary, second printed form.** Besides a line starting `N. `, a line starting with a parenthesized note
  number directly followed by the first subdivision, `(N)(a)`, starts a new note and closes the open lead-in. In
  HTS Rev. 22 note 21 is printed `(21)(a) Except as provided ...`, which v1 did not read.
- **Later siblings.** A non-lead-in marker closes the open lead-in when it has the same form and comes later in
  sequence, not only when it is the next label: digits by value; single letters, and repeated letters of the same
  length, alphabetically, in both cases unless the label is also a roman numeral (`(v)`, `(x)`, `(ii)` may be items
  inside a lettered subdivision); roman numerals by value. In note 20, `(mm) The U.S. Trade Representative ...` is
  not a lead-in (its first sentence is longer than 300 characters), so in v1 it did not close `(gg)`.
- **Page boundary (unchanged, restated).** State is carried only to physical page n + 1 of the same source, and only
  when page n parsed as a notes page; with a gap, another revision, a rate-table page or a page whose lines do not
  rebuild its text, nothing is inherited.
- A first draft of the later-sibling rule closed lettered lead-ins at roman items (12 same-page contexts lost); the
  roman exception for single letters was added before the hashes below. No v2 search had been run.

Fixed values (module sha256 is over the LF file committed with them):

| Item | Value |
|---|---|
| config sha256 (`b2_heading_v2`) | `ca5f5d91b4e9fa9c65dac5ead19f40d809d42fbb6f619ca0314c9ddd03d27ab7` |
| module sha256 (`structure.py`) | `6fac43cac53656e5025c617b64379ce33311f46e7ec406755ea0bee98d7266af` |
| B2 v2 chunks sha256 | `07fd7363248a838ae00277a641b70ec24fd422abfefa495500b6ddcab3b0332d` |

Structure statistics, v1 → v2 (also in the run manifest; checked by tests):

| Statistic | v1 | v2 |
|---|---|---|
| chapter 99 notes/table chunks | 5,359 | 5,359 |
| chunks with a governing context | 1,649 | 675 |
| of which inherited from an earlier page | 1,100 (66.7%) | 126 (18.7%) |
| same-page contexts | 549 | 549 (identical text) |
| maximum inheritance distance | 136 pages | 6 pages |
| contexts reaching over 2 pages | 14 | 14 |
| chapter 99 chunks without context (unknown) | 69.2% | 87.4% |
| `duty_family` unknown among governed chunks | 88.7% | 72.4% |

The 14 contexts that still reach 3 to 6 pages are long code lists under one subdivision (spot-checked: e.g. Rev. 22
pages 198 to 204 under `(b) As provided in heading 9903.02.81 ...`, pages 582 to 588 under `(iii) ... heading
9903.05.40`); they were not verified one by one. The contexts of the 75 B1 review units are the same in v1 and v2.

## Review of the 14 long contexts of v2 (3 to 6 pages), 2026-11-09

All in HTS Rev. 22 chapter 99. Read line by line from the page text; the expected boundaries are written by hand in
`tests/fixtures/structure_boundaries.csv` (36 probes, independent of the parser's output).

| # | Lead-in (page, label) | Duty-source heading (first) | v2 span | v2 closed by | Verdict | v3 span | Reason; `(v)` check |
|---|---|---|---|---|---|---|---|
| L01 | p177 `(a)` | 9903.01.25 | 177-183 | `(b)` lead-in p183 | correct | 177-183 | next lettered lead-in; no `(v)` in the span |
| L02 | p189 `(xxii)` | 9903.02.19 | 189-192 | `(xxiii)` lead-in p193 | correct | 189-192 | next roman lead-in; no `(v)` |
| L03 | p193 `(xxiii)` | 9903.02.19 | 193-197 | `(b)` lead-in p198 | **wrong** | 193-197 | must close at `(xxiv)`, printed alone on its line on p197; v2 did not read bare labels |
| L04 | p198 `(b)` under `(xxiv)` | 9903.02.79 | 198-204 | `(c)` lead-in p205 | **wrong** | 198-201 | must close at bare `(xxv)` on p201, the next sibling of its parent `(xxiv)`; p201-204 belong to `(xxv)` |
| L05 | p223 `(ii)` | 9903.03.01 | 223-227 | `(iii)` lead-in p227 | correct | 223-227 | roman sequence; no `(v)` |
| L06 | p365 `(gg)` | 9903.88.15 | 365-369 | `(mm)` p369 | correct | 365-369 | later sibling (the v2 rule); product list items `(1)`-`(83)`; no `(v)` |
| L07 | p545 `(ii)` | 9903.05.01 | 545-548 | `(iii)` lead-in p548 | correct | 545-548 | roman sequence; no `(v)` |
| L08 | p553 `(v)` | 9903.05.01 | 553-556 | `(vi)` lead-in p556 | correct | 553-556 | `(v)` is a **roman** numeral here: `(iv)`, `(v)`, `(vi)` in sequence |
| L09 | p562 `(d)` (note 51) | 9903.03.12 | 562-565 | `(b)` lead-in p566 | **wrong** | 562-565 | must close at the note number `52.` printed alone on p565 |
| L10 | p566 `(b)` | 9903.05.20 | 566-569 | `(c)` lead-in p569 | correct | 566-569 | next lettered lead-in; no `(v)` |
| L11 | p574 `(e)` | 9903.05.20 | 574-577 | `(f)` lead-in p577 | correct | 574-577 | next lettered lead-in; no `(v)` |
| L12 | p582 `(iii)` | 9903.05.40 | 582-588 | `(i)` lead-in p588 | correct | 582-588 | a new lead-in of the next numbered subdivision; no `(v)` |
| L13 | p589 `(iii)` | 9903.05.37 | 589-595 | `(i)` lead-in p595 | correct | 589-595 | as L12; no `(v)` |
| L14 | p599 `(i)` | 9903.05.50 | 599-605 | `(ii)` lead-in p605 | correct | 599-605 | roman sequence; no `(v)` |

Three of the 14 were wrong (chunks affected in v2: L03 1 of 6, L04 5 of 10, L09 3 of 8). The `(v)` question: the only
`(v)` in these spans (L08) is a roman numeral and is read as one; no span contains a `(v)` item inside a lettered
subdivision.

Also seen, not changed (a field gap, not a wrong context): `applicable_heading` takes the headings of the duty-source
phrase on the lead-in's first printed line only, so lists that continue on the next line are cut (L01 shows
9903.01.25 and 9903.01.35, the line goes on to 9903.01.39 and more).

## Configuration b2_heading_v3 (post-diagnostic change, 2026-11-09; written after run_005 was seen)

Only the closing of a lead-in changes again; v2's rules stay. Added:

- A label printed alone on its line (`(xxiv)`) is a marker, if it has a label form (digits, one letter, a repeated
  letter, a roman numeral, one capital; `(liters)` and `(Gallons)` are not). A note number printed alone (`52.`) is a
  note boundary.
- A lead-in's parent is the last marker of another form before it (for `(b)` on p198: `(xxiv)`). The next or a later
  sibling of the parent also closes the lead-in.

| Item | Value |
|---|---|
| config sha256 (`b2_heading_v3`) | `dc3bed23cd3522e79c0f714ff6e263924d07680199aa567bde5ef73791284c85` |
| module sha256 (`structure.py`, LF) | `a209ef0cc4f57acedce1e4f41bd44718e71658cd117887fe5f39bee1755219c9` |
| B2 v3 chunks sha256 | `981991b553ec462876bae99de2ec4809f33db8071e479a8e11cad030af9e2dde` |

Hashes taken before run_006 but not committed: the order is stated, not proven. The module still reproduces v1 and
v2 output exactly (tested against their manifests).

| Statistic | v2 | v3 |
|---|---|---|
| chunks with a governing context | 675 | 664 |
| inherited from an earlier page | 126 | 117 |
| maximum inheritance distance | 6 pages | 6 pages |
| contexts reaching over 2 pages | 14 | 14 (the 11 correct ones, L03, L04 and L09 shortened) |
| chapter 99 chunks without context | 87.4% | 87.6% |
| `duty_family` unknown among governed | 72.4% | 72.1% |
| hand-written boundary fixture | 4 of 36 fail | 0 of 36 fail |

## Heading-list cut in v3 and configuration b2_heading_v4 (post-diagnostic review checkpoint, 2026-11-09)

v4 was written after run_005 and run_006 had been seen; its hashes were taken before run_007 and are committed with
the review checkpoint, after run_007. It is a post-diagnostic review checkpoint, not a pre-run freeze.

Measured on v3: a lead-in sentence was read from its first printed line only, so headings continuing on the next
line were dropped. 65 of 302 contexts were cut; in every case headings were missing, none was wrong. 101 chunks; 7
run_006 top-10 rows (all dq10_en); 30 B2 review items, all of them quote-overlap candidates. Examples: Rev. 22 p177
`(a)` showed 2 of 12 headings; Rev. 4 p184 `(ix)` 6 of 12.

`b2_heading_v4` (only the sentence changes; detection and closing are v3's):
- Whether a line is a lead-in is decided on its first printed line as in v3; its sentence (governing_text,
  applicable_heading, duty_family, country_scope) is then read across line breaks, from the marker to the first `:`
  or sentence end, at most 600 characters.
- In a sentence that says the duty does "not apply", `duty_family` comes only from a named statute and
  `country_scope` stays empty: a product class or country there names the excluded goods. This also corrects a v3
  field error found while checking v4: 22 v3 chunks had `duty_family` taken from an exclusion line (14 "passenger
  vehicles", 7 "derivative iron or steel products", 1 "products of aluminum"); none was in run_006's top 10.

| Item | Value |
|---|---|
| config sha256 | `6ba7da219414a4a63f1f4547a27fbbe21f191f4ff3a9b2592b154e0f78786ccd` |
| module sha256 (`structure.py`, LF) | `2f98554df3da279fb9c367d8680a65b23cb0b23a6908983e8a2848674d663267` |
| B2 v4 chunks sha256 | `6072f8fc55104fe3d012fb9c1ed8c32dd734f6ee035bf9b9e6aa83daf31c75a6` |

v3 → v4: 582 contexts change (longer governing text), 101 gain headings, none loses one; subdivisions, notes and
origins are unchanged; `duty_family` unknown among governed chunks 72.1% → 75.3%. Hand-written fixtures: the 36
boundaries (`tests/fixtures/structure_boundaries.csv`) and 7 full sentences (`tests/fixtures/lead_in_sentences.csv`)
pass on v4; v3 fails the full-sentence cases. The module reproduces v1, v2 and v3 output exactly.

## Claim catalog, scoring and review items (prepared, review not started)

Nothing is reviewed and no reviewed metric is computed.

**Evidence** `evals/dev/claim_evidence.csv`: 22 exact official sentences (`evidence_id`, `source_file`, page,
`quote`, `gold_link`, `note`); each quote occurs exactly once in its official file (tested). Federal Register text,
the CBP CSMS message, HTS pages and the HTS 2026 Rev. 4 change record; no internal summary is evidence.
`gold_link` (a citation or regulatory-action id) is auxiliary metadata for tracing, not evidence.

**Claim catalog** `evals/dev/claims.csv`: 39 claims for 24 queries, 37 required (`claim_id`, `query_id`, `pair_id`,
`claim_text`, `required`, `evidence_ids`, `gold_links`, `intent_note`).

| Pair | Claims (same for en and ko unless noted) | Evidence |
|---|---|---|
| p01 | CBP stopped collecting IEEPA duties from 12:00 a.m. ET, February 24, 2026 | CSMS sentence, own id `EV.ieepa_end.csms` (not the deal rule's end citation) |
| p02 | 10% on all articles, except as provided in Proclamation 11012 and Annexes I and II | proclamation para. (1) |
| p03 | 9903.85.08 = applicable duty + 50% of the aluminum content | 2025 Rev. 19 rate row |
| p04 | c1 column 1 < 15%: sum is 15%; c2 column 1 >= 15%: additional rate 0 | FR 2025-21940, both sentences |
| p05 | c1 12.5% net of MFN, Annex I / II Part A exceptions; c2 MFN < 12.5%: sum 12.5%; c3 MFN >= 12.5%: section 301 rate 0 | FR 2026-15181 (South Korea paragraph) |
| p06 | de minimis suspension from 12:01 a.m. EDT, August 29, 2025 | EO 14324 sec. 4 |
| p07 | c1 effective July 24, 2026; c2 scope: $800 or less through the international postal network | the interim final rule |
| p08 | suspension extended to 12:01 a.m. EDT, August 1, 2025 | EO 14316 |
| p09 | c1 3304.99.50 on the note 16(n) list; c2 heading 9903.81.91 applies to that list | 2025 Rev. 19 p202 |
| p10 | c1 the surcharge is Proclamation 11012's, imposed through heading 9903.03.01; c2 it excludes the declared aluminum-content value of 9903.85.04/.07/.08 | proclamation title + HTS change record "9903.03.01 Added ... PP 11012"; 2026 Rev. 4 note 2(aa)(v)(d) |
| p11 en | c1 EO 14389 terminates the collection of IEEPA duties; c2 (not required) date | EO 14389 title and sec. 2(a); CSMS |
| p11 ko | c1 EO 14389 ends the IEEPA duties: no longer in effect and no longer collected; c2 (not required) date | EO 14389 title and sec. 1; CSMS |
| p12 en | 25% additional duty for South Korea (note 2(v)(xiii) list) | 2025 Rev. 7 p186 |
| p12 ko | the same, plus c2: that list carries the reciprocal tariff rates (EO 14266 "Modifying Reciprocal Tariff Rates" suspends (v)(xiii)) | 2025 Rev. 7 p186; FR 2025-06462 title and suspension sentence |

Per-query claim sets for the mismatched pairs (decision record):
- p02: the Korean query omits "on all articles", but the answer is the same proclamation paragraph, and "all
  articles" is the paragraph's own scope; one claim set.
- p04: the Korean query adds "한미 합의" (the U.S.-ROK Deal), which names the notice the rule comes from; the English
  query says "for Korea". Both ask for the same rule; one claim set with both branches.
- p06: the English query states the date, the Korean query asks for it; the claim is the date either way.
- p08: the Korean query has no year; the claim is the same, and its time condition is `underspecified`.
- p10: the Korean query is broader (no "derivative", no "declared value"), but the only gold answer is the (d)
  exclusion and the surcharge identification; a unit with another aluminum exclusion does not support c2. Same set.
- p11: different claims. The English query asks for the end of collection (sec. 2(a)); the Korean "관세 종료" covers
  the duties ending as well as collection (sec. 1).
- p12: different sets. The Korean query names the tariff type (상호관세); the English one asks for the additional
  duty only.

**Scoring** `src/tariffagent/retrieval/claim_scoring.py` (definitions in its docstring; tested on synthetic data).
Claim metrics only; the citation metrics of `evaluate.py` keep their own names and are never in the same table.
- Primary, the only B1/B2 comparison measures: `claim_recall@k`, `all_claims_covered@k`,
  `mrr_any_complete_claim@10`, `mrr_all_claims_complete@10`, `unreachable_claims`.
- Secondary: `partial_claim_recall@k`.
- Diagnostic only: `system_relative_ndcg@10` (fixed grades, IDCG from each system's own judged pool, so B1 and B2
  values are on different scales; no B1/B2 conclusion from it without a common IDCG) and `claim_novelty_dcg@10`.
- Per-query counts: `required_claims`, `unreachable_claims`, `uncertain@10`, `unjudged@10`.

**Review items** `evals/dev/review_claims/` (`scripts/make_claim_review_sheets.py`): one sheet per system. B1 items
show raw text and B1 metadata only; B2 items show the `b2_heading_v4` context, raw text and B2 metadata. Pool per
query: v2 candidates + the system's own top 10 (B1 run_003, B2 run_007) + chunks overlapping the cited quote.
Item key = (intent, required-claim-set hash, displayed-payload hash): intent is the pair for a matched pair and the
query otherwise, so a matched English/Korean pair that returns the same payload is judged once and a mismatched pair
per query. A B2 item whose key equals a B1 item's is marked `same_as:<b1 item>` and judged once; none occurs (every
B2 payload shows a context). Earlier human_assisted judgements are reused on a B1 item only when the intent is the
same matched pair, the gold links of the required claims' evidence equal the gold citations the earlier judgement
used, and the displayed payload and metadata hash is identical. So p01 (its claim now rests on the IEEPA-end
evidence) and p05 (three claims) reuse nothing. Reused relevant items still need their claims and support level.

| Items | B1 | B2 |
|---|---|---|
| query-level units before de-duplication | 327 | 324 |
| review items after de-duplication | 266 | 261 |
| items serving both queries of a matched pair | 61 | 63 |
| same displayed payload as a B1 item | - | 0 |
| reused, complete (not_relevant / uncertain) | 37 (dq09 36, dq07 1) | 0 |
| reused relevant, claims still to fill | 6 (dq03 5, dq07 1) | 0 |
| new judgements | 223 | 261 |

Per-query counts: `evals/dev/review_claims/summary.json`; which queries each item serves: `item_queries.csv`. The
two earlier sheets of this day (`evals/dev/review_b2v2/`, the first `review_claims` sheets on v3) were replaced before
any decision was recorded.

## Order of decisions (honest record)

v3, v4, the claim catalog revisions and the scoring definitions were all made after run_005 and run_006 had been
looked at (their strict diagnostics and top 10, and the 75 B1 review units' contexts), and the claim catalog after
the earlier B1 human_assisted judgements existed. They are design changes made with results in view, not
pre-registered; v4 is a `post-diagnostic review checkpoint`. The claim evidence was then tied to exact official
sentences (no internal summary), and the scoring split into primary claim measures and diagnostic ones. What has not
been seen by anyone: any judgement of a B2 unit, and any claim-level judgement. The checkpoint commit made before the
user's review holds `structure.py` (v4), the fixtures, the claim evidence and catalog, `claim_scoring.py`, the sheet
scripts, the empty review items, the run_005/006/007 diagnostics and this record; it holds no user judgement and no
B1/B2 conclusion.

## Run status

| Run | Status |
|---|---|
| run_004_b2_heading_v1 | diagnostic, `invalid_structural_context` |
| run_005_b2_heading_v2 | `exploratory_unreviewed` diagnostic; v2 `invalid_structural_context` |
| run_006_b2_heading_v3 | `exploratory_unreviewed` diagnostic; v3 superseded (heading lists cut) |
| run_007_b2_heading_v4 | `exploratory_unreviewed`, strict citation qrels only; its B2 top 10 feeds the review items |

run_006 diagnostics (strict citation qrels; macro R@5 / R@10 / MRR@10; exploratory, not a comparison):

| Set, group | B1 | B2 v2 (run_005) | B2 v3 (run_006) | B2 v4 (run_007) |
|---|---|---|---|---|
| main, en (7) | 0.57 / 0.71 / 0.50 | 0.71 / 0.71 / 0.64 | 0.71 / 0.71 / 0.64 | 0.71 / 0.71 / 0.64 |
| main, ko (7) | 0.14 / 0.43 / 0.08 | 0.14 / 0.43 / 0.11 | 0.14 / 0.43 / 0.11 | 0.14 / 0.43 / 0.10 |
| underspecified, en (5) | 0.40 / 0.90 / 0.25 | 0.70 / 0.80 / 0.60 | 0.70 / 0.80 / 0.70 | 0.50 / 0.70 / 0.43 |
| underspecified, ko (5) | 0.00 / 0.00 / 0.00 | 0.10 / 0.10 / 0.07 | 0.10 / 0.10 / 0.07 | 0.10 / 0.10 / 0.07 |

- B1: identical metric rows in run_005, run_006 and run_007, equal to run_003's citation rows; B1 corpus, chunk and
  index hashes equal B1's manifest.
- Top 10 changed v2 → v3 for 11 queries (order; set changes in dq03_ko 2, dq10_en 1, dq12_ko 1), v3 → v4 for 13
  (set changes in dq03_ko 1, dq09_en 1, dq09_ko 3, dq10_en 2, dq12_en 1, dq12_ko 1).
- dq03_en: the cited 9903.85.08 rate row is outside the top 10 in v2, v3 and v4; all 10 rows are notes-page chunks
  whose context names heading 9903.85.08.
- Context flooding, counted as top-10 rows where a heading named in the query appears in the context but not in the
  raw text: 9 of 230 rows in v2, v3 and v4 alike (dq09_en 3, dq09_ko 6). dq03_en's displacement is not counted by this
  measure (its rows also carry 9903.85.08 in the raw text); it comes from the heading being repeated in the context.
- The underspecified English drop in v4 (strict) is in the strict, cited-location-only qrels; it is not interpreted
  before the review.

No B1/B2 conclusion is drawn from any of them.

## First run of v2: run_005_b2_heading_v2 (status: exploratory_unreviewed, diagnostic)

Run after the freeze commit `5347361`; the run manifest records the same module, config and chunk hashes. B1 rows
reproduce run_003's `citation` rows exactly (B1 corpus, chunk and index hashes checked against B1's manifest).
Strict citation qrels count only the cited file and page; they are not the reviewed comparison.

| Set | Group | B1 macro R@5 | B2 v2 macro R@5 | B1 macro R@10 | B2 v2 macro R@10 | B1 MRR@10 | B2 v2 MRR@10 |
|---|---|---|---|---|---|---|---|
| main (14) | all | 0.3571 | 0.4286 | 0.5714 | 0.5714 | 0.2890 | 0.3763 |
| main | en | 0.5714 | 0.7143 | 0.7143 | 0.7143 | 0.4966 | 0.6429 |
| main | ko | 0.1429 | 0.1429 | 0.4286 | 0.4286 | 0.0813 | 0.1097 |
| underspecified (10) | en | 0.4000 | 0.7000 | 0.9000 | 0.8000 | 0.2536 | 0.6000 |
| underspecified | ko | 0.0000 | 0.1000 | 0.0000 | 0.1000 | 0.0000 | 0.0667 |

- Per query (strict): better for dq02_en, dq04_en, dq07_en, dq09_en, dq09_ko, dq10_en, dq05_ko and dq11_ko (MRR);
  worse for dq03_en, as in v1: the cited 9903.85.08 rate-table row leaves the top 10, which is filled by notes-page
  list chunks whose context names heading 9903.85.08. This is the context-flooding cost of the design, not the v1
  error.
- Main-set paired gap (3 pairs): Recall@10 0.00 for both systems. Unanswerable: English returns something in both
  (mean top score 15.09 B1, 12.77 B2 v2), Korean nothing in both.
- Units: 7,738 in both; mean indexed tokens 121.9 (B1) vs 143.1 (B2 v2); postings 559,758 vs 667,062; index terms
  35,479 vs 35,678; search 9.37 vs 18.32 ms per query (median of 5 rounds, wall clock, this machine; run_004 measured
  10.80 vs 11.25, so the timing is noisy at this size).

## Review pool for v2 (blind sheet, not reviewed)

`scripts/make_b2v2_review_sheet.py` writes `evals/dev/review_b2v2/`. Per answerable pair, the union of: the v2 qrel
candidates (quote overlap, 75 units), B1 top 10 (run_003) and B2 v2 top 10 (run_005) of both queries, and chunks
overlapping the cited quote; de-duplicated by the B1 parent chunk and shown as B2 v2 units (context_text, raw_text,
metadata). 255 units; 180 of them overlap no cited quote (pooled from the systems' top 10 only). Pool membership is
kept in `unit_pools.csv` and is not on the sheet. The v1 sheet (`evals/dev/review_b2_v1/`) is not used.

Open decisions before the review (not taken here):
- How a relevant unit that overlaps no cited quote counts for recall in a pair with two citations (p07, p09); for the
  other pairs it can only support the pair's one citation.
- B1 is compared on B1 units (raw text only). Units pooled from B1 top 10 that were not in v2 have no B1-form
  judgement; judging them as B2 units shows a context B1 never returns.

## First run of v1: run_004_b2_heading_v1 (exploratory, strict citation qrels only, diagnostic)

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
