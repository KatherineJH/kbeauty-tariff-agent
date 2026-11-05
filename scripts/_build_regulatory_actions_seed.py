"""Write warehouse/seeds/regulatory_actions.csv from the hand-transcribed rows below.

The rows are transcribed by reading the archived originals (data/raw); every value cites its source in
source_quote_ref. Kept as Python so commas inside values are quoted correctly. Run once after editing:

    uv run python scripts/_build_regulatory_actions_seed.py

rate_kind: additional_ad_valorem (added on top of the column 1 rate) | total_with_column1 (column 1 + this duty is
           capped at rate_pct; the added duty is rate_pct minus column 1, or 0) | none (not a rate)
PDF page numbers in source_quote_ref are physical 1-based indexes of data/raw/hts/chapter_99.pdf, with the printed
label (e.g. 99-III-486) where it matters.

status: quote_checked = the author compared every filled value with the source sentence (not yet reviewed by
        the user, who is the reference for gold labels; open_issues may hold caveats); incomplete = some value could not be transcribed from
        the archived sources. open_issues lists what is unknown and why; values are never guessed.
"""

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "warehouse" / "seeds" / "regulatory_actions.csv"
FIELDS = ["action_id", "instrument", "legal_basis", "signed_at", "published_at", "effective_at", "ends_at", "ends_rule",
          "applicability_rule", "scope", "rate_or_effect", "rate_kind", "rate_pct", "stacking_rule", "supersedes", "superseded_by", "amends",
          "unaffected_actions", "source_quote_ref", "cosmetics_3303_3307", "status", "open_issues"]

ENTRY = "goods entered for consumption, or withdrawn from warehouse for consumption, on or after effective_at"

