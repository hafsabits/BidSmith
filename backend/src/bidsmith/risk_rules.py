"""Deterministic risk checks. The risk agent adds qualitative risks on top of these."""

from datetime import datetime, timezone
from statistics import median

from bidsmith.schemas import CompanyProfile, Estimate, Opportunity, Project, RfpAnalysis, RiskItem


def _risk(rid: str, category: str, description: str, likelihood: int, impact: int, mitigation: str) -> RiskItem:
    return RiskItem(
        id=rid,
        category=category,
        description=description,
        likelihood=likelihood,
        impact=impact,
        score=likelihood * impact,
        mitigation=mitigation,
        source="rule",
    )


def rule_risks(
    opportunity: Opportunity,
    analysis: RfpAnalysis,
    profile: CompanyProfile,
    estimate: Estimate | None,
    company_stats: dict,
    comps: list[Project],
    now: datetime | None = None,
) -> list[RiskItem]:
    risks: list[RiskItem] = []
    now = now or datetime.now(timezone.utc)

    deadline = opportunity.response_deadline
    if deadline:
        deadline = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
        days = (deadline - now).days
        if 0 <= days < 14:
            risks.append(_risk("R-DEADLINE", "Schedule", f"Only {days} days until proposals are due.", 4, 3,
                               "Assign a dedicated capture lead; reuse boilerplate; decide on teaming partners this week."))

    if estimate and profile.bonding_capacity:
        if estimate.high > profile.bonding_capacity:
            risks.append(_risk("R-BONDING", "Financial",
                               f"High end of estimate (${estimate.high:,.0f}) exceeds bonding capacity (${profile.bonding_capacity:,.0f}).",
                               4, 5, "Confirm capacity with surety or pursue as a joint venture."))
        elif estimate.total > 0.6 * profile.bonding_capacity:
            risks.append(_risk("R-BONDING-LOAD", "Financial",
                               f"Estimate uses {estimate.total / profile.bonding_capacity:.0%} of single-project bonding capacity.",
                               3, 4, "Check aggregate bonding program against current backlog."))

    own_types = company_stats.get("by_building_type", {})
    if analysis.building_type not in own_types:
        risks.append(_risk("R-NO-PP", "Past performance",
                           f"No {analysis.building_type.replace('_', ' ')} projects in the company's record.", 3, 4,
                           "Team with a firm that has relevant past performance, or cite commercial work of the same type."))

    if analysis.state and profile.regions and analysis.state not in profile.regions:
        risks.append(_risk("R-REGION", "Execution", f"{analysis.state} is outside the company's operating regions.", 3, 3,
                           "Price travel and per diem; identify local subcontractors early."))

    if estimate and estimate.aace_class == 5:
        risks.append(_risk("R-CLASS5", "Estimate", "Building size not stated; estimate is AACE Class 5 with a wide range.", 3, 3,
                           "Submit questions to the contracting officer to confirm program size."))

    if estimate and analysis.magnitude_low and analysis.magnitude_high:
        lo, hi = analysis.magnitude_low, analysis.magnitude_high
        if estimate.total > hi * 1.2 or estimate.total < lo * 0.8:
            risks.append(_risk("R-MAGNITUDE", "Estimate",
                               f"Estimate ${estimate.total:,.0f} is outside the agency magnitude ${lo:,.0f}–${hi:,.0f}.", 3, 4,
                               "Revisit scope assumptions; the agency budget may imply a smaller program or lower quality level."))

    if estimate:
        same_type = [c.award_value for c in comps if c.building_type == analysis.building_type and c.award_value]
        if len(same_type) >= 3:
            m = median(same_type)
            if estimate.total > 2.5 * m or estimate.total < 0.4 * m:
                risks.append(_risk("R-COMPS", "Estimate",
                                   f"Estimate differs sharply from the median of {len(same_type)} comparable awards (${m:,.0f}).", 2, 3,
                                   "Sanity-check scope against comparable awards before pricing."))
    return risks
