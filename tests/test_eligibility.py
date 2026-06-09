import pytest

from src.config import OPENROUTER_API_KEY
from src.filters import eligibility as el


@pytest.mark.live
@pytest.mark.skipif(not OPENROUTER_API_KEY, reason="no OPENROUTER_API_KEY")
def test_uk_home_only_blocks_international_indian():
    ad = (
        "PhD Studentship in Materials Science. This fully-funded studentship covers UK/home "
        "tuition fees and a stipend. Applicants must be UK/home students; the funding does not "
        "cover international fees."
    )
    elig = el.extract_eligibility(ad)
    assert elig.get("home_or_domestic_only") is True
    assert el.eligible(elig, "Indian", "gb") is False


@pytest.mark.live
@pytest.mark.skipif(not OPENROUTER_API_KEY, reason="no OPENROUTER_API_KEY")
def test_international_welcome_allows_indian():
    ad = (
        "PhD position in computational biology. We welcome applications from candidates of all "
        "nationalities; full funding is available to domestic and international students alike."
    )
    elig = el.extract_eligibility(ad)
    assert el.eligible(elig, "Indian", "gb") is True


def test_eligible_defaults_open_when_no_constraints():
    assert el.eligible({}, "Indian", "gb") is True
