"""BM25 baseline: fixed tokenizer, fixed parameters, deterministic ranking. No stemming, synonyms or translation.

Tokenizer (applied to lower-cased text, in this order; everything else is a separator):
  1. HTS codes kept whole:            9903.85.08, 3304.99.50, 3304.99.5000, 9903.01.43-9903.01.62 -> two codes;
                                      codes printed back to back (0201.20.040201.20.02) split as in the PDF lists
  2. dates in ISO form kept whole:    2026-02-24
  3. legal subdivision references:    2(aa)(v), 1321(b), 3(a)
  4. dotted abbreviations:            u.s.c., u.s.
  5. numbers with decimals / percent: 12.5, 15%, 12:01
  6. latin words / numbers:           eo, 14389, section, ieepa
  7. Hangul runs (no morphological analysis): 관세, 과징금은
Parameters: k1 = 1.2, b = 0.75 (Robertson / Lucene defaults); idf = ln(1 + (N - df + 0.5) / (df + 0.5)).
Ties are broken by chunk_id ascending. A query with no matching term returns no results.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from tariffagent.retrieval.corpus import Chunk, logical_hash

K1, B = 1.2, 0.75
TOKEN = re.compile(
    r"\d{4}\.\d{2}\.\d{2}(?:\d{2})?(?=\d{4}\.\d{2}|\D|$)"   # HTS codes (also when printed without separators)
    r"|\d{4}-\d{2}-\d{2}"                       # ISO dates
    r"|\d+(?:\([a-z0-9]+\))+"                   # legal subdivision references
    r"|(?:[a-z]\.){2,}"                         # dotted abbreviations
    r"|\d+(?:[.:]\d+)+%?|\d+%"                  # decimals, times, percents
    r"|[a-z0-9]+"                               # words and numbers
    r"|[가-힣]+"                        # Hangul syllable runs
)


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


@dataclass(frozen=True)
class Hit:
    rank: int
    chunk: Chunk
    score: float


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = sorted(chunks, key=lambda c: c.chunk_id)
        self.tf: list[Counter] = [Counter(tokenize(c.text)) for c in self.chunks]
        self.lengths = [sum(t.values()) for t in self.tf]
        self.avgdl = sum(self.lengths) / len(self.lengths)
        df: Counter = Counter()
        for t in self.tf:
            df.update(t.keys())
        n = len(self.chunks)
        self.idf = {term: math.log(1 + (n - d + 0.5) / (d + 0.5)) for term, d in df.items()}
        self.postings: dict[str, list[int]] = {}
        for i, t in enumerate(self.tf):
            for term in t:
                self.postings.setdefault(term, []).append(i)

    def search(self, query: str, k: int = 10) -> list[Hit]:
        scores: dict[int, float] = {}
        for term in tokenize(query):
            if term not in self.idf:
                continue
            idf = self.idf[term]
            for i in self.postings[term]:
                f = self.tf[i][term]
                denom = f + K1 * (1 - B + B * self.lengths[i] / self.avgdl)
                scores[i] = scores.get(i, 0.0) + idf * f * (K1 + 1) / denom
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], self.chunks[kv[0]].chunk_id))[:k]
        return [Hit(r + 1, self.chunks[i], s) for r, (i, s) in enumerate(ranked)]

    def logical_hash(self) -> str:
        return logical_hash([[term, round(self.idf[term], 12), [self.chunks[i].chunk_id for i in self.postings[term]]]
                             for term in sorted(self.postings)])
