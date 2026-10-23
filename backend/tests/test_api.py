import time

from fastapi.testclient import TestClient

from bidsmith.api.main import app
from bidsmith.llm import set_llm
from fakes import FakeLLM


def wait_for(client, run_id, *statuses, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["status"] in statuses:
            return body
        time.sleep(0.05)
    raise AssertionError(f"run never reached {statuses}: {body}")


def start(client, **body):
    resp = client.post("/api/runs", json={"input": "SAMPLE-001", **body})
    assert resp.status_code == 200, resp.text
    return resp.json()["run_id"]


def test_step_by_step_over_http():
    set_llm(FakeLLM(score=4))
    client = TestClient(app)
    run_id = start(client)
    body = wait_for(client, run_id, "paused")
    assert body["next_node"] == "fit" and body["state"]["analysis"]
    assert body["pipeline"][0] == "analyst"

    client.post(f"/api/runs/{run_id}/continue", json={})
    body = wait_for(client, run_id, "waiting_review")
    assert body["state"]["fit"]["decision"] == "bid"

    client.post(f"/api/runs/{run_id}/decision", json={"decision": "bid", "run_all": True})
    body = wait_for(client, run_id, "done")
    assert body["state"]["estimate"]["aace_class"] == 4 and body["total_tokens"] > 0

    md = client.get(f"/api/runs/{run_id}/proposal.md")
    assert md.status_code == 200 and "Proposal:" in md.text
    # Continuing a finished run is refused
    assert client.post(f"/api/runs/{run_id}/continue", json={}).status_code == 409


def test_single_agent_run_and_bad_input():
    set_llm(FakeLLM(score=4))
    client = TestClient(app)
    run_id = start(client, pipeline="risk")
    body = wait_for(client, run_id, "done")
    assert body["pipeline"] == ["analyst", "risk"] and body["state"]["risks"]

    short = client.post("/api/runs", json={"input": "build me a clinic"})
    assert short.status_code == 422 and "too short" in short.json()["detail"]


def test_estimate_endpoint_needs_no_llm():
    client = TestClient(app)
    resp = client.post(
        "/api/estimate",
        json={"building_type": "office", "gross_sf": 80000, "sf_assumed": False, "construction_midpoint_year": 2025.5},
    )
    assert resp.status_code == 200 and resp.json()["aace_class"] == 4
    bad = {"building_type": "office", "gross_sf": 0, "sf_assumed": False, "construction_midpoint_year": 2025.5}
    assert client.post("/api/estimate", json=bad).status_code == 422


def test_events_resume_and_stop_when_finished():
    set_llm(FakeLLM(score=1))
    client = TestClient(app)
    run_id = start(client, step=False)
    wait_for(client, run_id, "waiting_review")
    client.post(f"/api/runs/{run_id}/decision", json={"decision": "no_bid", "note": ""})
    wait_for(client, run_id, "done")

    full = client.get(f"/api/runs/{run_id}/events").text
    ids = [int(line[3:]) for line in full.splitlines() if line.startswith("id:")]
    assert ids == list(range(len(ids))) and len(ids) > 3

    resumed = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(ids[-3])}).text
    assert [int(l[3:]) for l in resumed.splitlines() if l.startswith("id:")] == ids[-2:]

    done = client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": str(ids[-1])})
    assert done.status_code == 204


def test_sam_reference_resolves_inside_the_run(monkeypatch):
    from bidsmith import rfp_input
    from bidsmith.ingest.sam import SamApiError

    def slow_sam(_text):
        raise SamApiError("SAM.gov daily request limit reached (HTTP 429).")

    monkeypatch.setattr(rfp_input, "resolve", slow_sam)
    client = TestClient(app)
    resp = client.post("/api/runs", json={"input": "https://sam.gov/opp/" + "a" * 32 + "/view"})
    assert resp.status_code == 200  # returns at once; SAM.gov is called on the worker
    body = wait_for(client, resp.json()["run_id"], "error")
    assert body["error"] == "SAM.gov daily request limit reached (HTTP 429)."
    assert body["notice_id"] is None
