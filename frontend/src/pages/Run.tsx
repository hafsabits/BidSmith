import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useParams } from "react-router-dom";
import { api, Decision, Estimate, FitResult, label, Project, RiskItem, RunEvent, RunResponse, usd } from "../api";
import { Card, DecisionBadge, Empty, Pill, Spinner } from "../components/ui";

const STEPS = [
  { node: "analyst", title: "RFP Analyst", blurb: "Extracts scope, size, location, set-aside" },
  { node: "fit", title: "Bid / No-Bid", blurb: "Scores fit against own record and market comps" },
  { node: "human_review", title: "Human review", blurb: "Approve or override the recommendation" },
  { node: "estimator", title: "Estimator", blurb: "Calls the cost engine (AACE Class 5/4)" },
  { node: "risk", title: "Risk", blurb: "Rule checks + qualitative risk review" },
  { node: "writer", title: "Proposal Writer", blurb: "Drafts sections citing own projects only" },
];

function useRunEvents(runId: string) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const queryClient = useQueryClient();
  useEffect(() => {
    setEvents([]);
    const source = new EventSource(api.eventsUrl(runId));
    source.onmessage = (msg) => {
      const event: RunEvent = JSON.parse(msg.data);
      setEvents((prev) => (prev.some((e) => e.seq === event.seq) ? prev : [...prev, event]));
      if (event.type === "status" || event.type === "node_done") queryClient.invalidateQueries({ queryKey: ["run", runId] });
      if (event.type === "status" && (event.status === "done" || event.status === "error")) source.close();
    };
    source.onerror = () => {
      /* browser retries automatically; the run query keeps polling as a fallback */
    };
    return () => source.close();
  }, [runId, queryClient]);
  return events;
}

export default function RunPage() {
  const { runId = "" } = useParams();
  const events = useRunEvents(runId);
  const { data: run } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.run(runId),
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });
  const { data: opp } = useQuery({
    queryKey: ["opportunity", run?.notice_id],
    queryFn: () => api.opportunity(run!.notice_id),
    enabled: !!run,
  });

  if (!run) return <Spinner />;
  const s = run.state;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Run {run.id} · bidding as {run.profile_id}</div>
          <h1 className="mt-1 text-xl font-bold">{opp?.title.replace(/^SAMPLE:\s*/, "") ?? run.notice_id}</h1>
          {s.analysis && <p className="mt-1 max-w-3xl text-sm text-slate-600">{s.analysis.scope_summary}</p>}
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>{run.total_tokens.toLocaleString()} tokens</div>
          <div className="font-semibold text-slate-700">${run.total_cost_usd.toFixed(3)} API cost</div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="space-y-6 lg:sticky lg:top-20 lg:self-start">
          <Timeline run={run} events={events} />
        </div>
        <div className="space-y-6">
          {run.status === "error" && (
            <Card title="Run failed">
              <p className="text-sm text-rose-700">{run.error}</p>
            </Card>
          )}
          {s.fit && <Scorecard fit={s.fit} own={s.own_projects ?? []} comps={s.comps ?? []} />}
          {run.status === "waiting_review" && s.fit && <ReviewPanel runId={run.id} recommendation={s.fit.decision} />}
          {s.human_decision === "no_bid" && run.status === "done" && (
            <Card title="Pipeline stopped">
              <p className="text-sm text-slate-600">The opportunity was marked no-bid, so no estimate or proposal was produced.</p>
            </Card>
          )}
          {s.estimate && <EstimateCard est={s.estimate} notes={s.estimator_notes} />}
          {s.risks && <RiskCard risks={s.risks} />}
          {s.proposal_markdown && <ProposalCard run={run} />}
          {s.usage && s.usage.length > 0 && <UsageCard run={run} />}
        </div>
      </div>
    </div>
  );
}

