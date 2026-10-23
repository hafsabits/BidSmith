import asyncio
import json
import threading
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from bidsmith import retrieval, rfp_input
from bidsmith.api.runs import manager
from bidsmith.estimating import engine
from bidsmith.graph import runner
from bidsmith.graph.build import PIPELINES
from bidsmith.ingest import sam
from bidsmith.ingest.sam import get_opportunity, load_opportunities
from bidsmith.profiles import load_profile
from bidsmith.schemas import EstimateInputs

def _warm_embeddings() -> None:
    try:
        from bidsmith.embeddings import embed_one

        embed_one("warm up")
    except Exception:  # the first search will load it instead
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load the embedding model in the background so the first Bid/No-Bid run doesn't stall on it.
    threading.Thread(target=_warm_embeddings, daemon=True).start()
    yield


app = FastAPI(title="BidSmith API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


DEFAULT_PROFILE = "ryan"  # the UI is built for Ryan Companies; profiles stay a backend concept


class StartRun(BaseModel):
    input: str  # pasted RFP text, a SAM.gov link, a notice id, or SAMPLE-###
    pipeline: Literal["full", "analyst", "fit", "estimator", "risk", "writer"] = "full"
    step: bool = True


class ReviewDecision(BaseModel):
    decision: Literal["bid", "review", "no_bid"]
    note: str = ""
    run_all: bool = False


class Continue(BaseModel):
    run_all: bool = False


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/company")
def company():
    profile = load_profile(DEFAULT_PROFILE)
    try:
        count = retrieval.owner_counts().get(profile.id, 0)
    except Exception:
        count = 0
    return {**profile.model_dump(include={"id", "name", "description", "regions", "bonding_capacity"}), "project_count": count}


@app.get("/api/opportunities")
def opportunities():
    return load_opportunities()


@app.get("/api/sam/recent")
def sam_recent(offset: int = 0, limit: int = 5):
    """Saved SAM.gov notices, newest posted first. Costs no SAM.gov requests."""
    return sam.recent_page(offset, min(limit, 50))


@app.post("/api/sam/older")
def sam_older():
    """Pull the next (older) batch of notice summaries from SAM.gov: one request."""
    try:
        return sam.fetch_older_batch()
    except sam.SamApiError as exc:
        raise HTTPException(502, str(exc))


@app.get("/api/samples")
def samples():
    return [o for o in load_opportunities() if o.source == "sample"]


@app.post("/api/estimate")
def estimate_only(inputs: EstimateInputs):
    """Run the cost engine directly from user-entered parameters. No LLM, no cost."""
    try:
        return engine.estimate(inputs)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc))


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
    """Start a run. Pasted text and samples are checked right away; SAM.gov lookups happen inside the run."""
    if rfp_input.needs_sam(body.input):
        run = manager.start(lambda: rfp_input.resolve(body.input), DEFAULT_PROFILE, body.pipeline, body.step, from_sam=True)
        return {"run_id": run.id}
    try:
        opp = rfp_input.resolve(body.input)
    except rfp_input.InputError as exc:
        raise HTTPException(422, str(exc))
    run = manager.start(lambda: opp, DEFAULT_PROFILE, body.pipeline, body.step)
    return {"run_id": run.id}


def _run_or_404(run_id: str):
    try:
        return manager.get(run_id)
    except KeyError:
        raise HTTPException(404, "Run not found")


@app.get("/api/runs")
def list_runs():
    return [
        {"id": r.id, "notice_id": r.notice_id, "pipeline": r.pipeline, "status": r.status, "created_at": r.created_at}
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
            "pipeline": PIPELINES[run.pipeline],
            "step": run.step,
            "status": run.status,
            "next_node": run.next_node,
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
        manager.decide(run, body.decision, body.note, body.run_all)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True}


@app.post("/api/runs/{run_id}/continue")
def proceed(run_id: str, body: Continue):
    """Start the next agent (or, with run_all, everything left up to the review / end)."""
    run = _run_or_404(run_id)
    try:
        manager.proceed(run, body.run_all)
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
