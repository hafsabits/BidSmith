/** What each agent produced: a short summary up front, the rest behind "Show details". */
import { ReactNode, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Estimate, FitResult, label, Project, RiskItem, usd } from "../api";
import { DecisionBadge, Pill } from "./ui";

export function Details({ children, open: initial = false, label: text = "details" }: { children: ReactNode; open?: boolean; label?: string }) {
  const [open, setOpen] = useState(initial);
  return (
    <div className="mt-3">
      <button onClick={() => setOpen(!open)} className="text-xs font-medium text-brand-600 hover:text-brand-700">
        {open ? `Hide ${text}` : `Show ${text}`}
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  );
}

function Fact({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{k}</div>
      <div className="text-sm font-medium">{v || "—"}</div>
    </div>
  );
}

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="text-xs font-semibold text-slate-500">{title}</div>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-slate-700">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------

type Analysis = Record<string, unknown> & {
  scope_summary: string;
  building_type: string;
  gross_sf?: number | null;
  sf_is_stated?: boolean;
  assumed_sf_if_missing?: number | null;
  city?: string | null;
  state?: string | null;
  magnitude_low?: number | null;
  magnitude_high?: number | null;
  delivery_method?: string | null;
  set_aside?: string | null;
  evaluation_criteria?: string[];
  special_requirements?: string[];
  key_requirements?: string[];
};

