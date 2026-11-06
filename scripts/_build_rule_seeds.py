"""Write the machine-readable rule seeds that sit next to warehouse/seeds/regulatory_actions.csv.

    uv run python scripts/_build_rule_seeds.py

regulatory_actions.csv stays the sourced record (quotes, evidence, status). These seeds restate it for computation:

rule_segments.csv        one row per rule segment: an action applied to one origin, HTS scope, transport scope and
                         value component over a half-open period [starts_at, ends_at), with its duty family and its
                         own resolution status (a segment, not the whole action, is the unit of resolution).
rule_code_resolution.csv code-level overrides of a segment's resolution, and whether the code's membership in the
                         segment's exception list was checked for that period (list_membership_verified).
rule_hts_lists.csv       HTS 8-digit subheadings of list-scoped rules (only chapter 33 cosmetics are modelled)
list_versions.csv        for every HTS list: source revision, valid_from, valid_to and temporal status
duty_families.csv        duty families and whether each is modelled (MFN is not)
evidence_catalog.csv     every evidence id that exists in the committed corpus
action_evidence.csv      evidence ids cited by each action

boundary_fixtures.csv and family_fixtures.csv are NOT written here: they are hand-written expectations, kept apart
from any code that computes applicability (warehouse/seeds/README.md).

Time values keep their source text. A date-only value has precision 'date': the source gives the day but not the
time, so the whole day is a boundary-uncertain window (see mart_tariff_rules), not a midnight cut-off.
NULL meanings: ends_at empty = open-ended (no end in the corpus); rate_pct empty = not a rate (rate_kind 'none').
"""

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEEDS = REPO / "warehouse" / "seeds"
EXTRACTED = REPO / "data" / "extracted"

LESS_METAL = "FULL_VALUE_LESS_232_METAL_CONTENT"
SEG_FIELDS = ["segment_id", "action_id", "duty_family", "origin_country", "hts_scope", "transport_scope",
              "effect_kind", "value_component", "starts_at", "starts_precision", "ends_at", "ends_precision",
              "rate_kind", "rate_pct", "segment_resolution_status", "segment_resolution_note", "segment_note"]


def precision(v: str) -> str:
    return "" if not v else ("date" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else "minute")


def seg(segment_id, action_id, family, starts_at, ends_at, *, rate_kind, rate_pct="", hts_scope="ALL",
        transport="ALL", effect="duty", value=LESS_METAL, origin="KR", status="resolved", status_note="", note=""):
    return {"segment_id": segment_id, "action_id": action_id, "duty_family": family, "origin_country": origin,
            "hts_scope": hts_scope, "transport_scope": transport, "effect_kind": effect, "value_component": value,
            "starts_at": starts_at, "starts_precision": precision(starts_at), "ends_at": ends_at,
            "ends_precision": precision(ends_at), "rate_kind": rate_kind, "rate_pct": rate_pct,
            "segment_resolution_status": status, "segment_resolution_note": status_note, "segment_note": note}


