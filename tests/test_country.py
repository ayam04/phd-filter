from src.filters.country import passes_country
from src.schema import Candidate


def test_in_target_country_passes():
    c = Candidate(author_id="A1", name="X", country="us")
    assert passes_country(c, ["us", "gb", "au"]) is True


def test_out_of_target_country_fails():
    c = Candidate(author_id="A1", name="X", country="de")
    assert passes_country(c, ["us", "gb", "au"]) is False


def test_missing_country_fails():
    c = Candidate(author_id="A1", name="X", country="")
    assert passes_country(c, ["us"]) is False
