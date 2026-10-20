from datetime import datetime, timedelta, timezone

from bidsmith.estimating.engine import estimate
from bidsmith.profiles import DEFAULT_WEIGHTS
from bidsmith.risk_rules import rule_risks
from bidsmith.schemas import (
    CompanyProfile,
    CriterionScore,
    EstimateInputs,
    FitAssessment,
    Opportunity,
    RfpAnalysis,
)
from bidsmith.scoring import is_eligible, score_fit, set_aside_category, weighted_total

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def profile(**kw) -> CompanyProfile:
    return CompanyProfile(
        **{
            "id": "co",
            "name": "Co",
            "regions": ["MN"],
            "bonding_capacity": 100_000_000,
            "weights": DEFAULT_WEIGHTS,
            **kw,
        }
    )


def opportunity(**kw) -> Opportunity:
    return Opportunity(**{"notice_id": "X", "title": "T", "response_deadline": NOW + timedelta(days=30), **kw})


def analysis(**kw) -> RfpAnalysis:
    return RfpAnalysis(**{"scope_summary": "s", "building_type": "office", "sf_is_stated": True, "gross_sf": 50_000, "state": "MN", **kw})


def assessment(score: int) -> FitAssessment:
    return FitAssessment(
        scores=[CriterionScore(criterion=c, score=score, rationale="r", evidence_ids=[]) for c in DEFAULT_WEIGHTS],
        summary="s",
        strengths=[],
        concerns=[],
    )


def test_weighted_total_bounds():
    assert weighted_total(assessment(5), DEFAULT_WEIGHTS) == 100
    assert weighted_total(assessment(0), DEFAULT_WEIGHTS) == 0
    assert weighted_total(assessment(9), DEFAULT_WEIGHTS) == 100  # clamped


def test_thresholds():
    p = profile()
    assert score_fit(assessment(4), p, opportunity(), analysis(), NOW).decision == "bid"  # 80
    assert score_fit(assessment(3), p, opportunity(), analysis(), NOW).decision == "review"  # 60
    assert score_fit(assessment(2), p, opportunity(), analysis(), NOW).decision == "no_bid"  # 40


def test_set_aside_gate_overrides_high_score():
    result = score_fit(assessment(5), profile(), opportunity(set_aside="Total Small Business Set-Aside (FAR 19.5)"), analysis(), NOW)
    assert result.decision == "no_bid"
    assert result.gates_triggered


def test_set_aside_categories():
    assert set_aside_category("Service-Disabled Veteran-Owned Small Business Set-Aside") == "sdvosb"
    assert set_aside_category("Total Small Business Set-Aside (FAR 19.5)") == "small_business"
    assert set_aside_category(None) is None
    assert is_eligible(profile(set_aside_eligibility=["small_business"]), "Total Small Business Set-Aside (FAR 19.5)")
    assert not is_eligible(profile(set_aside_eligibility=["small_business"]), "SDVOSB Set-Aside")


def test_bonding_and_deadline_gates():
    big = analysis(magnitude_low=200_000_000, magnitude_high=300_000_000)
    assert score_fit(assessment(5), profile(), opportunity(), big, NOW).decision == "no_bid"
    past = opportunity(response_deadline=NOW - timedelta(days=1))
    assert "passed" in score_fit(assessment(5), profile(), past, analysis(), NOW).gates_triggered[0]


def test_rule_risks_fire():
    a = analysis(state="TX", building_type="hospital", magnitude_low=1_000_000, magnitude_high=2_000_000)
    est = estimate(EstimateInputs(building_type="hospital", gross_sf=200_000, sf_assumed=True, state="TX", construction_midpoint_year=2027.5))
    risks = rule_risks(
        opportunity(response_deadline=NOW + timedelta(days=5)),
        a,
        profile(),
        est,
        {"by_building_type": {"office": 3}},
        [],
        NOW,
    )
    ids = {r.id for r in risks}
    assert {"R-DEADLINE", "R-BONDING", "R-NO-PP", "R-REGION", "R-CLASS5", "R-MAGNITUDE"} <= ids
    assert all(r.score == r.likelihood * r.impact for r in risks)
