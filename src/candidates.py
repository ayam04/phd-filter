from __future__ import annotations

import asyncio
from collections import Counter, defaultdict

from .config import (
    CANDIDATES_PER_AREA,
    CONCURRENCY,
    ENRICH_LIMIT,
    MAX_PAPERS_PER_PI,
    RECENCY_YEARS,
    country_codes,
)
from .schema import Candidate, GrantEvidence, PaperEvidence, StudentProfile
from .sources import openalex


def _blank_record() -> dict:
    return {
        "name": "",
        "orcid": None,
        "areas": set(),
        "appearances": 0,
        "last_author": 0,
        "target_insts": {},
        "papers": {},
        "fields": Counter(),
        "domains": Counter(),
        "abstracts": [],
        "grants": {},
        "affiliation_raw": "",
    }


def _paper_from_work(work: dict) -> PaperEvidence:
    return PaperEvidence(
        title=(work.get("title") or "Untitled").strip(),
        year=work.get("publication_year"),
        doi=work.get("doi"),
        url=openalex.work_doi_url(work),
        citations=int(work.get("cited_by_count", 0) or 0),
    )


async def _gather_works(profile: StudentProfile, countries: list[str]) -> list[tuple[str, list[dict]]]:
    queries: list[tuple[str, str]] = []
    for area in profile.areas:
        for term in (area.query_terms or [area.name]):
            queries.append((area.name, term))
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(area_name: str, term: str):
        async with sem:
            works = await openalex.fetch_works(term, countries, RECENCY_YEARS, CANDIDATES_PER_AREA)
            return area_name, works

    return await asyncio.gather(*(one(a, t) for a, t in queries))


def _aggregate(area_works: list[tuple[str, list[dict]]], countries: list[str]) -> dict:
    agg: dict[str, dict] = defaultdict(_blank_record)
    for area_name, works in area_works:
        for w in works:
            field, domain = openalex.work_topic(w)
            abstract = openalex.decode_abstract(w.get("abstract_inverted_index"))
            grants = openalex.work_grants(w)
            work_id = w.get("id", "")
            for au in w.get("authorships", []):
                author = au.get("author") or {}
                aid = author.get("id")
                if not aid:
                    continue
                insts = au.get("institutions", []) or []
                tgt = next(
                    (i for i in insts if (i.get("country_code") or "").lower() in countries),
                    None,
                )
                rec = agg[aid]
                rec["name"] = author.get("display_name") or rec["name"]
                rec["orcid"] = author.get("orcid") or rec["orcid"]
                rec["areas"].add(area_name)
                rec["appearances"] += 1
                if au.get("author_position") == "last":
                    rec["last_author"] += 1
                if tgt:
                    tid = tgt["id"]
                    entry = rec["target_insts"].get(
                        tid,
                        {
                            "name": tgt.get("display_name", ""),
                            "country": (tgt.get("country_code") or "").lower(),
                            "type": tgt.get("type"),
                            "count": 0,
                        },
                    )
                    entry["count"] += 1
                    rec["target_insts"][tid] = entry
                    raws = au.get("raw_affiliation_strings") or []
                    if raws and not rec["affiliation_raw"]:
                        rec["affiliation_raw"] = raws[0]
                if work_id and work_id not in rec["papers"]:
                    rec["papers"][work_id] = _paper_from_work(w)
                if field:
                    rec["fields"][field] += 1
                if domain:
                    rec["domains"][domain] += 1
                if abstract and len(rec["abstracts"]) < 6:
                    rec["abstracts"].append(abstract)
                for g in grants:
                    if g.get("funder"):
                        key = (g["funder"], g.get("award_id"))
                        rec["grants"][key] = g
    return {aid: rec for aid, rec in agg.items() if rec["target_insts"]}


async def _enrich(top: list[tuple[str, dict]]) -> dict:
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(aid: str):
        async with sem:
            return aid, await openalex.fetch_author(aid)

    pairs = await asyncio.gather(*(one(aid) for aid, _ in top))
    return dict(pairs)


def _build(aid: str, rec: dict, author: dict, countries: list[str]) -> Candidate:
    prim = openalex.best_affiliation(author, countries)
    inst_id = prim.get("id")
    inst_name = prim.get("display_name", "")
    inst_country = (prim.get("country_code") or "").lower()
    if not inst_id or inst_country not in countries:
        academic = {
            k: v
            for k, v in rec["target_insts"].items()
            if v.get("type") in openalex.ACADEMIC_TYPES
        }
        if academic:
            inst_id = max(academic, key=lambda k: academic[k]["count"])
            inst_name = academic[inst_id]["name"]
            inst_country = academic[inst_id]["country"]
        else:
            inst_id, inst_name, inst_country = None, "", ""

    papers = sorted(rec["papers"].values(), key=lambda p: p.citations, reverse=True)[:MAX_PAPERS_PER_PI]
    grants = [
        GrantEvidence(
            title=f"{g['funder']} award {g.get('award_id') or ''}".strip(),
            funder=g["funder"],
            award_id=g.get("award_id"),
            url=g.get("url") or inst_id,
        )
        for g in rec["grants"].values()
    ][:3]

    topics = [t.get("display_name") for t in (author.get("topics") or [])[:5] if t.get("display_name")]
    primary_field = rec["fields"].most_common(1)[0][0] if rec["fields"] else None
    primary_domain = rec["domains"].most_common(1)[0][0] if rec["domains"] else None

    return Candidate(
        author_id=aid,
        name=rec["name"],
        orcid=rec["orcid"],
        institution=inst_name,
        institution_id=inst_id,
        country=inst_country,
        matched_areas=sorted(rec["areas"]),
        papers=papers,
        grants=grants,
        works_count=int(author.get("works_count", 0) or 0),
        h_index=openalex.h_index(author),
        first_pub_year=openalex.first_pub_year(author),
        recent_works=openalex.recent_works(author, RECENCY_YEARS),
        last_author_count=rec["last_author"],
        affiliation_raw=rec["affiliation_raw"],
        top_topics=topics,
        primary_field=primary_field,
        primary_domain=primary_domain,
        abstracts=rec["abstracts"][:5],
        research_focus=", ".join(topics[:3]) if topics else (primary_field or ""),
    )


async def generate_candidates(profile: StudentProfile) -> list[Candidate]:
    countries = country_codes(profile.target_countries)
    area_works = await _gather_works(profile, countries)
    agg = _aggregate(area_works, countries)

    ordered = sorted(
        agg.items(),
        key=lambda kv: (
            kv[1]["appearances"],
            max((p.citations for p in kv[1]["papers"].values()), default=0),
        ),
        reverse=True,
    )
    top = ordered[:ENRICH_LIMIT]
    details = await _enrich(top)
    return [_build(aid, rec, details.get(aid, {}), countries) for aid, rec in top]
