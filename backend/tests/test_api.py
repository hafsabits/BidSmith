import time

from fastapi.testclient import TestClient

from bidsmith.api.main import app
from bidsmith.llm import set_llm
from fakes import FakeLLM


def wait_for(client, run_id, status, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["status"] == status:
            return body
        time.sleep(0.05)
    raise AssertionError(f"run never reached {status}: {body}")


def test_run_lifecycle_over_http():
    set_llm(FakeLLM(score=4))
    client = TestClient(app)
    assert len(client.get("/api/opportunities").json()) >= 1

    run_id = client.post("/api/runs", json={"notice_id": "SAMPLE-001", "profile_id": "ryan"}).json()["run_id"]
    body = wait_for(client, run_id, "waiting_review")
    assert body["state"]["fit"]["decision"] == "bid"

    assert client.post(f"/api/runs/{run_id}/decision", json={"decision": "bid", "note": ""}).status_code == 200
    body = wait_for(client, run_id, "done")
    assert body["state"]["estimate"]["aace_class"] == 4
    assert body["total_tokens"] > 0

    md = client.get(f"/api/runs/{run_id}/proposal.md")
    assert md.status_code == 200 and "Proposal:" in md.text

    events = client.get(f"/api/runs/{run_id}/events").text
    assert "node_done" in events and '"status": "done"' in events
