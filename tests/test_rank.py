from src import rank
from src.schema import Candidate, PaperEvidence


def _cand(aid, sim, cites, area, h=20):
    return Candidate(
        author_id=aid, name=aid, embedding_sim=sim, h_index=h,
        matched_areas=[area],
        papers=[PaperEvidence(title="p", url="https://x", citations=cites)],
    )


def test_evidence_score_monotonic_in_citations():
    low = _cand("A", 0.7, 5, "x")
    high = _cand("B", 0.7, 5000, "x")
    assert rank.evidence_score(high) > rank.evidence_score(low)


def test_score_increases_with_similarity():
    lo = _cand("A", 0.61, 100, "x")
    hi = _cand("B", 0.95, 100, "x")
    assert rank.score(hi) > rank.score(lo)


def test_suppress_demotes():
    c = _cand("A", 0.9, 1000, "x")
    base = rank.score(c)
    demoted = rank.score(c, {"suppress": ["A"]})
    assert demoted < base


def test_balance_coverage_spreads_across_areas():
    cands = []
    for i in range(10):
        cands.append(_cand(f"P{i}", 0.9 - i * 0.01, 100, "PTSD"))
    for i in range(3):
        cands.append(_cand(f"G{i}", 0.8 - i * 0.01, 100, "Genomics"))
    for c in cands:
        rank.score(c)
    selected = rank.balance_coverage(cands, target_total=6)
    areas = [c.matched_areas[0] for c in selected]
    assert "PTSD" in areas and "Genomics" in areas
    assert len(selected) == 6


def test_assign_tiers_buckets_by_strength():
    cands = [_cand(f"A{i}", 0.8, 100, "x") for i in range(10)]
    for i, c in enumerate(cands):
        c.inst_strength = float(i)
    rank.assign_tiers(cands)
    tiers = {c.author_id: c.tier for c in cands}
    assert tiers["A9"] == "reach"
    assert tiers["A0"] == "safety"
