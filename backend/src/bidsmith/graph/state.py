import operator
from typing import Annotated, TypedDict

from bidsmith.schemas import (
    CompanyProfile,
    Estimate,
    FitResult,
    Opportunity,
    ProjectHit,
    ProposalDraft,
    RfpAnalysis,
    RiskItem,
    UsageRecord,
)


class RunState(TypedDict, total=False):
    # inputs
    opportunity: Opportunity
    profile: CompanyProfile
    # analyst
    analysis: RfpAnalysis
    # fit
    own_projects: list[ProjectHit]
    comps: list[ProjectHit]
    company_stats: dict
    fit: FitResult
    # human checkpoint
    human_decision: str
    human_note: str
    # estimator
    estimate: Estimate
    estimate_attempts: list[dict]
    estimator_notes: str
    # risk
    risks: list[RiskItem]
    # writer
    proposal: ProposalDraft
    proposal_markdown: str
    # bookkeeping (appended by every node)
    usage: Annotated[list[UsageRecord], operator.add]
    trace: Annotated[list[dict], operator.add]
