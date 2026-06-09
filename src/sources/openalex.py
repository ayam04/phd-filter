from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..cache import cached
from ..config import CURRENT_YEAR, OPENALEX_BASE, OPENALEX_MAILTO

WORK_SELECT = (
    "id,title,publication_year,doi,cited_by_count,authorships,"
    "primary_topic,awards,funders,abstract_inverted_index"
)
AUTHOR_SELECT = (
    "id,display_name,orcid,summary_stats,works_count,counts_by_year,affiliations,topics"
)
INST_SELECT = "id,display_name,country_code,type,works_count,cited_by_count,summary_stats"


_aclient: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _aclient
    if _aclient is None or _aclient.is_closed:
        _aclient = httpx.AsyncClient(
            timeout=40.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
            headers={"User-Agent": f"phd-shortlist-builder (mailto:{OPENALEX_MAILTO})"},
        )
    return _aclient


def _params(extra: dict) -> dict:
    p = dict(extra)
    if OPENALEX_MAILTO:
        p["mailto"] = OPENALEX_MAILTO
    return p


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=15))
async def _get(path: str, params: dict) -> dict:
    r = await _client().get(f"{OPENALEX_BASE}{path}", params=_params(params))
    r.raise_for_status()
    return r.json()


@cached("oa_works")
async def fetch_works(query: str, countries: list[str], recency_years: int, per_page: int) -> list[dict]:
    from_date = f"{CURRENT_YEAR - recency_years}-01-01"
    filt = (
        f"authorships.institutions.country_code:{'|'.join(countries)},"
        f"from_publication_date:{from_date}"
    )
    data = await _get(
        "/works",
        {
            "search": query,
            "filter": filt,
            "sort": "cited_by_count:desc",
            "per_page": per_page,
            "select": WORK_SELECT,
        },
    )
    return data.get("results", [])


@cached("oa_author")
async def fetch_author(author_id: str) -> dict:
    aid = short_id(author_id)
    return await _get(f"/authors/{aid}", {"select": AUTHOR_SELECT})


@cached("oa_inst")
async def fetch_institution(inst_id: str) -> dict:
    iid = short_id(inst_id)
    return await _get(f"/institutions/{iid}", {"select": INST_SELECT})


def short_id(url: str) -> str:
    return url.rsplit("/", 1)[-1] if url else url


def decode_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pairs: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            pairs.append((i, word))
    pairs.sort()
    return " ".join(w for _, w in pairs)


def first_pub_year(author: dict) -> int | None:
    years = [c["year"] for c in author.get("counts_by_year", []) if c.get("works_count")]
    return min(years) if years else None


def recent_works(author: dict, years: int) -> int:
    cutoff = CURRENT_YEAR - years
    return sum(
        c.get("works_count", 0)
        for c in author.get("counts_by_year", [])
        if c.get("year", 0) >= cutoff
    )


def primary_affiliation(author: dict) -> dict:
    affs = author.get("affiliations", [])
    if not affs:
        return {}
    best = max(affs, key=lambda a: max(a.get("years", [0]) or [0]))
    return best.get("institution", {})


ACADEMIC_TYPES = {"education", "healthcare", "facility", "government", "nonprofit"}


def best_affiliation(author: dict, countries: list[str]) -> dict:
    target_academic = []
    for a in author.get("affiliations", []):
        inst = a.get("institution", {})
        cc = (inst.get("country_code") or "").lower()
        if cc in countries and inst.get("type") in ACADEMIC_TYPES:
            target_academic.append((max(a.get("years", [0]) or [0]), inst))
    if not target_academic:
        return {}
    target_academic.sort(key=lambda t: t[0], reverse=True)
    return target_academic[0][1]


def h_index(author: dict) -> int:
    return int(author.get("summary_stats", {}).get("h_index", 0) or 0)


def work_doi_url(work: dict) -> str:
    doi = work.get("doi")
    if doi:
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    return work.get("id", "")


def work_topic(work: dict) -> tuple[str | None, str | None]:
    pt = work.get("primary_topic") or {}
    field = (pt.get("field") or {}).get("display_name")
    domain = (pt.get("domain") or {}).get("display_name")
    return field, domain


def work_grants(work: dict) -> list[dict]:
    out = []
    work_url = work.get("id", "")
    for a in work.get("awards", []) or []:
        out.append(
            {
                "funder": a.get("funder_display_name") or a.get("funder"),
                "award_id": a.get("funder_award_id") or a.get("award_id"),
                "url": a.get("funder_id") or work_url,
            }
        )
    return out
