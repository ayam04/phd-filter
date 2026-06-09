from feedback.ingest import read_outcomes
from feedback.learn import learn


def _write_csv(tmp_path):
    p = tmp_path / "outcomes.csv"
    p.write_text(
        "student_id, supervisor_id, institution, area, sent_at, outcome\n"
        "106419, A100, UNSW, PTSD, 2026-07-12, ADMIT\n"
        "106419, A101, UNSW, PTSD, 2026-07-12, INTERVIEW\n"
        "106419, A200, Ohio State, Pilgrim, 2026-07-12, WRONG_PERSON\n"
        "106419, A201, Ohio State, Pilgrim, 2026-07-12, NO_REPLY\n"
        "106419, A202, Ohio State, Pilgrim, 2026-07-12, BOUNCE\n",
        encoding="utf-8",
    )
    return p


def test_read_outcomes_handles_spaces(tmp_path):
    rows = read_outcomes(_write_csv(tmp_path))
    assert len(rows) == 5
    assert rows[0]["supervisor_id"] == "A100"
    assert rows[2]["outcome"] == "WRONG_PERSON"


def test_learn_suppresses_and_uplifts(tmp_path):
    adj = learn(read_outcomes(_write_csv(tmp_path)))
    assert "A200" in adj["suppress"]
    assert "A202" in adj["suppress"]
    assert "A200" in adj["wrong_person_ids"]
    assert adj["area_institution_uplift"]["PTSD::UNSW"] > 0
    assert adj["area_institution_uplift"]["Pilgrim::Ohio State"] < 0
