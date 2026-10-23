import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ReactNode, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AGENT_INFO } from "../agents";
import { api, Decision, RunEvent, RunResponse } from "../api";
import { AnalystResult, Details, EstimateResult, FitResultView, RiskResult, WriterResult } from "../components/AgentResults";
import { DecisionBadge, Pill, Spinner } from "../components/ui";
import { useLiveRun } from "../useLiveRun";

/** A node counts as finished once the state holds what it produces. */
function finished(run: RunResponse): Set<string> {
  const s = run.state;
  const done = new Set<string>();
  if (s.analysis) done.add("analyst");
  if (s.fit) done.add("fit");
  if (s.human_decision) done.add("human_review");
  if (s.estimate) done.add("estimator");
  if (s.risks) done.add("risk");
  if (s.proposal_markdown) done.add("writer");
  return done;
}

export default function RunPage() {
  const { runId = "" } = useParams();
  const { run, events } = useLiveRun(runId);
  const { data: opp } = useQuery({
    queryKey: ["opportunity", run?.notice_id],
    queryFn: () => api.opportunity(run!.notice_id!),
    enabled: !!run?.notice_id,
  });

  if (!run) return <Spinner />;
  const done = finished(run);
  const stoppedAtNoBid = run.state.human_decision === "no_bid";
  const working = run.status === "running" ? run.pipeline.find((n) => !done.has(n)) : undefined;
  const single = run.pipeline.length <= 2 && run.pipeline[0] === "analyst";
  const latest = (node: string) => [...events].reverse().find((e) => e.type === "trace" && e.node === node);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link to="/" className="text-xs text-slate-500 hover:text-slate-800">
          ← New analysis
        </Link>
        <h1 className="mt-2 text-xl font-bold leading-snug">{opp?.title.replace(/^SAMPLE:\s*/, "") ?? (run.status === "error" ? "RFP not loaded" : "Loading the RFP…")}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          {opp && <Pill>{opp.source === "pasted" ? "Pasted RFP" : opp.source === "sample" ? "Sample RFP" : "SAM.gov"}</Pill>}
          <span>{single ? `${AGENT_INFO[run.pipeline[run.pipeline.length - 1]].name} only` : run.step ? "Step by step" : "All agents"}</span>
          <span>· ${run.total_cost_usd.toFixed(3)} API cost</span>
        </div>
      </div>

      <Stepper nodes={run.pipeline} done={done} working={working} next={run.next_node} skipped={stoppedAtNoBid} />

      {run.pipeline.map((node) => {
        if (!done.has(node)) return null;
        return (
          <AgentCard key={node} node={node}>
            <AgentOutput node={node} run={run} />
          </AgentCard>
        );
      })}

      {working && (
        <AgentCard node={working} working>
          <p className="text-sm text-slate-500">{latest(working)?.message ?? AGENT_INFO[working].does}</p>
        </AgentCard>
      )}

      {run.status === "waiting_review" && run.state.fit && <ReviewPanel run={run} />}
      {run.status === "paused" && run.next_node && <NextStep run={run} />}

      {run.status === "error" && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <div className="font-semibold">The run stopped with an error</div>
          <div className="mt-1">{run.error}</div>
        </div>
      )}

      {run.status === "done" && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          {stoppedAtNoBid ? "Marked no-bid, so the estimate and proposal were skipped." : "All done."}{" "}
          <Link to="/" className="font-semibold underline">
            Analyze another RFP
          </Link>
        </div>
      )}

      <RunDetails run={run} events={events} />
    </div>
  );
}

