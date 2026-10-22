import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, label } from "../api";
import { Card, DecisionBadge, Empty, Spinner } from "../components/ui";
import { useLiveRun } from "../useLiveRun";

function Column({ runId }: { runId: string }) {
  const { run } = useLiveRun(runId);
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: api.profiles });
  if (!run) return <Spinner />;
  const fit = run.state.fit;
  const name = profiles?.find((p) => p.id === run.profile_id)?.name ?? run.profile_id;
  return (
    <Card title={name} actions={fit ? <DecisionBadge decision={fit.decision} size="lg" /> : <Spinner />}>
      {run.status === "error" && <p className="text-sm text-rose-700">{run.error}</p>}
      {!fit ? (
        <Empty>Agents are analyzing…</Empty>
      ) : (
        <div className="space-y-4">
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold tabular-nums">{Math.round(fit.total)}</span>
            <span className="text-sm text-slate-500">/ 100</span>
          </div>
          {fit.gates_triggered.map((g) => (
            <div key={g} className="rounded bg-rose-50 p-2 text-xs text-rose-800">
              {g}
            </div>
          ))}
          <p className="text-sm text-slate-600">{fit.summary}</p>
          <div className="space-y-2">
            {fit.scores.map((c) => (
              <div key={c.criterion} className="text-sm">
                <div className="flex justify-between">
                  <span className="capitalize">{label(c.criterion)}</span>
                  <span className="tabular-nums">{c.score}/5</span>
                </div>
                <div className="mt-0.5 h-1.5 rounded bg-slate-100">
                  <div className="h-1.5 rounded bg-brand-500" style={{ width: `${(c.score / 5) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <div className="text-xs text-slate-500">
            {run.state.own_projects?.length ?? 0} own projects retrieved ·{" "}
            <Link to={`/runs/${run.id}`} className="text-brand-600 underline">
              open full run
            </Link>
          </div>
        </div>
      )}
    </Card>
  );
}

export default function ComparePage() {
  const { data: opps } = useQuery({ queryKey: ["opportunities"], queryFn: api.opportunities });
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: api.profiles });
  const [noticeId, setNoticeId] = useState("");
  const [a, setA] = useState("ryan");
  const [b, setB] = useState("acme");
  const [runs, setRuns] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const compare = async () => {
    setBusy(true);
    try {
      const [ra, rb] = await Promise.all([api.startRun(noticeId, a), api.startRun(noticeId, b)]);
      setRuns([ra.run_id, rb.run_id]);
    } finally {
      setBusy(false);
    }
  };

  const select = "rounded-md border border-slate-300 px-2 py-1.5 text-sm";
  return (
    <div className="space-y-6">
      <Card title="Same opportunity, different companies">
        <p className="mb-4 text-sm text-slate-600">
          Swap the company profile and knowledge base, keep everything else the same, and watch the bid decision change with its evidence.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="min-w-[260px] flex-1 text-sm">
            <div className="mb-1 text-xs font-medium text-slate-500">Opportunity</div>
            <select value={noticeId} onChange={(e) => setNoticeId(e.target.value)} className={`${select} w-full`}>
              <option value="">Choose…</option>
              {opps?.map((o) => (
                <option key={o.notice_id} value={o.notice_id}>
                  {o.title.replace(/^SAMPLE:\s*/, "")}
                </option>
              ))}
            </select>
          </label>
          {[
            [a, setA],
            [b, setB],
          ].map(([value, set], i) => (
            <label key={i} className="text-sm">
              <div className="mb-1 text-xs font-medium text-slate-500">Company {i === 0 ? "A" : "B"}</div>
              <select value={value as string} onChange={(e) => (set as (v: string) => void)(e.target.value)} className={select}>
                {profiles?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <button
            disabled={!noticeId || a === b || busy}
            onClick={compare}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            Compare
          </button>
        </div>
      </Card>
      {runs.length === 2 && (
        <div className="grid gap-6 md:grid-cols-2">
          {runs.map((r) => (
            <Column key={r} runId={r} />
          ))}
        </div>
      )}
    </div>
  );
}
