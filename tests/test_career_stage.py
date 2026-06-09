from src.config import CURRENT_YEAR
from src.filters import career_stage as cs
from src.schema import Candidate, GrantEvidence


def _cand(**kw):
    base = dict(author_id="A1", name="X")
    base.update(kw)
    return Candidate(**base)


def test_grad_student_rejected():
    c = _cand(first_pub_year=CURRENT_YEAR - 2, works_count=3, last_author_count=0)
    ok, _ = cs.is_pi(c)
    assert ok is False


def test_trainee_affiliation_rejected_even_if_record_looks_ok():
    c = _cand(
        first_pub_year=CURRENT_YEAR - 8, works_count=20, last_author_count=2,
        affiliation_raw="PhD student, Department of Psychology",
    )
    ok, reason = cs.is_pi(c)
    assert ok is False
    assert "trainee" in reason


def test_senior_pi_accepted():
    c = _cand(first_pub_year=2005, works_count=80, last_author_count=6, recent_works=12)
    ok, _ = cs.is_pi(c)
    assert ok is True


def test_pi_score_orders_senior_above_junior():
    junior = _cand(first_pub_year=CURRENT_YEAR - 2, works_count=3, last_author_count=0)
    senior = _cand(first_pub_year=2005, works_count=80, last_author_count=6, recent_works=12)
    assert cs.pi_score(senior) > cs.pi_score(junior)


def test_fellowship_awardee_trap():
    fellow = [GrantEvidence(title="F32 award", url="https://x", is_personal_fellowship=True)]
    research = [GrantEvidence(title="R01 award", url="https://x", is_personal_fellowship=False)]
    assert cs.fellowship_awardee(fellow) is True
    assert cs.fellowship_awardee(research) is False
