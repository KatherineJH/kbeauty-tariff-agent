"""Integrity checks for the regulatory effect table and the HTS exception lists.

These run on committed / extracted files only (no network):
- every quote_checked row cites sources, and every quoted fragment is found in the cited archived text
- incomplete rows say what is missing (open_issues)
- effective_at < ends_at
- overlapping periods for the same legal basis and scope are declared (supersedes / superseded_by / amends / ends_rule)
- listed exception codes are well-formed; those in collected HTS tables exist there
"""

import csv
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "warehouse" / "seeds" / "regulatory_actions.csv"
FR_DOCS = REPO / "data" / "extracted" / "fr_documents.csv"
FR_TEXT = REPO / "data" / "extracted" / "fr_text"
CH99_PAGES = REPO / "data" / "extracted" / "hts_pdf" / "chapter_99"
HTS_RAW = REPO / "data" / "raw" / "hts"
EXC_CODES = REPO / "data" / "extracted" / "hts_exception_codes.csv"
COSMETICS = REPO / "data" / "extracted" / "cosmetics_exception_check.csv"


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


ROWS = read_csv(SEED)
IDS = {r["action_id"] for r in ROWS}


def norm(text: str) -> str:
    text = text.replace("–", "-").replace("—", "-").replace("``", '"').replace("''", '"')
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=None)
def fr_text(number: str) -> str:
    return norm((FR_TEXT / f"{number}.txt").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def hts_text() -> str:
    parts = [json.dumps(json.loads(p.read_text(encoding="utf-8")), ensure_ascii=False) for p in HTS_RAW.glob("export_*.json")]
    parts += [p.read_text(encoding="utf-8") for p in sorted(CH99_PAGES.glob("page_*.txt"))]
    return norm(" ".join(parts))


@lru_cache(maxsize=None)
def csms_text(number: str) -> str:
    path = REPO / "data" / "extracted" / "cbp_csms" / f"{number}.txt"
    return norm(path.read_text(encoding="utf-8")) if path.exists() else ""


@lru_cache(maxsize=None)
def archive_text(release: str) -> str:
    """Committed evidence pages and change record of an archived HTS revision cited as '<year> Rev. <n>'.

    Only the evidence snapshot is read (the full page texts are not committed), so a quote from a page outside the
    snapshot fails here and must be added to the snapshot rules first."""
    evidence = REPO / "data" / "extracted" / "hts_archive_evidence" / release
    record = REPO / "data" / "extracted" / "hts_archive" / release / "change_record.txt"
    if not record.exists():
        return ""
    parts = [p.read_text(encoding="utf-8") for p in sorted(evidence.glob("page_*.txt"))]
    parts.append(record.read_text(encoding="utf-8"))
    return norm(" ".join(parts))


def parse_time(value: str) -> datetime:
    if "T" in value:
        return datetime.fromisoformat(value)
    return datetime.fromisoformat(value + "T00:00:00-04:00")  # date-only values: start of the day, US eastern


def quote_problems(row: dict) -> list[str]:
    """Problems with a row's citations: missing reference, unknown documents, quoted fragments not in the sources."""
    ref = row["source_quote_ref"]
    if not ref.strip():
        return ["no source_quote_ref"]
    known = {r["document_number"] for r in read_csv(FR_DOCS)}
    numbers = set(re.findall(r"(?<!\d)(20\d{2}-\d{5})(?!\d)", ref + " " + row["instrument"]))
    problems = []
    if not numbers and "HTS" not in ref:
        problems.append("no Federal Register document or HTS source named")
    if numbers - known:
        problems.append(f"cited documents not in the corpus: {sorted(numbers - known)}")
    releases = {f"{y}HTSRev{n}" for y, n in re.findall(r"(20\d{2}) Rev\. (\d+)", ref + " " + row["instrument"])}
    corpus = " ".join(fr_text(n) for n in numbers & known) + " " + hts_text() + " " + " ".join(
        archive_text(r) for r in sorted(releases) if r != "2026HTSRev22") + " " + " ".join(
        csms_text(n) for n in re.findall(r"CSMS #? ?(\d{8})", ref))
    for quote in re.findall(r"'([^']{12,})'", ref):
        for fragment in (f.strip(" ,;") for f in norm(quote).split("...")):
            if len(fragment) >= 12 and fragment not in corpus:
                problems.append(f"quoted fragment not found in cited sources: {fragment!r}")
    return problems


@pytest.mark.parametrize("row", [r for r in ROWS if r["evidence_status"] == "quote_checked"], ids=lambda r: r["action_id"])
def test_quote_checked_rows_cite_existing_sources_and_quotes(row):
    assert not quote_problems(row)


def test_negative_altered_quote_fragment_fails():
    row = dict(next(r for r in ROWS if r["action_id"] == "EO14266_pause"))
    assert not quote_problems(row)
    row["source_quote_ref"] = row["source_quote_ref"].replace("April 10, 2025", "April 11, 2025", 1)
    assert any("not found" in p for p in quote_problems(row))


def test_negative_unknown_document_fails():
    row = dict(next(r for r in ROWS if r["action_id"] == "EO14266_pause"))
    row["source_quote_ref"] = row["source_quote_ref"].replace("2025-06462", "2025-99999", 1)
    assert any("not in the corpus" in p for p in quote_problems(row))


@pytest.mark.parametrize("row", ROWS, ids=lambda r: r["action_id"])
def test_status_and_open_issues(row):
    assert row["evidence_status"] in {"quote_checked", "unverified"}
    assert row["resolution_status"] in {"resolved", "partial", "unresolved"}
    if row["evidence_status"] != "quote_checked" or row["resolution_status"] != "resolved":
        assert row["open_issues"].strip(), "a row that is not checked and resolved must say what is missing"


@pytest.mark.parametrize("row", [r for r in ROWS if r["effective_at"] and r["ends_at"]], ids=lambda r: r["action_id"])
def test_effective_before_end(row):
    assert parse_time(row["effective_at"]) < parse_time(row["ends_at"])


def test_signed_not_after_published():
    for r in ROWS:
        if r["signed_at"] and r["published_at"]:
            assert r["signed_at"] <= r["published_at"], r["action_id"]


def test_references_between_actions_resolve():
    for r in ROWS:
        for col in ("supersedes", "superseded_by", "unaffected_actions", "ends_rule"):
            for ref in re.findall(r"\b[A-Z][A-Za-z0-9]*_[A-Za-z0-9_]+\b", r[col]):
                assert ref in IDS, f"{r['action_id']}.{col} names unknown action {ref}"


def _interval(r):
    if not r["effective_at"]:
        return None
    end = parse_time(r["ends_at"]) if r["ends_at"] else datetime.max.replace(tzinfo=timezone.utc)
    return parse_time(r["effective_at"]), end


RELATION_COLUMNS = ("supersedes", "superseded_by", "amends", "ends_rule", "stacking_rule", "open_issues")
CHAIN_COLUMNS = ("supersedes", "superseded_by")


def _mentions(row: dict, columns: tuple[str, ...], ids: set[str]) -> set[str]:
    text = " ".join(row[c] for c in columns)
    return {o for o in ids - {row["action_id"]}
            if re.search(r"(?<![A-Za-z0-9_])" + re.escape(o) + r"(?![A-Za-z0-9_])", text)}


def _linked(a: dict, b: dict, rows: list[dict]) -> bool:
    """Directly related in any relation column (a known, unresolved overlap named in open_issues counts), or
    connected through a chain of supersedes / superseded_by. Shared mentions of a third action (for example
    both 'ended by EO14389_end_ieepa') do not link two actions."""
    ids = {r["action_id"] for r in rows}
    if b["action_id"] in _mentions(a, RELATION_COLUMNS, ids) or a["action_id"] in _mentions(b, RELATION_COLUMNS, ids):
        return True
    graph = {i: set() for i in ids}
    for r in rows:
        for o in _mentions(r, CHAIN_COLUMNS, ids):
            graph[r["action_id"]].add(o)
            graph[o].add(r["action_id"])
    seen, todo = {a["action_id"]}, [a["action_id"]]
    while todo:
        for nxt in graph[todo.pop()] - seen:
            if nxt == b["action_id"]:
                return True
            seen.add(nxt)
            todo.append(nxt)
    return False


def _basis(r) -> str:
    return r["legal_basis"].split(" (")[0].split(",")[0].strip()


def _scope_key(r) -> str:
    return "korea" if "Korea" in r["scope"] else "all"


def _effect_kind(r) -> str:
    text = r["rate_or_effect"].lower()
    if "de minimis" in text:
        return "de_minimis"
    return "duty" if "%" in text or "duties" in text else "other"


def _mode(r) -> str:
    scope = r["scope"].lower()
    if "non-postal" in scope or "other than the international postal" in scope:
        return "non_postal"
    return "postal" if "postal network" in scope else "any"


def _comparable(a, b) -> bool:
    """Same legal basis and kind of effect, and modes that can apply to the same shipment."""
    modes = {_mode(a), _mode(b)}
    return (_basis(a) == _basis(b) and _effect_kind(a) == _effect_kind(b)
            and not (modes == {"postal", "non_postal"}))


def undeclared_overlaps(rows: list[dict]) -> list[tuple[str, str]]:
    found = []
    for a, b in combinations(rows, 2):
        ia, ib = _interval(a), _interval(b)
        if not ia or not ib or not _comparable(a, b):
            continue
        if ia[0] < ib[1] and ib[0] < ia[1] and not _linked(a, b, rows):
            found.append((a["action_id"], b["action_id"]))
    return found


def test_overlapping_periods_are_declared():
    assert not undeclared_overlaps(ROWS)


def test_negative_overlap_without_supersession_fails():
    rows = [dict(r) for r in ROWS]
    for r in rows:
        if r["action_id"] == "KORdeal_15allin":
            r["supersedes"] = ""
        if r["action_id"] == "EO14326_KR15":
            r["superseded_by"] = ""
            r["ends_rule"] = "IEEPA duties ended by EO14389_end_ieepa"  # a shared third action must not link them
    assert ("EO14326_KR15", "KORdeal_15allin") in undeclared_overlaps(rows)


def test_exception_codes_are_well_formed_and_exist_where_collected():
    rows = read_csv(EXC_CODES)
    assert rows
    ch33 = {i["htsno"] for i in json.loads((HTS_RAW / "export_ch33.json").read_text(encoding="utf-8"))}
    for r in rows:
        assert re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(\d{2})?", r["code"]), r["code"]
        assert int(r["digits"]) in (8, 10)
        if r["code"].startswith("33"):
            code8 = r["code"][:10]
            assert code8 in ch33 or any(h.startswith(code8) for h in ch33), f"{r['code']} not in chapter 33 table"


def test_cosmetics_check_covers_every_chapter33_code_in_both_regimes():
    ch33 = [i["htsno"] for i in json.loads((HTS_RAW / "export_ch33.json").read_text(encoding="utf-8"))
            if re.match(r"^330[3-7]\.\d{2}\.\d{2}", i.get("htsno") or "")]
    checks = read_csv(COSMETICS)
    for regime in ("surcharge", "s301_korea"):
        assert sorted(c["htsno"] for c in checks if c["regime"] == regime) == sorted(ch33)
    for c in checks:
        listed = bool(c["listed_in"])
        assert (c["determination"] == "explicit_exclusion") == listed
        if not listed:
            aluminum = c["aluminum_232_derivative_19k"] == "True"
            expected = "needs_review_232_aluminum_derivative" if aluminum else "not_excepted_rev22"
            assert c["determination"] == expected
