"""Write warehouse/seeds/regulatory_actions.csv from the hand-transcribed rows below.

The rows are transcribed by reading the archived originals (data/raw); every value cites its source in
source_quote_ref. Kept as Python so commas inside values are quoted correctly. Run once after editing:

    uv run python scripts/_build_regulatory_actions_seed.py

rate_kind: additional_ad_valorem (added on top of the column 1 rate) | total_with_column1 (column 1 + this duty is
           capped at rate_pct; the added duty is rate_pct minus column 1, or 0) | none (not a rate)
PDF page numbers in source_quote_ref are physical 1-based indexes of data/raw/hts/chapter_99.pdf (Rev. 22) or of the
named archived revision (data/raw/hts_archive/<release>/chapter_99.pdf), with the printed label where it matters.
archive_evidence: which archived HTS revisions and change-record entries support the dates; 'archive_gap' marks a
boundary that falls between two revisions without a dated change-record entry.

evidence_status: quote_checked (every filled value compared with the cited source sentence by the author; not yet
                 reviewed by the user) | unverified.
resolution_status: resolved | partial (application not fully modelled or dated; see open_issues and PARTIAL) |
                   unresolved (a needed value is not in the corpus).
The rows below still carry the transcription field `status` (quote_checked | incomplete), split by finish().

status: quote_checked = the author compared every filled value with the source sentence (not yet reviewed by
        the user, who is the reference for gold labels; open_issues may hold caveats); incomplete = some value could not be transcribed from
        the archived sources. open_issues lists what is unknown and why; values are never guessed.
"""

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "warehouse" / "seeds" / "regulatory_actions.csv"
FIELDS = ["action_id", "instrument", "legal_basis", "signed_at", "published_at", "effective_at", "ends_at", "ends_rule",
          "applicability_rule", "scope", "rate_or_effect", "rate_kind", "rate_pct", "stacking_rule", "supersedes", "superseded_by", "amends",
          "unaffected_actions", "source_quote_ref", "archive_evidence", "cosmetics_3303_3307", "evidence_status", "resolution_status",
          "open_issues"]

ENTRY = "goods entered for consumption, or withdrawn from warehouse for consumption, on or after effective_at"

