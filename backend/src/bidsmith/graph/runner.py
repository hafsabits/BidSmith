"""Start and resume runs. Shared by the CLI and the API."""

import uuid
from functools import lru_cache
from typing import Callable

from langgraph.types import Command

from bidsmith.graph.build import build_graph
from bidsmith.ingest.sam import get_opportunity
from bidsmith.profiles import load_profile

OnUpdate = Callable[[str, dict], None]


@lru_cache
def get_graph():
    return build_graph()


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _drive(graph_input, thread_id: str, on_update: OnUpdate | None) -> dict:
    graph = get_graph()
    for chunk in graph.stream(graph_input, _config(thread_id), stream_mode="updates"):
        for node, update in chunk.items():
            if on_update:
                on_update(node, update if isinstance(update, dict) else {"value": update})
    return graph.get_state(_config(thread_id)).values


def start_run(notice_id: str, profile_id: str, on_update: OnUpdate | None = None, thread_id: str | None = None) -> tuple[str, dict]:
    thread_id = thread_id or uuid.uuid4().hex[:12]
    initial = {"opportunity": get_opportunity(notice_id), "profile": load_profile(profile_id), "usage": [], "trace": []}
    return thread_id, _drive(initial, thread_id, on_update)


def resume_run(thread_id: str, answer: dict, on_update: OnUpdate | None = None) -> dict:
    return _drive(Command(resume=answer), thread_id, on_update)


def get_run_state(thread_id: str) -> dict:
    return get_graph().get_state(_config(thread_id)).values


def is_waiting_for_review(thread_id: str) -> bool:
    snapshot = get_graph().get_state(_config(thread_id))
    return "human_review" in (snapshot.next or ())
