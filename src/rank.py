from __future__ import annotations

import math
from collections import defaultdict

from .schema import Candidate


def evidence_score(cand: Candidate) -> float:
    cites = sum(p.citations for p in cand.papers)
    s = (
        min(math.log1p(cites) / 8.0, 1.0) * 0.5
        + min(cand.h_index / 40.0, 1.0) * 0.3
        + min(len(cand.grants) / 2.0, 1.0) * 0.2
    )
    return round(s, 4)


def apply_adjustments(base: float, cand: Candidate, adj: dict) -> float:
    if not adj:
        return base
    short_id = cand.author_id.rsplit("/", 1)[-1]
    suppress = set(adj.get("suppress", []))
    if short_id in suppress or cand.author_id in suppress:
        return base * 0.01
    uplift = adj.get("area_institution_uplift", {})
    for area in cand.matched_areas:
        key = f"{area}::{cand.institution}"
        if key in uplift:
            base *= 1.0 + float(uplift[key])
    tier_uplift = adj.get("tier_uplift", {})
    if cand.tier in tier_uplift:
        base *= 1.0 + float(tier_uplift[cand.tier])
    return base


def score(cand: Candidate, adj: dict | None = None) -> float:
    sim = cand.embedding_sim
    ev = evidence_score(cand)
    pi = cand.pi_score
    base = 0.5 * sim + 0.3 * ev + 0.2 * pi
    base = apply_adjustments(base, cand, adj or {})
    cand.final_score = round(base, 4)
    return cand.final_score


def assign_tiers(cands: list[Candidate]) -> None:
    if not cands:
        return
    ranked = sorted(cands, key=lambda c: c.inst_strength, reverse=True)
    n = len(ranked)
    for i, c in enumerate(ranked):
        frac = i / n
        if frac < 0.33:
            c.tier = "reach"
        elif frac < 0.70:
            c.tier = "target"
        else:
            c.tier = "safety"


def balance_coverage(cands: list[Candidate], target_total: int) -> list[Candidate]:
    by_area: dict[str, list[Candidate]] = defaultdict(list)
    for c in cands:
        primary = c.matched_areas[0] if c.matched_areas else "other"
        by_area[primary].append(c)
    for a in by_area:
        by_area[a].sort(key=lambda c: c.final_score, reverse=True)

    areas = sorted(by_area.keys())
    idx = {a: 0 for a in areas}
    selected: list[Candidate] = []
    seen: set[str] = set()
    while len(selected) < target_total and any(idx[a] < len(by_area[a]) for a in areas):
        for a in areas:
            if idx[a] < len(by_area[a]):
                c = by_area[a][idx[a]]
                idx[a] += 1
                if c.author_id not in seen:
                    seen.add(c.author_id)
                    selected.append(c)
                    if len(selected) >= target_total:
                        break
    return selected
