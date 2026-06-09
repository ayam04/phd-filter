import pytest

from src.sources import email_finder as ef


def test_find_email_none():
    assert ef.find_email(None) is None


def test_find_email_empty():
    assert ef.find_email("") is None


def test_bare_orcid_from_url():
    assert ef.bare_orcid("https://orcid.org/0000-0002-1825-0097") == "0000-0002-1825-0097"
    assert ef.bare_orcid("0000-0002-1825-0097") == "0000-0002-1825-0097"
    assert ef.bare_orcid(None) is None


@pytest.mark.live
def test_find_email_demo_orcid_shape():
    email = ef.find_email("0000-0002-1825-0097")
    assert email is None or isinstance(email, str)
