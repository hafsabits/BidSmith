import { ReactNode } from "react";
import { Decision, label } from "../api";

export function Card({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {title && (
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

const decisionStyles: Record<Decision, string> = {
  bid: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  review: "bg-amber-100 text-amber-800 ring-amber-200",
  no_bid: "bg-rose-100 text-rose-800 ring-rose-200",
};

export function DecisionBadge({ decision, size = "md" }: { decision: Decision; size?: "md" | "lg" }) {
  const pad = size === "lg" ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs";
  return <span className={`inline-flex rounded-full font-semibold uppercase tracking-wide ring-1 ${pad} ${decisionStyles[decision]}`}>{label(decision)}</span>;
}

export function Pill({ children, tone = "slate" }: { children: ReactNode; tone?: "slate" | "blue" | "amber" | "rose" | "emerald" }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700",
    blue: "bg-brand-50 text-brand-700",
    amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700",
    emerald: "bg-emerald-50 text-emerald-700",
  };
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function Spinner({ className = "" }: { className?: string }) {
  return <span className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent ${className}`} />;
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-slate-500">{children}</p>;
}

export function DeadlinePill({ days }: { days: number | null }) {
  if (days == null) return <Pill>no deadline</Pill>;
  if (days < 0) return <Pill tone="rose">closed</Pill>;
  if (days < 14) return <Pill tone="amber">{days} days left</Pill>;
  return <Pill>{days} days left</Pill>;
}
