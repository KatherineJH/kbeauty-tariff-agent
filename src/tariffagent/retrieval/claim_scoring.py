"""Claim-based scoring for reviewed retrieval units (defined before any reviewed metric is computed).

Separate from the citation metrics of evaluate.py (recall@k, mrr@10, ndcg@10 over cited locations): every name here
is a claim metric, so the two are never mixed in one table.

Inputs
  claims      evals/dev/claims.csv: per query, the claims its answer needs, each tied to exact official sentences in
              evals/dev/claim_evidence.csv; required = true / false
  judgements  per unit: decision relevant / not_relevant / uncertain, supports_claim_ids (claims of the query),
              support_level complete / partial
              - relevant  => supports_claim_ids not empty, support_level complete or partial
              - otherwise => supports_claim_ids empty, support_level empty
              one unit may support several claims; not_relevant, uncertain and unjudged units give nothing
  ranking     per query, the system's units in rank order
  pool        per query, every judged unit of that system (its own top 10, quote-overlap candidates, cited locations)

Per query, R = its required claims, k in (5, 10); "complete" = relevant with support_level complete.
Primary (the only measures used to compare B1 and B2):
  claim_recall@k              |claims of R completely supported by a unit ranked <= k| / |R|
  all_claims_covered@k        1 if every claim of R is completely supported within the top k, else 0
  mrr_any_complete_claim@10   1 / rank of the first unit completely supporting a claim of R (0 if none)
  mrr_all_claims_complete@10  1 / the rank at which every claim of R is completely supported (0 if not by 10)
  unreachable_claims          claims of R that no unit of the system's judged pool completely supports
Secondary:
  partial_claim_recall@k      |claims of R supported completely or partly within the top k| / |R|
Diagnostic only (not comparable across systems):
  system_relative_ndcg@10     nDCG with a fixed grade per unit (2 = relevant and completely supports a claim of R,
                              1 = other relevant, 0 = not relevant / uncertain / unjudged), gain 2^grade - 1,
                              discount log2(rank + 1); IDCG from this system's own judged pool, so B1 and B2 values
                              are on different scales. No B1/B2 conclusion is drawn from it without a common IDCG.
  claim_novelty_dcg@10        a rank gains 1 when its unit completes a claim of R not completed above it,
                              normalized by min(|R|, 10) gains at the top (not nDCG)
  unjudged@10, uncertain@10   counts in the top 10
Groups (summarize_claims): answerable queries, underspecified apart, en / ko, paired rows and the en - ko gap over
matched pairs only. Macro = mean over queries; claim_recall also micro (credited / required claims, pooled).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

DECISIONS = ("relevant", "not_relevant", "uncertain")
LEVELS = ("complete", "partial")
PRIMARY = ("claim_recall@5", "claim_recall@10", "all_claims_covered@5", "all_claims_covered@10",
           "mrr_any_complete_claim@10", "mrr_all_claims_complete@10")
SECONDARY = ("partial_claim_recall@5", "partial_claim_recall@10")
DIAGNOSTIC = ("system_relative_ndcg@10", "claim_novelty_dcg@10")


@dataclass(frozen=True)
class Judgement:
    decision: str
    supports: frozenset[str]
    level: str

    def validate(self, query_claims: set[str]) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"decision {self.decision!r}")
        if self.decision == "relevant":
            if not self.supports or self.level not in LEVELS:
                raise ValueError("a relevant unit needs supports_claim_ids and support_level")
            if not self.supports <= query_claims:
                raise ValueError(f"claims {sorted(self.supports - query_claims)} are not claims of this query")
        elif self.supports or self.level:
            raise ValueError("only a relevant unit supports claims")


def grade(j: Judgement | None, required: set[str]) -> int:
    if not j or j.decision != "relevant":
        return 0
    return 2 if j.level == "complete" and j.supports & required else 1


def _dcg(grades: list[int]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades[:10]))


def score_query(required: set[str], all_claims: set[str], ranking: list[str],
                judged: dict[str, Judgement], pool: set[str], k_values=(5, 10)) -> dict:
    for j in judged.values():
        j.validate(all_claims)

    def complete(u):
        j = judged.get(u)
        return (j.supports & required) if j and j.decision == "relevant" and j.level == "complete" else set()

    def anysup(u):
        j = judged.get(u)
        return (j.supports & required) if j and j.decision == "relevant" else set()

    n = len(required)
    row: dict = {"required_claims": n}
    for k in k_values:
        comp = set().union(*(complete(u) for u in ranking[:k]))
        anyl = set().union(*(anysup(u) for u in ranking[:k]))
        row[f"credited_claims@{k}"] = len(comp)
        row[f"claim_recall@{k}"] = len(comp) / n if n else 0.0
        row[f"all_claims_covered@{k}"] = int(n > 0 and comp >= required)
        row[f"partial_claim_recall@{k}"] = len(anyl) / n if n else 0.0
    first_any = next((i for i, u in enumerate(ranking[:10], 1) if complete(u)), None)
    done, first_all, gains = set(), None, []
    for i, u in enumerate(ranking[:10], 1):
        new = complete(u) - done
        done |= new
        gains.append(1 if new else 0)
        if first_all is None and n and done >= required:
            first_all = i
    row["mrr_any_complete_claim@10"] = 1 / first_any if first_any else 0.0
    row["mrr_all_claims_complete@10"] = 1 / first_all if first_all else 0.0
    ideal = _dcg(sorted((grade(judged.get(u), required) for u in pool), reverse=True))
    row["system_relative_ndcg@10"] = (_dcg([grade(judged.get(u), required) for u in ranking[:10]]) / ideal
                                      if ideal else 0.0)
    nov_ideal = sum(1 / math.log2(i + 2) for i in range(min(n, 10)))
    row["claim_novelty_dcg@10"] = (sum(g / math.log2(i + 2) for i, g in enumerate(gains)) / nov_ideal
                                   if nov_ideal else 0.0)
    row["unjudged@10"] = sum(1 for u in ranking[:10] if u not in judged)
    row["uncertain@10"] = sum(1 for u in ranking[:10] if u in judged and judged[u].decision == "uncertain")
    row["unreachable_claims"] = len(required - set().union(*(complete(u) for u in pool)))
    row["empty_result"] = int(not ranking)
    return row


def summarize_claims(per_query: list[dict], underspecified: bool = False,
                     matched_pairs: set[str] | None = None) -> list[dict]:
    """per_query rows: score_query output plus query_id, pair_id, lang, underspecified (0/1)."""
    base = [r for r in per_query if r["required_claims"] and bool(r.get("underspecified")) == underspecified]
    groups = [("all", base), ("en", [r for r in base if r["lang"] == "en"]),
              ("ko", [r for r in base if r["lang"] == "ko"])]
    if matched_pairs is not None:
        langs: dict[str, set] = {}
        for r in base:
            langs.setdefault(r["pair_id"], set()).add(r["lang"])
        both = {p for p, ls in langs.items() if p in matched_pairs and ls >= {"en", "ko"}}
        groups += [(f"{lang}_paired", [r for r in base if r["pair_id"] in both and r["lang"] == lang])
                   for lang in ("en", "ko")]
    out = []
    for group, rows in groups:
        if not rows:
            continue
        n_req = sum(r["required_claims"] for r in rows)
        row = {"group": group, "queries": len(rows), "required_claims": n_req,
               "unreachable_claims": sum(r["unreachable_claims"] for r in rows)}
        for m in PRIMARY + SECONDARY + DIAGNOSTIC:
            row[f"macro_{m}"] = round(sum(r[m] for r in rows) / len(rows), 4)
        for k in (5, 10):
            row[f"micro_claim_recall@{k}"] = round(sum(r[f"credited_claims@{k}"] for r in rows) / n_req, 4)
        row["uncertain@10"] = sum(r["uncertain@10"] for r in rows)
        row["unjudged@10"] = sum(r["unjudged@10"] for r in rows)
        out.append(row)
    paired = {r["group"]: r for r in out if r["group"].endswith("_paired")}
    if len(paired) == 2:
        en, ko = paired["en_paired"], paired["ko_paired"]
        out.append({"group": "gap_en_minus_ko", "queries": en["queries"],
                    **{f"macro_{m}": round(en[f"macro_{m}"] - ko[f"macro_{m}"], 4) for m in PRIMARY}})
    return out
