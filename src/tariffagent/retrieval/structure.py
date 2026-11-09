"""B2 retrieval unit: the B1 chunk with an explicit structural context (heading-enriched BM25).

Configuration b2_heading_v1. The raw text, the chunk windows and the BM25 parameters are B1's; only a context block
is added in front of the raw text for indexing. Written before the first B2 run (see CONFIG and
docs/retrieval_b2.md).

Inputs: the documents and B1 chunks of tariffagent.retrieval.corpus, the raw page files they come from, the HTS
release label (data/raw/hts/RELEASE.txt) and the Federal Register API metadata (data/raw/federal_register/doc_*.json:
title, document type and number, publication date only). Nothing else: no citation seed, no qrels, no queries, no
evaluation output.

Structure rules (all deterministic; a field that cannot be determined is left empty, never guessed):

  R1 chapter 99 notes pages (htsarch:<release> and hts22:chapter_99 pages whose text starts with "U.S. Notes"):
     - Markers are read from the raw page lines: a note line "N. " and subdivision lines that start with "(x) ".
     - A lead-in is a subdivision line whose first sentence (up to the first ":" or 300 characters) names a chapter
       99 heading as the source of a duty ("rates of duty (set forth) in heading X", "duty imposed by heading(s) X").
       A line that only mentions headings ("products ... provided for in headings X") is not a lead-in.
       It governs the text after it until (a) another lead-in, (b) a line-start marker whose label is the successor
       of the lead-in's label (n -> o, v -> w or vi, aa -> bb), (c) a new note line.
     - A chunk takes the lead-in governing its start offset; the running page header "U.S. Notes (con.)" at the
       top of a page is skipped. Its fields come from that lead-in only:
       applicable_heading (the headings in the duty-source phrase), subdivision label, governing_text (the lead-in
       sentence), country_scope ("of [the] Capitalized Name" in the sentence), duty_family (a statute named in the
       sentence, else the product class it names, else "unknown"). note = the last note number seen.
     - Page boundary: when no lead-in governs the chunk start on its page, the state at the end of the previous
       physical page is carried over only if that page is in the corpus for the same source (contiguous);
       otherwise the fields stay empty. context_origin records same_page / previous_page:<n> / none.
  R2 chapter 99 rate-table pages (all other chapter 99 pages): no heading is inherited (a description line precedes
     its heading number, so the previous heading would be wrong); context = revision and page only.
  R3 Federal Register documents: official title, document type and number, publication date from the API metadata.
  R4 CSMS messages: the first line of the message (its subject).
  R5 everything else (other HTS PDFs, HTS exports, change records): revision and document kind only.

context_text is a fixed-order "key: value" block of the non-empty fields; index_text =
"[context] " + context_text + " [/context] [text] " + raw_text + " [/text]".
B2 chunk_id = first 16 hex of SHA-256 over "b2|<config hash>|<parent B1 chunk_id>|<context_text>".
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from tariffagent.answer.citations import normalize
from tariffagent.retrieval.corpus import REPO, Chunk, Document, logical_hash

CONFIG = {
    "config_id": "b2_heading_v1",
    "parent": "B1 chunks (120 words, 30 overlap) unchanged; raw_text == B1 chunk text",
    "bm25": "B1 tokenizer, k1 = 1.2, b = 0.75",
    "notes_pages": "R1: lead-in = subdivision line whose first sentence names a 9903 heading as the source of a "
                   "duty (rates of duty in / duty imposed by heading); closed by another lead-in, the successor "
                   "label, or a new note; the page header 'U.S. Notes (con.)' is skipped; carried to the next "
                   "physical page only when that page is in the corpus for the same source",
    "table_pages": "R2: no heading inheritance",
    "federal_register": "R3: title, document type and number, publication date (API metadata)",
    "csms": "R4: first line",
    "other": "R5: revision and document kind",
    "unknown": "fields that cannot be determined stay empty; duty_family 'unknown' on notes pages",
    "index_text": "[context] <context_text> [/context] [text] <raw_text> [/text]",
    "chunk_id": "sha256(b2|config_hash|parent_chunk_id|context_text)[:16]",
}
CONFIG_ID = CONFIG["config_id"]

HEADING = re.compile(r"\b9903\.\d{2}\.\d{2}\b")
MARKER = re.compile(r"^\(([a-z]{1,7}|[0-9]{1,2}|[A-Z])\) ")
NOTE_LINE = re.compile(r"^(\d{1,2})\. ")
PAGE_HEADER = re.compile(r"^U\.S\. Notes(?: \(con\.\))?$")
# a heading named as the source of a duty: "rates of duty (set forth) in heading X", "duty imposed by headings X, Y"
DUTY_SOURCE = re.compile(r"(?:rates? of duty|dut(?:y|ies))[^.:;]{0,40}?\b(?:in|by) headings? (.*?)(?= shall| apply|$)")
STATUTE = re.compile(r"section 232|section 301|section 122|section 201|"
                     r"International Emergency Economic Powers Act|IEEPA", re.I)
PRODUCT = re.compile(r"derivative [a-z]+(?: or [a-z]+)? products|products of (?:iron or steel|aluminum|copper)|"
                     r"passenger vehicles|light trucks|auto(?:mobile)? parts")
COUNTRY = re.compile(r"\b(?:products|articles|goods)(?: the product)? of (?:the )?([A-Z][a-z]+(?: [A-Z][a-z]+)*)")


def _roman(n: int) -> str:
    out = ""
    for v, s in ((50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= v:
            out, n = out + s, n - v
    return out


ROMAN = {_roman(i): i for i in range(1, 90)}
ROMAN_BY_N = {i: v for v, i in ROMAN.items()}


def config_hash() -> str:
    return logical_hash([CONFIG])


def successors(label: str) -> set[str]:
    """Labels that close a lead-in with this label (the next sibling under either reading of the label)."""
    out = set()
    if label.isdigit():
        out.add(str(int(label) + 1))
    elif len(label) == 1 and label.isalpha():
        out.add(chr(ord(label) + 1))
    elif len(set(label)) == 1 and label.isalpha():           # aa -> bb
        out.add(chr(ord(label[0]) + 1) * len(label))
    if label in ROMAN and ROMAN[label] + 1 in ROMAN_BY_N:
        out.add(ROMAN_BY_N[ROMAN[label] + 1])
    return out


@dataclass(frozen=True)
class LeadIn:
    label: str
    sentence: str
    headings: tuple[str, ...]

    def fields(self) -> dict:
        statute = STATUTE.search(self.sentence)
        product = PRODUCT.search(self.sentence)
        country = COUNTRY.search(self.sentence)
        return {"subdivision": f"({self.label})", "applicable_heading": ";".join(self.headings),
                "governing_text": self.sentence,
                "duty_family": statute.group(0) if statute else (product.group(0) if product else "unknown"),
                "country_scope": country.group(1) if country else ""}


@dataclass
class PageState:
    """Notes-page state at a point: the open lead-in and the last note number."""
    lead_in: LeadIn | None = None
    note: str = ""


@dataclass(frozen=True)
class Event:
    offset: int                 # offset in the normalized page text where the line starts
    state: PageState


def _line_offsets(raw: str, doc_text: str) -> list[tuple[int, str]] | None:
    """(offset in doc_text, normalized line) per non-empty raw line, or None if the lines do not rebuild doc_text."""
    out, pos, parts = [], 0, []
    for line in raw.splitlines():
        n = unicodedata.normalize("NFC", normalize(line))
        if not n:
            continue
        if parts:
            pos += 1
        out.append((pos, n))
        parts.append(n)
        pos += len(n)
    return out if " ".join(parts) == doc_text else None


def notes_events(raw: str, doc_text: str, start: PageState) -> tuple[list[Event], PageState] | None:
    """State changes on one notes page, starting from `start` (carried state or empty)."""
    lines = _line_offsets(raw, doc_text)
    if lines is None:
        return None
    state = PageState(start.lead_in, start.note)
    events = [Event(0, PageState(state.lead_in, state.note))]
    for off, line in lines:
        changed = False
        note = NOTE_LINE.match(line)
        if note:
            state = PageState(None, note.group(1))
            changed = True
            line = line[note.end():]
        m = MARKER.match(line)
        if m:
            label = m.group(1)
            sentence = re.split(r"(?<=:)|(?<=\.) (?=[A-Z(])", line, maxsplit=1)[0][:300]
            src = DUTY_SOURCE.search(sentence)
            heads = tuple(dict.fromkeys(HEADING.findall(src.group(1)))) if src else ()
            if heads:
                state = PageState(LeadIn(label, sentence, heads), state.note)
                changed = True
            elif state.lead_in and label in successors(state.lead_in.label):
                state = PageState(None, state.note)
                changed = True
        if changed:
            events.append(Event(off, PageState(state.lead_in, state.note)))
    return events, state


def state_at(events: list[Event], offset: int) -> PageState:
    cur = events[0].state
    for e in events:
        if e.offset <= offset:
            cur = e.state
        else:
            break
    return cur


@dataclass(frozen=True)
class B2Chunk:
    chunk_id: str
    parent_chunk_id: str
    config_id: str
    source_id: str
    source_file: str
    source_revision: str
    physical_page: str
    printed_page: str
    start: int
    end: int
    raw_text: str
    context_text: str
    index_text: str
    note: str
    subdivision: str
    applicable_heading: str
    duty_family: str
    country_scope: str
    context_origin: str
    fields: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def text(self) -> str:          # what BM25 indexes
        return self.index_text


def _revision(doc: Document, root: Path) -> str:
    if doc.source_id.startswith("htsarch:"):
        return doc.source_id.split(":")[1]
    if doc.source_id.startswith("hts22:"):
        rel = (root / "data" / "raw" / "hts" / "RELEASE.txt").read_text("utf-8")
        m = re.search(r"(\d{4}) HTS Revision (\d+)", rel)
        return f"{m.group(1)}HTSRev{m.group(2)}" if m else ""
    return ""


def _is_chapter99_page(doc: Document) -> bool:
    return bool(doc.physical_page) and (doc.source_id.startswith("htsarch:")
                                        or doc.source_id == "hts22:chapter_99")


def _fr_meta(doc: Document, root: Path) -> dict:
    p = root / "data" / "raw" / "federal_register" / f"doc_{doc.source_id.split(':')[1]}.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text("utf-8"))
    number = d.get("executive_order_number") or d.get("proclamation_number") or ""
    kind = d.get("subtype") or d.get("type") or ""
    return {"document": f"{kind} {number}".strip(), "title": d.get("title") or "",
            "published": d.get("publication_date") or ""}


def _context_text(f: dict) -> str:
    keys = ("source", "revision", "page", "document", "title", "published", "note", "subdivision",
            "applicable_heading", "duty_family", "country_scope", "governing_text")
    return " | ".join(f"{k}: {f[k]}" for k in keys if f.get(k))


def page_states(docs: list[Document], root: Path = REPO) -> dict[str, list[Event] | None]:
    """Events per chapter 99 notes page (source_file -> events), with the R1 page-boundary rule."""
    out: dict[str, list[Event] | None] = {}
    pages: dict[str, dict[int, Document]] = {}
    for d in docs:
        if _is_chapter99_page(d):
            pages.setdefault(d.source_id, {})[int(d.physical_page)] = d
    for src, by_page in pages.items():
        carried: tuple[int, PageState] | None = None
        for n in sorted(by_page):
            d = by_page[n]
            if not d.text.startswith("U.S. Notes"):
                out[d.source_file] = None              # rate-table page: R2
                carried = None
                continue
            start = carried[1] if carried and carried[0] == n - 1 else PageState()
            res = notes_events((root / d.source_file).read_text("utf-8"), d.text, start)
            if res is None:
                out[d.source_file] = None
                carried = None
                continue
            events, end_state = res
            out[d.source_file] = events
            carried = (n, end_state)
    return out


def enrich(docs: list[Document], chunks: list[Chunk], root: Path = REPO) -> list[B2Chunk]:
    by_file = {d.source_file: d for d in docs}
    states = page_states(docs, root)
    chash = config_hash()
    fr_cache: dict[str, dict] = {}
    out = []
    for c in chunks:
        d = by_file[c.source_file]
        f = {"source": d.source_id, "revision": _revision(d, root),
             "page": f"{d.physical_page}/{d.printed_page}" if d.physical_page else ""}
        origin = "none"
        if d.source_id.startswith("fr:"):
            fr_cache.setdefault(d.source_id, _fr_meta(d, root))
            f.update(fr_cache[d.source_id])
            origin = "document_metadata"
        elif d.source_id.startswith("csms:"):
            f["title"] = d.text.split(" CSMS # ")[0][:200]
            origin = "document_metadata"
        elif states.get(c.source_file):
            events = states[c.source_file]
            header = re.match(r"U\.S\. Notes(?: \(con\.\))? ", d.text)
            at = max(c.start, header.end() if header else 0)     # the running page header belongs to no subdivision
            st = state_at(events, at)
            if st.note:
                f["note"] = st.note
            if st.lead_in:
                f.update(st.lead_in.fields())
                first_own = next((e for e in events[1:] if e.state.lead_in is st.lead_in), None)
                origin = "same_page" if first_own and first_own.offset <= at else \
                    f"previous_page:{int(d.physical_page) - 1}"
        ctx = _context_text(f)
        index_text = f"[context] {ctx} [/context] [text] {c.text} [/text]"
        cid = hashlib.sha256(f"b2|{chash}|{c.chunk_id}|{ctx}".encode("utf-8")).hexdigest()[:16]
        out.append(B2Chunk(cid, c.chunk_id, CONFIG_ID, c.source_id, c.source_file, f["revision"], c.physical_page,
                           c.printed_page, c.start, c.end, c.text, ctx, index_text, f.get("note", ""),
                           f.get("subdivision", ""), f.get("applicable_heading", ""), f.get("duty_family", ""),
                           f.get("country_scope", ""), origin, f))
    return sorted(out, key=lambda b: b.chunk_id)


def b2_hashes(b2: list[B2Chunk]) -> dict:
    return {
        "config_id": CONFIG_ID,
        "config_sha256": config_hash(),
        "b2_chunks": len(b2),
        "b2_chunks_sha256": logical_hash([[b.chunk_id, b.parent_chunk_id, b.source_file, b.start, b.end,
                                           hashlib.sha256(b.index_text.encode("utf-8")).hexdigest()] for b in b2]),
        "context_origin_counts": {k: sum(1 for b in b2 if b.context_origin.split(":")[0] == k)
                                  for k in sorted({b.context_origin.split(":")[0] for b in b2})},
    }
