from __future__ import annotations

import json
from pathlib import Path

from . import llm
from .schema import Area, StudentProfile

_SYSTEM = "You are a research-matching assistant for PhD supervisor search. Output strict JSON only."


def load_profile(path: str | Path) -> StudentProfile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return StudentProfile(**data)


def _edu_summary(profile: StudentProfile) -> str:
    bits = []
    for e in profile.education:
        bits.append(f"{e.degree} in {e.field or '?'} from {e.institution} ({e.year or '?'})")
    return "; ".join(bits)


def normalize_areas(profile: StudentProfile) -> StudentProfile:
    interests = profile.research_interests or []
    user = (
        "Given a PhD applicant's profile, produce search-ready research areas for finding "
        "supervisors.\n\n"
        f"Stated research interests: {interests}\n"
        f"Education: {_edu_summary(profile)}\n"
        f"Intro call summary: {(profile.intro_call_summary or '')[:1500]}\n"
        f"Resume excerpt: {(profile.raw_resume or '')[:2000]}\n\n"
        "Return JSON with this exact shape:\n"
        '{"nationality": "<applicant nationality/citizenship if stated or clearly implied, else null>",'
        ' "areas": [{"name": "<short area label>",'
        ' "discipline": "<academic discipline, e.g. clinical psychology, computational biology / genomics, mechanical engineering>",'
        ' "query_terms": ["<3-5 specific multi-word literature-search phrases>"],'
        ' "region_hint": "<region if the area is geographically specific, else global>"}]}\n'
        "One area per stated interest (merge near-duplicates). query_terms must be specific "
        "multi-word phrases, never single generic words."
    )
    out = llm.complete_json(_SYSTEM, user)
    areas: list[Area] = []
    for a in out.get("areas", []) or []:
        name = (a.get("name") or "").strip()
        if not name:
            continue
        terms = [t for t in (a.get("query_terms") or []) if t and t.strip()]
        areas.append(
            Area(
                name=name,
                discipline=(a.get("discipline") or None),
                query_terms=terms or [name],
                region_hint=(a.get("region_hint") or None),
            )
        )
    if not areas:
        areas = [Area(name=i, query_terms=[i]) for i in interests]
    profile.areas = areas
    nat = out.get("nationality")
    if nat and not profile.nationality:
        profile.nationality = nat
    return profile
