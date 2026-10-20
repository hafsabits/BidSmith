"""In-process run manager: runs the graph on a worker thread and records events for SSE."""

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Literal

from bidsmith.graph import runner

Status = Literal["running", "waiting_review", "done", "error"]


@dataclass
class Run:
    id: str
    notice_id: str
    profile_id: str
    status: Status = "running"
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

    def _set_status(self, run: Run) -> None:
        run.status = "waiting_review" if runner.is_waiting_for_review(run.id) else "done"
        run.emit({"type": "status", "status": run.status})

    def _work(self, run: Run, fn) -> None:
        try:
            fn()
            self._set_status(run)
        except Exception as exc:
            run.status = "error"
            run.error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            run.emit({"type": "status", "status": "error", "error": run.error})

    def start(self, notice_id: str, profile_id: str) -> Run:
        run = Run(id=uuid.uuid4().hex[:12], notice_id=notice_id, profile_id=profile_id)
        with self._lock:
            self.runs[run.id] = run
        run.emit({"type": "status", "status": "running"})
        fn = lambda: runner.start_run(notice_id, profile_id, self._on_update(run), thread_id=run.id)  # noqa: E731
        threading.Thread(target=self._work, args=(run, fn), daemon=True).start()
        return run

    def decide(self, run: Run, decision: str, note: str) -> None:
        if run.status != "waiting_review":
            raise ValueError(f"Run is {run.status}, not waiting for review")
        run.status = "running"
        run.emit({"type": "status", "status": "running"})
        fn = lambda: runner.resume_run(run.id, {"decision": decision, "note": note}, self._on_update(run))  # noqa: E731
        threading.Thread(target=self._work, args=(run, fn), daemon=True).start()

    def get(self, run_id: str) -> Run:
        return self.runs[run_id]


manager = RunManager()
