import inspect

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

from bidsmith import schemas
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


def checkpoint_types() -> list[tuple[str, str]]:
    """Every Pydantic model in bidsmith.schemas, i.e. everything run state may hold."""
    return [
        (schemas.__name__, name)
        for name, obj in vars(schemas).items()
        if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj.__module__ == schemas.__name__
    ]


def make_checkpointer() -> InMemorySaver:
    # An explicit allowlist: our own types load, anything else in a checkpoint is refused.
    return InMemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=checkpoint_types()))


NODES = {"analyst": analyst, "fit": fit, "human_review": human_review, "estimator": estimator, "risk": risk, "writer": writer}

# Which agents each kind of run executes, in order. Single-agent runs still start with the
# analyst, because every agent works from the analyst's structured reading of the RFP.
PIPELINES: dict[str, list[str]] = {
    "full": ["analyst", "fit", "human_review", "estimator", "risk", "writer"],
    "analyst": ["analyst"],
    "fit": ["analyst", "fit"],
    "estimator": ["analyst", "estimator"],
    "risk": ["analyst", "risk"],
    "writer": ["analyst", "writer"],
}


def build_graph(pipeline: str = "full", checkpointer=None):
    nodes = PIPELINES[pipeline]
    g = StateGraph(RunState)
    for name in nodes:
        g.add_node(name, NODES[name])
    g.add_edge(START, nodes[0])
    for current, following in zip(nodes, nodes[1:]):
        if current == "human_review":
            g.add_conditional_edges("human_review", after_review, [following, END])
        else:
            g.add_edge(current, following)
    g.add_edge(nodes[-1], END)
    return g.compile(checkpointer=checkpointer or make_checkpointer())