ROWS = [
    dict(action_id="EO14257_baseline10", rate_kind='additional_ad_valorem', rate_pct='10', stacking_rule="'in addition to any other duties, fees, taxes, exactions, or charges' (2025-06063 sec. 3(c)) except as provided in 3(d)-(e); replaced (not stacked) by the country rate for Korea on 2025-04-09 (see EO14257_KR25)",
         instrument="EO 14257 (FR 2025-06063)", legal_basis="IEEPA",
         signed_at="2025-04-02", published_at="2025-04-07", effective_at="2025-04-05T00:01-04:00",
         ends_at="2026-02-24T00:00-05:00",
         ends_rule="IEEPA additional duties ended by EO14389_end_ieepa (cut-off per CBP CSMS # 67834313); for Korea the 10% is replaced by the "
                   "country rate EO14326_KR15 from 2025-08-07",
         applicability_rule=ENTRY + "; goods loaded onto a vessel and in transit on the final mode of transit before "
                            "effective_at, and entered after it, are not subject (no entry deadline in this text)",
         scope="all trading partners", rate_or_effect="+10% ad valorem (HTS 9903.01.25)",
         superseded_by="EO14326_KR15 (Korea)",
         source_quote_ref="2025-06063 sec. 3(a): 'on or after 12:01 a.m. eastern daylight time on April 5, 2025, "
                          "except that goods loaded onto a vessel ... before 12:01 a.m. ... April 5, 2025, and "
                          "entered ... after 12:01 a.m. ... April 5, 2025, shall not be subject'",
         status="quote_checked", open_issues=""),
    dict(action_id="EO14257_KR25", rate_kind='additional_ad_valorem', rate_pct='25',
         stacking_rule="replaces, does not stack with, EO14257_baseline10: in HTS 2025 Rev. 7 heading 9903.01.25 (10%) "
                       "excepts articles of countries enumerated in U.S. note 2(v)(xiii) entered after 12:01 a.m. EDT "
                       "on April 9, 2025; South Korea is item (xlvi) of that list",
         archive_evidence="2025 Rev. 7 (posted 2025-04-05) PDF p. 470 (99-III-298) heading 9903.01.25 and pp. 185-186 "
                          "(99-III-13 to 14) note 2(v)(xiii)(xlvi); change record of Rev. 7: 9903.01.54 Added, effective "
                          "April 9, 2025; Rev. 9 change record: 9903.01.25 Modified, effective April 10, 2025. No "
                          "archive_gap: the boundary dates are the change-record effective dates",
         instrument="EO 14257 Annex I (FR 2025-06063); HTS 9903.01.54", legal_basis="IEEPA",
         signed_at="2025-04-02", published_at="2025-04-07", effective_at="2025-04-09T00:01-04:00",
         ends_at="2025-04-10T00:01-04:00",
         ends_rule="enforcement suspended by EO14266_pause from 2025-04-10T00:01-04:00",
         applicability_rule=ENTRY + "; same in-transit exception as the 10% rate (loaded before effective_at)",
         scope="Korea", rate_or_effect="+25% ad valorem (country-specific)",
         superseded_by="EO14266_pause", amends="",
         source_quote_ref="2025-06063 sec. 3(b) '12:01 a.m. eastern daylight time on April 9, 2025'; HTS export "
                          "9903.01.54 'The duty provided in the applicable subheading + 25%'; 2025-06462 sec. 2; "
                          "HTS 2025 Rev. 7 heading 9903.01.25 'except for articles the product of a country enumerated "
                          "in subdivision (v)(xiii) of U.S. note 2' and '(xlvi) South Korea, subject to an additional "
                          "duty of 25%'",
         status="quote_checked", open_issues=""),
    dict(action_id="EO14266_pause", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="EO 14266 (FR 2025-06462)", legal_basis="IEEPA",
         signed_at="2025-04-09", published_at="2025-04-15", effective_at="2025-04-10T00:01-04:00",
         ends_at="2025-07-09T00:01-04:00",
         applicability_rule=ENTRY,
         scope="all Annex I trading partners except the PRC",
         rate_or_effect="country-specific rates suspended; the 10% rate (9903.01.25) applies instead",
         amends="EO 14257", supersedes="EO14257_KR25",
         ends_rule="extended by EO14316_extend to 2025-08-01T00:01-04:00; during the suspension EO14257_baseline10 "
                   "applies instead",
         source_quote_ref="2025-06462 sec. 2: 'on or after 12:01 a.m. eastern daylight time on April 10, 2025, "
                          "enforcement of the second paragraph of section 3(a) of Executive Order 14257 is suspended "
                          "until 12:01 a.m. eastern daylight time on July 9, 2025'",
         status="quote_checked", open_issues=""),
    dict(action_id="EO14316_extend", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="EO 14316 (FR 2025-12962)", legal_basis="IEEPA",
         signed_at="2025-07-07", published_at="2025-07-10", effective_at="2025-07-09T00:01-04:00",
         ends_at="2025-08-01T00:01-04:00",
         ends_rule="suspension continued by EO14326_continue until 2025-08-07T00:01-04:00",
         applicability_rule=ENTRY, scope="all Annex I trading partners except the PRC",
         rate_or_effect="suspension of country-specific rates extended (HTS 9903.01.43-9903.01.62 and "
                        "9903.01.64-9903.01.76 suspended)",
         amends="EO 14266",
         source_quote_ref="2025-12962: 'extend the suspension effectuated by Executive Order 14266 until 12:01 a.m. "
                          "eastern daylight time on August 1, 2025'; sec. 2 'on or after 12:01 a.m. eastern daylight "
                          "time on July 9, 2025, by suspending headings 9903.01.43 through 9903.01.62 and 9903.01.64 "
                          "through 9903.01.76'",
         status="quote_checked", open_issues=""),
    dict(action_id="EO14326_continue", rate_kind="none", rate_pct="", stacking_rule="",
         instrument="EO 14326 sec. 2(e) (FR 2025-15010)", legal_basis="IEEPA",
         signed_at="2025-07-31", published_at="2025-08-06", effective_at="2025-08-01T00:01-04:00",
         ends_at="2025-08-07T00:01-04:00",
         ends_rule="ends when the Annex modifications take effect (EO14326_KR15); EO14257_baseline10 applies to "
                   "Korean goods meanwhile",
         applicability_rule=ENTRY, scope="all Annex I trading partners except the PRC (Korea included)",
         rate_or_effect="country-specific rates stay suspended (HTS 9903.01.43-9903.01.62 and 9903.01.64-9903.01.76); "
                        "the 10% rate applies",
         amends="EO 14316", supersedes="EO14316_extend", superseded_by="EO14326_KR15",
         source_quote_ref="2025-15010 sec. 2(e): 'continuing to suspend headings 9903.01.43 through 9903.01.62 and "
                          "9903.01.64 through 9903.01.76' ... 'until the effective date of the modifications provided "
                          "in A'; HTS 2025 Rev. 17 heading 9903.01.54 'provision suspended'",
         archive_evidence="2025 Rev. 17 (posted 2025-08-01) PDF p. 484 (99-III-312): 9903.01.54 suspended, 9903.01.25 "
                          "applies to any country; Rev. 18 change record: 9903.01.54 Modified (terminated) and 9903.02.56 "
                          "Added, effective August 7, 2025. effective_at is the end of EO14316_extend; the order was "
                          "signed before that date",
         cosmetics_3303_3307="", status="quote_checked", open_issues=""),
    dict(action_id="EO14326_KR15", rate_kind='additional_ad_valorem', rate_pct='15', stacking_rule='added on top of column 1; HTS Rev. 22 heading 9903.01.25 (10%) excludes 9903.02.02-9903.02.91, but that is the current wording; per Rev. 22 U.S. note 2(v)(ix) (PDF p. 184) the 9903.02.01-9903.02.73 duties do not apply to the aluminum content of 9903.85.08 derivative products (current wording)',
         instrument="EO 14326 (FR 2025-15010); HTS 9903.02.56", legal_basis="IEEPA",
         signed_at="2025-07-31", published_at="2025-08-06", effective_at="2025-08-07T00:01-04:00",
         ends_rule="for Korean goods other than autos and parts replaced by KORdeal_15allin from "
                   "2025-11-14T00:01-05:00; IEEPA duties ended by EO14389_end_ieepa",
         applicability_rule=ENTRY + " (7 days after 2025-07-31); goods loaded before effective_at and entered "
                            "before 2025-10-05T00:01-04:00 are not subject",
         scope="Korea", rate_or_effect="+15% ad valorem",
         supersedes="EO14257_baseline10 (Korea)", superseded_by="KORdeal_15allin", amends="EO 14257",
         source_quote_ref="2025-15010 sec. 2(a): '12:01 a.m. eastern daylight time 7 days after the date of this "
                          "order' and in-transit '... before 12:01 a.m. eastern daylight time on October 5, 2025'; "
                          "HTS export 9903.02.56 'The duty provided in the applicable subheading + 15%'",
         status="quote_checked", open_issues=""),
    dict(action_id="KORdeal_15allin", rate_kind='total_with_column1', rate_pct='15', stacking_rule='reciprocal duty = 15% minus column 1 rate (0 when column 1 >= 15%); per HTS Rev. 22 U.S. note 2(v)(ix) (PDF p. 184 = 99-III-12) the duties of 9903.02.79-9903.02.80 do not apply to the declared value of the aluminum content of 9903.85.04/.07/.08/.09 derivative products but apply to the non-aluminum content (current wording)',
         instrument="Notice FR 2025-21940 (ITA and USTR)",
         legal_basis="IEEPA (implements EO 14257 as amended and EO 14346)",
         published_at="2025-12-04", effective_at="2025-11-14T00:01-05:00", ends_at="2026-02-24T00:00-05:00",
         ends_rule="IEEPA duties ended by EO14389_end_ieepa (cut-off per CBP CSMS # 67834313)",
         applicability_rule=ENTRY + "; effective_at precedes published_at (the notice applies retroactively)",
         scope="goods of Korea subject to the country-specific reciprocal tariff (Part B of the Annex); autos and "
               "parts are Part A from 2025-11-01",
         rate_or_effect="column 1 rate + reciprocal = 15% when column 1 < 15%; reciprocal = 0% when column 1 >= 15%",
         supersedes="EO14326_KR15 (non-auto goods)", amends="EO 14257",
         source_quote_ref="2025-21940 DATES '... on or after 12:01 a.m. eastern time on November 14, 2025'; "
                          "'the sum of the column 1 duty rate and the additional ad valorem rate ... will be 15 percent'",
         status="quote_checked", open_issues=""),
    dict(action_id="EO14389_end_ieepa", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="EO 14389 (FR 2026-03832)", legal_basis="IEEPA",
         signed_at="2026-02-20", published_at="2026-02-25", effective_at="2026-02-24T00:00-05:00",
         ends_rule="the listed IEEPA duties 'shall no longer be in effect and, as soon as practicable, shall no "
                   "longer be collected' (EO); CBP set the cut-off in CSMS # 67834313",
         applicability_rule="goods entered for consumption or withdrawn from warehouse for consumption on or after "
                            "12:00 a.m. eastern time on February 24, 2026 (CBP CSMS # 67834313); the EO itself has no "
                            "entry-date rule. Dates kept apart: EO signed 2026-02-20; CSMS sent 2026-02-22 09:57 PM "
                            "EST; collection ends 2026-02-24 00:00 ET; published 2026-02-25; HTS 2026 Rev. 4 posted "
                            "2026-02-25 with change-record effective date February 24, 2026. Note: P11012_surcharge "
                            "starts at 12:01 a.m. EST, one minute after this cut-off",
         scope="additional ad valorem duties under IEEPA in EOs 14193, 14194, 14195, 14245, 14257, 14323, 14329, "
               "14380 and 14382",
         rate_or_effect="ends those IEEPA additional duties",
         amends="EO 14257 and the other listed orders",
         unaffected_actions="EO14388_continue and P11012_surcharge (named by title and date in sec. 2(c)); duties "
                            "under section 232 and section 301 (sec. 2(d))",
         source_quote_ref="2026-03832 sec. 1, sec. 2(a), 2(c), 2(d); API disposition_notes list EO 14388 and "
                          "Proc. 11012; CBP CSMS # 67834313 'will no longer be in effect and will no longer be collected "
                          "for goods entered for consumption or withdrawn from warehouse for consumption, on or after "
                          "12:00 a.m. eastern time on February 24, 2026' and 'all Harmonized Tariff Schedule of the "
                          "United States (HTSUS) numbers applicable to the IEEPA tariffs will be inactive in ACE as of "
                          "February 24, 2026'",
         archive_evidence="2026 Rev. 4 (posted 2026-02-25) change record: U.S. note 2(a), (c), (j), (l), (m), (u), "
                          "(y) Modified and 2(w) Deleted, effective February 24, 2026, source 'Executive Order'. The "
                          "collection cut-off itself comes from CBP CSMS # 67834313 (official implementing guidance), "
                          "so no archive_gap remains",
         status="quote_checked",
         open_issues="Caveat: the CSMS lists EOs 14193, 14194, 14195, 14245, 14257, 14323 and 14329; EO 14389 also "
                     "names 14380 and 14382, which the CSMS does not list. Neither concerns Korean goods"),
    dict(action_id="P11012_surcharge", rate_kind="additional_ad_valorem", rate_pct="10",
         stacking_rule="'in addition to any other duties' (para. (3)); 'shall not apply in addition to tariffs imposed "
                       "under section 232' and applies only to the non-232 part of an import (para. (4)); in HTS 2026 "
                       "Rev. 4 note 2(aa)(v)(b) and (d) it does not apply to the declared value of the steel content of "
                       "9903.81.89-9903.81.93 / .96-.99 derivatives or of the aluminum content of 9903.85.04/.07/.08/.09 "
                       "/.13-.15 derivatives but applies to the non-metal content; those subdivisions were deleted "
                       "effective April 6, 2026 (Rev. 5 change record, PP 11021); ends when S301_KR_12_5 starts "
                       "(2026-07-24T00:01-04:00), so the two do not overlap",
         instrument="Proclamation 11012 (FR 2026-03824); HTS 9903.03.01-9903.03.11",
         legal_basis="Trade Act of 1974 sec. 122", signed_at="2026-02-20", published_at="2026-02-25",
         effective_at="2026-02-24T00:01-05:00", ends_at="2026-07-24T00:01-04:00",
         ends_rule="through ends_at unless suspended, modified or terminated earlier, or extended by an Act of "
                   "Congress (150-day limit of sec. 122)",
         applicability_rule=ENTRY + "; goods loaded before effective_at and entered before 2026-02-28T00:01-05:00 "
                            "are not subject (HTS 9903.03.02)",
         scope="articles of all countries, except those in Annex I paragraph 2 and Annex II; not in addition to "
               "section 232 tariffs",
         rate_or_effect="+10% ad valorem temporary import surcharge (HTS 9903.03.01), treated as a regular customs "
                        "duty and in addition to other duties",
         unaffected_actions="",
         source_quote_ref="2026-03824 paras. 13, (1)-(5), (7); HTS export 9903.03.01-9903.03.11; HTS Rev. 22 chapter 99 "
                          "PDF p. 221 U.S. note 2(aa)(i) 'imposes an additional ad valorem rate of duty on imports of "
                          "all products of any country' and compiler's note 'expired at the close of July 23, 2026'; "
                          "HTS 2026 Rev. 4 note 2(aa)(v) 'the declared value of the aluminum content of the derivative "
                          "aluminum products provided for in headings 9903.85.04, 9903.85.07, 9903.85.08'",
         archive_evidence="2026 Rev. 4 (posted 2026-02-25) change record: note 2(aa)(i)-(viii) and 9903.03.01-.11 "
                          "Added, effective February 24, 2026, PP 11012; Rev. 4 PDF p. 230 (99-III-58) note 2(aa)(v)(a)-(e). "
                          "2026 Rev. 5 (posted 2026-04-08) change record: note 2(aa)(v)(a)-(d), (g) Deleted and "
                          "9903.85.08, 9903.81.91 Deleted, effective April 6, 2026, PP 11021. Rev. 13 change record: note "
                          "52 Established effective July 24, 2026. No archive_gap for cosmetics: each change is dated in "
                          "a change record",
         status="quote_checked",
         cosmetics_3303_3307="By period, for Korean cosmetics of headings 3303-3307 (none is in the code lists of note "
                             "2(aa)(ii)-(iv) in Rev. 4 or Rev. 22): "
                             "(a) 2026-02-24 to 2026-04-06: the 10 subheadings outside the 232 derivative lists bear the "
                             "surcharge on full value; the 14 subheadings in note 16(n) (S232_ST_derivative_16n) and note "
                             "19(k) (S232_AL_derivative_19k) bear it on the non-metal content only, per note 2(aa)(v)(b) "
                             "and (d). (b) 2026-04-06 to 2026-07-24: those 232 derivative headings were deleted and the "
                             "14 subheadings appear in no 9903.82 list (Rev. 5, 6, 12, 13), so all 24 bear the surcharge "
                             "on full value. Determinations follow the HTS text and change records; the reviewed "
                             "subheadings were not confirmed as excepted",
         open_issues="Caveat: the treatment of a single entry whose steel and aluminum content are both present is "
                     "not modelled; per-entry metal values are outside this table"),
    dict(action_id="S301_KR_12_5", rate_kind="total_with_column1", rate_pct="12.5",
         stacking_rule="section 301 duty = 12.5% minus MFN (column 1) rate, 0 when MFN >= 12.5%; products also remain "
                       "subject to any additional duty in subchapters III-IV of chapter 99 except as provided in U.S. "
                       "note 52(b)-(k) (PDF p. 565, note 52(a))",
         instrument="USTR notice FR 2026-15181; presidential memorandum FR 2026-15274",
         legal_basis="Trade Act of 1974 sec. 301", signed_at="2026-07-23", published_at="2026-07-28",
         effective_at="2026-07-24T00:01-04:00",
         applicability_rule=ENTRY + "; goods loaded before effective_at and entered before 2026-07-28T00:01-04:00 "
                            "are not subject",
         scope="products of South Korea, except as provided in Annex I and Annex II Part A of the notice",
         rate_or_effect="MFN + section 301 = 12.5% when MFN < 12.5%; section 301 = 0% when MFN >= 12.5%",
         source_quote_ref="2026-15181 para. 49 'South Korea: Determination of Action' and DATES '12:01 a.m. eastern "
                          "time on July 24, 2026'; 2026-15274 '(ii) ... For a product of Japan, Korea, or "
                          "Switzerland ... 12.5 percent'; HTS Rev. 22 chapter 99 PDF p. 658 headings 9903.05.70 "
                          "(MFN >= 12.5%: no change) and 9903.05.71 (12.5%), both 'Except for products described "
                          "in headings 9903.05.85-9903.05.92'; U.S. note 52(a)-(j) pp. 565-605",
         archive_evidence="2026 Rev. 13 (posted 2026-07-28) change record: note 52(a)-(k), 9903.05.70 and 9903.05.71 "
                          "Established, effective July 24, 2026 (Notice). Rev. 13 and Rev. 22 show no 3303-3307 "
                          "subheading in note 52 lists and none in a 232 derivative heading in force (9903.85.08 and "
                          "9903.81.91 deleted effective 2026-04-06)",
         status="quote_checked",
         cosmetics_3303_3307="All 24 subheadings of 3303-3307: not in note 52(b)-(e) code lists (Rev. 13, Rev. 22) and, "
                             "after 2026-04-06, not in any 232 derivative heading, so the 52(f) exception does not reach "
                             "them. The reviewed Korean cosmetics subheadings were not confirmed as excepted from the "
                             "section 301 action",
         open_issues="Caveat: amendments to note 52 after Rev. 13 are read only as of Rev. 22 (2026-11-05)"),
    dict(action_id="S232_AL_derivative_19k",
         instrument="HTS U.S. note 19(k), heading 9903.85.08 (2025 Rev. 19 to 2026 Rev. 4)",
         legal_basis="Trade Expansion Act of 1962 sec. 232",
         effective_at="2025-08-18", ends_at="2026-04-06",
         ends_rule="heading 9903.85.08 Deleted effective April 6, 2026 (2026 Rev. 5 change record, PP 11021); note 19 "
                   "text naming it remains in later revisions but the heading has no tariff row",
         applicability_rule="derivative aluminum products classifiable in the subheadings listed in note 19(k), unless "
                            "processed in another country from aluminum smelted and cast in the United States; the duty "
                            "applies only to the declared value of the aluminum content. effective_at is the date the "
                            "14 cosmetics subheadings entered the list (change record effective date, no time given)",
         scope="all countries other than the United Kingdom (UK: note 19(s), heading 9903.85.15); the list includes 14 "
               "cosmetics subheadings 3303.00.10, 3303.00.20, 3303.00.30, 3304.30.00, 3304.99.50, 3305.10.00, "
               "3305.30.00, 3305.90.00, 3306.90.00, 3307.10.10, 3307.10.20, 3307.20.00, 3307.49.00, 3307.90.00",
         rate_or_effect="+50% upon the value of the aluminum content (HTS 9903.85.08)",
         rate_kind="additional_ad_valorem", rate_pct="50",
         stacking_rule="note 19(h): any additional duty of subchapters III-IV is imposed in addition; the reciprocal "
                       "duties (note 2(v)(ix)) and the surcharge (note 2(aa)(v)(d), until 2026-04-06) apply only to "
                       "the non-aluminum content",
         source_quote_ref="HTS 2025 Rev. 19 heading 9903.85.08 'The duty provided in the applicable subheading + a duty "
                          "of 50% upon the value of the aluminum content'; HTS Rev. 22 chapter 99 PDF p. 256 (99-III-84) "
                          "note 19(k) 'The rates of duty in heading 9903.85.08 apply to all entries of derivative "
                          "aluminum products' and 'shall only apply to the declared value of the aluminum content'",
         archive_evidence="Cosmetics subheadings absent from note 19(k) in 2025 Rev. 18 (posted 2025-08-06) and present "
                          "in Rev. 19 (posted 2025-08-18, PDF note 19(k)); Rev. 19 change record: note 19(k) Modified, "
                          "effective August 18, 2025, source 'Notice' (not identified by number); rate +50% in Rev. 19 "
                          "and 2026 Rev. 3-4; 2026 Rev. 5 change record: 9903.85.08 Deleted, effective April 6, 2026",
         cosmetics_3303_3307="14 of the 24 cosmetics subheadings are listed in note 19(k) from 2025-08-18 to 2026-04-06; "
                             "the other 10 are not",
         status="quote_checked",
         open_issues="Caveat: the Notice behind the 2025-08-18 change is not named in the change record and was not "
                     "collected; the effective time of day is not given"),
    dict(action_id="S232_ST_derivative_16n",
         instrument="HTS U.S. note 16(n), heading 9903.81.91 (2025 Rev. 19 to 2026 Rev. 4)",
         legal_basis="Trade Expansion Act of 1962 sec. 232",
         effective_at="2025-08-18", ends_at="2026-04-06",
         ends_rule="heading 9903.81.91 Deleted effective April 6, 2026 (2026 Rev. 5 change record, PP 11021)",
         applicability_rule="derivative iron or steel products classified in the subheadings listed in note 16(n); "
                            "the duty applies only to the declared value of the steel content. effective_at is the "
                            "date the 14 cosmetics subheadings entered the list (change record effective date)",
         scope="all countries other than the United Kingdom (UK: note 16(u), heading 9903.81.98); the list includes the "
               "same 14 cosmetics subheadings as S232_AL_derivative_19k",
         rate_or_effect="+50% upon the value of the steel content (HTS 9903.81.91)",
         rate_kind="additional_ad_valorem", rate_pct="50",
         stacking_rule="applies together with S232_AL_derivative_19k: note 19(h) says entries of derivative aluminum "
                       "products under 9903.85.04, 9903.85.07 and 9903.85.08 'shall also be subject to the additional "
                       "duties imposed on entries of derivative iron and steel products' (9903.81.89-.91, .93) when "
                       "their conditions are met; the surcharge does not apply to the declared value of the steel "
                       "content (note 2(aa)(v)(b), until 2026-04-06)",
         source_quote_ref="HTS Rev. 22 note 19(h) PDF p. 255 'shall also be subject to the additional duties imposed on "
                          "entries of derivative iron and steel products'; "
                          "HTS 2025 Rev. 19 heading 9903.81.91 'The duty provided in the applicable subheading + a duty "
                          "of 50% upon the' and 'derivative iron or steel products provided for in the tariff "
                          "subheadings enumerated in subdivision (n) of note 16'; HTS 2026 Rev. 4 note 16(n) 'The rates "
                          "of duty in heading 9903.81.91 apply to'",
         archive_evidence="Cosmetics subheadings in note 16(n) from 2025 Rev. 19 to 2026 Rev. 4 (Rev. 4 PDF p. 242, "
                          "99-III-70), absent in Rev. 18; Rev. 19 change record: note 16(n) Modified, effective August "
                          "18, 2025 (Notice); 2026 Rev. 5 change record: 9903.81.91 Deleted, effective April 6, 2026",
         cosmetics_3303_3307="the same 14 cosmetics subheadings, 2025-08-18 to 2026-04-06",
         status="quote_checked",
         open_issues="Caveat: the Notice behind the 2025-08-18 change is not named and was not collected"),
    dict(action_id="EO14324_deminimis", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="EO 14324 (FR 2025-14897)",
         legal_basis="IEEPA (suspends the administrative exemption of 19 U.S.C. 1321(a)(2)(C))",
         signed_at="2025-07-30", published_at="2025-08-05", effective_at="2025-08-29T00:01-04:00",
         ends_rule="continued and modified by EO14388_continue; made indefinite by CBP_IFR_nonpostal and "
                   "CBP_IFR_postal",
         applicability_rule=ENTRY, scope="all countries",
         rate_or_effect="duty-free de minimis treatment suspended",
         supersedes="EO 14256 sec. 2 (for goods entered on or after effective_at)",
         source_quote_ref="2025-14897 sec. 4(a) and 4(b); 1321(a)(2)(C) named in 2025-16802 and 2026-12670",
         status="quote_checked", open_issues=""),
    dict(action_id="CBP_EO14324_notice", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="CBP notice FR 2025-16802", legal_basis="implements EO 14324",
         published_at="2025-09-02", effective_at="2025-08-29T00:01-04:00",
         applicability_rule=ENTRY + " (non-postal); postal articles: entered for consumption on or after effective_at",
         scope="all countries; separate duty methods for the international postal network (Annex)",
         rate_or_effect="HTSUS modifications and duty collection procedures implementing the suspension",
         amends="HTSUS",
         source_quote_ref="2025-16802 SUMMARY and DATES (both on or after 12:01 a.m. eastern daylight time on "
                          "August 29, 2025)",
         status="quote_checked", open_issues=""),
    dict(action_id="EO14388_continue", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="EO 14388 (FR 2026-03829)",
         legal_basis="IEEPA, National Emergencies Act, Trade Act of 1974 sec. 604",
         signed_at="2026-02-20", published_at="2026-02-25", effective_at="2026-02-24T00:01-05:00",
         applicability_rule="modifications to EO 14324 apply to " + ENTRY,
         scope="all countries", rate_or_effect="continues the de minimis suspension and revises EO 14324",
         amends="EO 14324",
         unaffected_actions="",
         source_quote_ref="2026-03829 preamble (authorities) and sec. 5(a) '12:01 a.m. eastern standard time on "
                          "February 24, 2026'; named unaffected in EO 14389 sec. 2(c)",
         status="quote_checked", open_issues=""),
    dict(action_id="CBP_IFR_nonpostal", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="CBP interim final rule FR 2026-12670",
         legal_basis="19 U.S.C. 1321(b) (regulation; 19 CFR 10.151)", published_at="2026-06-24",
         effective_at="2026-06-24", ends_rule="indefinite",
         applicability_rule="entries of merchandise valued at $800 or less arriving by modes other than the "
                            "international postal network",
         scope="all countries; non-postal modes",
         rate_or_effect="de minimis administrative exemption indefinitely suspended; formal or informal entry "
                        "required; bona fide gifts and travelers' personal articles (1321(a)(2)(A)-(B)) unaffected",
         source_quote_ref="2026-12670 SUMMARY, DATES 'effective on June 24, 2026', '1321(b), to protect revenue'",
         status="quote_checked", open_issues=""),
    dict(action_id="CBP_IFR_postal", rate_kind='none', rate_pct='', stacking_rule='',
         instrument="CBP interim final rule FR 2026-12669",
         legal_basis="19 U.S.C. 1321(b) (regulation; 19 CFR part 145)", published_at="2026-06-24",
         effective_at="2026-07-24", ends_rule="indefinite",
         applicability_rule="mail shipments through the international postal network; amendatory instruction 4 "
                            "(19 CFR 145.31) effective 2026-06-24; compliance date for 145.12(a)(2)(v)-(vi) 2026-10-22",
         scope="all countries; international postal network",
         rate_or_effect="de minimis exemption for mail indefinitely suspended; new postal informal entry process",
         source_quote_ref="2026-12669 SUMMARY and DATES",
         status="quote_checked", open_issues=""),
]


# resolution_status for rows whose evidence is checked but whose application is not fully modelled or dated.
PARTIAL = {
    "P11012_surcharge": "an entry containing both steel and aluminum content is not modelled",
    "S301_KR_12_5": "note 52 between Rev. 13 and Rev. 22 is not reconstructed",
    "S232_AL_derivative_19k": "time of day of the 2025-08-18 inclusion not given; the Notice is not identified",
    "S232_ST_derivative_16n": "time of day of the 2025-08-18 inclusion not given; the Notice is not identified",
}


def finish(row: dict) -> dict:
    """Split the transcription status into evidence_status and resolution_status."""
    status = row.pop("status")
    row["evidence_status"] = "quote_checked" if status in ("quote_checked", "incomplete") else "unverified"
    if status == "incomplete":
        row["resolution_status"] = "unresolved"
    else:
        row["resolution_status"] = "partial" if row["action_id"] in PARTIAL else "resolved"
    return row


def main() -> None:
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for row in ROWS:
            row = finish(dict(row))
            w.writerow({k: row.get(k, "") for k in FIELDS})
    print(f"wrote {OUT.relative_to(OUT.parents[2])} ({len(ROWS)} rows)")


if __name__ == "__main__":
    main()
