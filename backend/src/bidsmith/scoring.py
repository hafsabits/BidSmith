"""Bid/no-bid math. The fit agent supplies per-criterion scores with evidence;
this module applies weights, hard gates, and thresholds."""

import re
from datetime import datetime, timezone

from bidsmith.schemas import CompanyProfile, Decision, FitAssessment, FitResult, Opportunity, RfpAnalysis

SET_ASIDE_CATEGORIES = [
    # (category, substrings that identify it); checked in order, most specific first
    ("sdvosb", ("service-disabled", "sdvosb")),
    ("vosb", ("veteran-owned", "vosb")),
    ("wosb", ("women-owned", "wosb", "edwosb")),
    ("hubzone", ("hubzone",)),
    ("8a", ("8(a)", "8a")),
    ("isbee", ("indian small business", "isbee", "buy indian")),
    ("small_business", ("small business", "sba", "19.5")),
]


def set_aside_category(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower()
    if "none" in lowered or "full and open" in lowered or re.search(r"\bno set[- ]?aside", lowered):
        return None
    for category, needles in SET_ASIDE_CATEGORIES:
        if any(n in lowered for n in needles):
            return category
    return "other"


def is_eligible(profile: CompanyProfile, set_aside: str | None) -> bool:
    category = set_aside_category(set_aside)
    if category is None:
        return True
    return category in {c.lower() for c in profile.set_aside_eligibility}


def weighted_total(assessment: FitAssessment, weights: dict[str, float]) -> float:
    by_criterion = {s.criterion: max(0, min(5, s.score)) for s in assessment.scores}
    weight_sum = sum(weights.values())
    total = sum(w * by_criterion.get(c, 0) / 5 for c, w in weights.items())
    return round(100 * total / weight_sum, 1) if weight_sum else 0.0


def hard_gates(
    profile: CompanyProfile, opportunity: Opportunity, analysis: RfpAnalysis, now: datetime | None = None
) -> list[str]:
    gates = []
    set_aside = opportunity.set_aside or analysis.set_aside
    if not is_eligible(profile, set_aside):
        gates.append(f"Set-aside '{set_aside}' and {profile.name} is not eligible.")
    if analysis.magnitude_low and profile.bonding_capacity and analysis.magnitude_low > profile.bonding_capacity:
        gates.append(
            f"Low end of agency magnitude (${analysis.magnitude_low:,.0f}) exceeds bonding capacity (${profile.bonding_capacity:,.0f})."
        )
    now = now or datetime.now(timezone.utc)
    deadline = opportunity.response_deadline
    if deadline and (deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)) < now:
        gates.append("Response deadline has passed.")
    return gates


def decide(total: float, gates: list[str], profile: CompanyProfile) -> Decision:
    if gates:
        return "no_bid"
    if total >= profile.bid_threshold:
        return "bid"
    if total >= profile.review_threshold:
        return "review"
    return "no_bid"


def score_fit(
    assessment: FitAssessment,
    profile: CompanyProfile,
    opportunity: Opportunity,
    analysis: RfpAnalysis,
    now: datetime | None = None,
) -> FitResult:
    total = weighted_total(assessment, profile.weights)
    gates = hard_gates(profile, opportunity, analysis, now)
    return FitResult(
        total=total,
        decision=decide(total, gates, profile),
        gates_triggered=gates,
        scores=assessment.scores,
        summary=assessment.summary,
        strengths=assessment.strengths,
        concerns=assessment.concerns,
    )
