# Review process notes (human_assisted)

The user reviewed every unit and query in chat, 2026-11-06. For each batch of five, Claude showed the query (English
and Korean), the returned metadata and a plain Korean translation of the chunk, without stating a judgement, and
recorded the user's answer word for word (관련 → relevant, 무관 → not_relevant, 불확실 → uncertain). Claude's sealed
files (`claude_review.csv`, `claude_time_review.csv`) were not opened during the review.

Possible influence of the translation, recorded so the agreement can be read with it:

- Long HTS code lists were summarized (first code, last code, approximate count, whether 3304.99.50 appears), not
  translated code by code.
- Chunks whose text is identical to an earlier unit were marked as identical (checked by script, character for
  character), and later ones were shortened.
- Bracketed words were added in a few translations: `[끊김]` where the chunk is cut, `[기준]` after "prior to …",
  `[예외로 하고]` in u017, `[비철강 함량]` at the start of u064, and in **u065** the phrase
  `[호에 정한 알루미늄 파생 제품의 알루미늄 함량 신고가액]`, which is **not in the chunk**. Claude pointed this out after
  the user's u065 answer; the answer was kept unchanged.
- For p10 the question shown was a translation of the English query; for p09 the question was rendered as
  "9903.81.91 호의 철강 파생 제품 목록에 3304.99.50(화장품)이 있는가", which adds the word 화장품 from the Korean query.

Query pairs: the user also judged whether each English/Korean pair asks the same thing (`pair_checks.csv`): 7 pairs
mismatched, 5 matched. Mismatched pairs are left out of paired language comparisons; their individual results stay.
