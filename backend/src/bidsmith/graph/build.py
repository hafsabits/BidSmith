from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from bidsmith.graph.nodes.analyst import analyst
from bidsmith.graph.nodes.estimator import estimator
from bidsmith.graph.nodes.fit import fit
from bidsmith.graph.nodes.risk import risk
from bidsmith.graph.nodes.writer import writer
from bidsmith.graph.state import RunState


def human_review(state: RunState) -> dict:
    """Pause for a person to accept or override the bid/no-bid recommendation."""
    fit_result = state["fit"]
    answer = interrupt({"recommendation": fit_result.decision, "total": fit_result.total})
    decision = answer.get("decision") or fit_result.decision
    note = answer.get("note", "")
    overridden = decision != fit_result.decision
    message = f"Human {'overrode to' if overridden else 'approved'} {decision.replace('_', ' ').upper()}"
    return {
        "human_decision": decision,
        "human_note": note,
        "trace": [{"node": "human_review", "message": message + (f" — “{note}”" if note else "")}],
    }


def after_review(state: RunState) -> str:
    return END if state["human_decision"] == "no_bid" else "estimator"


def build_graph(checkpointer=None):
    g = StateGraph(RunState)
    g.add_node("analyst", analyst)
    g.add_node("fit", fit)
    g.add_node("human_review", human_review)
    g.add_node("estimator", estimator)
    g.add_node("risk", risk)
    g.add_node("writer", writer)

    g.add_edge(START, "analyst")
    g.add_edge("analyst", "fit")
    g.add_edge("fit", "human_review")
    g.add_conditional_edges("human_review", after_review, ["estimator", END])
    g.add_edge("estimator", "risk")
    g.add_edge("risk", "writer")
    g.add_edge("writer", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())
