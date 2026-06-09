import pytest

from src import candidates, pipeline
from src.config import OPENROUTER_API_KEY
from src.schema import Shortlist


@pytest.mark.live
@pytest.mark.skipif(not OPENROUTER_API_KEY, reason="no OPENROUTER_API_KEY")
def test_end_to_end_small(tmp_path, monkeypatch):
    monkeypatch.setattr(candidates, "CANDIDATES_PER_AREA", 25)
    monkeypatch.setattr(candidates, "ENRICH_LIMIT", 40)
    monkeypatch.setattr(pipeline, "VERIFY_LIMIT", 30)

    out = tmp_path / "sl.json"
    sl = pipeline.run("data/sample_student.json", str(out), target_total=8)

    assert isinstance(sl, Shortlist)
    assert len(sl.supervisors) >= 1
    assert all(s.country in ("United States", "United Kingdom", "Australia") for s in sl.supervisors)
    assert all(s.evidence.papers or s.evidence.grants for s in sl.supervisors)
    assert all(s.verification.domain_match and s.verification.is_pi for s in sl.supervisors)
    assert out.exists()
    assert "contamination_self_check" in sl.summary
