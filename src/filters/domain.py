from __future__ import annotations

from .. import llm
from ..config import SIM_THRESHOLD
from ..schema import Area, Candidate, StudentProfile


def area_text(area: Area) -> str:
    parts = [area.name]
    if area.discipline:
        parts.append(area.discipline)
    parts.extend(area.query_terms[:3])
    return ". ".join(parts)


def area_vectors(profile: StudentProfile) -> dict[str, list[float]]:
    return {a.name: llm.embed(area_text(a)) for a in profile.areas}


def _candidate_vectors(cand: Candidate) -> list[list[float]]:
    texts = [ab[:1000] for ab in cand.abstracts[:5]]
    if cand.research_focus:
        texts.append(cand.research_focus)
    if not texts:
        texts = [cand.name]
    return [llm.embed(t) for t in texts]


def score_similarity(cand: Candidate, area_vecs: dict[str, list[float]]) -> tuple[float, str | None]:
    cvecs = _candidate_vectors(cand)
    best, best_area = 0.0, None
    for area, av in area_vecs.items():
        s = max((llm.cosine(av, cv) for cv in cvecs), default=0.0)
        if s > best:
            best, best_area = s, area
    cand.embedding_sim = round(best, 4)
    return cand.embedding_sim, best_area


def passes_similarity(cand: Candidate) -> bool:
    return cand.embedding_sim >= SIM_THRESHOLD
