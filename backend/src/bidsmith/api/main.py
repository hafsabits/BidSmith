import asyncio
import json
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from bidsmith import retrieval
from bidsmith.api.runs import manager
from bidsmith.graph import runner
from bidsmith.ingest.sam import get_opportunity, load_opportunities
from bidsmith.profiles import list_profiles, load_profile

app = FastAPI(title="BidSmith API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


class StartRun(BaseModel):
    notice_id: str
    profile_id: str


class ReviewDecision(BaseModel):
    decision: Literal["bid", "review", "no_bid"]
    note: str = ""


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/profiles")
def profiles():
    try:
        counts = retrieval.owner_counts()
    except Exception:
        counts = {}
    return [{**p.model_dump(exclude={"sources"}), "project_count": counts.get(p.id, 0)} for p in list_profiles()]


@app.get("/api/opportunities")
def opportunities():
    return load_opportunities()


@app.get("/api/opportunities/{notice_id}")
def opportunity(notice_id: str):
    try:
        return get_opportunity(notice_id)
    except KeyError:
        raise HTTPException(404, "Opportunity not found")


@app.get("/api/projects")
def projects(owner: str | None = None, q: str | None = None, limit: int = 50):
    return retrieval.list_projects(owner=owner, query=q, limit=min(limit, 200))


@app.post("/api/runs")
def start_run(body: StartRun):
    get_opportunity(body.notice_id)
    load_profile(body.profile_id)
    run = manager.start(body.notice_id, body.profile_id)
    return {"run_id": run.id}


def _run_or_404(run_id: str):
    try:
        return manager.get(run_id)
    except KeyError:
        raise HTTPException(404, "Run not found")


@app.get("/api/runs")
def list_runs():
    return [
        {"id": r.id, "notice_id": r.notice_id, "profile_id": r.profile_id, "status": r.status, "created_at": r.created_at}
        for r in sorted(manager.runs.values(), key=lambda r: -r.created_at)
    ]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = _run_or_404(run_id)
    state = runner.get_run_state(run_id) or {}
    state = {k: v for k, v in state.items() if k not in {"opportunity", "profile"}}
    usage = state.get("usage", [])
    return jsonable_encoder(
        {
            "id": run.id,
            "notice_id": run.notice_id,
            "profile_id": run.profile_id,
            "status": run.status,
            "error": run.error,
            "state": state,
            "total_cost_usd": round(sum(u.cost_usd for u in usage), 4),
            "total_tokens": sum(u.input_tokens + u.output_tokens for u in usage),
        }
    )


@app.post("/api/runs/{run_id}/decision")
def decide(run_id: str, body: ReviewDecision):
    run = _run_or_404(run_id)
    try:
        manager.decide(run, body.decision, body.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True}


@app.get("/api/runs/{run_id}/events")
async def events(run_id: str, after: int = -1, last_event_id: str | None = Header(None)):
    run = _run_or_404(run_id)
    # Browsers send Last-Event-ID when they reconnect; resume after it instead of replaying.
    if last_event_id and last_event_id.isdigit():
        after = max(after, int(last_event_id))
    cursor = after + 1
    if run.status in ("done", "error") and cursor >= len(run.events):
        # Nothing left to send. 204 tells EventSource to stop reconnecting.
        return Response(status_code=204)

    async def stream():
        nonlocal cursor
        while True:
            while cursor < len(run.events):
                yield {"event": "message", "id": str(cursor), "data": json.dumps(run.events[cursor])}
                cursor += 1
            if run.status in ("done", "error") and cursor >= len(run.events):
                return
            await asyncio.sleep(0.3)

    return EventSourceResponse(stream(), ping=15)


@app.get("/api/runs/{run_id}/proposal.md", response_class=PlainTextResponse)
def proposal(run_id: str):
    _run_or_404(run_id)
    md = (runner.get_run_state(run_id) or {}).get("proposal_markdown")
    if not md:
        raise HTTPException(404, "No proposal yet")
    return PlainTextResponse(md, headers={"Content-Disposition": f'attachment; filename="proposal-{run_id}.md"'})
