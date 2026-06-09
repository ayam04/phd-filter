"""Central config: env, model names, pipeline thresholds, country mapping.

Every tunable that affects contamination/coverage/latency lives here so the
trade-offs are auditable in one place (and documented in DECISIONS.md).
"""
from __future__ import annotations

import datetime
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# --- LLM -------------------------------------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-004")

# --- OpenAlex --------------------------------------------------------------
OPENALEX_BASE = "https://api.openalex.org"
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

# --- Cache -----------------------------------------------------------------
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(ROOT / ".cache")))

# --- Pipeline knobs (the levers behind precision/recall trade-offs) --------
CURRENT_YEAR = int(os.getenv("CURRENT_YEAR", datetime.date.today().year))
RECENCY_YEARS = 8            # only consider works from the last N years
CANDIDATES_PER_AREA = 120    # OpenAlex works pulled per area before aggregation
TARGET_TOTAL = 80            # desired final shortlist size (50-200 band)
MIN_PAPERS = 1               # evidence-or-drop floor
SIM_THRESHOLD = 0.60         # embedding cosine floor (profile <-> PI abstracts)
PI_MIN_CAREER_YEARS = 6      # rough faculty threshold (career-stage gate)
PI_MIN_WORKS = 8             # sustained output floor for a PI
PI_MIN_LAST_AUTHOR = 2       # senior-authorship signal
CONCURRENCY = 8              # async fan-out width for API + LLM calls

# Personal-fellowship / career-award codes whose listed person is the
# AWARDEE (a junior researcher), not a supervising PI. (Confirmed against
# NIH activity-code conventions; extended from grant-source research.)
PERSONAL_FELLOWSHIP_CODES = {
    "F30", "F31", "F32", "F33", "F99", "K00", "K99", "T32", "T15", "TL1",
}
FELLOWSHIP_KEYWORDS = [
    "fellowship", "studentship", "doctoral training", "phd scholarship",
    "early career", "msca individual", "msca postdoctoral", "marie sklodowska",
    "marie curie individual", "graduate research fellowship",
]

# --- Country name -> ISO-2 (lowercase, OpenAlex style) ---------------------
COUNTRY_CODE = {
    "united states": "us", "united states of america": "us", "usa": "us", "us": "us",
    "u.s.": "us", "u.s.a.": "us", "america": "us",
    "united kingdom": "gb", "uk": "gb", "u.k.": "gb", "england": "gb",
    "scotland": "gb", "wales": "gb", "great britain": "gb", "britain": "gb",
    "australia": "au", "canada": "ca", "germany": "de", "netherlands": "nl",
    "the netherlands": "nl", "switzerland": "ch", "singapore": "sg",
    "ireland": "ie", "new zealand": "nz", "france": "fr", "sweden": "se",
    "denmark": "dk", "norway": "no", "finland": "fi", "belgium": "be",
    "italy": "it", "spain": "es", "austria": "at", "hong kong": "hk", "japan": "jp",
}
CODE_TO_NAME = {
    "us": "United States", "gb": "United Kingdom", "au": "Australia",
    "ca": "Canada", "de": "Germany", "nl": "Netherlands", "ch": "Switzerland",
    "sg": "Singapore", "ie": "Ireland", "nz": "New Zealand", "fr": "France",
    "se": "Sweden", "dk": "Denmark", "no": "Norway", "fi": "Finland",
    "be": "Belgium", "it": "Italy", "es": "Spain", "at": "Austria",
    "hk": "Hong Kong", "jp": "Japan",
}


def country_codes(names: list[str]) -> list[str]:
    """Map free-text country names to OpenAlex ISO-2 codes (deduped, ordered)."""
    out: list[str] = []
    for n in names:
        c = COUNTRY_CODE.get(n.strip().lower())
        if c and c not in out:
            out.append(c)
    return out
