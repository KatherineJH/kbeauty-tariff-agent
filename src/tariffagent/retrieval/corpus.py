"""Deterministic retrieval corpus: every committed normalized document, cut into fixed word windows.

Documents (all committed, no network):
  fr:<number>                 data/extracted/fr_text/<number>.txt
  csms:<number>               data/extracted/cbp_csms/<number>.txt
  hts22:<pdf stem>            data/extracted/hts_pdf/<stem>/page_NNNN.txt       (one document per page)
  hts22:<export stem>         data/raw/hts/export_*.json                        (decoded JSON text)
  htsarch:<release>           data/extracted/hts_archive_evidence/<release>/page_NNNN.txt (one per page)
  htsarch:<release>:change_record   data/extracted/hts_archive/<release>/change_record.txt

The corpus never reads warehouse/seeds/rule_citations.csv: relevance is attached only at evaluation time.

Normalization: Unicode NFC, line endings LF, then the same whitespace collapse as the citation verifier
(tariffagent.answer.citations.normalize), so chunk offsets and citation quotes live in one text.
Chunks: windows of CHUNK_WORDS words with OVERLAP_WORDS words of overlap (stride CHUNK_WORDS - OVERLAP_WORDS);
start / end are character offsets in the normalized document text.
chunk_id = first 16 hex of SHA-256 over "source_id|page|start|end|text".
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from tariffagent.answer.citations import file_text

REPO = Path(__file__).resolve().parents[3]
CHUNK_WORDS = 120
OVERLAP_WORDS = 30


@dataclass(frozen=True)
class Document:
    source_id: str
    source_file: str        # repository-relative path
    physical_page: str      # '' when the file is not a page
    printed_page: str
    text: str               # normalized


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    source_file: str
    physical_page: str
    printed_page: str
    start: int
    end: int
    text: str


def _norm(path: Path) -> str:
    text = unicodedata.normalize("NFC", file_text(path))
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _page_doc(source_id: str, path: Path, root: Path) -> Document:
    text = _norm(path)
    m = re.fullmatch(r"page_(\d{4})\.txt", path.name)
    label = re.search(r"99 - ([IVX]+) - (\d+)", text)
    return Document(source_id, path.relative_to(root).as_posix(), str(int(m.group(1))) if m else "",
                    f"99-{label.group(1)}-{label.group(2)}" if (m and label) else "", text)


def documents(root: Path = REPO) -> list[Document]:
    ex = root / "data" / "extracted"
    docs: list[Document] = []
    for p in sorted((ex / "fr_text").glob("*.txt")):
        docs.append(Document(f"fr:{p.stem}", p.relative_to(root).as_posix(), "", "", _norm(p)))
    for p in sorted((ex / "cbp_csms").glob("*.txt")):
        docs.append(Document(f"csms:{p.stem}", p.relative_to(root).as_posix(), "", "", _norm(p)))
    for stem_dir in sorted(p for p in (ex / "hts_pdf").iterdir() if p.is_dir()):
        for p in sorted(stem_dir.glob("page_*.txt")):
            docs.append(_page_doc(f"hts22:{stem_dir.name}", p, root))
    for p in sorted((root / "data" / "raw" / "hts").glob("export_*.json")):
        docs.append(Document(f"hts22:{p.stem}", p.relative_to(root).as_posix(), "", "", _norm(p)))
    for rel_dir in sorted(p for p in (ex / "hts_archive_evidence").iterdir() if p.is_dir()):
        for p in sorted(rel_dir.glob("page_*.txt")):
            docs.append(_page_doc(f"htsarch:{rel_dir.name}", p, root))
    for rel_dir in sorted(p for p in (ex / "hts_archive").iterdir() if p.is_dir()):
        cr = rel_dir / "change_record.txt"
        if cr.exists():
            docs.append(Document(f"htsarch:{rel_dir.name}:change_record", cr.relative_to(root).as_posix(), "", "",
                                 _norm(cr)))
    return docs


def chunk_document(d: Document) -> list[Chunk]:
    words = list(re.finditer(r"\S+", d.text))
    if not words:
        return []
    out, stride = [], CHUNK_WORDS - OVERLAP_WORDS
    for i in range(0, len(words), stride):
        window = words[i:i + CHUNK_WORDS]
        start, end = window[0].start(), window[-1].end()
        text = d.text[start:end]
        cid = hashlib.sha256(f"{d.source_id}|{d.physical_page}|{start}|{end}|{text}".encode("utf-8")).hexdigest()[:16]
        out.append(Chunk(cid, d.source_id, d.source_file, d.physical_page, d.printed_page, start, end, text))
        if i + CHUNK_WORDS >= len(words):
            break
    return out


def build_chunks(root: Path = REPO) -> list[Chunk]:
    chunks = [c for d in documents(root) for c in chunk_document(d)]
    return sorted(chunks, key=lambda c: c.chunk_id)


def logical_hash(items) -> str:
    h = hashlib.sha256()
    for it in items:
        h.update(json.dumps(it, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


CHUNK_CONFIG = {
    "unit": "whitespace-delimited word of the normalized page text",
    "chunk_words": CHUNK_WORDS,
    "overlap_words": OVERLAP_WORDS,
    "chunk_id": "sha256(source_id|physical_page|start|end|text)[:16]",
    "pages": "one document per page; chunks never cross pages",
}


def chunk_config_hash() -> str:
    """Hash of the chunking rule, recorded next to the qrels so a changed rule is detected."""
    return logical_hash([CHUNK_CONFIG])


def corpus_hashes(docs: list[Document], chunks: list[Chunk]) -> dict:
    return {
        "chunk_config_sha256": chunk_config_hash(),
        "documents": len(docs),
        "documents_sha256": logical_hash([[d.source_id, d.source_file, d.physical_page, d.printed_page,
                                           hashlib.sha256(d.text.encode("utf-8")).hexdigest()] for d in docs]),
        "chunks": len(chunks),
        "chunks_sha256": logical_hash([[c.chunk_id, c.source_id, c.source_file, c.physical_page, c.start, c.end]
                                       for c in chunks]),
        "chunk_words": CHUNK_WORDS,
        "overlap_words": OVERLAP_WORDS,
    }
