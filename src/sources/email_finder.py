from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..cache import cached

ORCID_BASE = "https://pub.orcid.org/v3.0"
HEADERS = {"Accept": "application/json"}


def bare_orcid(orcid: str | None) -> str | None:
    if not orcid:
        return None
    s = str(orcid).strip()
    if not s:
        return None
    return s.rstrip("/").rsplit("/", 1)[-1].strip()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=15))
def _get(path: str) -> dict | None:
    with httpx.Client(timeout=40.0, headers=HEADERS) as c:
        r = c.get(f"{ORCID_BASE}{path}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


@cached("orcid_email")
def _fetch_email(bare_id: str) -> str | None:
    try:
        data = _get(f"/{bare_id}/email")
    except httpx.HTTPError:
        return None
    if not data:
        return None
    for entry in data.get("email") or []:
        value = entry.get("email")
        if value:
            return value
    return None


@cached("orcid_employments")
def _fetch_role_title(bare_id: str) -> str | None:
    try:
        data = _get(f"/{bare_id}/employments")
    except httpx.HTTPError:
        return None
    if not data:
        return None
    summaries: list[dict] = []
    for group in data.get("affiliation-group") or []:
        for summary in group.get("summaries") or []:
            es = summary.get("employment-summary")
            if es:
                summaries.append(es)
    if not summaries:
        return None

    def sort_key(es: dict):
        sd = es.get("start-date") or {}
        year = (sd.get("year") or {}).get("value") if sd else None
        try:
            return int(year)
        except (TypeError, ValueError):
            return -1

    summaries.sort(key=sort_key, reverse=True)
    for es in summaries:
        title = es.get("role-title")
        if title:
            return title
    return None


def find_email(
    orcid: str | None, author_name: str = "", institution: str = ""
) -> tuple[str | None, bool]:
    bare = bare_orcid(orcid)
    if not bare:
        return None, False
    email = _fetch_email(bare)
    if email:
        return email, False
    return None, False


def orcid_role_title(orcid: str | None) -> str | None:
    bare = bare_orcid(orcid)
    if not bare:
        return None
    return _fetch_role_title(bare)
