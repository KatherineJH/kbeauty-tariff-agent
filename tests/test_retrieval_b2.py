"""B2 heading-enriched chunks: determinism, lineage, unchanged raw text, no answer leakage, structure rules."""

import ast
import json
import builtins
import hashlib
import io
import re
import unicodedata
from pathlib import Path

import pytest

import tariffagent.retrieval.structure as st
from tariffagent.answer.citations import normalize
from tariffagent.retrieval.bm25 import BM25Index
from tariffagent.retrieval.corpus import REPO, Document, build_chunks, chunk_document, documents
from tariffagent.retrieval.structure import (PageState, b2_hashes, enrich, later_sibling, notes_events, state_at,
                                             structure_stats, successors)

MODULE = REPO / "src" / "tariffagent" / "retrieval" / "structure.py"


@pytest.fixture(scope="module")
def docs():
    return documents()


@pytest.fixture(scope="module")
def b1(docs):
    return build_chunks()


@pytest.fixture(scope="module")
def b2(docs, b1):
    return enrich(docs, b1)


@pytest.fixture(scope="module")
def b2_v1(docs, b1):
    return enrich(docs, b1, config_id="b2_heading_v1")


def test_b2_is_deterministic(docs, b1, b2):
    again = enrich(docs, build_chunks())
    assert b2_hashes(again) == b2_hashes(b2)
    assert BM25Index(again).logical_hash() == BM25Index(b2).logical_hash()


def test_b2_ids_unique_and_one_child_per_b1_chunk(b1, b2):
    ids = [b.chunk_id for b in b2]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"[0-9a-f]{16}", i) for i in ids)
    assert sorted(b.parent_chunk_id for b in b2) == sorted(c.chunk_id for c in b1)


def test_raw_text_is_unchanged_and_traceable(docs, b1, b2):
    parents = {c.chunk_id: c for c in b1}
    texts = {d.source_file: d.text for d in docs}
    for b in b2:
        p = parents[b.parent_chunk_id]
        assert b.raw_text == p.text == texts[b.source_file][b.start:b.end]
        assert (b.source_file, b.start, b.end, b.physical_page) == (p.source_file, p.start, p.end, p.physical_page)
        assert b.index_text == f"[context] {b.context_text} [/context] [text] {b.raw_text} [/text]"
        assert "[text]" not in b.context_text and "[/context]" not in b.context_text


def test_governing_text_is_copied_from_the_source(docs, b2):
    texts = {d.source_file: d.text for d in docs}
    by_page = {(d.source_id, d.physical_page): d.text for d in docs if d.physical_page}
    for b in b2:
        g = b.fields.get("governing_text")
        if not g:
            continue
        if b.context_origin == "same_page":
            assert g in texts[b.source_file]
        else:
            prev = int(b.context_origin.split(":")[1])
            assert prev == int(b.physical_page) - 1 and (b.source_id, str(prev)) in by_page
        for h in b.applicable_heading.split(";"):
            assert h in g


# --- leakage -------------------------------------------------------------------------------------------------------