SEGMENTS = [
    seg("KR_RECIP10_A", "EO14257_baseline10", "ieepa_reciprocal", "2025-04-05T00:01-04:00", "2025-04-09T00:01-04:00",
        rate_kind="additional_ad_valorem", rate_pct="10", value="FULL_VALUE",
        note="before the Korea 25% rate; in-transit exceptions not modelled"),
    seg("KR_RECIP25", "EO14257_KR25", "ieepa_reciprocal", "2025-04-09T00:01-04:00", "2025-04-10T00:01-04:00",
        rate_kind="additional_ad_valorem", rate_pct="25", value="FULL_VALUE",
        note="replaces the 10% for Korea (HTS 2025 Rev. 7 heading 9903.01.25)"),
    seg("KR_RECIP10_B", "EO14257_baseline10", "ieepa_reciprocal", "2025-04-10T00:01-04:00", "2025-08-07T00:01-04:00",
        rate_kind="additional_ad_valorem", rate_pct="10", value="FULL_VALUE",
        note="country rate suspended (EO14266_pause, EO14316_extend, EO14326_continue); the 10% applies"),
    seg("KR_RECIP15", "EO14326_KR15", "ieepa_reciprocal", "2025-08-07T00:01-04:00", "2025-11-14T00:01-05:00",
        rate_kind="additional_ad_valorem", rate_pct="15",
        note="does not apply to the 232 metal content of derivative products (note 2(v)); non-auto goods"),
    seg("KR_DEAL15", "KORdeal_15allin", "ieepa_reciprocal", "2025-11-14T00:01-05:00", "2026-02-24T00:00-05:00",
        rate_kind="total_with_column1", rate_pct="15",
        note="Part B goods; ends at the CBP cut-off for IEEPA collection (CSMS 67834313)"),
    seg("KR_S232_AL", "S232_AL_derivative_19k", "s232_derivative", "2025-08-18", "2026-04-06",
        rate_kind="additional_ad_valorem", rate_pct="50", hts_scope="LIST:s232_al_19k", value="ALUMINUM_CONTENT",
        status="partial", status_note="dates are change-record days without a time; the Notice is not identified",
        note="list modelled for chapter 33 cosmetics only"),
    seg("KR_S232_ST", "S232_ST_derivative_16n", "s232_derivative", "2025-08-18", "2026-04-06",
        rate_kind="additional_ad_valorem", rate_pct="50", hts_scope="LIST:s232_st_16n", value="STEEL_CONTENT",
        status="partial", status_note="dates are change-record days without a time; the Notice is not identified",
        note="list modelled for chapter 33 cosmetics only"),
    seg("KR_S122_A", "P11012_surcharge", "s122_surcharge", "2026-02-24T00:01-05:00", "2026-04-06",
        rate_kind="additional_ad_valorem", rate_pct="10", hts_scope="ALL_EXCEPT_LIST:surcharge", status="partial",
        status_note="exception lists only read from HTS Rev. 22; entries with both steel and aluminum content not "
                    "modelled; end day 2026-04-06 has no time",
        note="note 2(aa)(v)(b),(d) exclude 232 metal content until 2026-04-06"),
    seg("KR_S122_B", "P11012_surcharge", "s122_surcharge", "2026-04-06", "2026-07-24T00:01-04:00",
        rate_kind="additional_ad_valorem", rate_pct="10", hts_scope="ALL_EXCEPT_LIST:surcharge", value="FULL_VALUE",
        status="partial", status_note="exception lists only read from HTS Rev. 22; start day 2026-04-06 has no time",
        note="after the 232 derivative headings were deleted"),
    seg("KR_S301", "S301_KR_12_5", "s301", "2026-07-24T00:01-04:00", "", rate_kind="total_with_column1",
        rate_pct="12.5", hts_scope="ALL_EXCEPT_LIST:s301_korea", status="partial",
        status_note="note 52 lists read from HTS Rev. 22 (and Rev. 13 for cosmetics only)",
        note="note 52(f)(1) excepts 232 derivative content of 9903.82 headings"),
    seg("ALL_DEMIN_EO", "EO14324_deminimis", "de_minimis", "2025-08-29T00:01-04:00", "", rate_kind="none",
        origin="ALL", effect="de_minimis_suspended", value="NA", note="continued by EO14388_continue"),
    seg("ALL_DEMIN_IFR_NP", "CBP_IFR_nonpostal", "de_minimis", "2026-06-24", "", rate_kind="none", origin="ALL",
        transport="NON_POSTAL", effect="de_minimis_suspended", value="NA",
        note="regulatory suspension under 19 U.S.C. 1321(b); entries valued at $800 or less"),
    seg("ALL_DEMIN_IFR_P", "CBP_IFR_postal", "de_minimis", "2026-07-24", "", rate_kind="none", origin="ALL",
        transport="POSTAL", effect="de_minimis_suspended", value="NA",
        note="regulatory suspension for the international postal network"),
]

FAMILIES = [
    {"duty_family": "ieepa_reciprocal", "modelled": "true", "note": "reciprocal and Korea rates under IEEPA"},
    {"duty_family": "s232_derivative", "modelled": "true", "note": "232 derivative duties, chapter 33 cosmetics only"},
    {"duty_family": "s122_surcharge", "modelled": "true", "note": "temporary import surcharge (Proclamation 11012)"},
    {"duty_family": "s301", "modelled": "true", "note": "section 301 action on South Korea"},
    {"duty_family": "de_minimis", "modelled": "true", "note": "suspension of duty-free de minimis treatment"},
    {"duty_family": "mfn", "modelled": "false", "note": "column 1 (MFN / FTA) rates are not modelled here"},
]


def cosmetics() -> tuple[list[str], set[str]]:
    """All chapter 33 cosmetics subheadings, and those in the 232 derivative lists (from the extracted check)."""
    with (EXTRACTED / "cosmetics_exception_check.csv").open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["regime"] == "surcharge"]
    all8 = sorted({r["subheading_8"] for r in rows})
    metal = {r["subheading_8"] for r in rows if r["aluminum_232_derivative_19k"] == "True"}
    return all8, metal


def code_resolution(all8: list[str], metal: set[str]) -> list[dict]:
    rows = []
    for c in all8:
        rows.append({"segment_id": "KR_S122_A", "hts8": c, "list_membership_verified": "true",
                     "resolution_status": "partial" if c in metal else "resolved",
                     "reason": "not in note 2(aa) code lists in 2026 Rev. 4 (cosmetics mentions)"
                               + ("; 232 metal content and combined-metal entries not modelled" if c in metal else "")})
        rows.append({"segment_id": "KR_S122_B", "hts8": c, "list_membership_verified": "true",
                     "resolution_status": "resolved",
                     "reason": "not in note 2(aa) code lists in 2026 Rev. 5, 6, 12 (cosmetics mentions); no 232 "
                               "derivative heading in force after 2026-04-06"})
        rows.append({"segment_id": "KR_S301", "hts8": c, "list_membership_verified": "true",
                     "resolution_status": "resolved",
                     "reason": "not in note 52 code lists in 2026 Rev. 13 and Rev. 22 (cosmetics mentions)"})
    return rows