export function AnalystResult({ analysis }: { analysis: Analysis }) {
  const size = analysis.gross_sf
    ? `${analysis.gross_sf.toLocaleString()} SF${analysis.sf_is_stated ? "" : " (implied)"}`
    : analysis.assumed_sf_if_missing
      ? `~${analysis.assumed_sf_if_missing.toLocaleString()} SF (assumed)`
      : null;
  const budget =
    analysis.magnitude_low || analysis.magnitude_high ? `${usd(analysis.magnitude_low, true)} – ${usd(analysis.magnitude_high, true)}` : null;
  return (
    <div>
      <p className="text-sm text-slate-700">{analysis.scope_summary}</p>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Fact k="Building" v={label(analysis.building_type)} />
        <Fact k="Size" v={size} />
        <Fact k="Location" v={[analysis.city, analysis.state].filter(Boolean).join(", ")} />
        <Fact k="Agency budget" v={budget} />
        <Fact k="Delivery" v={analysis.delivery_method} />
        <Fact k="Set-aside" v={analysis.set_aside || "Full and open"} />
      </div>
      <Details>
        <div className="space-y-3">
          <Bullets title="Key requirements" items={analysis.key_requirements ?? []} />
          <Bullets title="Evaluation criteria" items={analysis.evaluation_criteria ?? []} />
          <Bullets title="Special requirements" items={analysis.special_requirements ?? []} />
        </div>
      </Details>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Dots({ score }: { score: number }) {
  return (
    <span className="inline-flex gap-0.5" aria-label={`${score} of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={`h-2 w-2 rounded-full ${i <= score ? "bg-brand-600" : "bg-slate-200"}`} />
      ))}
    </span>
  );
}

export function FitResultView({ fit, own, comps }: { fit: FitResult; own: Project[]; comps: Project[] }) {
  const byId = useMemo(() => new Map([...own, ...comps].map((p) => [p.id, p])), [own, comps]);
  const [openCriterion, setOpenCriterion] = useState<string | null>(null);
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <DecisionBadge decision={fit.decision} size="lg" />
        <span className="text-2xl font-bold tabular-nums">{Math.round(fit.total)}</span>
        <span className="text-sm text-slate-400">/ 100</span>
      </div>
      <p className="mt-2 text-sm text-slate-700">{fit.summary}</p>
      {fit.gates_triggered.length > 0 && (
        <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">{fit.gates_triggered.join(" ")}</div>
      )}
      <div className="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-100">
        {fit.scores.map((c) => (
          <div key={c.criterion}>
            <button
              onClick={() => setOpenCriterion(openCriterion === c.criterion ? null : c.criterion)}
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
            >
              <span className="capitalize">{label(c.criterion)}</span>
              <Dots score={c.score} />
            </button>
            {openCriterion === c.criterion && (
              <div className="px-3 pb-3 text-xs text-slate-600">
                <p>{c.rationale}</p>
                {c.evidence_ids.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {c.evidence_ids.map((id) => {
                      const p = byId.get(id);
                      const isOwn = own.some((o) => o.id === id);
                      return (
                        <span key={id} title={p?.description} className={`rounded px-1.5 py-0.5 ${isOwn ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                          {isOwn ? "Ryan project" : "competitor"}: {p?.title.slice(0, 50) ?? id}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
      <Details label="strengths and concerns">
        <div className="grid gap-4 sm:grid-cols-2">
          <Bullets title="Strengths" items={fit.strengths} />
          <Bullets title="Concerns" items={fit.concerns} />
        </div>
      </Details>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function EstimateResult({ est, notes, expanded = false }: { est: Estimate; notes?: string; expanded?: boolean }) {
  const lines = [...est.lines].sort((a, b) => b.amount - a.amount);
  const top = lines.slice(0, 6);
  const rest = lines.slice(6);
  const restTotal = rest.reduce((s, l) => s + l.amount, 0);
  const shown = [...top, ...(rest.length ? [{ division: "", name: `${rest.length} other divisions`, amount: restTotal, pct: restTotal / est.hard_cost }] : [])];
  const widest = Math.max(...shown.map((l) => l.amount));
  const point = ((est.total - est.low) / (est.high - est.low)) * 100;
  return (
    <div>
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <span className="text-2xl font-bold tabular-nums">{usd(est.total)}</span>
        <span className="text-sm text-slate-500">
          {usd(est.low, true)} – {usd(est.high, true)} · {usd(est.cost_per_sf)}/SF · AACE Class {est.aace_class}
        </span>
        <Pill tone="amber">synthetic cost data</Pill>
      </div>
      <div className="relative mt-3 h-2 rounded-full bg-gradient-to-r from-emerald-200 via-brand-100 to-rose-200">
        <div className="absolute -top-1 h-4 w-1 rounded bg-brand-900" style={{ left: `${point}%` }} />
      </div>
      <div className="mt-4 space-y-1.5">
        {shown.map((l) => (
          <div key={l.name} className="grid grid-cols-[1fr_auto] items-center gap-3 text-sm">
            <div>
              <div className="flex justify-between">
                <span>
                  {l.division && <span className="mr-1.5 font-mono text-xs text-slate-400">{l.division}</span>}
                  {l.name}
                </span>
              </div>
              <div className="mt-0.5 h-1 rounded bg-slate-100">
                <div className="h-1 rounded bg-brand-500" style={{ width: `${(l.amount / widest) * 100}%` }} />
              </div>
            </div>
            <span className="tabular-nums text-slate-600">{usd(l.amount, true)}</span>
          </div>
        ))}
      </div>
      <Details open={expanded} label="full breakdown and assumptions">
        <table className="w-full text-sm">
          <tbody className="divide-y divide-slate-100">
            {lines.map((l) => (
              <tr key={l.division}>
                <td className="py-1">
                  <span className="mr-2 font-mono text-xs text-slate-400">{l.division}</span>
                  {l.name}
                </td>
                <td className="py-1 text-right tabular-nums">{usd(l.amount)}</td>
              </tr>
            ))}
            <tr className="font-semibold">
              <td className="py-1">Hard cost</td>
              <td className="py-1 text-right tabular-nums">{usd(est.hard_cost)}</td>
            </tr>
            {est.markups.map((m) => (
              <tr key={m.name} className="text-slate-600">
                <td className="py-1">
                  {m.name} ({Math.round(m.pct * 100)}%)
                </td>
                <td className="py-1 text-right tabular-nums">{usd(m.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3">
          <Bullets title="Assumptions (computed by code)" items={est.assumptions} />
        </div>
        {notes && <p className="mt-3 text-xs text-slate-600"><span className="font-semibold">Estimator's reasoning: </span>{notes}</p>}
      </Details>
    </div>
  );
}

// ---------------------------------------------------------------------------

function riskTone(score: number) {
  if (score >= 15) return "bg-rose-600 text-white";
  if (score >= 9) return "bg-amber-400 text-amber-950";
  return "bg-emerald-100 text-emerald-800";
}

function RiskRow({ r, full }: { r: RiskItem; full?: boolean }) {
  return (
    <li className="flex gap-3 py-2">
      <span className={`grid h-7 w-7 shrink-0 place-items-center rounded text-xs font-bold ${riskTone(r.score)}`} title="likelihood × impact">
        {r.score}
      </span>
      <div className="min-w-0 text-sm">
        <div className={full ? "" : "line-clamp-2"}>{r.description}</div>
        {full && (
          <div className="mt-0.5 text-xs text-slate-500">
            {r.category} · {r.source === "rule" ? "rule check" : "agent"} · Mitigation: {r.mitigation}
          </div>
        )}
      </div>
    </li>
  );
}

export function RiskResult({ risks }: { risks: RiskItem[] }) {
  const high = risks.filter((r) => r.score >= 12).length;
  return (
    <div>
      <p className="text-sm text-slate-700">
        {risks.length} risks found, {high} high.
      </p>
      <ul className="mt-2 divide-y divide-slate-100">
        {risks.slice(0, 3).map((r) => (
          <RiskRow key={r.id} r={r} />
        ))}
      </ul>
      <Details label={`all ${risks.length} risks with mitigations`}>
        <ul className="divide-y divide-slate-100">
          {risks.map((r) => (
            <RiskRow key={r.id} r={r} full />
          ))}
        </ul>
      </Details>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function WriterResult({ markdown, placeholders, downloadUrl }: { markdown: string; placeholders: string[]; downloadUrl: string }) {
  const sections = [...markdown.matchAll(/^## (.+)$/gm)].map((m) => m[1]);
  return (
    <div>
      <p className="text-sm text-slate-700">
        Drafted {sections.length} sections. {placeholders.length > 0 && <>{placeholders.length} placeholders need real details before submission.</>}
      </p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {sections.map((s) => (
          <Pill key={s}>{s}</Pill>
        ))}
      </div>
      <div className="mt-3">
        <a href={downloadUrl} className="rounded-md border border-slate-300 px-3 py-1 text-xs font-semibold hover:bg-slate-50">
          Download .md
        </a>
      </div>
      <Details label="draft">
        <article className="prose prose-sm max-w-none prose-headings:font-semibold prose-table:text-xs">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
        </article>
      </Details>
    </div>
  );
}
