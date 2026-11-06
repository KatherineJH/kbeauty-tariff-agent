"""BM25 baseline: deterministic chunks and index, no leakage of the gold citations, tie order, token rules,
retrieval never changing a cited answer, qrel integrity and the metric definitions."""

import ast
import csv
import re
import sys
import dataclasses
import json
import math
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path

import pytest

import tariffagent.retrieval.corpus as corpus_mod
from tariffagent.answer import compose, load_verified
from tariffagent.retrieval.bm25 import BM25Index, tokenize
from tariffagent.retrieval.corpus import REPO, Chunk, build_chunks, corpus_hashes, documents
from tariffagent.retrieval.bm25 import Hit
from tariffagent.retrieval.evaluate import (citation_qrels, gold_chunks, retrieval_qrels, summarize,
                                            summarize_unanswerable)
from tariffagent.retrieval.evaluate import evaluate as evaluate_retrieval
from tariffagent.rules import EntryInput, evaluate, load_rules

MANIFEST = json.loads((REPO / "data" / "extracted" / "retrieval" / "bm25_manifest.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def chunks():
    return build_chunks()


@pytest.fixture(scope="module")
def index(chunks):
    return BM25Index(chunks)


def test_chunks_are_deterministic_and_match_the_manifest(chunks):
    again = build_chunks()
    assert [c.chunk_id for c in again] == [c.chunk_id for c in chunks]
    h = corpus_hashes(documents(), chunks)
    for key in ("documents", "documents_sha256", "chunks", "chunks_sha256", "chunk_words", "overlap_words",
                "chunk_config_sha256"):
        assert h[key] == MANIFEST[key], key


def test_index_rebuild_is_identical(index):
    assert index.logical_hash() == MANIFEST["index_sha256"]
    assert len(index.idf) == MANIFEST["index_terms"]


def _code_without_docstrings(path: Path) -> str:
    tree = ast.parse(path.read_text("utf-8"))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        first = body[0] if isinstance(body, list) and body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            body.pop(0)
    return ast.unparse(tree)


def test_corpus_does_not_read_the_gold_citations(chunks, monkeypatch, tmp_path):
    for mod in ("corpus.py", "bm25.py"):
        code = _code_without_docstrings(REPO / "src" / "tariffagent" / "retrieval" / mod)
        assert "rule_citations" not in code and "CITATIONS" not in code
    # pointing the citation seed somewhere empty does not change the corpus
    import tariffagent.answer.citations as cit
    monkeypatch.setattr(cit, "CITATIONS", tmp_path / "missing.csv")
    monkeypatch.setattr(cit, "SEEDS", tmp_path)
    assert corpus_hashes(documents(), build_chunks())["chunks_sha256"] == MANIFEST["chunks_sha256"]
    # the corpus is the whole committed document set, not the cited excerpts
    gold = gold_chunks(chunks)
    gold_ids = set().union(*gold.values())
    assert len(chunks) > 50 * len(gold_ids)
    assert {c.source_id for c in chunks if c.chunk_id in gold_ids} < {c.source_id for c in chunks}


def test_ties_are_broken_by_chunk_id():
    same = "heading 9903.85.08 aluminum content"
    c = [Chunk(cid, "x", "x", "", "", 0, len(same), same) for cid in ("bbbb", "aaaa", "cccc")]
    c.append(Chunk("dddd", "x", "x", "", "", 0, 5, "other words entirely"))
    hits = BM25Index(c).search("9903.85.08 aluminum", 10)
    assert [h.chunk.chunk_id for h in hits] == ["aaaa", "bbbb", "cccc"]
    assert len({h.score for h in hits}) == 1


@pytest.mark.parametrize("text, must_contain", [
    ("heading 9903.85.08", ["9903.85.08"]),
    ("subheading 3304.99.50 and line 3304.99.5000", ["3304.99.50", "3304.99.5000"]),
    ("EO 14389", ["eo", "14389"]),
    ("on 2026-02-24", ["2026-02-24"]),
    ("19 U.S.C. 1321(b) and note 2(aa)(v)", ["u.s.c.", "1321(b)", "2(aa)(v)"]),
    ("12:01 a.m., 12.5 percent, 15%", ["12:01", "12.5", "15%"]),
    ("0201.20.040201.20.02", ["0201.20.04", "0201.20.02"]),
    ("과징금 세율", ["과징금", "세율"]),
])
def test_codes_dates_and_sections_are_single_tokens(text, must_contain):
    toks = tokenize(text)
    for t in must_contain:
        assert t in toks, (t, toks)


def test_no_matching_term_returns_no_result(index):
    assert index.search("zzzzqqq 없는단어", 10) == []


def test_retrieval_does_not_change_the_cited_answer(built_warehouse, index):
    rs = load_rules(built_warehouse[0])
    cites = load_verified()
    e = EntryInput(datetime.fromisoformat("2026-03-10T12:00-05:00"), "KR", "3304.99.1000", D("1000"), "VESSEL")
    hits = index.search("section 122 surcharge cosmetics exempt 50 percent", 5)
    context = [{"source": h.chunk.chunk_id, "text": h.chunk.text} for h in hits]
    a, b = compose(evaluate(rs, e), rs, cites), compose(evaluate(rs, e), rs, cites, context)
    strip = lambda x: {k: v for k, v in dataclasses.asdict(x).items() if k != "background"}
    assert strip(a) == strip(b) and len(b.background) == len(hits)


DEV = REPO / "evals" / "dev"


def _csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_chunk_ids_are_unique_16_hex(chunks):
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[0-9a-f]{16}", i) for i in ids)


def test_qrels_were_reviewed_on_this_corpus(chunks):
    meta = json.loads((DEV / "qrels_meta.json").read_text("utf-8"))
    h = corpus_hashes(documents(), chunks)
    for key in ("documents_sha256", "chunks_sha256", "chunk_config_sha256"):
        assert meta[key] == h[key], f"{key}: corpus changed, list and review the qrel candidates again"


def test_every_candidate_has_exactly_one_reviewed_decision():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        from list_qrel_candidates import candidates
    finally:
        sys.path.pop(0)
    listed = candidates()
    committed = _csv(DEV / "retrieval_qrel_candidates.csv")
    key = lambda r: (r["citation_id"], r["source_file"])
    assert [key(r) for r in listed] == [key(r) for r in committed]
    decisions = _csv(DEV / "retrieval_qrels.csv")
    keys = [(r["citation_id"], r["source_file"]) for r in decisions]
    assert len(keys) == len(set(keys))
    assert set(keys) == {(r["citation_id"], r["source_file"]) for r in committed}
    cited = {(r["citation_id"], r["source_file"]) for r in committed if r["is_cited_location"] == "1"}
    for r in decisions:
        assert r["decision"] in ("accept", "reject") and r["reason_code"] and r["reason"] and r["reviewer"]
        if (r["citation_id"], r["source_file"]) in cited:
            assert (r["decision"], r["reason_code"]) == ("accept", "cited_location")
        else:
            assert r["reason_code"] != "cited_location"


def test_uk_and_other_scope_rows_are_rejected():
    for r in _csv(DEV / "retrieval_qrels.csv"):
        if r["reason_code"] in ("uk_scope", "aluminum_heading_not_steel", "ieepa_stacking_not_surcharge",
                                "before_rule_period"):
            assert r["decision"] == "reject"


def test_retrieval_qrels_extend_citation_qrels(chunks):
    strict, broad = citation_qrels(chunks), retrieval_qrels(chunks)
    assert strict.keys() == broad.keys()
    assert all(strict[c] <= broad[c] for c in strict)
    assert any(strict[c] < broad[c] for c in strict)


def _chunk(cid: str) -> Chunk:
    return Chunk(cid, "s", "f", 1, "1", 0, 1, "t")


def _queries(tmp_path: Path, rows: list[tuple]) -> Path:
    p = tmp_path / "q.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["query_id", "lang", "pair_id", "text", "relevant_citation_ids", "author_note"])
        w.writerows(rows)
    return p


def test_recall_denominator_is_distinct_citations_not_chunks(tmp_path):
    # citation A has three relevant chunks, all ranked; citation B has one, not ranked; A listed twice
    qrels = {"A": {"a1", "a2", "a3"}, "B": {"b1"}}
    ranked = ["a1", "a2", "a3", "x1"]
    search = lambda text, k: [Hit(i + 1, _chunk(c), 1.0 / (i + 1)) for i, c in enumerate(ranked[:k])]
    q = _queries(tmp_path, [("q1", "en", "p1", "t", "A;B;A", "")])
    _, per_query = evaluate_retrieval(search, [], qrels, q)
    r = per_query[0]
    assert r["relevant_citations"] == 2 and r["found@10"] == 1 and r["recall@10"] == 0.5
    assert r["mrr@10"] == 1.0
    # one gain (first hit of A) at rank 1; ideal has two gains
    assert abs(r["ndcg@10"] - 1 / (1 + 1 / math.log2(3))) < 1e-12


def test_macro_and_micro_recall_differ_and_unanswerable_is_separate(tmp_path):
    qrels = {"A": {"a1"}, "B": {"b1"}, "C": {"c1"}}
    ranked = {"t1": ["a1"], "t2": ["x1"], "t3": [], "t4": ["x1"]}
    search = lambda text, k: [Hit(i + 1, _chunk(c), 1.0) for i, c in enumerate(ranked[text][:k])]
    q = _queries(tmp_path, [("q1", "en", "p1", "t1", "A", ""),       # 1/1
                            ("q2", "en", "p2", "t2", "B;C", ""),     # 0/2
                            ("q3", "en", "p3", "t3", "", "none"),    # unanswerable, empty result
                            ("q4", "ko", "p3", "t4", "", "none")])   # unanswerable, something returned
    _, per_query = evaluate_retrieval(search, [], qrels, q)
    m = {r["group"]: r for r in summarize(per_query)}["en"]
    assert m["queries"] == 2 and m["relevant_citations"] == 3
    assert m["macro_recall@10"] == "0.5000" and m["micro_recall@10"] == "0.3333"
    assert m["zero_result_rate"] == "0.0000"   # the empty unanswerable query is not counted here
    u = {r["group"]: r for r in summarize_unanswerable(per_query)}
    assert u["all"]["queries"] == 2 and u["all"]["empty_result_rate"] == "0.5000"
    assert u["en"]["mean_top_score_when_returned"] == "" and u["ko"]["mean_top_score_when_returned"] == "1.0000"


def test_dev_queries_are_append_only_after_run_001():
    import hashlib
    rows = (DEV / "queries.csv").read_bytes().split(b"\n")
    recorded = (REPO / "reports" / "retrieval" / "run_001_strict_citation_qrels" / "inputs.sha256").read_text()
    want = next(line.split()[0] for line in recorded.splitlines() if line.endswith("evals/dev/queries.csv"))
    # the first 25 lines (header + 24 queries, with trailing newline) are byte-identical to run_001's input
    assert hashlib.sha256(b"\n".join(rows[:25]) + b"\n").hexdigest() == want