ROWS = [
    dict(action_id="EO14257_baseline10", rate_kind='additional_ad_valorem', rate_pct='10', stacking_rule="'in addition to any other duties, fees, taxes, exactions, or charges' (2025-06063 sec. 3(c)) except as provided in 3(d)-(e); whether it stacked with a country rate is not settled here (see EO14257_KR25)",
         instrument="EO 14257 (FR 2025-06063)", legal_basis="IEEPA",
         signed_at="2025-04-02", published_at="2025-04-07", effective_at="2025-04-05T00:01-04:00",
         ends_rule="IEEPA additional duties ended by EO14389_end_ieepa; for Korea the 10% is replaced by the "
                   "country rate EO14326_KR15 from 2025-08-07",
         applicability_rule=ENTRY + "; goods loaded onto a vessel and in transit on the final mode of transit before "
                            "effective_at, and entered after it, are not subject (no entry deadline in this text)",
         scope="all trading partners", rate_or_effect="+10% ad valorem (HTS 9903.01.25)",
         superseded_by="EO14326_KR15 (Korea)",
         source_quote_ref="2025-06063 sec. 3(a): 'on or after 12:01 a.m. eastern daylight time on April 5, 2025, "
                          "except that goods loaded onto a vessel ... before 12:01 a.m. ... April 5, 2025, and "
                          "entered ... after 12:01 a.m. ... April 5, 2025, shall not be subject'",
         status="quote_checked", open_issues=""),
    dict(action_id="EO14257_KR25", rate_kind='additional_ad_valorem', rate_pct='25', stacking_rule='unknown relative to EO14257_baseline10 (open issue)',
         instrument="EO 14257 Annex I (FR 2025-06063); HTS 9903.01.54", legal_basis="IEEPA",
         signed_at="2025-04-02", published_at="2025-04-07", effective_at="2025-04-09T00:01-04:00",
         ends_at="2025-04-10T00:01-04:00",
         ends_rule="enforcement suspended by EO14266_pause from 2025-04-10T00:01-04:00",
         applicability_rule=ENTRY + "; same in-transit exception as the 10% rate (loaded before effective_at)",
         scope="Korea", rate_or_effect="+25% ad valorem (country-specific)",
         superseded_by="EO14266_pause", amends="",
         source_quote_ref="2025-06063 sec. 3(b) '12:01 a.m. eastern daylight time on April 9, 2025'; HTS export "
                          "9903.01.54 'The duty provided in the applicable subheading + 25%'; 2025-06462 sec. 2",
         status="incomplete",
         open_issues="Whether EO14257_baseline10 (10%) also applied on top of the 25% during 2025-04-09T00:01 to "
                     "2025-04-10T00:01 is not stated in the archived texts. The current HTS 9903.01.25 excludes "
                     "9903.02.02-9903.02.91 but that wording reflects the later state, not 2025-04-09"),
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
         ends_at="2025-08-01T00:01-04:00", ends_rule="suspension ends at ends_at",
         applicability_rule=ENTRY, scope="all Annex I trading partners except the PRC",
         rate_or_effect="suspension of country-specific rates extended (HTS 9903.01.43-9903.01.62 and "
                        "9903.01.64-9903.01.76 suspended)",
         amends="EO 14266",
         source_quote_ref="2025-12962: 'extend the suspension effectuated by Executive Order 14266 until 12:01 a.m. "
                          "eastern daylight time on August 1, 2025'; sec. 2 'on or after 12:01 a.m. eastern daylight "
                          "time on July 9, 2025, by suspending headings 9903.01.43 through 9903.01.62 and 9903.01.64 "
                          "through 9903.01.76'",
         status="incomplete",
         open_issues="Which rate applied to Korean goods between 2025-08-01T00:01 and the start of EO14326_KR15 "
                     "(2025-08-07T00:01) is not stated in the archived texts read so far"),
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
         published_at="2025-12-04", effective_at="2025-11-14T00:01-05:00",
         ends_rule="IEEPA duties ended by EO14389_end_ieepa",
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
         signed_at="2026-02-20", published_at="2026-02-25",
         ends_rule="the listed IEEPA duties 'shall no longer be in effect and, as soon as practicable, shall no "
                   "longer be collected'",
         applicability_rule="no entry-date rule in this document",
         scope="additional ad valorem duties under IEEPA in EOs 14193, 14194, 14195, 14245, 14257, 14323, 14329, "
               "14380 and 14382",
         rate_or_effect="ends those IEEPA additional duties",
         amends="EO 14257 and the other listed orders",
         unaffected_actions="EO14388_continue and P11012_surcharge (named by title and date in sec. 2(c)); duties "
                            "under section 232 and section 301 (sec. 2(d))",
         source_quote_ref="2026-03832 sec. 1, sec. 2(a), 2(c), 2(d); API disposition_notes list EO 14388 and "
                          "Proc. 11012",
         status="incomplete",
         open_issues="The date collection actually stopped is not in this document (CBP guidance outside the "
                     "corpus). The surcharge starting 2026-02-24T00:01-05:00 suggests the switch, but that is an "
                     "inference, not a source statement"),
    dict(action_id="P11012_surcharge", rate_kind='additional_ad_valorem', rate_pct='10', stacking_rule="'in addition to any other duties' (para. (3)); 'shall not apply in addition to tariffs imposed under section 232' and applies only to the non-232 part of an import (para. (4)); ends when S301_KR_12_5 starts (2026-07-24T00:01-04:00), so the two do not overlap",
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
         unaffected_actions="", source_quote_ref="2026-03824 paras. 13, (1)-(5), (7); HTS export 9903.03.01-9903.03.11; "
                                                "HTS Rev. 22 chapter 99 PDF p. 221 U.S. note 2(aa)(i) 'imposes an "
                                                "additional ad valorem rate of duty on imports of all products of any "
                                                "country' and compiler's note 'expired at the close of July 23, 2026'",
         status="incomplete",
         cosmetics_3303_3307="Based on the explicit code lists and descriptive exceptions of HTS Rev. 22, the Korean "
                             "cosmetics subheadings reviewed were not confirmed as excepted from the section 122 "
                             "surcharge. Not in note 2(aa)(ii)-(iv) code lists (PDF pp. 223-230 = 99-III-51 to 58): "
                             "all 24 subheadings of 3303-3307. Of these, 10 are not 232 aluminum derivatives "
                             "(not_excepted_rev22) and 14 are listed in U.S. note 19(k) heading 9903.85.08 (S232_AL_derivative_19k; PDF p. 256 = "
                             "99-III-84; needs_review_232_aluminum_derivative). See "
                             "data/extracted/cosmetics_exception_check.csv",
         open_issues="(1) Rev. 22 is read as of 2026-11-05; the note as in force on 2026-02-24 to 2026-07-24 is not "
                     "reconstructed (earlier HTS revisions not collected). (2) For the 14 subheadings in note 19(k), "
                     "para. (4) says the surcharge does not apply to the 232 part, while Rev. 22 note 2(aa)(v) names "
                     "232 headings 9903.82.xx, not 9903.85.08, and was modified after expiration by 91 Fed. Reg. 18183 "
                     "(not in the corpus): treatment of the aluminum content under S232_AL_derivative_19k is unresolved"),
    dict(action_id="S301_KR_12_5", rate_kind='total_with_column1', rate_pct='12.5', stacking_rule='section 301 duty = 12.5% minus MFN (column 1) rate, 0 when MFN >= 12.5%; products also remain subject to any additional duty in subchapters III-IV of chapter 99 except as provided in U.S. note 52(b)-(k) (PDF p. 565, note 52(a))',
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
         status="incomplete",
         cosmetics_3303_3307="Based on the explicit code lists and descriptive exceptions of HTS Rev. 22, the Korean "
                             "cosmetics subheadings reviewed were not confirmed as excepted from the section 301 action "
                             "on South Korea (headings 9903.05.70-9903.05.71, PDF p. 658 = 99-III-486). Not in note "
                             "52(b)-(e) code lists (PDF pp. 566-577): all 24 subheadings of 3303-3307; 10 are "
                             "not_excepted_rev22 and 14 are note 19(k) aluminum derivatives "
                             "(needs_review_232_aluminum_derivative). Note 52(f)(1) excepts derivative aluminum articles "
                             "of headings 9903.82.02 and 9903.82.04-9903.82.26, not 9903.85.08",
         open_issues="(1) Note 52 is read from HTS Rev. 22 (current at 2026-11-05); the state on 2026-07-24 and any "
                     "later amendment are not reconstructed. (2) Whether the aluminum content of the 14 note 19(k) "
                     "cosmetics subheadings falls under the 52(f)(1) exception (9903.82.xx) at a given date is "
                     "unresolved; the relation between 9903.85.08 (S232_AL_derivative_19k) and 9903.82.xx is not in "
                     "the corpus"),
    dict(action_id="S232_AL_derivative_19k",
         instrument="HTS Rev. 22 chapter 99 subchapter III U.S. note 19(h) and (k), heading 9903.85.08",
         legal_basis="Trade Expansion Act of 1962 sec. 232",
         effective_at="", ends_at="",
         ends_rule="not stated in the corpus; in Rev. 22 the derivative aluminum and steel headings in force for "
                   "these exceptions are 9903.82.xx (U.S. note 16), and no tariff row for 9903.85.08 was found in the "
                   "Rev. 22 PDF text (only notes 2, 19 and others refer to it)",
         applicability_rule="derivative aluminum products classifiable in the subheadings listed in note 19(k), "
                            "unless processed in another country from aluminum smelted and cast in the United States; "
                            "the duty applies only to the declared value of the aluminum content",
         scope="all countries other than the United Kingdom (UK: note 19(s), heading 9903.85.15); the list includes 14 "
               "cosmetics subheadings 3303.00.10, 3303.00.20, 3303.00.30, 3304.30.00, 3304.99.50, 3305.10.00, "
               "3305.30.00, 3305.90.00, 3306.90.00, 3307.10.10, 3307.10.20, 3307.20.00, 3307.49.00, 3307.90.00",
         rate_or_effect="section 232 additional duty on the aluminum content of derivative aluminum products (rate "
                        "not transcribed)",
         rate_kind="additional_ad_valorem", rate_pct="",
         stacking_rule="note 19(h): any additional duty of subchapters III-IV is imposed in addition; not subject to "
                       "9903.01.10 (Canada) or 9903.01.01 (Mexico); the reciprocal duties of note 2(v)(ix) apply only "
                       "to the non-aluminum content (current wording)",
         source_quote_ref="HTS Rev. 22 chapter 99 PDF p. 255 (99-III-83) note 19(h) 'provide the ordinary customs duty "
                          "treatment applicable to all entries of derivative aluminum products from all countries'; "
                          "p. 256 (99-III-84) note 19(k) 'The rates of duty in heading 9903.85.08 apply to all entries "
                          "of derivative aluminum products' and 'shall only apply to the declared value of the aluminum "
                          "content'; p. 184 (99-III-12) note 2(v)(ix)",
         cosmetics_3303_3307="14 of the 24 cosmetics subheadings are listed in note 19(k); the other 10 are not "
                             "(data/extracted/cosmetics_exception_check.csv, column aluminum_232_derivative_19k)",
         status="incomplete",
         open_issues="Rate, effective date and end date are not in the corpus: the proclamations that set and later "
                     "restructured the 232 aluminum derivative duties (e.g. FR 2025-10524 and FR 2026-06960, found in "
                     "the search but outside the selection rule) and earlier HTS revisions were not collected. Whether "
                     "the 14 cosmetics subheadings remain 232 derivatives under the 9903.82.xx structure (U.S. note "
                     "16) is not checked"),
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


def main() -> None:
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        for row in ROWS:
            w.writerow({k: row.get(k, "") for k in FIELDS})
    print(f"wrote {OUT.relative_to(OUT.parents[2])} ({len(ROWS)} rows)")


if __name__ == "__main__":
    main()
