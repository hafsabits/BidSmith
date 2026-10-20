from datetime import datetime, timezone

from bidsmith import retrieval
from bidsmith.graph.state import RunState
from bidsmith.llm import as_json, get_llm
from bidsmith.schemas import FitAssessment, ProjectHit
from bidsmith.scoring import is_eligible, score_fit
from bidsmith.settings import get_settings

SYSTEM = """You are the bid/no-bid reviewer for a commercial real estate and construction firm.
Score each criterion from 0 (very poor) to 5 (excellent):
- capability: does the scope match the company's services and core building types?
- past_performance: how relevant are the company's OWN past projects listed below?
- geography: is the work in or near the company's operating regions?
- size_vs_bonding: is the project size appropriate for the company's capacity?
- set_aside_eligibility: can the company compete under the set-aside rules (use the eligibility fact given)?
- competition: how strong are likely competitors, judging from the market comparables?
- schedule: is the response window and performance period workable?

Rules:
- Base every score on the facts provided. Cite supporting project ids in evidence_ids; only use ids
  that appear in the lists below. Own projects support past_performance and capability;
  market comparables support competition.
- Never treat a market comparable as the company's own experience.
- Do not compute a total or a decision. Code does that from your scores."""


def _project_lines(projects: list[ProjectHit]) -> str:
    if not projects:
        return "(none)"
    lines = []
    for p in projects:
        value = f"${p.award_value:,.0f}" if p.award_value else "n/a"
        year = p.start_date.year if p.start_date else "n/a"
        lines.append(f"- [{p.id}] owner={p.owner_company_id} | {p.title} | {p.building_type} | {p.state or '??'} | {value} | {year} | sim={p.similarity:.2f}")
    return "\n".join(lines)


def fit(state: RunState) -> dict:
    opp, profile, analysis = state["opportunity"], state["profile"], state["analysis"]
    query = f"{analysis.building_type.replace('_', ' ')} {opp.title}. {analysis.scope_summary}"
    own = retrieval.search_past_performance(profile.id, query, k=8)
    comps = retrieval.search_market_comps(profile.id, query, k=10)
    stats = retrieval.company_stats(profile.id)

    days_left = None
    if opp.response_deadline:
        deadline = opp.response_deadline if opp.response_deadline.tzinfo else opp.response_deadline.replace(tzinfo=timezone.utc)
        days_left = (deadline - datetime.now(timezone.utc)).days
    facts = {
        "set_aside": opp.set_aside or analysis.set_aside,
        "company_eligible_for_set_aside": is_eligible(profile, opp.set_aside or analysis.set_aside),
        "in_operating_region": (analysis.state in profile.regions) if analysis.state else "unknown",
        "days_until_response_deadline": days_left,
        "agency_magnitude_usd": [analysis.magnitude_low, analysis.magnitude_high],
        "company_bonding_capacity_usd": profile.bonding_capacity,
        "company_record_summary": stats,
    }
    user = f"""Company profile:
{as_json(profile.model_dump(include={"name", "description", "naics", "regions", "building_types"}))}

Opportunity analysis:
{as_json(analysis)}

Facts computed by code:
{as_json(facts)}

Company's OWN past projects (most similar first):
{_project_lines(own)}

Market comparables (OTHER firms' awards; competition intelligence only):
{_project_lines(comps)}"""
    assessment, usage = get_llm().structured("fit", get_settings().model_smart, SYSTEM, user, FitAssessment)

    # Drop any evidence id the model did not receive.
    valid = {p.id for p in own} | {p.id for p in comps}
    for s in assessment.scores:
        s.evidence_ids = [e for e in s.evidence_ids if e in valid]

    result = score_fit(assessment, profile, opp, analysis)
    return {
        "own_projects": own,
        "comps": comps,
        "company_stats": stats,
        "fit": result,
        "usage": [usage],
        "trace": [
            {"node": "fit", "message": f"Retrieved {len(own)} own projects and {len(comps)} market comparables"},
            {"node": "fit", "message": f"Score {result.total:.0f}/100 → {result.decision.replace('_', ' ').upper()}"
             + (f" (gate: {result.gates_triggered[0]})" if result.gates_triggered else "")},
        ],
    }
