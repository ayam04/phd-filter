import pytest
from pydantic import ValidationError

from src.schema import (
    Evidence,
    PaperEvidence,
    Shortlist,
    StudentProfile,
    Supervisor,
)


def _paper():
    return PaperEvidence(title="A study of X", year=2023, url="https://doi.org/10.1/x", citations=5)


def test_supervisor_requires_evidence():
    with pytest.raises(ValidationError):
        Supervisor(
            supervisor_id="A1",
            name="Dr Test",
            institution="MIT",
            country="us",
            research_focus="x",
            evidence=Evidence(),  # empty -> must fail
        )


def test_supervisor_valid_with_paper():
    s = Supervisor(
        supervisor_id="A1",
        name="Dr Test",
        institution="MIT",
        country="us",
        research_focus="x",
        evidence=Evidence(papers=[_paper()]),
    )
    assert s.tier == "target"
    assert s.evidence.papers[0].url.startswith("https://")


def test_shortlist_summary():
    s = Supervisor(
        supervisor_id="A1", name="Dr Test", institution="MIT", country="us",
        research_focus="x", matched_areas=["PTSD"], tier="reach",
        evidence=Evidence(papers=[_paper()]),
    )
    sl = Shortlist(
        student_id="106419", generated_at="2026-06-09T00:00:00Z",
        target_countries=["United States"], supervisors=[s],
    ).compute_summary(contamination_self_check={"dropped_domain": 3})
    assert sl.summary["total"] == 1
    assert sl.summary["by_tier"]["reach"] == 1
    assert sl.summary["by_area"]["PTSD"] == 1
    assert sl.summary["contamination_self_check"]["dropped_domain"] == 3


def test_student_profile_minimal():
    p = StudentProfile(student_id="x", target_countries=["United Kingdom"])
    assert p.areas == []
    assert p.target_countries == ["United Kingdom"]
