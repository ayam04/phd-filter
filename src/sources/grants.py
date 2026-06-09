from __future__ import annotations

import html

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..cache import cached
from ..config import FELLOWSHIP_KEYWORDS, PERSONAL_FELLOWSHIP_CODES

NIH_URL = "https://api.reporter.nih.gov/v2/projects/search"
UKRI_URL = "https://gtr.ukri.org/api/projects"
OPENAIRE_URL = "https://api.openaire.eu/search/projects"

NIH_FELLOWSHIP_CODES = {
    "F30", "F31", "F32", "F33", "F99",
    "K00", "K01", "K08", "K23", "K24", "K25", "K43", "K99",
    "R00", "T32", "T15", "T90",
}
NIH_CODES = {c.upper() for c in PERSONAL_FELLOWSHIP_CODES} | NIH_FELLOWSHIP_CODES

NIH_FIELDS = [
    "ProjectNum", "ProjectTitle", "Organization", "PrincipalInvestigators",
    "ActivityCode", "FiscalYear", "ProjectDetailUrl",
]

UKRI_FELLOWSHIP_CATEGORIES = {"studentship", "fellowship", "training grant"}

OPENAIRE_FELLOWSHIP_TERMS = [
    "fellowship", "studentship", "doctoral",
    "msca individual", "marie sklodowska",
]


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=15))
def _post(url: str, payload: dict) -> dict:
    with httpx.Client(timeout=60.0) as c:
        r = c.post(url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        return r.json()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=15))
def _get(url: str, params: dict, headers: dict | None = None) -> dict:
    with httpx.Client(timeout=60.0) as c:
        r = c.get(url, params=params, headers=headers or {})
        r.raise_for_status()
        return r.json()


def _activity_code(project_num: str | None, activity_code: str | None) -> str:
    if activity_code:
        return activity_code.strip().upper()
    if not project_num:
        return ""
    pn = project_num.strip().upper()
    i = 0
    while i < len(pn) and pn[i].isdigit():
        i += 1
    return pn[i:i + 3]


def _nih_is_fellowship(code: str, pis: list[dict]) -> bool:
    if code in NIH_CODES:
        return True
    for pi in pis:
        title = (pi.get("title") or "").upper()
        if "FELLOW" in title:
            return True
    return False


@cached("grants_nih")
def nih_reporter(query: str, limit: int = 30) -> list[dict]:
    payload = {
        "criteria": {
            "advanced_text_search": {
                "operator": "and",
                "search_field": "projecttitle,abstracttext,terms",
                "search_text": query,
            }
        },
        "offset": 0,
        "limit": limit,
        "include_fields": NIH_FIELDS,
    }
    try:
        data = _post(NIH_URL, payload)
    except Exception:
        return []
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []
    out: list[dict] = []
    for p in results:
        if not isinstance(p, dict):
            continue
        pis = p.get("principal_investigators") or []
        if not isinstance(pis, list):
            pis = []
        pi_names = [
            pi.get("full_name").strip()
            for pi in pis
            if isinstance(pi, dict) and pi.get("full_name")
        ]
        code = _activity_code(p.get("project_num"), p.get("activity_code"))
        org = p.get("organization") or {}
        out.append(
            {
                "title": (p.get("project_title") or "").strip(),
                "funder": "NIH",
                "award_id": p.get("project_num"),
                "url": p.get("project_detail_url") or "https://reporter.nih.gov",
                "pi_names": pi_names,
                "is_personal_fellowship": _nih_is_fellowship(code, pis),
                "source": "nih",
            }
        )
    return out


@cached("grants_ukri")
def ukri_gtr(query: str, limit: int = 30) -> list[dict]:
    params = {"q": query, "fetchSize": limit, "page": 1}
    try:
        data = _get(UKRI_URL, params, headers={"Accept": "application/json"})
    except Exception:
        return []
    bean = data.get("projectsBean") if isinstance(data, dict) else None
    projects = bean.get("projects") if isinstance(bean, dict) else None
    if not isinstance(projects, list):
        return []
    out: list[dict] = []
    for p in projects:
        if not isinstance(p, dict):
            continue
        fund = p.get("fund") or {}
        funder = (fund.get("funder") or {}).get("name") if isinstance(fund, dict) else None
        category = (p.get("grantCategory") or "").strip().lower()
        out.append(
            {
                "title": html.unescape((p.get("title") or "").strip()),
                "funder": funder,
                "award_id": p.get("grantReference") or p.get("id"),
                "url": p.get("resourceUrl") or "https://gtr.ukri.org",
                "pi_names": [],
                "is_personal_fellowship": category in UKRI_FELLOWSHIP_CATEGORIES,
                "source": "ukri",
            }
        )
    return out


def _unwrap(value):
    if isinstance(value, dict) and "$" in value:
        return value["$"]
    return value


def _funding_names(funding_tree) -> list[str]:
    trees = funding_tree if isinstance(funding_tree, list) else [funding_tree]
    names: list[str] = []
    for tree in trees:
        if not isinstance(tree, dict):
            continue
        funder = tree.get("funder")
        if isinstance(funder, dict):
            for k in ("name", "shortname"):
                v = _unwrap(funder.get(k))
                if isinstance(v, str) and v:
                    names.append(v)
        for key, node in tree.items():
            if not key.startswith("funding_level_") or not isinstance(node, dict):
                continue
            for k in ("name", "description"):
                v = _unwrap(node.get(k))
                if isinstance(v, str) and v:
                    names.append(v)
    return names


def _openaire_is_fellowship(title: str, funding_names: list[str]) -> bool:
    haystack = " ".join([title] + funding_names).lower()
    for term in OPENAIRE_FELLOWSHIP_TERMS + FELLOWSHIP_KEYWORDS:
        if term in haystack:
            return True
    return False


@cached("grants_openaire")
def openaire(query: str, country_code: str = "", limit: int = 20) -> list[dict]:
    params: dict = {"keywords": query, "format": "json", "size": limit}
    if country_code:
        params["participantCountries"] = country_code.strip().upper()
    try:
        data = _get(OPENAIRE_URL, params)
    except Exception:
        return []
    resp = data.get("response") if isinstance(data, dict) else None
    results = resp.get("results") if isinstance(resp, dict) else None
    items = results.get("result") if isinstance(results, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        meta = item.get("metadata") or {}
        entity = meta.get("oaf:entity") or {} if isinstance(meta, dict) else {}
        proj = entity.get("oaf:project") or {} if isinstance(entity, dict) else {}
        if not isinstance(proj, dict):
            continue
        title = _unwrap(proj.get("title"))
        title = title.strip() if isinstance(title, str) else ""
        code = _unwrap(proj.get("code"))
        award_id = code.strip() if isinstance(code, str) and code.strip() else None
        website = _unwrap(proj.get("websiteurl"))
        url = website if isinstance(website, str) and website else "https://explore.openaire.eu"
        funding_names = _funding_names(proj.get("fundingtree"))
        funder = funding_names[0] if funding_names else None
        out.append(
            {
                "title": title,
                "funder": funder,
                "award_id": award_id,
                "url": url,
                "pi_names": [],
                "is_personal_fellowship": _openaire_is_fellowship(title, funding_names),
                "source": "openaire",
            }
        )
    return out
