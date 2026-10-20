"""Shared data contracts.

Everything that crosses a boundary (data source -> DB, agent -> agent, backend -> frontend)
is one of these models. LLM-facing models are kept to simple types so they work as
structured-output schemas.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

BuildingType = Literal[
    "office",
    "warehouse",
    "manufacturing",
    "medical_office",
    "hospital",
    "laboratory",
    "senior_living",
    "multifamily",
    "retail",
    "data_center",
    "parking_garage",
    "education",
    "public_safety",
    "other",
]

Quality = Literal["low", "typical", "high"]

Criterion = Literal[
    "capability",
    "past_performance",
    "geography",
    "size_vs_bonding",
    "set_aside_eligibility",
    "competition",
    "schedule",
]

Decision = Literal["bid", "review", "no_bid"]


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


class Project(BaseModel):
    """A past project or award, normalized from any data source."""

    id: str
    owner_company_id: str
    source: str  # "usaspending", "csv", ...
    title: str
    client: str | None = None
    award_value: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    city: str | None = None
    state: str | None = None
    naics: str | None = None
    psc: str | None = None
    building_type: BuildingType = "other"
    description: str = ""

    def embedding_text(self) -> str:
        parts = [self.title, self.description, self.building_type.replace("_", " ")]
        if self.client:
            parts.append(f"client: {self.client}")
        if self.city or self.state:
            parts.append(f"location: {self.city or ''} {self.state or ''}".strip())
        return " | ".join(p for p in parts if p)


class ProjectHit(Project):
    similarity: float


class CompanyProfile(BaseModel):
    """Swap point: everything company-specific the agents need besides the knowledge base."""

    id: str
    name: str
    description: str = ""
    uei: str | None = None
    recipient_names: list[str] = []  # names to match in USAspending
    naics: list[str] = []
    regions: list[str] = []  # two-letter state codes
    building_types: list[BuildingType] = []  # core competencies
    bonding_capacity: float = 0  # single-project bonding limit, USD
    set_aside_eligibility: list[str] = []  # e.g. ["SBA", "8A"]; empty = large business
    weights: dict[str, float] = {}
    bid_threshold: float = 65
    review_threshold: float = 50
    is_demo_peer: bool = False  # peers exist to provide market comps
    sources: list[dict] = []  # knowledge-base adapters to ingest from, e.g. {"type": "csv", "path": ...}


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------


class Opportunity(BaseModel):
    notice_id: str
    title: str
    solicitation_number: str | None = None
    agency: str | None = None
    notice_type: str | None = None
    posted_date: date | None = None
    response_deadline: datetime | None = None
    naics: str | None = None
    psc: str | None = None
    set_aside: str | None = None
    place_city: str | None = None
    place_state: str | None = None
    description: str = ""
    url: str | None = None


# ---------------------------------------------------------------------------
# Agent outputs (LLM-produced)
# ---------------------------------------------------------------------------


class RfpAnalysis(BaseModel):
    scope_summary: str
    building_type: BuildingType
    gross_sf: int | None = Field(None, description="Gross square feet if stated or clearly implied; else null")
    sf_is_stated: bool = Field(description="True only if the solicitation states the size explicitly")
    assumed_sf_if_missing: int | None = Field(
        None, description="If size is not stated, a reasonable assumption for this facility type; else null"
    )
    city: str | None = None
    state: str | None = Field(None, description="Two-letter state code")
    quality: Quality = "typical"
    construction_start_year: int | None = None
    duration_months: int | None = None
    magnitude_low: float | None = Field(None, description="Agency-stated magnitude of construction, low end, USD")
    magnitude_high: float | None = Field(None, description="Agency-stated magnitude of construction, high end, USD")
    set_aside: str | None = None
    delivery_method: str | None = Field(None, description="e.g. design-bid-build, design-build, lease, IDIQ")
    evaluation_criteria: list[str] = []
    special_requirements: list[str] = []
    key_requirements: list[str] = []


class CriterionScore(BaseModel):
    criterion: Criterion
    score: int = Field(description="0 (very poor) to 5 (excellent)")
    rationale: str
    evidence_ids: list[str] = Field(description="Project ids from the provided records that support this score")


class FitAssessment(BaseModel):
    scores: list[CriterionScore]
    summary: str
    strengths: list[str]
    concerns: list[str]


class QualitativeRisk(BaseModel):
    category: str
    description: str
    likelihood: int = Field(description="1-5")
    impact: int = Field(description="1-5")
    mitigation: str


class QualitativeRisks(BaseModel):
    risks: list[QualitativeRisk]


class ProposalSection(BaseModel):
    title: str
    body_markdown: str


class ProposalDraft(BaseModel):
    sections: list[ProposalSection]
    cited_project_ids: list[str]
    placeholders: list[str] = Field(description="Every [PLACEHOLDER — ...] the draft contains")


# ---------------------------------------------------------------------------
# Code-produced results
# ---------------------------------------------------------------------------


class FitResult(BaseModel):
    total: float  # 0-100
    decision: Decision
    gates_triggered: list[str]
    scores: list[CriterionScore]
    summary: str
    strengths: list[str]
    concerns: list[str]


class EstimateLine(BaseModel):
    division: str  # e.g. "03"
    name: str
    pct: float
    amount: float


class Markup(BaseModel):
    name: str
    pct: float
    amount: float


class EstimateInputs(BaseModel):
    building_type: BuildingType
    gross_sf: int
    sf_assumed: bool
    state: str | None = None
    city: str | None = None
    quality: Quality = "typical"
    construction_midpoint_year: float


class Estimate(BaseModel):
    inputs: EstimateInputs
    aace_class: int
    accuracy_low_pct: float
    accuracy_high_pct: float
    base_cost_per_sf: float
    size_factor: float
    location_factor: float
    escalation_factor: float
    hard_cost: float
    lines: list[EstimateLine]
    markups: list[Markup]
    total: float
    low: float
    high: float
    cost_per_sf: float
    assumptions: list[str]


class RiskItem(BaseModel):
    id: str
    category: str
    description: str
    likelihood: int
    impact: int
    score: int
    mitigation: str
    source: Literal["rule", "llm"]


class UsageRecord(BaseModel):
    node: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
