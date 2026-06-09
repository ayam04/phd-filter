from __future__ import annotations

import asyncio
import datetime
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import rank, verify, why_match
from .candidates import generate_candidates
from .config import (
    CODE_TO_NAME,
    CONCURRENCY,
    TARGET_TOTAL,
    VERIFY_LIMIT,
    country_codes,
)
from .filters.career_stage import is_pi, pi_score
from .filters.country import passes_country
from .filters.domain import area_vectors, passes_similarity, score_similarity
from .profile import load_profile, normalize_areas
from .schema import (
    Candidate,
    Evidence,
    LinkedProgram,
    Scores,
    Shortlist,
    StudentProfile,
    Supervisor,
)
from .sources import openalex
from .sources.email_finder import find_email


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _load_adjustments(path: str | None) -> dict:
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}


def _verify_pool(pool: list[Candidate], profile: StudentProfile) -> list[dict]:
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        return list(ex.map(lambda c: verify.verify_raw(c, profile), pool))


def _fill_why_match(selected: list[Candidate], profile: StudentProfile) -> None:
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        texts = list(ex.map(lambda c: why_match.generate_why_match(c, profile), selected))
    for c, t in zip(selected, texts):
        c.why_match = t


def _fill_emails(selected: list[Candidate]) -> None:
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        results = list(ex.map(lambda c: find_email(c.orcid, c.name, c.institution), selected))
    for c, (email, is_guess) in zip(selected, results):
        c.contact_email = email
        c.email_is_guess = is_guess


async def _enrich_institutions(cands: list[Candidate]) -> None:
    import math

    ids = {c.institution_id for c in cands if c.institution_id}
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(iid: str):
        async with sem:
            return iid, await openalex.fetch_institution(iid)

    pairs = dict(await asyncio.gather(*(one(i) for i in ids)))
    for c in cands:
        inst = pairs.get(c.institution_id, {})
        c.inst_strength = round(math.log1p(inst.get("cited_by_count", 0) or 0), 3)


def _to_supervisor(c: Candidate) -> Supervisor:
    programs = []
    if c.institution_id:
        programs.append(
            LinkedProgram(
                name=f"PhD programs at {c.institution}",
                url=c.institution_id,
                eligibility_note=None,
            )
        )
    return Supervisor(
        supervisor_id=openalex.short_id(c.author_id),
        name=c.name,
        institution=c.institution,
        country=CODE_TO_NAME.get(c.country, c.country.upper()),
        contact_email=c.contact_email,
        research_focus=c.research_focus or (c.primary_field or ""),
        matched_areas=c.matched_areas,
        tier=c.tier,
        evidence=Evidence(papers=c.papers, grants=c.grants),
        why_match=c.why_match,
        linked_programs=programs,
        scores=Scores(
            similarity=c.embedding_sim,
            evidence=rank.evidence_score(c),
            final=c.final_score,
        ),
        verification=c.verdict,
    )


async def run_async(
    profile_path: str,
    out_path: str | None = None,
    adjustments_path: str | None = None,
    target_total: int | None = None,
) -> Shortlist:
    target_total = target_total or TARGET_TOTAL
    adjustments = _load_adjustments(adjustments_path)

    profile = normalize_areas(load_profile(profile_path))
    countries = country_codes(profile.target_countries)

    stats: dict[str, int] = {}
    cands = await generate_candidates(profile)
    stats["generated"] = len(cands)

    cands = [c for c in cands if passes_country(c, countries)]
    stats["dropped_out_of_country"] = stats["generated"] - len(cands)

    kept = []
    for c in cands:
        c.pi_score = pi_score(c)
        ok, _ = is_pi(c)
        if ok:
            kept.append(c)
    stats["dropped_career_stage"] = len(cands) - len(kept)
    cands = kept

    area_vecs = area_vectors(profile)
    for c in cands:
        _, best_area = score_similarity(c, area_vecs)
        if best_area:
            c.matched_areas = [best_area] + [a for a in c.matched_areas if a != best_area]
    before_sim = len(cands)
    cands = [c for c in cands if passes_similarity(c)]
    stats["dropped_low_similarity"] = before_sim - len(cands)

    cands.sort(key=lambda c: 0.6 * c.embedding_sim + 0.4 * rank.evidence_score(c), reverse=True)
    pool = cands[:VERIFY_LIMIT]
    stats["verified_pool"] = len(pool)

    verdicts = _verify_pool(pool, profile)
    verified: list[Candidate] = []
    rej = {"domain": 0, "non_pi": 0, "region": 0, "collision": 0}
    for c, v in zip(pool, verdicts):
        c.verdict = verify.to_verification(v)
        if verify.accept(v):
            verified.append(c)
        else:
            if not v.get("domain_match"):
                rej["domain"] += 1
            elif not v.get("is_pi"):
                rej["non_pi"] += 1
            elif not v.get("region_match", True):
                rej["region"] += 1
            elif v.get("is_collision"):
                rej["collision"] += 1
    stats["rejected_domain"] = rej["domain"]
    stats["rejected_non_pi"] = rej["non_pi"]
    stats["rejected_region"] = rej["region"]
    stats["rejected_collision"] = rej["collision"]

    for c in verified:
        rank.score(c, adjustments)

    await _enrich_institutions(verified)
    verified.sort(key=lambda c: c.final_score, reverse=True)
    rank.assign_tiers(verified)
    selected = rank.balance_coverage(verified, target_total)
    stats["final"] = len(selected)

    _fill_emails(selected)
    _fill_why_match(selected, profile)

    selected.sort(key=lambda c: c.final_score, reverse=True)
    shortlist = Shortlist(
        student_id=profile.student_id,
        generated_at=_now(),
        target_countries=profile.target_countries,
        supervisors=[_to_supervisor(c) for c in selected],
    ).compute_summary(contamination_self_check=stats)

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(shortlist.model_dump_json(indent=2), encoding="utf-8")
    return shortlist


def run(
    profile_path: str,
    out_path: str | None = None,
    adjustments_path: str | None = None,
    target_total: int | None = None,
) -> Shortlist:
    return asyncio.run(run_async(profile_path, out_path, adjustments_path, target_total))