function Stepper({ nodes, done, working, next, skipped }: { nodes: string[]; done: Set<string>; working?: string; next: string | null; skipped: boolean }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-xs">
      {nodes.map((n, i) => {
        const isDone = done.has(n);
        const isActive = n === working || n === next;
        const isSkipped = skipped && !isDone;
        return (
          <li key={n} className="flex items-center gap-2">
            <span
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${
                isDone ? "bg-emerald-50 text-emerald-700" : isActive ? "bg-brand-50 text-brand-700 ring-1 ring-brand-200" : "bg-slate-100 text-slate-400"
              } ${isSkipped ? "line-through opacity-60" : ""}`}
            >
              {isDone ? "✓" : n === working ? <Spinner className="h-3 w-3" /> : null}
              {AGENT_INFO[n].name}
            </span>
            {i < nodes.length - 1 && <span className="text-slate-300">→</span>}
          </li>
        );
      })}
    </ol>
  );
}

function AgentCard({ node, working, children }: { node: string; working?: boolean; children: ReactNode }) {
  return (
    <section className={`rounded-xl border bg-white p-5 shadow-sm ${working ? "border-brand-200" : "border-slate-200"}`}>
      <header className="mb-3 flex items-center gap-2">
        {working && <Spinner className="h-3.5 w-3.5" />}
        <h2 className="text-sm font-semibold">{AGENT_INFO[node].name}</h2>
        {working && <span className="text-xs text-slate-500">working…</span>}
      </header>
      {children}
    </section>
  );
}

function AgentOutput({ node, run }: { node: string; run: RunResponse }) {
  const s = run.state;
  switch (node) {
    case "analyst":
      return <AnalystResult analysis={s.analysis!} />;
    case "fit":
      return <FitResultView fit={s.fit!} own={s.own_projects ?? []} comps={s.comps ?? []} />;
    case "human_review":
      return (
        <p className="text-sm text-slate-700">
          You chose <DecisionBadge decision={s.human_decision!} />
          {s.human_decision !== s.fit?.decision && " (overriding the recommendation)"}
          {s.human_note && <> with the note “{s.human_note}”</>}.
        </p>
      );
    case "estimator":
      return <EstimateResult est={s.estimate!} notes={s.estimator_notes} />;
    case "risk":
      return <RiskResult risks={s.risks!} />;
    case "writer":
      return <WriterResult markdown={s.proposal_markdown!} placeholders={s.proposal?.placeholders ?? []} downloadUrl={api.proposalUrl(run.id)} />;
    default:
      return null;
  }
}

function useRunAction(runId: string, fn: () => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["run", runId] }) });
}

function NextStep({ run }: { run: RunResponse }) {
  const next = useRunAction(run.id, () => api.continueRun(run.id, false));
  const rest = useRunAction(run.id, () => api.continueRun(run.id, true));
  const info = AGENT_INFO[run.next_node!];
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50/60 p-4">
      <div className="text-sm">
        <div className="font-semibold">Next: {info.name}</div>
        <div className="text-slate-600">{info.does}</div>
      </div>
      <div className="flex gap-2">
        <button onClick={() => rest.mutate()} disabled={next.isPending || rest.isPending} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50">
          Run the rest
        </button>
        <button onClick={() => next.mutate()} disabled={next.isPending || rest.isPending} className="rounded-md bg-brand-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-700">
          Continue
        </button>
      </div>
    </div>
  );
}

function ReviewPanel({ run }: { run: RunResponse }) {
  const recommendation = run.state.fit!.decision;
  const [decision, setDecision] = useState<Decision>(recommendation === "review" ? "bid" : recommendation);
  const [note, setNote] = useState("");
  const step = useRunAction(run.id, () => api.decide(run.id, decision, note, false));
  const all = useRunAction(run.id, () => api.decide(run.id, decision, note, true));
  const busy = step.isPending || all.isPending;
  return (
    <section className="rounded-xl border border-amber-300 bg-white p-5 shadow-sm ring-2 ring-amber-100">
      <h2 className="text-sm font-semibold">Your decision</h2>
      <p className="mt-1 text-sm text-slate-600">
        The agents recommend <DecisionBadge decision={recommendation} />. Nothing is priced or drafted until you decide.
      </p>
      <div className="mt-3 flex gap-2">
        {(["bid", "no_bid"] as Decision[]).map((d) => (
          <button
            key={d}
            onClick={() => setDecision(d)}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium ${decision === d ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-300"}`}
          >
            {d === "bid" ? "Pursue (bid)" : "Pass (no-bid)"}
          </button>
        ))}
      </div>
      {decision === "bid" && (
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Optional note for the proposal writer"
          rows={2}
          className="mt-3 w-full rounded-md border border-slate-300 p-2 text-sm"
        />
      )}
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        {decision === "bid" && run.step && (
          <button onClick={() => all.mutate()} disabled={busy} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50">
            Run the rest
          </button>
        )}
        <button onClick={() => (run.step ? step : all).mutate()} disabled={busy} className="rounded-md bg-brand-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-700">
          {decision === "no_bid" ? "Stop here" : run.step ? "Continue to Estimator" : "Continue"}
        </button>
      </div>
    </section>
  );
}

function RunDetails({ run, events }: { run: RunResponse; events: RunEvent[] }) {
  const usage = run.state.usage ?? [];
  const log = events.filter((e) => e.type === "trace");
  if (!usage.length && !log.length) return null;
  return (
    <div className="border-t border-slate-200 pt-4">
      <Details label="run details (agent log and cost)">
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <div className="text-xs font-semibold text-slate-500">Agent log</div>
            <ul className="mt-1 max-h-64 space-y-1 overflow-y-auto font-mono text-[11px] text-slate-600">
              {log.map((e) => (
                <li key={e.seq}>
                  <span className="text-brand-600">{e.node}</span> {e.message}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="text-xs font-semibold text-slate-500">Model usage · {run.total_tokens.toLocaleString()} tokens</div>
            <table className="mt-1 w-full text-xs tabular-nums">
              <tbody className="divide-y divide-slate-100">
                {usage.map((u, i) => (
                  <tr key={i}>
                    <td className="py-1">{AGENT_INFO[u.node]?.name ?? u.node}</td>
                    <td className="py-1 font-mono text-slate-500">{u.model}</td>
                    <td className="py-1 text-right">${u.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Details>
    </div>
  );
}
