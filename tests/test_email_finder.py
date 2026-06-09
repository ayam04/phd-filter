import pytest

from src.sources import email_finder as ef


def test_find_email_none():
    assert ef.find_email(None) == (None, False)


def test_find_email_empty():
    assert ef.find_email("") == (None, False)


def test_bare_orcid_from_url():
    assert ef.bare_orcid("https://orcid.org/0000-0002-1825-0097") == "0000-0002-1825-0097"
    assert ef.bare_orcid("0000-0002-1825-0097") == "0000-0002-1825-0097"
    assert ef.bare_orcid(None) is None


@pytest.mark.live
def test_find_email_demo_orcid_shape():
    email, is_guess = ef.find_email("0000-0002-1825-0097")
    assert isinstance(is_guess, bool)
    assert email is None or isinstance(email, str)
    assert is_guess is False


@pytest.mark.live
def test_orcid_role_title_demo():
    title = ef.orcid_role_title("0000-0002-1825-0097")
    assert title is None or (isinstance(title, str) and "Professor" in title)
