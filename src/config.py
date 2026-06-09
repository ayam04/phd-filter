from __future__ import annotations

import datetime
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")

OPENALEX_BASE = "https://api.openalex.org"
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

CACHE_DIR = Path(os.getenv("CACHE_DIR", str(ROOT / ".cache")))

CURRENT_YEAR = int(os.getenv("CURRENT_YEAR", datetime.date.today().year))
RECENCY_YEARS = 8
CANDIDATES_PER_AREA = 120
TARGET_TOTAL = 80
MIN_PAPERS = 1
SIM_THRESHOLD = 0.60
PI_MIN_CAREER_YEARS = 6
PI_MIN_WORKS = 8
PI_MIN_LAST_AUTHOR = 2
CONCURRENCY = 8

PERSONAL_FELLOWSHIP_CODES = {
    "F30", "F31", "F32", "F33", "F99", "K00", "K99", "T32", "T15", "TL1",
}
FELLOWSHIP_KEYWORDS = [
    "fellowship", "studentship", "doctoral training", "phd scholarship",
    "early career", "msca individual", "msca postdoctoral", "marie sklodowska",
    "marie curie individual", "graduate research fellowship",
]

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
    out: list[str] = []
    for n in names:
        c = COUNTRY_CODE.get(n.strip().lower())
        if c and c not in out:
            out.append(c)
    return out
