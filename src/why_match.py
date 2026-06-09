from __future__ import annotations

from . import llm
from .schema import Candidate, StudentProfile

_SYSTEM = (
    "You write concise, specific outreach rationales for a PhD applicant emailing a professor. "
    "Output strict JSON only. Reference the professor's ACTUAL work; never use generic praise."
)


def _evidence_block(cand: Candidate) -> str:
    lines = []
    for p in cand.papers[:3]:
        lines.append(f'- paper: "{p.title}" ({p.year or "n.d."})')
    for g in cand.grants[:2]:
        lines.append(f"- grant: {g.funder} {g.award_id or ''}".rstrip())
    return "\n".join(lines) or "- (research focus: " + (cand.research_focus or "n/a") + ")"


def _student_block(profile: StudentProfile) -> str:
    interests = ", ".join(profile.research_interests) or ", ".join(a.name for a in profile.areas)
    return (
        f"Interests: {interests}. "
        f"Background: {(profile.intro_call_summary or '')[:400]}"
    )


def generate_why_match(cand: Candidate, profile: StudentProfile) -> str:
    user = (
        "Write a 2-3 sentence 'why this supervisor' note the applicant can use when emailing them.\n\n"
        f"Applicant — {_student_block(profile)}\n\n"
        f"Supervisor: {cand.name} at {cand.institution}. Matched areas: {', '.join(cand.matched_areas)}.\n"
        f"Specific evidence of their work:\n{_evidence_block(cand)}\n\n"
        "Requirements: reference at least one SPECIFIC paper title or grant above; connect it to the "
        "applicant's interests; no generic flattery; no invented facts.\n"
        'Return JSON: {"why_match": "<text>"}'
    )
    out = llm.complete_json(_SYSTEM, user, temperature=0.3)
    text = (out.get("why_match") or "").strip()
    if not _references_evidence(text, cand):
        text = _fallback(cand)
    return text


def _references_evidence(text: str, cand: Candidate) -> bool:
    if not text:
        return False
    low = text.lower()
    for p in cand.papers[:3]:
        words = [w for w in p.title.lower().split() if len(w) > 4]
        hits = sum(1 for w in words if w in low)
        if hits >= 2:
            return True
    for g in cand.grants[:2]:
        if g.funder and g.funder.lower() in low:
            return True
    return False


def _fallback(cand: Candidate) -> str:
    if cand.papers:
        p = cand.papers[0]
        return (
            f"{cand.name}'s work, including \"{p.title}\", aligns directly with the areas you want to "
            f"pursue, making them a strong supervisor to approach at {cand.institution}."
        )
    return (
        f"{cand.name} at {cand.institution} publishes actively in {cand.research_focus or 'your area'}, "
        "which overlaps your stated research interests."
    )
