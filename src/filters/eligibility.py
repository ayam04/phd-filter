from __future__ import annotations

from .. import llm

_SYSTEM = "You extract PhD-vacancy eligibility constraints. Output strict JSON only."

_DOMESTIC = {
    "gb": {"uk", "united kingdom", "home", "british", "england", "scotland", "wales"},
    "us": {"us", "usa", "united states", "american", "domestic"},
    "au": {"australia", "australian", "domestic"},
}


def extract_eligibility(ad_text: str) -> dict:
    user = (
        "Read this PhD position advertisement and extract eligibility constraints.\n\n"
        f"AD TEXT:\n{ad_text[:4000]}\n\n"
        "Return JSON exactly:\n"
        '{"home_or_domestic_only": <true if funding/eligibility is restricted to home/domestic/'
        'citizen/resident applicants, else false>,'
        ' "international_eligible": <true if international applicants are eligible, else false>,'
        ' "citizenship_or_residency_restrictions": ["<short phrases, e.g. UK/home fees only, EU residents>"],'
        ' "summary": "<one sentence>"}'
    )
    return llm.complete_json(_SYSTEM, user)


def eligible(elig: dict, nationality: str | None, country_code: str = "") -> bool:
    if not elig:
        return True
    nat = (nationality or "").strip().lower()
    domestic = _DOMESTIC.get(country_code.lower(), set())
    is_domestic_applicant = any(d in nat for d in domestic) if nat else False
    if elig.get("home_or_domestic_only") and not is_domestic_applicant:
        return False
    if elig.get("international_eligible") is False and not is_domestic_applicant:
        return False
    return True
