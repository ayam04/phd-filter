from __future__ import annotations

from ..config import CURRENT_YEAR, PI_MIN_CAREER_YEARS, PI_MIN_WORKS
from ..schema import Candidate, GrantEvidence

TRAINEE_MARKERS = [
    "phd student", "ph.d. student", "ph.d student", "doctoral candidate",
    "doctoral student", "phd candidate", "graduate student", "grad student",
    "research assistant", "undergraduate", "master's student", "masters student",
    "msc student", "m.sc student", "mphil", "predoctoral", "pre-doctoral",
]


def affiliation_is_trainee(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in TRAINEE_MARKERS)


def career_years(cand: Candidate) -> int | None:
    return (CURRENT_YEAR - cand.first_pub_year) if cand.first_pub_year else None


def pi_score(cand: Candidate) -> float:
    score = 0.0
    cy = career_years(cand)
    if cy is not None:
        score += min(cy / 12.0, 1.0) * 0.40
    score += min(cand.works_count / 40.0, 1.0) * 0.25
    score += min(cand.last_author_count / 4.0, 1.0) * 0.25
    score += min(cand.recent_works / 10.0, 1.0) * 0.10
    return round(score, 4)


def is_pi(cand: Candidate) -> tuple[bool, str]:
    if affiliation_is_trainee(cand.affiliation_raw):
        return False, "affiliation indicates a trainee (student/postdoc/RA)"
    cy = career_years(cand)
    if cand.works_count < PI_MIN_WORKS and (cy is None or cy < PI_MIN_CAREER_YEARS):
        return False, "thin publication record and short career — likely junior"
    if cy is not None and cy < 4 and cand.last_author_count == 0:
        return False, "very early career with no senior-author signal"
    return True, "meets PI criteria"


def fellowship_awardee(grants: list[GrantEvidence]) -> bool:
    return any(g.is_personal_fellowship for g in grants)
