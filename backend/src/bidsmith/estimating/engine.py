"""Deterministic conceptual (AACE Class 5/4) estimate.

    cost/SF = base $/SF(type, quality) x size factor x location factor x escalation x (1 + premiums)
    hard cost = cost/SF x gross SF, split across CSI MasterFormat divisions
    total = hard cost + fee + bonds/insurance + design fee (design-build) + design contingency

The LLM chooses inputs; every number is computed here.
"""

import math

from bidsmith.estimating.costdata import BASE_YEAR, CostData, get_cost_data
from bidsmith.schemas import Estimate, EstimateInputs, EstimateLine, Markup

FEE_PCT = 0.05
BONDS_INSURANCE_PCT = 0.02
DESIGN_FEE_PCT = 0.07  # design-build only
SIZE_EXPONENT = 0.10  # mild economies of scale
SIZE_FACTOR_BOUNDS = (0.85, 1.25)

# AACE 18R-97: Class 5 is roughly -20..-50% / +30..+100%; Class 4 roughly -15..-30% / +20..+50%.
# We use the midpoints of those bands.
CLASS_RANGES = {5: (-0.30, 0.50), 4: (-0.20, 0.30)}
CLASS_CONTINGENCY = {5: 0.15, 4: 0.10}


def size_factor(gross_sf: int, typical_sf: int) -> float:
    raw = (typical_sf / gross_sf) ** SIZE_EXPONENT
    return min(max(raw, SIZE_FACTOR_BOUNDS[0]), SIZE_FACTOR_BOUNDS[1])


def escalation_factor(midpoint_year: float, rates: dict[int, float]) -> float:
    """Compound annual escalation from the middle of BASE_YEAR to the construction midpoint."""
    start = BASE_YEAR + 0.5
    if midpoint_year <= start:
        return 1.0
    factor = 1.0
    t = start
    last_rate = rates[max(rates)]
    while t < midpoint_year:
        year = math.floor(t)
        step = min(year + 1, midpoint_year) - t
        factor *= (1 + rates.get(year, last_rate)) ** step
        t += step
    return factor


def aace_class(inputs: EstimateInputs) -> int:
    return 5 if inputs.sf_assumed else 4


def estimate(inputs: EstimateInputs, data: CostData | None = None) -> Estimate:
    data = data or get_cost_data()
    if inputs.gross_sf <= 0:
        raise ValueError("gross_sf must be positive")
    building = data.buildings[inputs.building_type]
    unknown = [p for p in inputs.premiums if p not in data.premiums]
    if unknown:
        raise ValueError(f"Unknown premiums: {unknown}. Valid: {sorted(data.premiums)}")

    base = getattr(building, inputs.quality)
    s_factor = size_factor(inputs.gross_sf, building.typical_sf)
    loc = data.location.get(inputs.state or "", 1.0)
    esc = escalation_factor(inputs.construction_midpoint_year, data.escalation)
    premium_pct = sum(data.premiums[p].pct for p in inputs.premiums)

    cost_per_sf_hard = base * s_factor * loc * esc * (1 + premium_pct)
    hard_cost = cost_per_sf_hard * inputs.gross_sf

    lines = [
        EstimateLine(division=d.code, name=d.name, pct=d.pct, amount=round(hard_cost * d.pct, 2))
        for d in data.splits[building.archetype]
    ]

    cls = aace_class(inputs)
    markup_specs = [("Contractor fee (OH&P)", FEE_PCT), ("Bonds & insurance", BONDS_INSURANCE_PCT)]
    if inputs.design_build:
        markup_specs.append(("Design fee (design-build)", DESIGN_FEE_PCT))
    markup_specs.append((f"Design contingency (Class {cls})", CLASS_CONTINGENCY[cls]))
    markups = [Markup(name=n, pct=p, amount=round(hard_cost * p, 2)) for n, p in markup_specs]

    total = hard_cost + sum(m.amount for m in markups)
    low_pct, high_pct = CLASS_RANGES[cls]

    assumptions = [
        f"Base ${base:,.0f}/SF for {inputs.building_type.replace('_', ' ')} ({inputs.quality} quality), {BASE_YEAR} national average (synthetic data).",
        f"Gross area {inputs.gross_sf:,} SF ({'assumed' if inputs.sf_assumed else 'stated in solicitation'}); size factor {s_factor:.3f}.",
        f"Location factor {loc:.2f} for {inputs.state or 'unknown state (1.00 used)'}.",
        f"Escalated to construction midpoint {inputs.construction_midpoint_year:.1f}: factor {esc:.3f}.",
    ]
    for p in inputs.premiums:
        assumptions.append(f"Premium +{data.premiums[p].pct:.0%}: {data.premiums[p].description}.")
    assumptions.append(f"AACE Class {cls} accuracy range {low_pct:+.0%} / {high_pct:+.0%}.")

    return Estimate(
        inputs=inputs,
        aace_class=cls,
        accuracy_low_pct=low_pct,
        accuracy_high_pct=high_pct,
        base_cost_per_sf=base,
        size_factor=round(s_factor, 4),
        location_factor=loc,
        escalation_factor=round(esc, 4),
        hard_cost=round(hard_cost, 2),
        lines=lines,
        markups=markups,
        total=round(total, 2),
        low=round(total * (1 + low_pct), 2),
        high=round(total * (1 + high_pct), 2),
        cost_per_sf=round(total / inputs.gross_sf, 2),
        assumptions=assumptions,
    )


def premium_catalog(data: CostData | None = None) -> dict[str, str]:
    data = data or get_cost_data()
    return {k: f"+{p.pct:.0%} {p.description}" for k, p in data.premiums.items()}
