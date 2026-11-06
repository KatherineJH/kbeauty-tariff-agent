"""Claim-scoped verified citations for rule segments.

The mapping is explicit and written by a person: warehouse/seeds/rule_citations.csv gives, for every citation,
rule_id, claim_role, evidence_id, source_file, physical_page, printed_page and the quote. Nothing is searched: the
verifier only checks that the quote is in the named file, that the page numbers match that file, and that the file
bytes still match data/extracted/rule_citations.lock.csv. There is no fallback to another file or page.

claim_role: authority | rate | effective_start | effective_end | scope | exclusion | stacking | resolution_condition

check_coverage() requires, for every rule segment, a citation for each role its fields call for, and a period
citation from every action listed in the segment's period_actions.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SEEDS = REPO / "warehouse" / "seeds"
CITATIONS = SEEDS / "rule_citations.csv"
LOCK = REPO / "data" / "extracted" / "rule_citations.lock.csv"
ROLES = ("authority", "rate", "effective_start", "effective_end", "scope", "exclusion", "stacking",
         "resolution_condition")
PERIOD_ROLES = ("effective_start", "effective_end")


class CitationError(RuntimeError):
    """Evidence missing, changed, not at the stated place, or not covering a required claim."""


@dataclass(frozen=True)
class Citation:
    citation_id: str
    rule_id: str
    claim_role: str
    evidence_id: str
    source_file: str
    physical_page: str
    printed_page: str
    quote: str
    note: str
    file_sha256: str


def normalize(text: str) -> str:
    text = text.replace("–", "-").replace("—", "-").replace("``", '"').replace("''", '"')
    return re.sub(r"\s+", " ", text).strip()


def file_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        raw = json.dumps(json.loads(raw), ensure_ascii=False)
    return normalize(raw)


def evidence_files(evidence_id: str, root: Path = REPO) -> list[Path]:
    """Committed files behind one evidence id (sorted). Used for consistency checks and the draft helper only."""
    kind, _, key = evidence_id.partition(":")
    ex = root / "data" / "extracted"
    if kind == "fr":
        return [ex / "fr_text" / f"{key}.txt"]
    if kind == "csms":
        return [ex / "cbp_csms" / f"{key}.txt"]
    if kind == "hts" and key == "current_rev22":
        return sorted((root / "data" / "raw" / "hts").glob("export_*.json")) + \
            sorted((ex / "hts_pdf" / "chapter_99").glob("page_*.txt"))
    if kind == "hts":
        return sorted((ex / "hts_archive_evidence" / key).glob("page_*.txt")) + \
            [ex / "hts_archive" / key / "change_record.txt"]
    raise CitationError(f"unknown evidence id {evidence_id}")


def _read(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _check_location(r: dict, root: Path, text: str) -> None:
    file = root / r["source_file"]
    m = re.fullmatch(r"page_(\d{4})\.txt", file.name)
    if (str(int(m.group(1))) if m else "") != r["physical_page"]:
        raise CitationError(f"{r['citation_id']}: physical_page {r['physical_page']!r} does not match {file.name}")
    label = re.search(r"99 - ([IVX]+) - (\d+)", text) if m else None
    if (f"99-{label.group(1)}-{label.group(2)}" if label else "") != r["printed_page"]:
        raise CitationError(f"{r['citation_id']}: printed_page {r['printed_page']!r} does not match the page")
    if file not in evidence_files(r["evidence_id"], root):
        raise CitationError(f"{r['citation_id']}: {r['source_file']} is not a file of {r['evidence_id']}")


def verify_rows(rows: list[dict], root: Path = REPO) -> dict[str, str]:
    """Check every row at its stated location only; returns {source_file: sha256}."""
    cache: dict[Path, str] = {}
    shas: dict[str, str] = {}
    for r in rows:
        if r["claim_role"] not in ROLES:
            raise CitationError(f"{r['citation_id']}: unknown claim_role {r['claim_role']}")
        file = root / r["source_file"]
        if not file.exists():
            raise CitationError(f"{r['citation_id']}: evidence file missing: {r['source_file']}")
        text = cache.setdefault(file, file_text(file))
        _check_location(r, root, text)
        if normalize(r["quote"]) not in text:
            raise CitationError(f"{r['citation_id']}: quote not in the stated file {r['source_file']}")
        shas[r["source_file"]] = hashlib.sha256(file.read_bytes()).hexdigest()
    return shas


def write_lock(path: Path = CITATIONS, lock: Path = LOCK, root: Path = REPO) -> int:
    rows = _read(path)
    shas = verify_rows(rows, root)
    with lock.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["source_file", "file_sha256"])
        for k in sorted(shas):
            w.writerow([k, shas[k]])
    return len(shas)


def load_verified(path: Path = CITATIONS, lock: Path = LOCK, root: Path = REPO) -> dict[str, list[Citation]]:
    """Citations by rule_id, verified at their stated locations and against the lock; raises CitationError."""
    if not path.exists() or not lock.exists():
        raise CitationError("citation seed or lock missing")
    rows = _read(path)
    locked = {r["source_file"]: r["file_sha256"] for r in _read(lock)}
    for r in rows:
        file = root / r["source_file"]
        if not file.exists():
            raise CitationError(f"{r['citation_id']}: evidence file missing: {r['source_file']}")
        if locked.get(r["source_file"]) != hashlib.sha256(file.read_bytes()).hexdigest():
            raise CitationError(f"{r['citation_id']}: evidence file changed: {r['source_file']}")
    verify_rows(rows, root)
    out: dict[str, list[Citation]] = {}
    for r in rows:
        out.setdefault(r["rule_id"], []).append(Citation(
            r["citation_id"], r["rule_id"], r["claim_role"], r["evidence_id"], r["source_file"], r["physical_page"],
            r["printed_page"], normalize(r["quote"]), r["note"], locked[r["source_file"]]))
    for v in out.values():
        v.sort(key=lambda c: (ROLES.index(c.claim_role), c.citation_id))
    return out


def required_roles(segment: dict, code_conditions: set[str]) -> set[str]:
    """Roles a segment's fields call for (segment: a row of rule_segments.csv)."""
    roles = {"authority", "effective_start", "scope"}
    if segment["rate_kind"] != "none":
        roles.add("rate")
    if segment["ends_at"]:
        roles.add("effective_end")
    if segment["hts_scope"].startswith("ALL_EXCEPT_LIST:"):
        roles.add("exclusion")
    if segment["value_component"] in ("FULL_VALUE_LESS_232_METAL_CONTENT", "ALUMINUM_CONTENT", "STEEL_CONTENT") \
            or segment["rate_kind"] == "total_with_column1":
        roles.add("stacking")
    if segment["segment_id"] in code_conditions:
        roles.add("resolution_condition")
    return roles


def check_coverage(citations: dict[str, list[Citation]], seeds: Path = SEEDS) -> None:
    """Every segment has every required role, and a period citation from each of its period_actions."""
    segments = _read(seeds / "rule_segments.csv")
    conditions = {r["segment_id"] for r in _read(seeds / "rule_code_resolution.csv") if r["resolved_when"]}
    action_ev: dict[str, set[str]] = {}
    for r in _read(seeds / "action_evidence.csv"):
        action_ev.setdefault(r["action_id"], set()).add(r["evidence_id"])
    problems = []
    for s in segments:
        cites = citations.get(s["segment_id"], [])
        have = {c.claim_role for c in cites}
        for role in sorted(required_roles(s, conditions) - have):
            problems.append(f"{s['segment_id']}: no {role} citation")
        period_ev = {c.evidence_id for c in cites if c.claim_role in PERIOD_ROLES}
        for action in s["period_actions"].split(";"):
            if not period_ev & action_ev.get(action, set()):
                problems.append(f"{s['segment_id']}: no period citation from {action}")
    if problems:
        raise CitationError("; ".join(problems))
