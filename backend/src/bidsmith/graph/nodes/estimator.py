import json
import typing

from bidsmith.estimating.engine import estimate, premium_catalog
from bidsmith.graph.state import RunState
from bidsmith.llm import as_json, get_llm
from bidsmith.schemas import BuildingType, Estimate, EstimateInputs
from bidsmith.settings import get_settings

SYSTEM = """You are a preconstruction estimator preparing a conceptual (AACE Class 5/4) estimate.
You never do arithmetic yourself: call run_estimate, which applies the firm's cost database.
Choose inputs from the solicitation analysis:
- building_type, gross_sf, and sf_assumed=true whenever the size was not stated in the solicitation
- quality: low / typical / high based on the program (e.g. federal courthouse or lab = high)
- construction_midpoint_year as a decimal year (start + half the duration)
- design_build=true only for design-build or CMc delivery with design responsibility
- premiums: only those clearly required by the solicitation
You may call run_estimate more than once to test one alternative assumption, but your LAST call
must be the estimate you recommend. Finish with 2-4 sentences explaining your input choices."""


def _tool_schema() -> dict:
    return {
        "name": "run_estimate",
        "description": "Run the deterministic conceptual estimate. Returns totals, range, and line items by CSI division.",
        "input_schema": {
            "type": "object",
            "properties": {
                "building_type": {"type": "string", "enum": list(typing.get_args(BuildingType))},
                "gross_sf": {"type": "integer", "description": "Gross square feet"},
                "sf_assumed": {"type": "boolean"},
                "state": {"type": "string", "description": "Two-letter state code"},
                "city": {"type": "string"},
                "quality": {"type": "string", "enum": ["low", "typical", "high"]},
                "construction_midpoint_year": {"type": "number"},
                "design_build": {"type": "boolean"},
                "premiums": {"type": "array", "items": {"type": "string", "enum": list(premium_catalog())}},
            },
            "required": ["building_type", "gross_sf", "sf_assumed", "quality", "construction_midpoint_year"],
            "additionalProperties": False,
        },
    }


def _summarize(est: Estimate) -> str:
    return json.dumps(
        {
            "aace_class": est.aace_class,
            "total": round(est.total),
            "low": round(est.low),
            "high": round(est.high),
            "cost_per_sf": est.cost_per_sf,
            "factors": {"size": est.size_factor, "location": est.location_factor, "escalation": est.escalation_factor},
            "top_divisions": [
                {"division": l.division, "name": l.name, "amount": round(l.amount)}
                for l in sorted(est.lines, key=lambda l: -l.amount)[:5]
            ],
        }
    )


def estimator(state: RunState) -> dict:
    analysis = state["analysis"]
    attempts: list[Estimate] = []
    trace: list[dict] = []

    def run_estimate(args: dict) -> str:
        est = estimate(EstimateInputs(**args))
        attempts.append(est)
        return _summarize(est)

    def on_call(name: str, args: dict, output: str) -> None:
        trace.append({"node": "estimator", "message": f"tool {name}({', '.join(f'{k}={v}' for k, v in args.items())})", "detail": output})

    user = f"""Solicitation analysis:
{as_json(analysis)}

Available premiums:
{as_json(premium_catalog())}"""
    notes, usage = get_llm().tool_loop(
        "estimator", get_settings().model_smart, SYSTEM, user, [_tool_schema()], {"run_estimate": run_estimate}, on_call
    )
    if not attempts:
        # Model never called the tool: fall back to the analyst's facts so the pipeline continues.
        sf = analysis.gross_sf or analysis.assumed_sf_if_missing or 50_000
        start = analysis.construction_start_year or 2027
        attempts.append(
            estimate(
                EstimateInputs(
                    building_type=analysis.building_type,
                    gross_sf=sf,
                    sf_assumed=not (analysis.sf_is_stated and analysis.gross_sf),
                    state=analysis.state,
                    quality=analysis.quality,
                    construction_midpoint_year=start + (analysis.duration_months or 18) / 24,
                )
            )
        )
        notes = (notes + "\n\n" if notes else "") + "Estimator did not call the tool; used analyst facts directly."
    chosen = attempts[-1]
    trace.append({"node": "estimator", "message": f"Class {chosen.aace_class} estimate ${chosen.total:,.0f} (range ${chosen.low:,.0f}–${chosen.high:,.0f})"})
    return {
        "estimate": chosen,
        "estimate_attempts": [a.inputs.model_dump() for a in attempts],
        "estimator_notes": notes,
        "usage": [usage],
        "trace": trace,
    }
