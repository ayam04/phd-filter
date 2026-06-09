"""Pydantic models: the student-profile input, the internal Candidate carried
through the pipeline, and the documented output Shortlist.

The output schema is the contract documented in schema.md. The key invariant —
**evidence-or-drop** — is enforced here: a Supervisor cannot be constructed
without at least one verifiable paper or grant.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------
class Area(BaseModel):
    """A normalised research area (one of the student's 3-5 stated interests)."""
    name: str
    query_terms: list[str] = Field(default_factory=list)
    discipline: Optional[str] = None      # e.g. "clinical psychology"
    region_hint: Optional[str] = None     # e.g. "global", "South Asia"


class Education(BaseModel):
    degree: str
    institution: str
    field: Optional[str] = None
    grade: Optional[str] = None
    year: Optional[int] = None
    thesis: Optional[str] = None


class StudentProfile(BaseModel):
    student_id: str
    name: Optional[str] = None
    nationality: Optional[str] = None
    education: list[Education] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)
    research_interests: list[str] = Field(default_factory=list)
    target_countries: list[str]
    target_intake: Optional[str] = None
    intro_call_summary: Optional[str] = None
    raw_resume: Optional[str] = None
    # Filled in by profile.normalize_areas()
    areas: list[Area] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Evidence + output sub-objects
# --------------------------------------------------------------------------
class PaperEvidence(BaseModel):
    title: str
    year: Optional[int] = None
    doi: Optional[str] = None
    url: str
    citations: int = 0


class GrantEvidence(BaseModel):
    title: str
    funder: Optional[str] = None
    award_id: Optional[str] = None
    url: str
    is_personal_fellowship: bool = False


class Evidence(BaseModel):
    papers: list[PaperEvidence] = Field(default_factory=list)
    grants: list[GrantEvidence] = Field(default_factory=list)


class LinkedProgram(BaseModel):
    name: str
    url: str
    eligibility_note: Optional[str] = None


class Scores(BaseModel):
    similarity: float = 0.0
    evidence: float = 0.0
    final: float = 0.0


class Verification(BaseModel):
    domain_match: bool = True
    region_match: bool = True
    is_pi: bool = True
    collision_checked: bool = True
    reason: Optional[str] = None


class Supervisor(BaseModel):
    supervisor_id: str            # OpenAlex Author ID (A...), same ID space as bonus CSV
    name: str
    institution: str
    country: str
    contact_email: Optional[str] = None
    research_focus: str
    matched_areas: list[str] = Field(default_factory=list)
    tier: Literal["reach", "target", "safety"] = "target"
    evidence: Evidence = Field(default_factory=Evidence)
    why_match: str = ""
    linked_programs: list[LinkedProgram] = Field(default_factory=list)
    scores: Scores = Field(default_factory=Scores)
    verification: Verification = Field(default_factory=Verification)

    @model_validator(mode="after")
    def _require_evidence(self):
        if not self.evidence.papers and not self.evidence.grants:
            raise ValueError(
                f"Supervisor {self.supervisor_id} has no verifiable paper/grant evidence"
            )
        return self


class Shortlist(BaseModel):
    student_id: str
    generated_at: str
    target_countries: list[str]
    summary: dict = Field(default_factory=dict)
    supervisors: list[Supervisor] = Field(default_factory=list)

    def compute_summary(self, contamination_self_check: Optional[dict] = None) -> "Shortlist":
        by_tier: dict[str, int] = {}
        by_area: dict[str, int] = {}
        for s in self.supervisors:
            by_tier[s.tier] = by_tier.get(s.tier, 0) + 1
            for a in s.matched_areas:
                by_area[a] = by_area.get(a, 0) + 1
        self.summary = {
            "total": len(self.supervisors),
            "by_tier": by_tier,
            "by_area": by_area,
        }
        if contamination_self_check is not None:
            self.summary["contamination_self_check"] = contamination_self_check
        return self


# --------------------------------------------------------------------------
# Internal pipeline carrier (not part of the output contract)
# --------------------------------------------------------------------------
class Candidate(BaseModel):
    """A potential supervisor as it flows through the filter cascade."""
    author_id: str
    name: str
    orcid: Optional[str] = None
    institution: str = ""
    institution_id: Optional[str] = None
    country: str = ""               # ISO-2 lowercase
    matched_areas: list[str] = Field(default_factory=list)

    papers: list[PaperEvidence] = Field(default_factory=list)
    grants: list[GrantEvidence] = Field(default_factory=list)

    # Author meta used by filters
    works_count: int = 0
    h_index: int = 0
    first_pub_year: Optional[int] = None
    recent_works: int = 0
    last_author_count: int = 0
    affiliation_raw: str = ""
    top_topics: list[str] = Field(default_factory=list)
    primary_field: Optional[str] = None
    primary_domain: Optional[str] = None
    abstracts: list[str] = Field(default_factory=list)

    # Scoring / verification scratch
    embedding_sim: float = 0.0
    pi_score: float = 0.0
    inst_strength: float = 0.0
    contact_email: Optional[str] = None
    email_is_guess: bool = False
    verdict: Optional[Verification] = None
    research_focus: str = ""
    why_match: str = ""
    final_score: float = 0.0
    tier: Literal["reach", "target", "safety"] = "target"
