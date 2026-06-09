from __future__ import annotations

from . import llm
from .filters.career_stage import career_years
from .schema import Candidate, StudentProfile, Verification

_SYSTEM = (
    "You are a meticulous academic verifier preventing bad PhD supervisor matches. "
    "Output strict JSON only. Be skeptical: when genuinely uncertain, reject."
)


def _areas_block(profile: StudentProfile) -> str:
    lines = []
    for a in profile.areas:
        lines.append(
            f"- {a.name} (discipline: {a.discipline or 'unspecified'}; "
            f"region: {a.region_hint or 'global'})"
        )
    return "\n".join(lines)


def _prompt(cand: Candidate, profile: StudentProfile) -> str:
    cy = career_years(cand)
    abstracts = "\n".join(
        f"  {i + 1}) {ab[:600]}" for i, ab in enumerate(cand.abstracts[:3])
    ) or "  (no abstracts available)"
    return (
        "A PhD applicant seeks supervisors in these areas:\n"
        f"{_areas_block(profile)}\n\n"
        "Candidate researcher to verify:\n"
        f"- Name: {cand.name}\n"
        f"- Institution: {cand.institution} ({cand.country.upper()})\n"
        f"- Affiliation text: {cand.affiliation_raw or 'n/a'}\n"
        f"- Career signals: ~{cy if cy is not None else '?'} years since first publication, "
        f"{cand.works_count} total works, {cand.last_author_count} last-author papers in the matched set, "
        f"h-index {cand.h_index}\n"
        f"- Stated topics: {', '.join(cand.top_topics) or cand.research_focus or 'n/a'}\n"
        "- Representative abstracts from their recent work:\n"
        f"{abstracts}\n\n"
        "Judge by the ABSTRACTS, not title keywords. Return JSON exactly:\n"
        '{"discipline": "<candidate actual discipline from the abstracts>",'
        ' "domain_match": <true if the candidate works in the SAME broad field as one of the'
        " student's areas OR a directly adjacent subfield a domain mentor would consider worth"
        " contacting; false ONLY for a clearly different discipline or a keyword coincidence>,"
        ' "region_match": <true if no region constraint applies or the work matches the area region;'
        " false if the area is region-specific and the work is about a different region/ecosystem>,"
        ' "is_pi": <true if a supervising principal investigator / faculty member who runs their own'
        " lab and can supervise PhD students; false if they look like a PhD student, postdoc,"
        " personal-fellowship awardee, OR a research-data-coordinator / core-facility / consortium"
        " staff scientist or administrator who does not run a lab>,"
        ' "is_collision": <true if the abstracts look like different people merged under one name, or'
        " the person clearly does not match the area>,"
        ' "reason": "<one sentence>"}\n'
        "Keyword traps to avoid: 'trauma' in classics/history is NOT clinical psychology; 'DNA "
        "barcoding' in single-cell genomics is NOT species/plant barcoding; 'biodegradable "
        "cartridges' may be munitions not biomaterials; 'high-elevation social-ecological systems' "
        "may be fire archaeology, not Himalayan studies."
    )


def verify_raw(cand: Candidate, profile: StudentProfile) -> dict:
    return llm.complete_json(_SYSTEM, _prompt(cand, profile))


def accept(verdict: dict) -> bool:
    return (
        bool(verdict.get("domain_match"))
        and bool(verdict.get("region_match", True))
        and bool(verdict.get("is_pi"))
        and not bool(verdict.get("is_collision"))
    )


def to_verification(verdict: dict) -> Verification:
    disc = verdict.get("discipline") or "?"
    reason = (verdict.get("reason") or "").strip()
    return Verification(
        domain_match=bool(verdict.get("domain_match")),
        region_match=bool(verdict.get("region_match", True)),
        is_pi=bool(verdict.get("is_pi")),
        collision_checked=True,
        reason=f"discipline={disc}; {reason}"[:300],
    )
