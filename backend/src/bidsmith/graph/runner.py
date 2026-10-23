"""Start, step, and resume runs. Shared by the CLI and the API.

A run executes one pipeline (see PIPELINES). In step mode the full pipeline pauses after
each agent so a person can read its summary before the next one starts; the bid/no-bid
review always pauses, in every mode.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Literal

from langgraph.types import Command

from bidsmith.graph.build import PIPELINES, build_graph, make_checkpointer
from bidsmith.profiles import load_profile
from bidsmith.schemas import Opportunity

OnUpdate = Callable[[str, dict], None]
RunStatus = Literal["paused", "waiting_review", "done"]


@dataclass
class _RunInfo:
    pipeline: str
    step: bool


_runs: dict[str, _RunInfo] = {}


@lru_cache
def _checkpointer():
    return make_checkpointer()


@lru_cache
def get_graph(pipeline: str = "full"):
    return build_graph(pipeline, checkpointer=_checkpointer())


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _step_pauses(info: _RunInfo) -> list[str]:
    """Agents to pause after. The review node pauses on its own; the last agent just ends the run."""
    if not info.step or info.pipeline != "full":  # single-agent runs go straight through
        return []
    nodes = PIPELINES[info.pipeline]
    return [n for n in nodes[:-1] if n not in ("human_review", "fit")]


def _drive(thread_id: str, graph_input, on_update: OnUpdate | None, run_all: bool) -> dict:
    info = _runs[thread_id]
    graph = get_graph(info.pipeline)
    pauses = [] if run_all else _step_pauses(info)
    for chunk in graph.stream(graph_input, _config(thread_id), stream_mode="updates", interrupt_after=pauses):
        for node, update in chunk.items():
            if on_update:
                on_update(node, update if isinstance(update, dict) else {"value": update})
    return graph.get_state(_config(thread_id)).values


def start_run(
    opportunity: Opportunity,
    profile_id: str = "ryan",
    pipeline: str = "full",
    step: bool = True,
    on_update: OnUpdate | None = None,
    thread_id: str | None = None,
) -> tuple[str, dict]:
    if pipeline not in PIPELINES:
        raise ValueError(f"Unknown pipeline '{pipeline}'. Choose from {sorted(PIPELINES)}")
    thread_id = thread_id or uuid.uuid4().hex[:12]
    _runs[thread_id] = _RunInfo(pipeline=pipeline, step=step)
    initial = {"opportunity": opportunity, "profile": load_profile(profile_id), "usage": [], "trace": []}
    return thread_id, _drive(thread_id, initial, on_update, run_all=False)


def continue_run(thread_id: str, run_all: bool = False, on_update: OnUpdate | None = None) -> dict:
    """Resume a run paused between agents."""
    return _drive(thread_id, None, on_update, run_all)


def resume_run(thread_id: str, answer: dict, on_update: OnUpdate | None = None, run_all: bool = False) -> dict:
    """Resume a run waiting at the bid/no-bid review with the person's decision."""
    return _drive(thread_id, Command(resume=answer), on_update, run_all)


def get_run_state(thread_id: str) -> dict:
    info = _runs.get(thread_id)
    if info is None:
        return {}
    return get_graph(info.pipeline).get_state(_config(thread_id)).values


def run_status(thread_id: str) -> tuple[RunStatus, str | None]:
    """Where the run stands, and which agent runs next (if any)."""
    info = _runs[thread_id]
    snapshot = get_graph(info.pipeline).get_state(_config(thread_id))
    upcoming = snapshot.next or ()
    if not upcoming:
        return "done", None
    if "human_review" in upcoming:
        return "waiting_review", "human_review"
    return "paused", upcoming[0]


def is_waiting_for_review(thread_id: str) -> bool:
    return run_status(thread_id)[0] == "waiting_review"


def pipeline_of(thread_id: str) -> list[str]:
    return PIPELINES[_runs[thread_id].pipeline]
