"""End-to-end graph test with a fake LLM and fake retrieval (no API calls, no database)."""

from bidsmith.graph import runner
from bidsmith.llm import set_llm
from fakes import FakeLLM


def test_bid_path_runs_all_agents():
    set_llm(FakeLLM(score=4))
    thread_id, state = runner.start_run("SAMPLE-001", "ryan")
    assert runner.is_waiting_for_review(thread_id)
    assert state["fit"].decision == "bid"
    # invented evidence id is dropped
    assert state["fit"].scores[0].evidence_ids == ["own-1"]

    state = runner.resume_run(thread_id, {"decision": "bid", "note": "go"})
    assert state["estimate"].aace_class == 4
    assert state["risks"]
    md = state["proposal_markdown"]
    assert "{{" not in md and "$" in md and "Class 4" in md
    # writer may not cite another firm's project
    assert state["proposal"].cited_project_ids == ["own-1"]
    assert {u.node for u in state["usage"]} == {"analyst", "fit", "estimator", "risk", "writer"}


def test_no_bid_stops_after_review():
    set_llm(FakeLLM(score=1))
    thread_id, state = runner.start_run("SAMPLE-001", "ryan")
    assert state["fit"].decision == "no_bid"
    state = runner.resume_run(thread_id, {"decision": "no_bid"})
    assert "estimate" not in state and "proposal" not in state
