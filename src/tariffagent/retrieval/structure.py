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

CONFIG_V1 = {
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
# v2 changes only how a lead-in is closed (status of v1: invalid_structural_context, see docs/retrieval_b2.md)
CONFIG_V2 = {
    **CONFIG_V1,
    "config_id": "b2_heading_v2",
    "notes_pages": "R1 as v1, and a lead-in is also closed by (i) a note line printed as '(N)(a)' (a parenthesized "
                   "note number directly followed by the first subdivision), (ii) any later sibling label, not only "
                   "the next one: same form, later in sequence (digits by value; single letters alphabetically and "
                   "repeated letters of the same length alphabetically, in both cases unless the label is also a "
                   "roman numeral; roman numerals by value)",
    "page_boundary": "state carried only to physical page n + 1 of the same source when page n parsed as a notes "
                     "page; otherwise nothing is inherited",
    "unchanged": "lead-in definition, fields, duty_family and country rules, R2 to R5, index_text, chunk_id",
}
# v3 again changes only how a lead-in is closed (status of v2: invalid_structural_context after the review of its
# long contexts, see docs/retrieval_b2.md)
CONFIG_V3 = {
    **CONFIG_V2,
    "config_id": "b2_heading_v3",
    "notes_pages": CONFIG_V2["notes_pages"] + "; and (iii) a label or a note number printed alone on its line "
                   "('(xxiv)', '52.') is a marker or a note boundary (a bare label counts only in a valid label form: "
                   "digits, one letter, a repeated letter, a roman numeral, one capital; '(liters)' does not), "
                   "(iv) a lead-in is also closed by the next or a later sibling of its parent, the last marker of "
                   "another form before it",
}
# v4 changes only the extent of the lead-in sentence (v3: applicable_heading cut at the end of the printed line)
CONFIG_V4 = {
    **CONFIG_V3,
    "config_id": "b2_heading_v4",
    "lead_in_sentence": "whether a line is a lead-in is decided on its first printed line as in v3; its sentence "
                        "(governing_text, applicable_heading, duty_family, country_scope) is then read across line "
                        "breaks, from the marker to the first ':' or sentence end, at most 600 characters",
    "exclusion_sentences": "when the lead-in sentence says the duty does 'not apply', duty_family is read only from a "
                           "named statute and country_scope is left empty (a product class or country there names "
                           "the excluded goods)",
}
CONFIGS = {c["config_id"]: c for c in (CONFIG_V1, CONFIG_V2, CONFIG_V3, CONFIG_V4)}
RULES = {"b2_heading_v1": {"paren_note": False, "later_sibling": False, "bare": False, "parent": False,
                           "multiline": False},
         "b2_heading_v2": {"paren_note": True, "later_sibling": True, "bare": False, "parent": False,
                           "multiline": False},
         "b2_heading_v3": {"paren_note": True, "later_sibling": True, "bare": True, "parent": True,
                           "multiline": False},
         "b2_heading_v4": {"paren_note": True, "later_sibling": True, "bare": True, "parent": True,
                           "multiline": True}}
CONFIG = CONFIG_V4
CONFIG_ID = CONFIG["config_id"]

HEADING = re.compile(r"\b9903\.\d{2}\.\d{2}\b")
MARKER = re.compile(r"^\(([a-z]{1,7}|[0-9]{1,2}|[A-Z])\) ")
BARE_MARKER = re.compile(r"^\(([a-z]{1,7}|[0-9]{1,2}|[A-Z])\)$")
NOTE_LINE = re.compile(r"^(\d{1,2})\. ")
NOTE_LINE_PAREN = re.compile(r"^\((\d{1,2})\)(?=\([a-z]\))")
NOTE_LINE_BARE = re.compile(r"^(\d{1,2})\.$")
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


def config_hash(config_id: str = CONFIG_ID) -> str:
    return logical_hash([CONFIGS[config_id]])


def later_sibling(lead: str, label: str) -> bool:
    """v2: does `label` come later than `lead` in the same label sequence?"""
    if lead.isdigit() and label.isdigit():
        return int(label) > int(lead)
    if len(lead) == 1 and len(label) == 1 and lead.isalpha() and label.isalpha() and lead.islower() == label.islower():
        if label > lead and label not in ROMAN:     # (v), (x), (l) may be roman items inside a lettered subdivision
            return True
    rep = lambda s: len(s) >= 2 and s.isalpha() and len(set(s)) == 1
    if rep(lead) and rep(label) and len(lead) == len(label) and label not in ROMAN and label[0] > lead[0]:
        return True
    return lead in ROMAN and label in ROMAN and ROMAN[label] > ROMAN[lead] and not (len(lead) == len(label) == 1)


def _rep(s: str) -> bool:
    return len(s) >= 2 and s.isalpha() and len(set(s)) == 1


def valid_label(label: str) -> bool:
    """v3: label forms used by the notes (a bare '(liters)' is not one)."""
    return label.isdigit() or (len(label) == 1 and label.isalpha()) or _rep(label) or label in ROMAN


def label_form(label: str) -> str:
    if label.isdigit():
        return "digit"
    if len(label) == 1 and label.isupper():
        return "capital"
    if len(label) == 1:
        return "letter_or_roman" if label in ROMAN else "letter"
    if label in ROMAN:
        return "roman"
    return f"repeated{len(label)}" if _rep(label) else "other"


def same_form(a: str, b: str) -> bool:
    fa, fb = label_form(a), label_form(b)
    return fa == fb or {fa, fb} <= {"letter", "letter_or_roman"} or {fa, fb} <= {"roman", "letter_or_roman"}


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
    page: int = 0               # physical page where the lead-in is printed (bookkeeping, not in the context)
    note: str = ""
    parent: str = ""            # v3: last marker of another form before the lead-in (bookkeeping)
    exclusion_guard: bool = False   # v4: product class and country are not read from an exclusion sentence

    def fields(self) -> dict:
        statute = STATUTE.search(self.sentence)
        # in an exclusion ("shall not apply to ..."), a product class or a country names the excluded goods, not the
        # duty's own scope
        excluded = self.exclusion_guard and re.search(r"\bnot apply\b", self.sentence)
        product = None if excluded else PRODUCT.search(self.sentence)
        country = None if excluded else COUNTRY.search(self.sentence)
        return {"subdivision": f"({self.label})", "applicable_heading": ";".join(self.headings),
                "governing_text": self.sentence,
                "duty_family": statute.group(0) if statute else (product.group(0) if product else "unknown"),
                "country_scope": country.group(1) if country else ""}


@dataclass
class PageState:
    """Notes-page state at a point: the open lead-in and the last note number."""
    lead_in: LeadIn | None = None
    note: str = ""
    recent: tuple[str, ...] = ()    # v3: labels of the markers seen since the last note line, latest last


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


def notes_events(raw: str, doc_text: str, start: PageState, config_id: str = CONFIG_ID,
                 page: int = 0) -> tuple[list[Event], PageState] | None:
    """State changes on one notes page, starting from `start` (carried state or empty)."""
    rules = RULES[config_id]
    lines = _line_offsets(raw, doc_text)
    if lines is None:
        return None
    state = PageState(start.lead_in, start.note, start.recent)
    events = [Event(0, PageState(state.lead_in, state.note, state.recent))]
    for off, line in lines:
        changed = False
        line_full = line
        note = NOTE_LINE.match(line) or (NOTE_LINE_PAREN.match(line) if rules["paren_note"] else None) \
            or (NOTE_LINE_BARE.match(line) if rules["bare"] else None)
        if note:
            state = PageState(None, note.group(1), ())
            changed = True
            line = line[note.end():].lstrip()
        m = MARKER.match(line)
        if not m and rules["bare"]:
            m = BARE_MARKER.match(line)
            if m and not valid_label(m.group(1)):
                m = None
        if m:
            label = m.group(1)
            sentence = re.split(r"(?<=:)|(?<=\.) (?=[A-Z(])", line, maxsplit=1)[0][:300]
            src = DUTY_SOURCE.search(sentence)
            heads = tuple(dict.fromkeys(HEADING.findall(src.group(1)))) if src else ()
            lead = state.lead_in
            if heads and rules["multiline"]:
                start_at = off + (len(line_full) - len(line))     # the marker's offset in the page text
                window = doc_text[start_at:start_at + 600]
                sentence = re.split(r"(?<=:)|(?<=\.) (?=[A-Z(])", window, maxsplit=1)[0]
                src = DUTY_SOURCE.search(sentence)
                heads = tuple(dict.fromkeys(HEADING.findall(src.group(1)))) if src else heads
            if heads:
                parent = next((r for r in reversed(state.recent) if not same_form(r, label)), "") \
                    if rules["parent"] else ""
                state = PageState(LeadIn(label, sentence, heads, page, state.note, parent, rules["multiline"]),
                                  state.note, state.recent)
                changed = True
            elif lead and (label in successors(lead.label)
                           or (rules["later_sibling"] and later_sibling(lead.label, label))
                           or (rules["parent"] and lead.parent and same_form(label, lead.parent)
                               and (label in successors(lead.parent) or later_sibling(lead.parent, label)))):
                state = PageState(None, state.note, state.recent)
                changed = True
            if rules["parent"]:
                state = PageState(state.lead_in, state.note, (state.recent + (label,))[-40:])
        if changed:
            events.append(Event(off, PageState(state.lead_in, state.note, state.recent)))
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


def page_states(docs: list[Document], root: Path = REPO,
                config_id: str = CONFIG_ID) -> dict[str, list[Event] | None]:
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
            res = notes_events((root / d.source_file).read_text("utf-8"), d.text, start, config_id, n)
            if res is None:
                out[d.source_file] = None
                carried = None
                continue
            events, end_state = res
            out[d.source_file] = events
            carried = (n, end_state)
    return out


def enrich(docs: list[Document], chunks: list[Chunk], root: Path = REPO,
           config_id: str = CONFIG_ID) -> list[B2Chunk]:
    by_file = {d.source_file: d for d in docs}
    states = page_states(docs, root, config_id)
    chash = config_hash(config_id)
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
                f["_lead_in_page"], f["_lead_in_note"] = st.lead_in.page, st.lead_in.note
                first_own = next((e for e in events[1:] if e.state.lead_in is st.lead_in), None)
                origin = "same_page" if first_own and first_own.offset <= at else \
                    f"previous_page:{int(d.physical_page) - 1}"
        ctx = _context_text(f)
        index_text = f"[context] {ctx} [/context] [text] {c.text} [/text]"
        cid = hashlib.sha256(f"b2|{chash}|{c.chunk_id}|{ctx}".encode("utf-8")).hexdigest()[:16]
        out.append(B2Chunk(cid, c.chunk_id, config_id, c.source_id, c.source_file, f["revision"], c.physical_page,
                           c.printed_page, c.start, c.end, c.text, ctx, index_text, f.get("note", ""),
                           f.get("subdivision", ""), f.get("applicable_heading", ""), f.get("duty_family", ""),
                           f.get("country_scope", ""), origin, f))
    return sorted(out, key=lambda b: b.chunk_id)


def structure_stats(b2: list[B2Chunk]) -> dict:
    """Inheritance quality: how far governing contexts reach. A context = (source, lead-in page, governing text)."""
    notes = [b for b in b2 if b.fields.get("governing_text") or b.context_origin == "none" and b.physical_page
             and (b.source_id.startswith("htsarch:") or b.source_id == "hts22:chapter_99")]
    governed = [b for b in b2 if b.fields.get("governing_text")]
    inherited = [b for b in governed if b.context_origin.startswith("previous_page")]
    contexts: dict[tuple, list[B2Chunk]] = {}
    for b in governed:
        contexts.setdefault((b.source_id, b.fields["_lead_in_page"], b.fields["governing_text"]), []).append(b)
    per_context = sorted(({"source_id": k[0], "lead_in_page": k[1], "governing_text": k[2][:120],
                           "chunks": len(v), "inherited_chunks": sum(1 for b in v if b in inherited),
                           "pages": len({b.physical_page for b in v}),
                           "max_distance_pages": max(int(b.physical_page) - k[1] for b in v)}
                          for k, v in contexts.items()),
                         key=lambda r: (-r["max_distance_pages"], -r["chunks"], r["source_id"], r["lead_in_page"]))
    crossing = [b for b in governed if b.fields.get("_lead_in_note") and b.note and b.fields["_lead_in_note"] != b.note]
    return {
        "chapter99_chunks": len(notes),
        "governed_chunks": len(governed),
        "inherited_chunks": len(inherited),
        "inherited_ratio_of_governed": round(len(inherited) / len(governed), 4) if governed else 0.0,
        "governed_ratio_of_chapter99": round(len(governed) / len(notes), 4) if notes else 0.0,
        "unknown_context_ratio_of_chapter99": round(1 - len(governed) / len(notes), 4) if notes else 0.0,
        "duty_family_unknown_ratio_of_governed": round(
            sum(1 for b in governed if b.duty_family == "unknown") / len(governed), 4) if governed else 0.0,
        "contexts": len(per_context),
        "max_distance_pages": max((r["max_distance_pages"] for r in per_context), default=0),
        "contexts_over_2_pages": sum(1 for r in per_context if r["max_distance_pages"] > 2),
        "chunks_crossing_a_note_boundary": len(crossing),
        "top_contexts_by_distance": per_context[:10],
    }


def b2_hashes(b2: list[B2Chunk]) -> dict:
    config_id = b2[0].config_id
    return {
        "config_id": config_id,
        "config_sha256": config_hash(config_id),
        "b2_chunks": len(b2),
        "b2_chunks_sha256": logical_hash([[b.chunk_id, b.parent_chunk_id, b.source_file, b.start, b.end,
                                           hashlib.sha256(b.index_text.encode("utf-8")).hexdigest()] for b in b2]),
        "context_origin_counts": {k: sum(1 for b in b2 if b.context_origin.split(":")[0] == k)
                                  for k in sorted({b.context_origin.split(":")[0] for b in b2})},
    }
