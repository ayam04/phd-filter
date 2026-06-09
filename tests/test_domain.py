import pytest

from src.filters import domain
from src.schema import Area, Candidate, StudentProfile


@pytest.mark.live
def test_similarity_prefers_on_topic_candidate():
    profile = StudentProfile(
        student_id="t", target_countries=["United States"],
        areas=[Area(name="PTSD", discipline="clinical psychology",
                    query_terms=["post-traumatic stress disorder treatment", "trauma therapy veterans"])],
    )
    vecs = domain.area_vectors(profile)

    on_topic = Candidate(
        author_id="A1", name="On Topic",
        abstracts=["A randomized trial of prolonged exposure therapy for PTSD in combat veterans."],
    )
    off_topic = Candidate(
        author_id="A2", name="Off Topic",
        abstracts=["Single-cell RNA sequencing reveals transcriptional heterogeneity in plant root meristem tissue."],
    )
    s_on, _ = domain.score_similarity(on_topic, vecs)
    s_off, _ = domain.score_similarity(off_topic, vecs)
    assert s_on > s_off