def _code(path: Path) -> str:
    tree = ast.parse(path.read_text("utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        first = body[0] if isinstance(body, list) and body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            body.pop(0)
    return ast.unparse(tree)


def test_enrichment_code_names_no_answer_source():
    code = _code(MODULE)
    for word in ("rule_citations", "CITATIONS", "qrel", "queries", "evals", "reports", "run_00", "dq0", "dq1",
                 "3304", "9903.81.91", "9903.03.01", "pair_id"):
        assert word not in code, word


def test_enrichment_opens_no_answer_file(docs, b1, b2, monkeypatch):
    opened = []
    real_open, real_read = builtins.open, Path.read_text

    def spy_open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    def spy_read(self, *a, **k):
        opened.append(str(self))
        return real_read(self, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(io, "open", spy_open)
    monkeypatch.setattr(Path, "read_text", spy_read)
    again = enrich(docs, b1)
    monkeypatch.undo()
    assert b2_hashes(again) == b2_hashes(b2)
    norm = [p.replace("\\", "/") for p in opened]
    assert opened and not [p for p in norm if "/evals/" in p or "/reports/" in p or "rule_citations" in p
                           or "/warehouse/" in p]
    assert all(("/data/" in p) for p in norm), sorted(set(norm))[:5]


def test_enrichment_ignores_moved_answer_files(docs, b1, b2, monkeypatch, tmp_path):
    import tariffagent.answer.citations as citations
    import tariffagent.retrieval.evaluate as evaluate
    monkeypatch.setattr(citations, "CITATIONS", tmp_path / "none.csv")
    monkeypatch.setattr(evaluate, "QUERIES", tmp_path / "none.csv")
    monkeypatch.setattr(evaluate, "RETRIEVAL_QRELS", tmp_path / "none.csv")
    assert b2_hashes(enrich(docs, b1)) == b2_hashes(b2)


# --- structure rules on synthetic pages (negative tests) -------------------------------------------------------------

def _page(root: Path, source: str, n: int, raw: str) -> Document:
    rel = f"data/extracted/hts_archive_evidence/{source}/page_{n:04d}.txt"
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(raw, encoding="utf-8")
    text = unicodedata.normalize("NFC", normalize(raw))
    return Document(f"htsarch:{source}", rel, str(n), f"99-III-{n}", text)


LIST = "0402.99.68; 0402.99.70; 2106.90.9998; 2710.19.3050; 3208.10.00; 3208.20.00; 3209.10.00;"


def _b2_for(root, docs):
    chunks = [c for d in docs for c in chunk_document(d)]
    return enrich(docs, chunks, root)


def test_sibling_label_closes_the_lead_in():
    raw = ("U.S. Notes (con.)\n(n) The rates of duty in heading 9903.80.01 apply to:\n" + LIST + "\n"
           "(o) For subheadings 7317.00.55 and 7317.00.65, this provision applies to the numbers listed above.\n")
    text = normalize(raw)
    events, end = notes_events(raw, text, PageState())
    assert state_at(events, text.index("0402.99.68")).lead_in.headings == ("9903.80.01",)
    assert state_at(events, text.index("(o)")).lead_in is None and end.lead_in is None


def test_items_that_mention_headings_are_not_lead_ins():
    raw = ("U.S. Notes (con.)\n(v) As provided in heading 9903.80.06, the additional duty imposed by heading "
           "9903.80.01 shall not apply to:\n(a) products of iron or steel provided for in headings 9903.80.02 and "
           "9903.80.03, but such additional duty shall apply to the non-steel content;\n"
           "(b) the declared value of the aluminum content of products provided for in heading 9903.80.04;\n")
    text = normalize(raw)
    events, _ = notes_events(raw, text, PageState())
    for marker in ("(a)", "(b)"):
        assert state_at(events, text.index(marker)).lead_in.headings == ("9903.80.01",)
    assert {"vi", "w"} <= successors("v") and "bb" in successors("aa") and "o" in successors("n")


def test_same_list_under_different_headings_links_to_its_own_parent(tmp_path):
    words = " ".join(["filler"] * 130)
    docs = [_page(tmp_path, "R1", 10, f"U.S. Notes (con.)\n(n) The rates of duty in heading 9903.80.01 apply to:\n"
                                      f"{words}\n{LIST}\n"),
            _page(tmp_path, "R1", 20, f"U.S. Notes (con.)\n(u) The rates of duty in heading 9903.80.08 apply to:\n"
                                      f"{words}\n{LIST}\n"),
            _page(tmp_path, "R1", 30, f"U.S. Notes (con.)\n(s) The rates of duty set forth in heading 9903.80.15 "
                                      f"apply to all entries of derivative aluminum products of the United "
                                      f"Kingdom classifiable in the following provisions:\n{words}\n{LIST}\n")]
    b2 = _b2_for(tmp_path, docs)
    tails = {b.physical_page: b for b in b2 if b.raw_text.endswith("3209.10.00;")}
    assert {p: b.applicable_heading for p, b in tails.items()} == {"10": "9903.80.01", "20": "9903.80.08",
                                                                    "30": "9903.80.15"}
    assert tails["30"].country_scope == "United Kingdom" and tails["10"].country_scope == ""
    assert len({b.chunk_id for b in tails.values()}) == 3


def test_page_boundary_needs_the_contiguous_page(tmp_path):
    lead = "U.S. Notes (con.)\n(n) The rates of duty in heading 9903.80.01 apply to:\n" + LIST + "\n"
    cont = "U.S. Notes (con.)\n" + LIST + "\n"
    contiguous = _b2_for(tmp_path / "a", [_page(tmp_path / "a", "R1", 10, lead), _page(tmp_path / "a", "R1", 11, cont)])
    gap = _b2_for(tmp_path / "b", [_page(tmp_path / "b", "R1", 10, lead), _page(tmp_path / "b", "R1", 12, cont)])
    other = _b2_for(tmp_path / "c", [_page(tmp_path / "c", "R1", 10, lead), _page(tmp_path / "c", "R2", 11, cont)])
    page = lambda b2, n: next(b for b in b2 if b.physical_page == n)
    assert page(contiguous, "11").applicable_heading == "9903.80.01"
    assert page(contiguous, "11").context_origin == "previous_page:10"
    assert page(gap, "12").applicable_heading == "" and page(gap, "12").context_origin == "none"
    assert page(other, "11").applicable_heading == ""        # another revision is another source


def test_rate_table_pages_inherit_nothing(tmp_path):
    notes = "U.S. Notes (con.)\n(n) The rates of duty in heading 9903.80.01 apply to:\n" + LIST + "\n"
    table = "Heading/ Subheading Article Description Rates of Duty\nderivative products ....\n1/9903.80.02 +25%\n"
    b2 = _b2_for(tmp_path, [_page(tmp_path, "R1", 10, notes), _page(tmp_path, "R1", 11, table)])
    t = next(b for b in b2 if b.physical_page == "11")
    assert t.applicable_heading == "" and t.subdivision == "" and t.context_origin == "none"


def test_new_note_closes_the_lead_in():
    raw = ("U.S. Notes (con.)\n(n) The rates of duty in heading 9903.80.01 apply to:\n" + LIST + "\n"
           "20. (a) For the purposes of this note, the following terms apply.\n" + LIST + "\n")
    text = normalize(raw)
    events, end = notes_events(raw, text, PageState())
    st_after = state_at(events, text.rindex("0402.99.68"))
    assert st_after.lead_in is None and st_after.note == "20"


def test_page_header_is_skipped_for_the_page_top_chunk(tmp_path):
    prev = "U.S. Notes (con.)\n(j) The rates of duty in heading 9903.80.07 apply to:\n" + LIST + "\n"
    top = "U.S. Notes (con.)\n(k) The rates of duty in heading 9903.80.08 apply to:\n" + LIST + "\n"
    b2 = _b2_for(tmp_path, [_page(tmp_path, "R1", 10, prev), _page(tmp_path, "R1", 11, top)])
    assert next(b for b in b2 if b.physical_page == "11").applicable_heading == "9903.80.08"


def test_v1_review_sheet_is_blind_and_maps_every_b1_unit(b2_v1):
    import csv
    dev = REPO / "evals" / "dev"
    with (dev / "review_b2_v1" / "qrel_review_sheet.csv").open(encoding="utf-8-sig", newline="") as f:
        sheet = list(csv.DictReader(f))
    with (dev / "review" / "qrel_review_sheet.csv").open(encoding="utf-8-sig", newline="") as f:
        b1_units = list(csv.DictReader(f))
    with (dev / "review_b2_v1" / "b2_qrel_candidates.csv").open(encoding="utf-8", newline="") as f:
        cands = list(csv.DictReader(f))
    by_parent = {b.parent_chunk_id: b for b in b2_v1}
    assert len(sheet) == len(b1_units) == len(cands)
    for s, u, c in zip(sheet, b1_units, cands):
        child = by_parent[u["chunk_id"]]
        assert (s["pair_id"], s["chunk_id"], s["raw_text"], s["context_text"]) == \
            (u["pair_id"], child.chunk_id, child.raw_text, child.context_text)
        assert (c["b2_chunk_id"], c["parent_chunk_id"], c["citation_ids"]) == \
            (child.chunk_id, u["chunk_id"], u["citation_ids"])
        assert not s["user_decision"] and "decision" not in c
    for col in sheet[0]:
        assert not any(w in col for w in ("claude", "cited", "rule", "period", "citation"))


# --- v2: v1 kept reproducible, long-range inheritance fixed ------------------------------------------------------

def test_v1_output_is_reproduced_exactly(b2_v1):
    m = json.loads((REPO / "data" / "extracted" / "retrieval_b2" / "b2_heading_v1_manifest.json").read_text("utf-8"))
    h = b2_hashes(b2_v1)
    assert (h["config_sha256"], h["b2_chunks_sha256"]) == (m["config_sha256"], m["b2_chunks_sha256"])


def test_v2_changes_only_cross_page_inheritance(b2, b2_v1):
    v1 = {b.parent_chunk_id: b for b in b2_v1}
    for b in b2:
        a = v1[b.parent_chunk_id]
        assert b.raw_text == a.raw_text
        if a.context_origin in ("same_page", "document_metadata", "none"):
            assert b.context_text == a.context_text, (a.source_id, a.physical_page)


def test_v2_parenthesized_note_number_closes_the_lead_in():
    raw = ("U.S. Notes (con.)\n(gg) For purposes of heading 9903.80.28, the additional duties imposed by heading "
           "9903.80.15 shall not apply to the following products:\n(1) Item one\n"
           "(21)(a) Except as provided in this note, products of the listed countries are subject to duties.\n"
           "(2) Item two\n")
    text = normalize(raw)
    v1_events, _ = notes_events(raw, text, PageState(), "b2_heading_v1")
    v2_events, end = notes_events(raw, text, PageState(), "b2_heading_v2")
    at = text.index("(2) Item two")
    assert state_at(v1_events, at).lead_in is not None            # the v1 error
    assert state_at(v2_events, at).lead_in is None and end.note == "21"


def test_v2_any_later_sibling_closes_but_roman_items_do_not():
    assert later_sibling("gg", "mm") and later_sibling("n", "q") and later_sibling("viii", "xi")
    assert later_sibling("3", "7") and not later_sibling("7", "3")
    assert not later_sibling("o", "v") and not later_sibling("b", "x")      # roman items inside a lettered lead-in
    assert not later_sibling("aa", "ii") and not later_sibling("v", "a")
    raw = ("U.S. Notes (con.)\n(gg) For purposes of heading 9903.80.28, the additional duties imposed by heading "
           "9903.80.15 shall not apply to:\n(1) Item\n(mm) The U.S. Trade Representative determined to establish "
           "a process by which particular products classified in heading 9903.80.02 could be excluded.\n(1) Item\n")
    text = normalize(raw)
    events, _ = notes_events(raw, text, PageState(), "b2_heading_v2")
    assert state_at(events, text.index("(1) Item")).lead_in.headings == ("9903.80.15",)
    assert state_at(events, text.rindex("(1) Item")).lead_in is None
    raw2 = "U.S. Notes (con.)\n(o) The rates of duty in heading 9903.80.30 apply to:\n(i) castings\n(v) forgings\n"
    text2 = normalize(raw2)
    ev2, _ = notes_events(raw2, text2, PageState(), "b2_heading_v2")
    assert state_at(ev2, text2.index("(v) forgings")).lead_in.headings == ("9903.80.30",)


def test_v2_structure_statistics(b2, b2_v1):
    s1, s2 = structure_stats(b2_v1), structure_stats(b2)
    assert s1["max_distance_pages"] == 136 and s1["inherited_chunks"] == 1100      # the recorded v1 error
    assert s2["max_distance_pages"] <= 6 and s2["inherited_chunks"] == 126
    assert s2["chunks_crossing_a_note_boundary"] == 0
    for s in (s1, s2):
        assert s["governed_chunks"] == s["inherited_chunks"] + sum(
            1 for b in (b2 if s is s2 else b2_v1) if b.context_origin == "same_page")
        assert 0 <= s["unknown_context_ratio_of_chapter99"] <= 1
        assert 0 <= s["duty_family_unknown_ratio_of_governed"] <= 1
    for b in b2:
        if b.context_origin.startswith("previous_page"):
            assert 0 < int(b.physical_page) - b.fields["_lead_in_page"] <= s2["max_distance_pages"]


def test_v2_manifest_statistics_match(b2):
    path = REPO / "data" / "extracted" / "retrieval_b2" / "b2_heading_v2_manifest.json"
    if not path.exists():
        pytest.skip("run_005 not written yet")
    m = json.loads(path.read_text("utf-8"))
    assert m["structure_stats"] == json.loads(json.dumps(structure_stats(b2)))
    assert m["b2_chunks_sha256"] == b2_hashes(b2)["b2_chunks_sha256"]
