"""Fakes shared by graph and API tests: no API calls, no database."""

from bidsmith.profiles import DEFAULT_WEIGHTS
from bidsmith.schemas import (
    CriterionScore,
    FitAssessment,
    ProjectHit,
    ProposalDraft,
    ProposalSection,
    QualitativeRisk,
    QualitativeRisks,
    RfpExtraction,
    UsageRecord,
)


def usage(node):
    return UsageRecord(node=node, model="fake", input_tokens=10, output_tokens=5, cost_usd=0.0)


class FakeLLM:
    def __init__(self, score: int):
        self.score = score

    def structured(self, node, model, system, user, schema, **kw):
        if schema is RfpExtraction:
            out = RfpExtraction(
                scope_summary="New outpatient clinic",
                building_type="medical_office",
                gross_sf=45_000,
                sf_is_stated=True,
                assumed_sf_if_missing=0,
                city="",
                state="mn",
                quality="typical",
                construction_start_year=2027,
                duration_months=20,
                magnitude_low=25_000_000,
                magnitude_high=50_000_000,
                set_aside="",
                delivery_method="design-build",
                evaluation_criteria=[],
                special_requirements=[],
                key_requirements=[],
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
