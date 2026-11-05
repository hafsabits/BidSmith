"""Bid/no-bid rules. Plain Python: no AI, so every decision is testable and repeatable.

Each check looks at one thing. It returns a sentence describing the problem,
or None when there's no problem (including when the RFP didn't give us the information).
"""

from datetime import date

from app.schemas import Company, Decision, RfpFacts


def check_set_aside(facts: RfpFacts, company: Company) -> str | None:
    if facts.set_aside == "none":
        return None
    if facts.set_aside in company.eligible_set_asides:
        return None
    return f"Reserved for '{facts.set_aside}' businesses, and {company.name} is not eligible."


def check_bonding(facts: RfpFacts, company: Company) -> str | None:
    if facts.value_low_usd is None:
        return None
    if facts.value_low_usd > company.bonding_capacity_usd:
        return (
            f"Even the low end of the project value (${facts.value_low_usd:,.0f}) is more than "
            f"{company.name}'s bonding capacity (${company.bonding_capacity_usd:,.0f})."
        )
    return None


def check_deadline(facts: RfpFacts, today: date) -> str | None:
    if facts.response_deadline is None:
        return None
    if facts.response_deadline < today:
        return f"The response deadline ({facts.response_deadline}) has already passed."
    return None


def check_region(facts: RfpFacts, company: Company) -> str | None:
    if facts.state is None:
        return None
    if facts.state not in company.states:
        return f"The work is in {facts.state}, outside the states where {company.name} operates."
    return None


def decide(facts: RfpFacts, company: Company, today: date | None = None) -> Decision:
    today = today or date.today()
    results = [
        check_set_aside(facts, company),
        check_bonding(facts, company),
        check_deadline(facts, today),
        check_region(facts, company),
    ]
    problems = [r for r in results if r is not None]
    if problems:
        return Decision(verdict="no_bid", reasons=problems)
    return Decision(
        verdict="bid",
        reasons=["Passed every check: set-aside eligibility, bonding capacity, deadline, and region."],
    )