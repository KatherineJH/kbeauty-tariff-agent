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
from tariffagent.retrieval.evaluate import (citation_qrels, gold_chunks, pair_qrels, retrieval_qrels, summarize,
                                            summarize_unanswerable, time_conditions)
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
    with path.open(encoding="utf-8-sig", newline="") as f:
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


def _load_script(name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_review_sheet_is_blind_and_states_the_criterion():
    mod = _load_script("make_qrel_review_sheet")
    sheet = _csv(DEV / "review" / "qrel_review_sheet.csv")
    built, times = mod.build()
    assert [(r["pair_id"], r["chunk_id"]) for r in sheet] == [(r["pair_id"], r["chunk_id"]) for r in built]
    assert len({(r["pair_id"], r["chunk_id"]) for r in sheet}) == len(sheet)
    # every candidate location of every answerable pair is covered, cited locations included and not marked
    assert {c for r in sheet for c in r["citation_ids"].split(";")} ==         {c for q in _csv(DEV / "queries.csv") for c in q["relevant_citation_ids"].split(";") if c}
    for col in sheet[0]:
        assert not any(w in col for w in ("claude", "cited", "rule", "period", "decision_v1", "reason_code"))
    md = (DEV / "review" / "qrel_review_sheet.md").read_text("utf-8")
    assert "only from the conditions stated in the query" in md and "underspecified" in md
    assert {r["query_id"] for r in _csv(DEV / "review" / "query_time_sheet.csv")} ==         {q["query_id"] for q in _csv(DEV / "queries.csv") if q["relevant_citation_ids"]}


def _fill(tmp_path: Path, decide, kind="human", second=None) -> object:
    mod = _load_script("finalize_qrel_review")
    sheet = _csv(DEV / "review" / "qrel_review_sheet.csv")
    for i, r in enumerate(sheet):
        r["user_decision"], r["user_reason"], r["reviewer_type"] = decide(i), "test", kind
    times = _csv(DEV / "review" / "query_time_sheet.csv")
    for i, r in enumerate(times):
        r["time_condition"], r["reason"] = ("underspecified" if i == 0 else "time_invariant"), "test"
    review = tmp_path / "review"
    review.mkdir()
    for name, rows in (("qrel_review_sheet.csv", sheet), ("query_time_sheet.csv", times)):
        with (review / name).open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    if second:
        with (review / "claude_review.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["unit_id", "decision", "reason"], lineterminator="\n")
            w.writeheader()
            w.writerows({"unit_id": r["unit_id"], "decision": second(i), "reason": "x"} for i, r in enumerate(sheet))
    for name, path in (("REVIEW", review), ("SHEET", review / "qrel_review_sheet.csv"),
                       ("TIME_SHEET", review / "query_time_sheet.csv"), ("SECOND", review / "claude_review.csv"),
                       ("V2", tmp_path / "v2.csv"), ("CONDITIONS", tmp_path / "times.csv"),
                       ("PAIRS", tmp_path / "pairs.csv")):
        setattr(mod, name, path)
    return mod


def test_finalize_reports_agreement_and_writes_v2(tmp_path):
    n = len(_csv(DEV / "review" / "qrel_review_sheet.csv"))
    user = lambda i: "uncertain" if i == 0 else ("relevant" if i % 2 else "not_relevant")
    claude = lambda i: "relevant" if i in (0, 2) or i % 2 else "not_relevant"
    mod = _fill(tmp_path, user, second=claude)
    mod.main()
    report = (tmp_path / "review" / "agreement.md").read_text("utf-8")
    assert f"{n - 2}/{n}" in report and f"{n - 2}/{n - 1}" in report and "human" in report
    assert len(_csv(tmp_path / "review" / "disagreements.csv")) == 2
    v2 = _csv(tmp_path / "v2.csv")
    assert len(v2) == n and sum(r["decision"] == "uncertain" for r in v2) == 1
    with pytest.raises(SystemExit):
        mod.main()   # never overwrites v2


def test_finalize_refuses_blank_and_labels_model_review(tmp_path):
    mod = _fill(tmp_path, lambda i: "" if i == 3 else "relevant")
    with pytest.raises(SystemExit):
        mod.main()
    (tmp_path / "m").mkdir()
    mod = _fill(tmp_path / "m", lambda i: "relevant", kind="second_model_review")
    mod.main()
    assert "a model, not a human review" in (tmp_path / "m" / "review" / "agreement.md").read_text("utf-8")


def test_v2_uncertain_is_kept_but_not_relevant_and_underspecified_is_apart(chunks, tmp_path, index):
    mod = _fill(tmp_path, lambda i: "uncertain" if i == 0 else "relevant")
    mod.main()
    by_pair = pair_qrels(tmp_path / "v2.csv")
    first = _csv(tmp_path / "v2.csv")[0]
    assert all(first["chunk_id"] not in by_pair.get(first["pair_id"], {}).get(c, set())
               for c in first["citation_ids"].split(";"))
    conditions = time_conditions(tmp_path / "times.csv")
    _, pq = evaluate_retrieval(index.search, chunks, by_pair=by_pair, conditions=conditions)
    main_rows = {r["group"]: r for r in summarize(pq)}
    under = {r["group"]: r for r in summarize(pq, underspecified=True)}
    assert under["all"]["queries"] == 1 and main_rows["all"]["queries"] == 23


def test_claude_sealed_reading_is_unchanged():
    import hashlib
    readme = (DEV / "README.md").read_text("utf-8")
    for name in ("claude_review.csv", "claude_time_review.csv"):
        recorded = re.search(rf"`review/{re.escape(name)}` \| `([0-9a-f]{{64}})`", readme).group(1)
        assert hashlib.sha256((DEV / "review" / name).read_bytes()).hexdigest() == recorded
    units = {r["unit_id"] for r in _csv(DEV / "review" / "qrel_review_sheet.csv")}
    assert {r["unit_id"] for r in _csv(DEV / "review" / "claude_review.csv")} == units


def test_paired_language_rows_use_only_matched_pairs():
    rows = []
    for pid, recall in (("p1", (1.0, 0.0)), ("p2", (1.0, 1.0)), ("p3", (0.0, 1.0))):
        for lang, r in zip(("en", "ko"), recall):
            rows.append({"query_id": f"{pid}_{lang}", "pair_id": pid, "lang": lang, "answerable": 1,
                         "underspecified": 0, "relevant_citations": 1, "unreachable_citations": 0, "zero": 0,
                         "found@5": int(r), "found@10": int(r), "recall@5": r, "recall@10": r, "mrr@10": r,
                         "ndcg@10": r, "top_score": 1.0})
    rows[5]["underspecified"] = 1          # p3_ko is outside the main set, so p3 cannot be paired there
    out = {r["group"]: r for r in summarize(rows, matched_pairs={"p1", "p3"})}
    assert out["en"]["queries"] == 3 and out["ko"]["queries"] == 2        # mismatched p2 stays in en / ko
    assert out["en_paired"]["queries"] == 1 and out["ko_paired"]["queries"] == 1   # only p1
    assert out["gap_en_minus_ko"]["macro_recall@10"] == "1.0000"
    assert "en_paired" not in {r["group"] for r in summarize(rows)}


def test_fixed_dev_qrels_v2_are_unchanged():
    import hashlib
    readme = (DEV / "README.md").read_text("utf-8")
    for name in ("retrieval_qrels_v2.csv", "query_time_conditions.csv", "query_pair_checks.csv", "queries.csv"):
        recorded = re.search(rf"\| `{re.escape(name)}` \| `([0-9a-f]{{64}})`", readme).group(1)
        assert hashlib.sha256((DEV / name).read_bytes()).hexdigest() == recorded, name