function Timeline({ run, events }: { run: RunResponse; events: RunEvent[] }) {
  const done = new Set(events.filter((e) => e.type === "node_done").map((e) => e.node));
  (run.state.trace ?? []).forEach((t) => done.add(t.node));
  const stopped = run.state.human_decision === "no_bid";
  const firstPending = STEPS.find((st) => !done.has(st.node));
  const traces = events.filter((e) => e.type === "trace");
  const shownTraces = traces.length ? traces : (run.state.trace ?? []).map((t, i) => ({ ...t, seq: i, ts: 0, type: "trace" as const }));

  return (
    <Card title="Agent pipeline">
      <ol className="space-y-3">
        {STEPS.map((st) => {
          const isDone = done.has(st.node);
          const isSkipped = stopped && !isDone && ["estimator", "risk", "writer"].includes(st.node);
          const isActive = !isDone && !isSkipped && firstPending?.node === st.node && run.status !== "error";
          const waiting = isActive && st.node === "human_review" && run.status === "waiting_review";
          return (
            <li key={st.node} className="flex gap-3">
              <div
                className={`mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold ${
                  isDone ? "bg-emerald-500 text-white" : waiting ? "bg-amber-400 text-white" : isActive ? "bg-brand-100" : "bg-slate-100 text-slate-400"
                }`}
              >
                {isDone ? "✓" : waiting ? "!" : isActive ? <Spinner className="h-3 w-3" /> : isSkipped ? "–" : ""}
              </div>
              <div className={isSkipped ? "opacity-40" : ""}>
                <div className="text-sm font-semibold">{st.title}</div>
                <div className="text-xs text-slate-500">{waiting ? "Waiting for your decision" : st.blurb}</div>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="mt-5 border-t border-slate-100 pt-4">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Trace</div>
        <ul className="max-h-80 space-y-2 overflow-y-auto font-mono text-[11px] leading-snug text-slate-600">
          {shownTraces.map((t) => (
            <li key={t.seq}>
              <span className="text-brand-600">{t.node}</span> {t.message}
            </li>
          ))}
          {shownTraces.length === 0 && <li>Starting…</li>}
        </ul>
      </div>
    </Card>
  );
}

function Scorecard({ fit, own, comps }: { fit: FitResult; own: Project[]; comps: Project[] }) {
  const byId = useMemo(() => new Map([...own, ...comps].map((p) => [p.id, p])), [own, comps]);
  return (
    <Card title="Bid / no-bid scorecard" actions={<DecisionBadge decision={fit.decision} size="lg" />}>
      <div className="flex flex-wrap items-center gap-6">
        <div className="relative grid h-24 w-24 place-items-center rounded-full" style={{ background: `conic-gradient(#1d4ed8 ${fit.total * 3.6}deg, #e2e8f0 0)` }}>
          <div className="grid h-[76px] w-[76px] place-items-center rounded-full bg-white">
            <span className="text-2xl font-bold">{Math.round(fit.total)}</span>
          </div>
        </div>
        <p className="min-w-[200px] flex-1 text-sm text-slate-700">{fit.summary}</p>
      </div>
      {fit.gates_triggered.length > 0 && (
        <div className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">
          <div className="font-semibold">Hard gate triggered</div>
          {fit.gates_triggered.map((g) => (
            <div key={g}>{g}</div>
          ))}
        </div>
      )}
      <div className="mt-5 space-y-4">
        {fit.scores.map((c) => (
          <div key={c.criterion}>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium capitalize">{label(c.criterion)}</span>
              <span className="tabular-nums text-slate-500">{c.score}/5</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-slate-100">
              <div className="h-2 rounded-full bg-brand-500" style={{ width: `${(c.score / 5) * 100}%` }} />
            </div>
            <p className="mt-1 text-xs text-slate-600">{c.rationale}</p>
            {c.evidence_ids.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {c.evidence_ids.map((id) => {
                  const p = byId.get(id);
                  const isOwn = own.some((o) => o.id === id);
                  return (
                    <span key={id} title={p?.description} className={`rounded px-1.5 py-0.5 text-[11px] ${isOwn ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                      {isOwn ? "own" : p?.owner_company_id ?? "comp"}: {p?.title.slice(0, 48) ?? id}
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <List title="Strengths" items={fit.strengths} tone="text-emerald-700" />
        <List title="Concerns" items={fit.concerns} tone="text-rose-700" />
      </div>
    </Card>
  );
}

function List({ title, items, tone }: { title: string; items: string[]; tone: string }) {
  return (
    <div>
      <div className={`text-xs font-semibold uppercase tracking-wide ${tone}`}>{title}</div>
      <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-slate-700">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  );
}

function ReviewPanel({ runId, recommendation }: { runId: string; recommendation: Decision }) {
  const queryClient = useQueryClient();
  const [decision, setDecision] = useState<Decision>(recommendation === "review" ? "bid" : recommendation);
  const [note, setNote] = useState("");
  const submit = useMutation({
    mutationFn: () => api.decide(runId, decision, note),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["run", runId] }),
  });
  return (
    <Card title="Your decision" className="border-amber-300 ring-2 ring-amber-100">
      <p className="text-sm text-slate-600">
        The agents recommend <DecisionBadge decision={recommendation} />. Approve it or override before any estimating or drafting happens.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
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
      <textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Optional note for the writer, e.g. 'team with a healthcare designer'"
        className="mt-3 w-full rounded-md border border-slate-300 p-2 text-sm"
        rows={2}
      />
      <button
        onClick={() => submit.mutate()}
        disabled={submit.isPending}
        className="mt-3 rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
      >
        {decision === recommendation ? "Approve and continue" : "Override and continue"}
      </button>
    </Card>
  );
}

function EstimateCard({ est, notes }: { est: Estimate; notes?: string }) {
  const lines = [...est.lines].sort((a, b) => b.amount - a.amount);
  const span = est.high - est.low;
  const pointPct = ((est.total - est.low) / span) * 100;
  return (
    <Card title={`Conceptual estimate · AACE Class ${est.aace_class}`} actions={<Pill tone="amber">synthetic cost data</Pill>}>
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Point estimate" value={usd(est.total)} />
        <Stat label="Cost per SF" value={`${usd(est.cost_per_sf)}/SF`} />
        <Stat label={`Range (${Math.round(est.accuracy_low_pct * 100)}% / +${Math.round(est.accuracy_high_pct * 100)}%)`} value={`${usd(est.low, true)} – ${usd(est.high, true)}`} />
      </div>
      <div className="relative mt-4 h-3 rounded-full bg-gradient-to-r from-emerald-200 via-brand-100 to-rose-200">
        <div className="absolute -top-1 h-5 w-1 rounded bg-brand-900" style={{ left: `${pointPct}%` }} />
      </div>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-1">CSI division</th>
              <th className="py-1 text-right">Amount</th>
              <th className="w-1/3 py-1 pl-4">Share</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {lines.map((l) => (
              <tr key={l.division}>
                <td className="py-1.5">
                  <span className="mr-2 font-mono text-xs text-slate-400">{l.division}</span>
                  {l.name}
                </td>
                <td className="py-1.5 text-right tabular-nums">{usd(l.amount)}</td>
                <td className="py-1.5 pl-4">
                  <div className="h-1.5 rounded bg-slate-100">
                    <div className="h-1.5 rounded bg-brand-500" style={{ width: `${(l.pct / lines[0].pct) * 100}%` }} />
                  </div>
                </td>
              </tr>
            ))}
            <tr className="font-semibold">
              <td className="py-1.5">Hard cost</td>
              <td className="py-1.5 text-right tabular-nums">{usd(est.hard_cost)}</td>
              <td />
            </tr>
            {est.markups.map((m) => (
              <tr key={m.name} className="text-slate-600">
                <td className="py-1.5">
                  {m.name} <span className="text-xs">({Math.round(m.pct * 100)}%)</span>
                </td>
                <td className="py-1.5 text-right tabular-nums">{usd(m.amount)}</td>
                <td />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Assumptions (computed by code)</div>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-slate-600">
            {est.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
        {notes && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estimator reasoning</div>
            <p className="mt-1 text-xs text-slate-600">{notes}</p>
          </div>
        )}
      </div>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-0.5 text-lg font-bold tabular-nums">{value}</div>
    </div>
  );
}

function riskTone(score: number) {
  if (score >= 15) return "bg-rose-600 text-white";
  if (score >= 9) return "bg-amber-400 text-amber-950";
  return "bg-emerald-100 text-emerald-800";
}

function RiskCard({ risks }: { risks: RiskItem[] }) {
  return (
    <Card title={`Risk register (${risks.length})`}>
      {risks.length === 0 ? (
        <Empty>No risks flagged.</Empty>
      ) : (
        <ul className="divide-y divide-slate-100">
          {risks.map((r) => (
            <li key={r.id} className="flex gap-3 py-3">
              <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-md text-sm font-bold ${riskTone(r.score)}`} title="likelihood × impact">
                {r.score}
              </div>
              <div className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{r.description}</span>
                  <Pill>{r.category}</Pill>
                  <Pill tone={r.source === "rule" ? "blue" : "slate"}>{r.source === "rule" ? "rule check" : "agent"}</Pill>
                </div>
                <div className="mt-0.5 text-xs text-slate-600">
                  L{r.likelihood} × I{r.impact} · Mitigation: {r.mitigation}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ProposalCard({ run }: { run: RunResponse }) {
  const placeholders = run.state.proposal?.placeholders ?? [];
  return (
    <Card
      title="Proposal draft"
      actions={
        <a href={api.proposalUrl(run.id)} className="rounded-md border border-slate-300 px-3 py-1 text-xs font-semibold hover:bg-slate-50">
          Download .md
        </a>
      }
    >
      {placeholders.length > 0 && (
        <div className="mb-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
          <span className="font-semibold">{placeholders.length} placeholders to fill:</span> {placeholders.slice(0, 6).join(" · ")}
          {placeholders.length > 6 && " …"}
        </div>
      )}
      <article className="prose prose-sm max-w-none prose-headings:font-semibold prose-table:text-xs">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{run.state.proposal_markdown ?? ""}</ReactMarkdown>
      </article>
    </Card>
  );
}

function UsageCard({ run }: { run: RunResponse }) {
  return (
    <Card title="Model usage">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-1">Agent</th>
              <th className="py-1">Model</th>
              <th className="py-1 text-right">Input</th>
              <th className="py-1 text-right">Output</th>
              <th className="py-1 text-right">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 tabular-nums">
            {run.state.usage!.map((u, i) => (
              <tr key={i}>
                <td className="py-1.5">{u.node}</td>
                <td className="py-1.5 font-mono text-xs">{u.model}</td>
                <td className="py-1.5 text-right">{u.input_tokens.toLocaleString()}</td>
                <td className="py-1.5 text-right">{u.output_tokens.toLocaleString()}</td>
                <td className="py-1.5 text-right">${u.cost_usd.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
