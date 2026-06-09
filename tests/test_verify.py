import pytest

from src import verify
from src.config import OPENROUTER_API_KEY
from src.schema import Area, Candidate, StudentProfile

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not OPENROUTER_API_KEY, reason="no OPENROUTER_API_KEY"),
]


def _profile(area_name, discipline, region="global", terms=None):
    return StudentProfile(
        student_id="t",
        target_countries=["United States"],
        areas=[Area(name=area_name, discipline=discipline, region_hint=region,
                    query_terms=terms or [area_name])],
    )


def _cand(abstract, name="Dr Test"):
    return Candidate(
        author_id="A1", name=name, institution="Test University", country="us",
        affiliation_raw="Professor, Department", works_count=60, last_author_count=5,
        first_pub_year=2006, h_index=30, abstracts=[abstract],
    )


def test_trauma_informed_roman_antiquity_rejected():
    profile = _profile("PTSD treatment", "clinical psychology", terms=["post-traumatic stress disorder"])
    cand = _cand(
        "This project is a literary-historical study of the rhetoric of grief and mourning in "
        "Roman antiquity, examining trauma-informed readings of Latin elegiac poetry and Senecan "
        "consolation literature in the early imperial period."
    )
    v = verify.verify_raw(cand, profile)
    assert verify.accept(v) is False


def test_dna_barcoding_singlecell_rejected_for_plant_biology():
    profile = _profile("plant biology", "plant biology / botany", terms=["plant species DNA barcoding"])
    cand = _cand(
        "We present a single-cell DNA barcoding method for Hi-C chromatin conformation capture in "
        "human cell lines, enabling high-resolution mapping of 3D genome architecture and "
        "topologically associating domains."
    )
    v = verify.verify_raw(cand, profile)
    assert verify.accept(v) is False


def test_high_elevation_fire_archaeology_rejected_for_himalayan_pilgrimage():
    profile = _profile("Himalayan pilgrimage", "religious studies / anthropology", region="Himalaya / South Asia",
                        terms=["Himalayan pilgrimage routes"])
    cand = _cand(
        "Using paleo-fire records and charcoal sedimentary analysis, this study reconstructs the "
        "fire history of high-elevation social-ecological systems in the Pacific Northwest of North "
        "America over the Holocene."
    )
    v = verify.verify_raw(cand, profile)
    assert verify.accept(v) is False


def test_genuine_ptsd_pi_accepted():
    profile = _profile("PTSD treatment", "clinical psychology", terms=["post-traumatic stress disorder treatment"])
    cand = _cand(
        "A randomized controlled trial comparing prolonged exposure therapy and cognitive "
        "processing therapy for post-traumatic stress disorder in military veterans, with "
        "twelve-month follow-up on symptom remission."
    )
    v = verify.verify_raw(cand, profile)
    assert verify.accept(v) is True