def list_versions() -> list[dict]:
    return [
        {"list_id": "s232_al_19k", "list_role": "include", "source_revision": "2025HTSRev19..2026HTSRev4",
         "valid_from": "2025-08-18", "valid_to": "2026-04-06", "temporal_status": "verified_for_period",
         "note": "cosmetics in note 19(k) in every collected revision of the period; change-record dates"},
        {"list_id": "s232_st_16n", "list_role": "include", "source_revision": "2025HTSRev19..2026HTSRev4",
         "valid_from": "2025-08-18", "valid_to": "2026-04-06", "temporal_status": "verified_for_period",
         "note": "cosmetics in note 16(n) in every collected revision of the period; change-record dates"},
        {"list_id": "surcharge", "list_role": "exclude", "source_revision": "2026HTSRev22", "valid_from": "2026-10-30",
         "valid_to": "", "temporal_status": "current_revision_only",
         "note": "read from Rev. 22 (posted 2026-10-30); not valid evidence for an earlier instant"},
        {"list_id": "s301_korea", "list_role": "exclude", "source_revision": "2026HTSRev22", "valid_from": "2026-10-30",
         "valid_to": "", "temporal_status": "current_revision_only",
         "note": "read from Rev. 22 (posted 2026-10-30); not valid evidence for an earlier instant"},
    ]


def evidence_ids(row: dict) -> list[str]:
    text = " ".join(row[c] for c in ("instrument", "source_quote_ref", "archive_evidence"))
    ids = {f"fr:{n}" for n in re.findall(r"(?<!\d)(20\d{2}-\d{5})(?!\d)", text)}
    ids |= {f"csms:{n}" for n in re.findall(r"CSMS #? ?(\d{8})", text)}
    ids |= {f"hts:{y}HTSRev{n}" for y, n in re.findall(r"(20\d{2}) Rev\. (\d+)", text)}
    if "HTS Rev. 22" in text or "HTS export" in text:
        ids.add("hts:current_rev22")
    return sorted(ids)


def catalog() -> list[dict]:
    rows = []
    with (EXTRACTED / "fr_documents.csv").open(encoding="utf-8") as f:
        rows += [{"evidence_id": f"fr:{r['document_number']}", "kind": "federal_register",
                  "path": f"data/extracted/fr_text/{r['document_number']}.txt"} for r in csv.DictReader(f)]
    rows += [{"evidence_id": f"csms:{p.stem}", "kind": "cbp_csms", "path": p.relative_to(REPO).as_posix()}
             for p in sorted((EXTRACTED / "cbp_csms").glob("*.txt"))]
    rows += [{"evidence_id": f"hts:{p.name}", "kind": "hts_archive_evidence", "path": p.relative_to(REPO).as_posix()}
             for p in sorted((EXTRACTED / "hts_archive_evidence").iterdir()) if p.is_dir()]
    rows.append({"evidence_id": "hts:current_rev22", "kind": "hts_current",
                 "path": "data/extracted/hts_pdf/chapter_99"})
    return rows


def write(name: str, rows: list[dict], fields: list[str]) -> None:
    with (SEEDS / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote warehouse/seeds/{name} ({len(rows)} rows)")


def main() -> None:
    all8, metal = cosmetics()
    write("rule_segments.csv", SEGMENTS, SEG_FIELDS)
    write("rule_code_resolution.csv", code_resolution(all8, metal),
          ["segment_id", "hts8", "list_membership_verified", "resolution_status", "reason"])
    lists = [{"list_id": lid, "hts8": c, "source": src} for lid, src in
             (("s232_al_19k", "HTS note 19(k)"), ("s232_st_16n", "HTS note 16(n)")) for c in sorted(metal)]
    write("rule_hts_lists.csv", lists, ["list_id", "hts8", "source"])
    write("list_versions.csv", list_versions(),
          ["list_id", "list_role", "source_revision", "valid_from", "valid_to", "temporal_status", "note"])
    write("duty_families.csv", FAMILIES, ["duty_family", "modelled", "note"])
    write("evidence_catalog.csv", catalog(), ["evidence_id", "kind", "path"])
    with (SEEDS / "regulatory_actions.csv").open(encoding="utf-8") as f:
        actions = list(csv.DictReader(f))
    write("action_evidence.csv", [{"action_id": a["action_id"], "evidence_id": e}
                                  for a in actions for e in evidence_ids(a)], ["action_id", "evidence_id"])


if __name__ == "__main__":
    main()
