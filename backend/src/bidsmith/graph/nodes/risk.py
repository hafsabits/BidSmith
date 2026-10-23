from bidsmith import retrieval
from bidsmith.graph.state import RunState
from bidsmith.llm import as_json, get_llm
from bidsmith.risk_rules import rule_risks
from bidsmith.schemas import QualitativeRisks, RiskItem
from bidsmith.settings import get_settings

SYSTEM = """You are a construction risk manager reviewing a federal solicitation before pricing.
Identify qualitative risks that the rule-based checks below do not already cover: contract terms
(liquidated damages, bonding, warranties), site and phasing constraints, regulatory and design
standards, security, labor, supply chain, and owner/agency risks. Return 3-6 risks.
Likelihood and impact are integers 1-5. Give a concrete mitigation for each."""


def risk(state: RunState) -> dict:
    opp, analysis, profile = state["opportunity"], state["analysis"], state["profile"]
    est = state.get("estimate")
    # Run on its own, the bid review hasn't loaded the company record yet; fetch it here.
    stats = state.get("company_stats") or retrieval.company_stats(profile.id)
    rules = rule_risks(opp, analysis, profile, est, stats, state.get("comps", []))
    estimate_summary = (
        {"class": est.aace_class, "total": round(est.total), "low": round(est.low), "high": round(est.high), "assumptions": est.assumptions}
        if est
        else None
    )
    user = f"""Solicitation text:
<solicitation>
{opp.description}
</solicitation>

Analysis:
{as_json(analysis)}

Estimate summary:
{as_json(estimate_summary)}

Risks already flagged by rule-based checks (do not repeat):
{as_json([r.description for r in rules])}"""
    qualitative, usage = get_llm().structured("risk", get_settings().model_smart, SYSTEM, user, QualitativeRisks)
    llm_risks = []
    for i, q in enumerate(qualitative.risks, start=1):
        likelihood, impact = max(1, min(5, q.likelihood)), max(1, min(5, q.impact))
        llm_risks.append(
            RiskItem(
                id=f"R-Q{i}",
                category=q.category,
                description=q.description,
                likelihood=likelihood,
                impact=impact,
                score=likelihood * impact,
                mitigation=q.mitigation,
                source="llm",
            )
        )
    register = sorted(rules + llm_risks, key=lambda r: -r.score)
    high = sum(1 for r in register if r.score >= 12)
    return {
        "risks": register,
        "usage": [usage],
        "trace": [{"node": "risk", "message": f"{len(rules)} rule-based + {len(llm_risks)} qualitative risks ({high} high)"}],
    }
