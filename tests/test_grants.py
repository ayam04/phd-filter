import pytest

from src.sources import grants

REQUIRED_KEYS = {
    "title", "funder", "award_id", "url",
    "pi_names", "is_personal_fellowship", "source",
}


def _check_shape(rows, source):
    assert isinstance(rows, list)
    for row in rows:
        assert set(row.keys()) == REQUIRED_KEYS
        assert isinstance(row["title"], str)
        assert row["funder"] is None or isinstance(row["funder"], str)
        assert row["award_id"] is None or isinstance(row["award_id"], str)
        assert isinstance(row["url"], str)
        assert isinstance(row["pi_names"], list)
        assert isinstance(row["is_personal_fellowship"], bool)
        assert row["source"] == source


@pytest.mark.live
def test_nih_reporter_live():
    rows = grants.nih_reporter("post-traumatic stress disorder", limit=10)
    assert isinstance(rows, list)
    assert len(rows) > 0
    _check_shape(rows, "nih")


@pytest.mark.live
def test_ukri_gtr_live():
    rows = grants.ukri_gtr("post-traumatic stress disorder", limit=10)
    assert isinstance(rows, list)
    assert len(rows) > 0
    _check_shape(rows, "ukri")


@pytest.mark.live
def test_openaire_live():
    rows = grants.openaire("trauma", "AU", limit=10)
    _check_shape(rows, "openaire")


def test_nih_flags_f32_not_r01():
    code_f32 = grants._activity_code("5F32MH123456-01", None)
    assert code_f32 == "F32"
    assert grants._nih_is_fellowship(code_f32, []) is True

    code_r01 = grants._activity_code("5R01MH123456-01", None)
    assert code_r01 == "R01"
    assert grants._nih_is_fellowship(code_r01, []) is False
