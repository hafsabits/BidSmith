from datetime import date

from bidsmith.graph.state import RunState
from bidsmith.llm import as_json, get_llm
from bidsmith.schemas import RfpAnalysis
from bidsmith.settings import get_settings

SYSTEM = """You are a capture analyst at a commercial real estate and construction firm.
You read federal solicitations and extract the facts an estimator and a bid committee need.
Extract only what the text supports. When the building size is not stated, set sf_is_stated
to false, leave gross_sf null, and give a reasonable assumed_sf_if_missing for this facility type.
Report agency-stated construction magnitude as numbers in USD. Use two-letter state codes."""


def analyst(state: RunState) -> dict:
    opp = state["opportunity"]
    settings = get_settings()
    user = f"""Today's date: {date.today().isoformat()}

Solicitation metadata:
{as_json(opp.model_dump(exclude={"description"}))}

Solicitation text:
<solicitation>
{opp.description}
</solicitation>"""
    analysis, usage = get_llm().structured("analyst", settings.model_fast, SYSTEM, user, RfpAnalysis)
    if not analysis.state and opp.place_state:
        analysis.state = opp.place_state
    if not analysis.city and opp.place_city:
        analysis.city = opp.place_city
    size = f"{analysis.gross_sf:,} SF stated" if analysis.sf_is_stated and analysis.gross_sf else f"size not stated (assume ~{analysis.assumed_sf_if_missing or 0:,} SF)"
    return {
        "analysis": analysis,
        "usage": [usage],
        "trace": [{"node": "analyst", "message": f"Extracted scope: {analysis.building_type.replace('_', ' ')}, {size}, {analysis.state or '??'}"}],
    }
