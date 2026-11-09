"""Claim-based scoring for reviewed retrieval units (defined before any reviewed metric is computed).

Separate from the citation metrics of evaluate.py (recall@k, mrr@10, ndcg@10 over cited locations): every name here
is a claim metric, so the two are never mixed in one table.

Inputs
  claims       evals/dev/claims.csv: per query, the claims its answer needs; required = true / false
  components   evals/dev/claim_components.csv: each claim has one or more evidence components, each tied to one exact
               official sentence (evals/dev/claim_evidence.csv). A claim with several components is composite
               (dq10 c1: the proclamation imposes a surcharge + heading 9903.03.01 was added by it)
  judgements   per unit: decision relevant / not_relevant / uncertain, and per (unit, component of the query's
               claims) a support level complete / partial / none. Components the reviewer did not mark count as none.
               - relevant      => at least one component complete or partial
               - not_relevant  => every component none
               - uncertain     => every component none
  ranking      per query, the system's units in rank order
  pool         per query, every judged unit of that system (its own top 10, quote-overlap candidates, cited locations)

Completing a claim: components may come from different units. A claim is complete at rank r when every one of its
components has a complete support from some relevant unit ranked <= r (the top-r union). It is partly supported at r
when at least one of its components has a complete or partial support within the top r. A single-component claim is
therefore complete exactly when one unit supports it completely.

Per query, R = its required claims, k in (5, 10).
Primary (the only measures used to compare B1 and B2):
  claim_recall@k              |claims of R complete at rank k| / |R|
  all_claims_covered@k        1 if every claim of R is complete at rank k, else 0
  mrr_any_complete_claim@10   1 / the first rank at which some claim of R is complete (0 if none by 10)
  mrr_all_claims_complete@10  1 / the first rank at which every claim of R is complete (0 if not by 10)
  unreachable_claims          claims of R that the union of the system's whole judged pool does not complete
Secondary:
  partial_claim_recall@k      |claims of R at least partly supported within the top k| / |R|
Diagnostic only (not comparable across systems):
  system_relative_ndcg@10     nDCG with a fixed grade per unit (2 = relevant and completely supports at least one
                              component of a claim of R, 1 = other relevant, 0 = not relevant / uncertain /
                              unjudged), gain 2^grade - 1, discount log2(rank + 1); IDCG from this system's own
                              judged pool, so B1 and B2 values are on different scales. No B1/B2 conclusion from it
                              without a common IDCG.
  claim_novelty_dcg@10        a rank gains 1 when a claim of R becomes complete at that rank, normalized by
                              min(|R|, 10) gains at the top (not nDCG)
  unjudged@10, uncertain@10   counts in the top 10
Groups (summarize_claims): answerable queries, underspecified apart, en / ko, paired rows and the en - ko gap over
matched pairs only. Macro = mean over queries; claim_recall also micro (credited / required claims, pooled).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

DECISIONS = ("relevant", "not_relevant", "uncertain")
LEVELS = ("complete", "partial", "none")
PRIMARY = ("claim_recall@5", "claim_recall@10", "all_claims_covered@5", "all_claims_covered@10",
           "mrr_any_complete_claim@10", "mrr_all_claims_complete@10")
SECONDARY = ("partial_claim_recall@5", "partial_claim_recall@10")
DIAGNOSTIC = ("system_relative_ndcg@10", "claim_novelty_dcg@10")


@dataclass(frozen=True)
class Judgement:
    decision: str
    supports: dict = field(default_factory=dict)      # component_id -> complete / partial / none

    def validate(self, components: set[str]) -> None:
        if self.decision not in DECISIONS:
            raise ValueError(f"decision {self.decision!r}")
        unknown = set(self.supports) - components
        if unknown:
            raise ValueError(f"components {sorted(unknown)} are not components of this query's claims")
        bad = {v for v in self.supports.values() if v not in LEVELS}
        if bad:
            raise ValueError(f"support levels {sorted(bad)}")
        some = any(v in ("complete", "partial") for v in self.supports.values())
        if self.decision == "relevant" and not some:
            raise ValueError("a relevant unit must support at least one component completely or partly")
        if self.decision != "relevant" and some:
            raise ValueError(f"a {self.decision} unit supports no component")

    def level(self, component: str) -> str:
        return self.supports.get(component, "none") if self.decision == "relevant" else "none"


def grade(j: Judgement | None, required_components: set[str]) -> int:
    if not j or j.decision != "relevant":
        return 0
    return 2 if any(j.level(c) == "complete" for c in required_components) else 1


def _dcg(grades: list[int]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades[:10]))


def score_query(claims: dict[str, list[str]], required: set[str], ranking: list[str],
                judged: dict[str, Judgement], pool: set[str], k_values=(5, 10)) -> dict:
    """claims: claim_id -> its component ids (all claims of the query); required: required claim ids."""
    components = {c for comps in claims.values() for c in comps}
    for j in judged.values():
        j.validate(components)
    req_components = {c for cl in required for c in claims[cl]}

    def state(units):
        """claims complete / partly supported by the union of `units`."""
        done = {c for u in units if u in judged for c in components if judged[u].level(c) == "complete"}
        some = {c for u in units if u in judged for c in components if judged[u].level(c) in ("complete", "partial")}
        complete = {cl for cl in required if set(claims[cl]) <= done}
        partly = {cl for cl in required if set(claims[cl]) & some}
        return complete, partly

    n = len(required)
    row: dict = {"required_claims": n}
    for k in k_values:
        comp, part = state(ranking[:k])
        row[f"credited_claims@{k}"] = len(comp)
        row[f"claim_recall@{k}"] = len(comp) / n if n else 0.0
        row[f"all_claims_covered@{k}"] = int(n > 0 and comp == required)
        row[f"partial_claim_recall@{k}"] = len(part) / n if n else 0.0
    first_any = first_all = None
    seen: set[str] = set()
    gains = []
    for r in range(1, min(len(ranking), 10) + 1):
        comp, _ = state(ranking[:r])
        gains.append(1 if comp - seen else 0)
        seen = comp
        if first_any is None and comp:
            first_any = r
        if first_all is None and n and comp == required:
            first_all = r
    row["mrr_any_complete_claim@10"] = 1 / first_any if first_any else 0.0
    row["mrr_all_claims_complete@10"] = 1 / first_all if first_all else 0.0
    ideal = _dcg(sorted((grade(judged.get(u), req_components) for u in pool), reverse=True))
    row["system_relative_ndcg@10"] = (_dcg([grade(judged.get(u), req_components) for u in ranking[:10]]) / ideal
                                      if ideal else 0.0)
    nov_ideal = sum(1 / math.log2(i + 2) for i in range(min(n, 10)))
    row["claim_novelty_dcg@10"] = (sum(g / math.log2(i + 2) for i, g in enumerate(gains)) / nov_ideal
                                   if nov_ideal else 0.0)
    row["unjudged@10"] = sum(1 for u in ranking[:10] if u not in judged)
    row["uncertain@10"] = sum(1 for u in ranking[:10] if u in judged and judged[u].decision == "uncertain")
    row["unreachable_claims"] = n - len(state(pool)[0])
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
