import pytest

from src.sources import openalex as oa


@pytest.mark.live
async def test_search_works_returns_authors_and_country():
    works = await oa.fetch_works(
        "post-traumatic stress disorder treatment", ["us", "gb", "au"], 8, 25
    )
    assert len(works) > 5
    w = works[0]
    assert "authorships" in w
    countries = {
        (inst.get("country_code") or "").lower()
        for a in w["authorships"]
        for inst in a.get("institutions", [])
    }
    assert countries & {"us", "gb", "au"}


@pytest.mark.live
async def test_fetch_author_has_career_signals():
    works = await oa.fetch_works("clinical psychology trauma", ["us"], 8, 10)
    last = None
    for w in works:
        for a in w["authorships"]:
            if a["author"].get("id"):
                last = a["author"]["id"]
    author = await oa.fetch_author(last)
    assert "summary_stats" in author
    assert oa.first_pub_year(author) is not None
    assert author.get("works_count", 0) >= 0


def test_decode_abstract():
    inv = {"PTSD": [0, 3], "is": [1], "common": [2]}
    assert oa.decode_abstract(inv) == "PTSD is common PTSD"


def test_work_topic_and_grants():
    work = {
        "id": "https://openalex.org/W1",
        "primary_topic": {"field": {"display_name": "Psychology"}, "domain": {"display_name": "Social Sciences"}},
        "awards": [{"funder_display_name": "NIH", "funder_award_id": "R01XYZ", "funder_id": "https://openalex.org/F1"}],
    }
    assert oa.work_topic(work) == ("Psychology", "Social Sciences")
    g = oa.work_grants(work)[0]
    assert g["funder"] == "NIH" and g["award_id"] == "R01XYZ" and g["url"].startswith("https://")
