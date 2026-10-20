"""End-to-end graph test with a fake LLM and fake retrieval (no API calls, no database)."""

import pytest

from bidsmith import retrieval
from bidsmith.graph import runner
from bidsmith.llm import set_llm
from bidsmith.profiles import DEFAULT_WEIGHTS
from bidsmith.schemas import (
    CriterionScore,
    FitAssessment,
    ProjectHit,
    ProposalDraft,
    ProposalSection,
    QualitativeRisk,
    QualitativeRisks,
    RfpAnalysis,
    UsageRecord,
)


def usage(node):
    return UsageRecord(node=node, model="fake", input_tokens=10, output_tokens=5, cost_usd=0.0)


class FakeLLM:
    def __init__(self, score: int):
        self.score = score

    def structured(self, node, model, system, user, schema, **kw):
        if schema is RfpAnalysis:
            out = RfpAnalysis(
                scope_summary="New outpatient clinic",
                building_type="medical_office",
                gross_sf=45_000,
                sf_is_stated=True,
                state="MN",
                construction_start_year=2027,
                duration_months=20,
                magnitude_low=25_000_000,
                magnitude_high=50_000_000,
                delivery_method="design-build",
            )
        elif schema is FitAssessment:
            out = FitAssessment(
                scores=[CriterionScore(criterion=c, score=self.score, rationale="r", evidence_ids=["own-1", "made-up"]) for c in DEFAULT_WEIGHTS],
                summary="ok",
                strengths=["s"],
                concerns=["c"],
            )
        elif schema is QualitativeRisks:
            out = QualitativeRisks(risks=[QualitativeRisk(category="Contract", description="LDs", likelihood=3, impact=4, mitigation="m")])
        elif schema is ProposalDraft:
            out = ProposalDraft(
                sections=[ProposalSection(title="Rough Order of Magnitude Price", body_markdown="Total {{TOTAL}} ({{AACE_CLASS}})\n\n{{PRICE_TABLE}}")],
                cited_project_ids=["own-1", "peer-1"],
                placeholders=[],
            )
        else:
            raise AssertionError(schema)
        return out, usage(node)

    def tool_loop(self, node, model, system, user, tools, handlers, on_tool_call=None, **kw):
        args = {"building_type": "medical_office", "gross_sf": 45_000, "sf_assumed": False, "state": "MN",
                "quality": "typical", "construction_midpoint_year": 2027.9, "design_build": True}
        out = handlers["run_estimate"](args)
        if on_tool_call:
            on_tool_call("run_estimate", args, out)
        return "Chose typical quality.", usage(node)


def hit(pid, owner):
    return ProjectHit(id=pid, owner_company_id=owner, source="test", title=pid, building_type="medical_office", similarity=0.9, award_value=30_000_000)


@pytest.fixture(autouse=True)
def fake_retrieval(monkeypatch):
    monkeypatch.setattr(retrieval, "search_past_performance", lambda cid, q, k=8: [hit("own-1", cid)])
    monkeypatch.setattr(retrieval, "search_market_comps", lambda cid, q, k=10: [hit("peer-1", "other")])
    monkeypatch.setattr(retrieval, "company_stats", lambda cid: {"by_building_type": {"medical_office": 1}})
    runner.get_graph.cache_clear()
    yield
    set_llm(None)


def test_bid_path_runs_all_agents():
    set_llm(FakeLLM(score=4))
    thread_id, state = runner.start_run("SAMPLE-001", "ryan")
    assert runner.is_waiting_for_review(thread_id)
    assert state["fit"].decision == "bid"
    # invented evidence id is dropped
    assert state["fit"].scores[0].evidence_ids == ["own-1"]

    state = runner.resume_run(thread_id, {"decision": "bid", "note": "go"})
    assert state["estimate"].aace_class == 4
    assert state["risks"]
    md = state["proposal_markdown"]
    assert "{{" not in md and "$" in md and "Class 4" in md
    # writer may not cite another firm's project
    assert state["proposal"].cited_project_ids == ["own-1"]
    assert {u.node for u in state["usage"]} == {"analyst", "fit", "estimator", "risk", "writer"}


def test_no_bid_stops_after_review():
    set_llm(FakeLLM(score=1))
    thread_id, state = runner.start_run("SAMPLE-001", "ryan")
    assert state["fit"].decision == "no_bid"
    state = runner.resume_run(thread_id, {"decision": "no_bid"})
    assert "estimate" not in state and "proposal" not in state
