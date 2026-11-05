"""Each test is one concrete example of a rule. Run with: python -m pytest"""

from datetime import date

from app.rules import decide
from app.schemas import Company, RfpFacts

TODAY = date(2026, 11, 5)

COMPANY = Company(
    name="Test Co",
    eligible_set_asides=[],
    bonding_capacity_usd=100_000_000,
    states=["MN", "WI"],
)


def make_facts(**changes) -> RfpFacts:
    """A good RFP that should pass every check. Each test changes only what it's testing."""
    base = dict(
        summary="New office building in Minneapolis.",
        building_type="office",
        city="Minneapolis",
        state="MN",
        set_aside="none",
        value_low_usd=10_000_000,
        value_high_usd=20_000_000,
        response_deadline=date(2026, 12, 1),
    )
    base.update(changes)
    return RfpFacts(**base)


def test_good_rfp_is_a_bid():
    decision = decide(make_facts(), COMPANY, TODAY)
    assert decision.verdict == "bid"


def test_set_aside_company_is_not_eligible_for():
    decision = decide(make_facts(set_aside="sdvosb"), COMPANY, TODAY)
    assert decision.verdict == "no_bid"
    assert "sdvosb" in decision.reasons[0]


def test_set_aside_company_is_eligible_for():
    eligible = COMPANY.model_copy(update={"eligible_set_asides": ["small_business"]})
    decision = decide(make_facts(set_aside="small_business"), eligible, TODAY)
    assert decision.verdict == "bid"


def test_project_bigger_than_bonding_capacity():
    decision = decide(make_facts(value_low_usd=150_000_000), COMPANY, TODAY)
    assert decision.verdict == "no_bid"
    assert "bonding" in decision.reasons[0]


def test_deadline_already_passed():
    decision = decide(make_facts(response_deadline=date(2026, 11, 1)), COMPANY, TODAY)
    assert decision.verdict == "no_bid"
    assert "passed" in decision.reasons[0]


def test_deadline_today_is_still_open():
    decision = decide(make_facts(response_deadline=TODAY), COMPANY, TODAY)
    assert decision.verdict == "bid"


def test_work_outside_company_states():
    decision = decide(make_facts(state="CA"), COMPANY, TODAY)
    assert decision.verdict == "no_bid"
    assert "CA" in decision.reasons[0]


def test_missing_information_is_not_a_problem():
    facts = make_facts(state=None, value_low_usd=None, response_deadline=None)
    decision = decide(facts, COMPANY, TODAY)
    assert decision.verdict == "bid"


def test_every_problem_is_reported():
    facts = make_facts(set_aside="8a", state="CA", response_deadline=date(2026, 1, 1))
    decision = decide(facts, COMPANY, TODAY)
    assert decision.verdict == "no_bid"
    assert len(decision.reasons) == 3