"""In-process run manager: runs the graph on a worker thread and records events for SSE."""

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Callable, Literal

from bidsmith.graph import runner
from bidsmith.ingest.sam import SamApiError
from bidsmith.rfp_input import InputError
from bidsmith.schemas import Opportunity

Status = Literal["running", "paused", "waiting_review", "done", "error"]


@dataclass
class Run:
    id: str
    notice_id: str | None  # unknown until a SAM.gov reference has been looked up
    profile_id: str
    pipeline: str
    step: bool
    status: Status = "running"
    next_node: str | None = None
    events: list[dict] = field(default_factory=list)
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def emit(self, event: dict) -> None:
        self.events.append({"seq": len(self.events), "ts": time.time(), **event})


class RunManager:
    def __init__(self):
        self.runs: dict[str, Run] = {}
        self._lock = threading.Lock()

    def _on_update(self, run: Run):
        def handler(node: str, update: dict) -> None:
            if node == "__interrupt__":
                return
            for item in update.get("trace", []) or []:
                run.emit({"type": "trace", **item})
            run.emit({"type": "node_done", "node": node})

        return handler

    def _work(self, run: Run, fn: Callable[[], object]) -> None:
        try:
            fn()
            run.status, run.next_node = runner.run_status(run.id)
            run.emit({"type": "status", "status": run.status, "next_node": run.next_node})
        except Exception as exc:
            run.status = "error"
            # Problems the user can act on (bad input, SAM.gov refusing) read as plain sentences.
            run.error = str(exc) if isinstance(exc, (InputError, SamApiError)) else f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            run.emit({"type": "status", "status": "error", "error": run.error})

    def _launch(self, run: Run, fn: Callable[[], object]) -> None:
        run.status, run.next_node = "running", None
        run.emit({"type": "status", "status": "running"})
        threading.Thread(target=self._work, args=(run, fn), daemon=True).start()

    def start(self, load: Callable[[], Opportunity], profile_id: str, pipeline: str, step: bool, from_sam: bool = False) -> Run:
        """`load` produces the RFP. For SAM.gov references it calls SAM, so it runs on the worker thread."""
        run = Run(id=uuid.uuid4().hex[:12], notice_id=None, profile_id=profile_id, pipeline=pipeline, step=step)
        with self._lock:
            self.runs[run.id] = run

        def work():
            if from_sam:
                run.emit({"type": "trace", "node": "analyst", "message": "Fetching the RFP from SAM.gov…"})
            opportunity = load()
            run.notice_id = opportunity.notice_id
            run.emit({"type": "rfp", "notice_id": opportunity.notice_id})
            runner.start_run(opportunity, profile_id, pipeline, step, self._on_update(run), thread_id=run.id)

        self._launch(run, work)
        return run

    def proceed(self, run: Run, run_all: bool) -> None:
        if run.status != "paused":
            raise ValueError(f"Run is {run.status}, not paused between agents")
        self._launch(run, lambda: runner.continue_run(run.id, run_all, self._on_update(run)))

    def decide(self, run: Run, decision: str, note: str, run_all: bool = False) -> None:
        if run.status != "waiting_review":
            raise ValueError(f"Run is {run.status}, not waiting for review")
        answer = {"decision": decision, "note": note}
        self._launch(run, lambda: runner.resume_run(run.id, answer, self._on_update(run), run_all))

    def get(self, run_id: str) -> Run:
        return self.runs[run_id]


manager = RunManager()
