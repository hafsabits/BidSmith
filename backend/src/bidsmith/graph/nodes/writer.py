import re

from bidsmith import retrieval
from bidsmith.graph.state import RunState
from bidsmith.llm import as_json, get_llm
from bidsmith.schemas import Estimate, ProposalDraft
from bidsmith.settings import get_settings

SYSTEM = """You are a proposal writer for a commercial real estate and construction firm responding to
a federal solicitation. Write a first-draft technical proposal with these sections, in order:
1. Executive Summary
2. Understanding of the Project
3. Technical Approach
4. Past Performance
5. Management Approach and Schedule
6. Risk Management
7. Rough Order of Magnitude Price

Hard rules:
- Past Performance may cite ONLY the company's own projects listed below, by their [id], using only
  facts given for them. List every id you cite in cited_project_ids. If the list is thin, say so plainly
  and propose a mitigation (e.g. a teaming partner) instead of inventing experience.
- Never write dollar amounts or square-foot costs yourself. In the price section use these tokens,
  which code will replace: {{TOTAL}}, {{LOW}}, {{HIGH}}, {{COST_PER_SF}}, {{AACE_CLASS}}, {{PRICE_TABLE}}.
- For anything you do not know (names of key personnel, specific dates, certifications), write
  [PLACEHOLDER — what is needed] and list each placeholder in placeholders.
- Mirror the solicitation's evaluation factors in the order they are listed.
- Write in confident, specific, plain language. Markdown is fine inside sections; no top-level # headings."""


def price_table(est: Estimate) -> str:
    rows = ["| CSI Division | Amount | Share |", "|---|---:|---:|"]
    for line in est.lines:
        rows.append(f"| {line.division} {line.name} | ${line.amount:,.0f} | {line.pct:.0%} |")
    rows.append(f"| **Hard cost subtotal** | **${est.hard_cost:,.0f}** | |")
    for m in est.markups:
        rows.append(f"| {m.name} | ${m.amount:,.0f} | {m.pct:.0%} of hard cost |")
    rows.append(f"| **Total (point estimate)** | **${est.total:,.0f}** | |")
    return "\n".join(rows)


def fill_price_tokens(text: str, est: Estimate | None) -> str:
    if est is None:
        # Writer ran without the estimator: leave visible placeholders instead of numbers.
        return re.sub(r"\{\{(\w+)\}\}", "[PLACEHOLDER — run the Estimator for pricing]", text)
    values = {
        "TOTAL": f"${est.total:,.0f}",
        "LOW": f"${est.low:,.0f}",
        "HIGH": f"${est.high:,.0f}",
        "COST_PER_SF": f"${est.cost_per_sf:,.0f}/SF",
        "AACE_CLASS": f"Class {est.aace_class}",
        "PRICE_TABLE": price_table(est),
    }
    return re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), m.group(0)), text)


def render_markdown(state: RunState, draft: ProposalDraft) -> str:
    opp, profile = state["opportunity"], state["profile"]
    parts = [
        f"# Proposal: {opp.title}",
        f"**Offeror:** {profile.name}  \n**Solicitation:** {opp.solicitation_number or opp.notice_id}  \n**Agency:** {opp.agency or 'n/a'}",
        "> AI-generated first draft. Verify every fact and replace all placeholders before submission.",
    ]
    for section in draft.sections:
        parts.append(f"## {section.title}\n\n{fill_price_tokens(section.body_markdown, state.get('estimate'))}")
    return "\n\n".join(parts) + "\n"


def writer(state: RunState) -> dict:
    opp, profile, analysis = state["opportunity"], state["profile"], state["analysis"]
    fit, est = state.get("fit"), state.get("estimate")
    own = state.get("own_projects")
    if own is None:  # running without the bid review: retrieve past performance directly
        own = retrieval.search_past_performance(profile.id, f"{analysis.building_type.replace('_', ' ')} {opp.title}. {analysis.scope_summary}", k=8)
    own_facts = [
        p.model_dump(include={"id", "title", "client", "award_value", "start_date", "end_date", "state", "building_type", "description"})
        for p in own
    ]
    user = f"""Company:
{as_json(profile.model_dump(include={"name", "description", "regions", "building_types"}))}

Solicitation:
{as_json(opp.model_dump(include={"title", "solicitation_number", "agency", "set_aside", "place_city", "place_state"}))}
<solicitation>
{opp.description}
</solicitation>

Analysis:
{as_json(analysis)}

Bid review strengths: {as_json(fit.strengths if fit else "bid review not run")}
Bid review concerns: {as_json(fit.concerns if fit else "bid review not run")}
Human reviewer note: {state.get("human_note") or "none"}

Company's OWN past projects (the only ones you may cite):
{as_json(own_facts)}

Estimate assumptions (for narrative only; use tokens for numbers):
{as_json(est.assumptions if est else [])}

Top risks and mitigations:
{as_json([{"risk": r.description, "mitigation": r.mitigation} for r in state.get("risks", [])[:6]])}"""
    draft, usage = get_llm().structured("writer", get_settings().model_smart, SYSTEM, user, ProposalDraft, max_tokens=24000)

    own_ids = {p.id for p in own}
    invalid = [c for c in draft.cited_project_ids if c not in own_ids]
    draft.cited_project_ids = [c for c in draft.cited_project_ids if c in own_ids]
    trace = [{"node": "writer", "message": f"Drafted {len(draft.sections)} sections citing {len(draft.cited_project_ids)} own projects; {len(draft.placeholders)} placeholders"}]
    if invalid:
        trace.append({"node": "writer", "message": f"Removed {len(invalid)} citation(s) to projects the company does not own"})
    return {"proposal": draft, "proposal_markdown": render_markdown(state, draft), "usage": [usage], "trace": trace}
