from __future__ import annotations

from ..schema import Candidate


def passes_country(cand: Candidate, countries: list[str]) -> bool:
    return bool(cand.country) and cand.country.lower() in countries
