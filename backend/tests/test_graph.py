"""Graph tests with a fake LLM and fake retrieval (no API calls, no database)."""

from bidsmith.graph import runner
from bidsmith.ingest.sam import get_opportunity
from bidsmith.llm import set_llm
from fakes import FakeLLM


def sample():
    return get_opportunity("SAMPLE-001")


def test_auto_mode_runs_to_review_then_to_end():
    set_llm(FakeLLM(score=4))
    thread_id, state = runner.start_run(sample(), "ryan", "full", step=False)
    assert runner.run_status(thread_id) == ("waiting_review", "human_review")
    assert state["fit"].decision == "bid"
    assert state["fit"].scores[0].evidence_ids == ["own-1"]  # invented id dropped

    state = runner.resume_run(thread_id, {"decision": "bid", "note": "go"}, run_all=True)
    assert runner.run_status(thread_id) == ("done", None)
    assert state["estimate"].aace_class == 4
    md = state["proposal_markdown"]
    assert "{{" not in md and "$" in md and "Class 4" in md
    assert state["proposal"].cited_project_ids == ["own-1"]  # peer project citation removed
    assert {u.node for u in state["usage"]} == {"analyst", "fit", "estimator", "risk", "writer"}


def test_step_mode_pauses_after_each_agent():
    set_llm(FakeLLM(score=4))
    thread_id, state = runner.start_run(sample(), "ryan", "full", step=True)
    assert runner.run_status(thread_id) == ("paused", "fit")
    assert "analysis" in state and "fit" not in state

    state = runner.continue_run(thread_id)
    assert runner.run_status(thread_id) == ("waiting_review", "human_review")

    state = runner.resume_run(thread_id, {"decision": "bid"})
    assert runner.run_status(thread_id) == ("paused", "risk")
    assert "estimate" in state and "risks" not in state

    state = runner.continue_run(thread_id, run_all=True)  # "Run the rest"
    assert runner.run_status(thread_id) == ("done", None)
    assert state["proposal_markdown"]


def test_no_bid_stops_after_review():
    set_llm(FakeLLM(score=1))
    thread_id, state = runner.start_run(sample(), "ryan", "full", step=True)
    runner.continue_run(thread_id)
    state = runner.resume_run(thread_id, {"decision": "no_bid"})
    assert runner.run_status(thread_id)[0] == "done"
    assert "estimate" not in state and "proposal" not in state


def test_single_agent_pipelines_run_alone():
    set_llm(FakeLLM(score=4))
    for pipeline, produced, absent in [
        ("analyst", "analysis", "fit"),
        ("fit", "fit", "estimate"),
        ("estimator", "estimate", "fit"),
        ("risk", "risks", "estimate"),
        ("writer", "proposal", "estimate"),
    ]:
        thread_id, state = runner.start_run(sample(), "ryan", pipeline, step=True)
        assert runner.run_status(thread_id)[0] == "done", pipeline  # no review stop, no step pauses
        assert produced in state and absent not in state, pipeline


def test_writer_alone_marks_missing_pricing():
    set_llm(FakeLLM(score=4))
    _, state = runner.start_run(sample(), "ryan", "writer")
    assert "run the Estimator for pricing" in state["proposal_markdown"]
    assert state["proposal"].cited_project_ids == ["own-1"]  # retrieved its own past performance


def test_checkpoint_allowlist_restores_app_types(caplog):
    from bidsmith.graph.build import checkpoint_types
    from bidsmith.schemas import Estimate, FitResult, ProposalDraft

    assert ("bidsmith.schemas", "ProposalDraft") in checkpoint_types()
    set_llm(FakeLLM(score=4))
    thread_id, _ = runner.start_run(sample(), "ryan", "full", step=False)
    runner.resume_run(thread_id, {"decision": "bid"}, run_all=True)
    state = runner.get_run_state(thread_id)  # read back from the checkpoint
    assert isinstance(state["fit"], FitResult)
    assert isinstance(state["estimate"], Estimate)
    assert isinstance(state["proposal"], ProposalDraft)
    assert "unregistered type" not in caplog.text
