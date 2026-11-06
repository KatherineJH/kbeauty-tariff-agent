"""DRAFT helper only: list every file/page where each specified quote occurs inside its evidence.

    uv run python scripts/_draft_rule_citations.py > draft.txt

It never decides. A person picks one location per quote and writes it into warehouse/seeds/rule_citations.csv
(source_file, physical_page, printed_page). The verifier then checks that exact location only.
"""

import sys

from tariffagent.answer.citations import evidence_files, file_text, normalize

SPEC = [  # (rule_id, claim_role, evidence_id, quote)
    ("KR_RECIP10_A", "authority", "fr:2025-06063", "the International Emergency Economic Powers Act (50 U.S.C. 1701 et seq.)"),
    ("KR_RECIP10_A", "rate", "fr:2025-06063", "subject to an additional ad valorem rate of duty of 10 percent"),
    ("KR_RECIP10_A", "effective_start", "fr:2025-06063", "on or after 12:01 a.m. eastern daylight time on April 5, 2025"),
    ("KR_RECIP10_A", "effective_end", "hts:2025HTSRev7", "except for articles the product of a country enumerated in subdivision (v)(xiii) of U.S. note 2"),
    ("KR_RECIP10_A", "scope", "hts:2025HTSRev7", "9903.01.34, articles the product of any country"),
    ("KR_RECIP25", "authority", "fr:2025-06063", "the International Emergency Economic Powers Act (50 U.S.C. 1701 et seq.)"),
    ("KR_RECIP25", "rate", "hts:2025HTSRev7", "(xlvi) South Korea, subject to an additional duty of 25%"),
    ("KR_RECIP25", "effective_start", "fr:2025-06063", "at 12:01 a.m. eastern daylight time on April 9, 2025, all articles from trading partners enumerated in Annex I"),
    ("KR_RECIP25", "effective_end", "fr:2025-06462", "on or after 12:01 a.m. eastern daylight time on April 10, 2025, enforcement of the second paragraph of section 3(a) of Executive Order 14257 is suspended"),
    ("KR_RECIP25", "scope", "hts:2025HTSRev7", "(xlvi) South Korea, subject to an additional duty of 25%"),
    ("KR_RECIP10_B", "authority", "fr:2025-06063", "the International Emergency Economic Powers Act (50 U.S.C. 1701 et seq.)"),
    ("KR_RECIP10_B", "rate", "fr:2025-06462", "and to instead impose on articles of all such trading partners an additional ad valorem rate of duty"),
    ("KR_RECIP10_B", "effective_start", "fr:2025-06462", "on or after 12:01 a.m. eastern daylight time on April 10, 2025, enforcement of the second paragraph of section 3(a) of Executive Order 14257 is suspended"),
    ("KR_RECIP10_B", "effective_end", "fr:2025-12962", "extend the suspension effectuated by Executive Order 14266 until 12:01 a.m. eastern daylight time on August 1, 2025"),
    ("KR_RECIP10_B", "effective_end", "fr:2025-15010", "continuing to suspend headings 9903.01.43 through 9903.01.62 and 9903.01.64 through 9903.01.76"),
    ("KR_RECIP10_B", "effective_end", "fr:2025-15010", "12:01 a.m. eastern daylight time 7 days after the date of this order"),
    ("KR_RECIP10_B", "scope", "hts:2025HTSRev17", "provision suspended"),
    ("KR_RECIP15", "authority", "fr:2025-15010", "the International Emergency Economic Powers Act (50 U.S.C. 1701 et seq.)"),
    ("KR_RECIP15", "rate", "hts:current_rev22", "The duty provided in the applicable subheading + 15%"),
    ("KR_RECIP15", "effective_start", "fr:2025-15010", "12:01 a.m. eastern daylight time 7 days after the date of this order"),
    ("KR_RECIP15", "effective_end", "fr:2025-21940", "on or after 12:01 a.m. eastern time on November 14, 2025"),
    ("KR_RECIP15", "scope", "hts:2026HTSRev4", "articles the product of South Korea, as provided for in subdivision (v) of U.S. note 2"),
    ("KR_RECIP15", "stacking", "hts:current_rev22", "shall not apply to the declared value of the aluminum content of the derivative aluminum products provided for in headings 9903.85.04, 9903.85.07, 9903.85.08"),
    ("KR_DEAL15", "authority", "fr:2025-21940", "the additional ad valorem rate of duty pursuant to Executive Order 14257, as amended, will be 15 percent"),
    ("KR_DEAL15", "rate", "fr:2025-21940", "the sum of the column 1 duty rate and the additional ad valorem rate of duty pursuant to Executive Order 14257, as amended, will be 15 percent"),
    ("KR_DEAL15", "effective_start", "fr:2025-21940", "on or after 12:01 a.m. eastern time on November 14, 2025"),
    ("KR_DEAL15", "effective_end", "csms:67834313", "will no longer be in effect and will no longer be collected for goods entered for consumption or withdrawn from warehouse for consumption, on or after 12:00 a.m. eastern time on February 24, 2026"),
    ("KR_DEAL15", "scope", "fr:2025-21940", "for goods of the ROK with a column 1 duty rate in the HTSUS that is less than 15 percent"),
    ("KR_DEAL15", "stacking", "fr:2025-21940", "as amended, will be zero percent"),
    ("KR_S232_AL", "authority", "hts:2025HTSRev19", "The rates of duty in heading 9903.85.08 apply to all entries of derivative aluminum products"),
    ("KR_S232_AL", "rate", "hts:2025HTSRev19", "a duty of 50% upon the value of the aluminum content"),
    ("KR_S232_AL", "effective_start", "hts:2025HTSRev19", "U.S. note 19(k), subch III, ch 99 Modified August 18, 2025 Notice"),
    ("KR_S232_AL", "effective_end", "hts:2026HTSRev5", "9903.85.08 Deleted April 6, 2026 PP 11021"),
    ("KR_S232_AL", "scope", "hts:2025HTSRev19", "3303.00.30; 3304.30.00; 3304.99.50; 3305.10.00"),
    ("KR_S232_AL", "stacking", "hts:current_rev22", "shall only apply to the declared value of the aluminum content"),
    ("KR_S232_ST", "authority", "hts:2025HTSRev19", "The rates of duty in heading 9903.81.91 apply to"),
    ("KR_S232_ST", "rate", "hts:2025HTSRev19", "a duty of 50% upon the"),
    ("KR_S232_ST", "effective_start", "hts:2025HTSRev19", "U.S. note 16(n), subch III, ch 99 Modified August 18, 2025 Notice"),
    ("KR_S232_ST", "effective_end", "hts:2026HTSRev5", "9903.81.91 Deleted April 6, 2026 PP 11021"),
    ("KR_S232_ST", "scope", "hts:2025HTSRev19", "3303.00.30; 3304.30.00; 3304.99.50; 3305.10.00"),
    ("KR_S232_ST", "stacking", "hts:2026HTSRev4", "shall only apply to the declared value of the steel content of the derivative article"),
    ("KR_S122_A", "authority", "fr:2026-03824", "including section 122 of the Trade Act of 1974 (19 U.S.C. 2132)"),
    ("KR_S122_A", "rate", "fr:2026-03824", "all articles imported into the United States shall be subject to a 10 percent ad valorem duty rate"),
    ("KR_S122_A", "effective_start", "fr:2026-03824", "on or after 12:01 a.m. eastern standard time on February 24, 2026"),
    ("KR_S122_A", "effective_end", "hts:2026HTSRev5", "U.S. note 2(aa)(v)(a)-(d), (g), subch III, ch 99 Deleted April 6, 2026 PP 11021"),
    ("KR_S122_A", "scope", "fr:2026-03824", "all articles imported into the United States shall be subject to a 10 percent ad valorem duty rate"),
    ("KR_S122_A", "exclusion", "hts:current_rev22", "shall not apply to articles the product of any country that are classifiable in the following subheadings"),
    ("KR_S122_A", "stacking", "hts:2026HTSRev4", "the declared value of the aluminum content of the derivative aluminum products provided for in headings 9903.85.04, 9903.85.07, 9903.85.08"),
    ("KR_S122_A", "stacking", "hts:2026HTSRev4", "the declared value of the steel content of the derivative iron or steel products provided for in headings 9903.81.89, 9903.81.90, 9903.81.91"),
    ("KR_S122_B", "authority", "fr:2026-03824", "including section 122 of the Trade Act of 1974 (19 U.S.C. 2132)"),
    ("KR_S122_B", "rate", "fr:2026-03824", "all articles imported into the United States shall be subject to a 10 percent ad valorem duty rate"),
    ("KR_S122_B", "effective_start", "hts:2026HTSRev5", "U.S. note 2(aa)(v)(a)-(d), (g), subch III, ch 99 Deleted April 6, 2026 PP 11021"),
    ("KR_S122_B", "effective_end", "fr:2026-03824", "shall continue in effect through 12:01 a.m. eastern daylight time on July 24, 2026"),
    ("KR_S122_B", "scope", "fr:2026-03824", "all articles imported into the United States shall be subject to a 10 percent ad valorem duty rate"),
    ("KR_S122_B", "exclusion", "hts:current_rev22", "shall not apply to articles the product of any country that are classifiable in the following subheadings"),
    ("KR_S301", "authority", "fr:2026-15274", "section 301"),
    ("KR_S301", "rate", "fr:2026-15181", "has determined to impose 12.5 percent tariffs net of MFN on products of South Korea"),
    ("KR_S301", "effective_start", "fr:2026-15181", "on or after 12:01 a.m. eastern time on July 24, 2026"),
    ("KR_S301", "scope", "fr:2026-15181", "on products of South Korea, except as provided in Annex I and Annex II, Part A, of this Notice"),
    ("KR_S301", "exclusion", "hts:current_rev22", "shall not apply to articles that are classifiable in the following provisions of the HTSUS"),
    ("KR_S301", "stacking", "fr:2026-15181", "where such product's MFN tariff is greater than or equal to 12.5 percent, the Section 301 tariff applied shall be zero"),
    ("ALL_DEMIN_EO", "authority", "fr:2025-14897", "the International Emergency Economic Powers Act (50 U.S.C. 1701 et seq.)"),
    ("ALL_DEMIN_EO", "effective_start", "fr:2025-14897", "shall be effective with respect to goods entered for consumption, or withdrawn from warehouse for consumption, on or after 12:01 a.m. eastern daylight time on August 29"),
    ("ALL_DEMIN_EO", "effective_start", "fr:2026-03829", "to Executive Order 14324 in this order shall be effective with respect to goods entered for consumption"),
    ("ALL_DEMIN_EO", "scope", "fr:2025-14897", "Suspending Duty-Free De Minimis Treatment for All Countries"),
    ("ALL_DEMIN_IFR_NP", "authority", "fr:2026-12670", "1321(b), to protect revenue"),
    ("ALL_DEMIN_IFR_NP", "effective_start", "fr:2026-12670", "This interim final rule is effective on June 24, 2026"),
    ("ALL_DEMIN_IFR_NP", "scope", "fr:2026-12670", "for imports valued at $800 or less arriving via all modes other than through the international postal network"),
    ("ALL_DEMIN_IFR_P", "authority", "fr:2026-12669", "1321(b), to protect revenue"),
    ("ALL_DEMIN_IFR_P", "effective_start", "fr:2026-12669", "This interim final rule is effective on July 24, 2026"),
    ("ALL_DEMIN_IFR_P", "scope", "fr:2026-12669", "for imports valued at $800 or less arriving through the international postal network"),
]


def main() -> None:
    cache = {}
    for rule_id, role, evidence_id, quote in SPEC:
        q = normalize(quote)
        hits = []
        for path in evidence_files(evidence_id):
            text = cache.setdefault(path, file_text(path))
            if q in text:
                hits.append(path.as_posix().split("kbeauty-tariff-agent/")[-1])
        flag = "OK " if len(hits) == 1 else ("NONE" if not hits else f"{len(hits)}x ")
        print(f"{flag} {rule_id} {role} {evidence_id} :: {' | '.join(hits)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
