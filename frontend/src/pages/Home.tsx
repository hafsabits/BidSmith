import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { RUN_OPTIONS } from "../agents";
import { api, Estimate, EstimateInputs, Opportunity, Pipeline } from "../api";
import { EstimateResult } from "../components/AgentResults";
import RfpDrawer from "../components/RfpDrawer";
import { Spinner } from "../components/ui";

const BUILDING_TYPES = [
  "office", "warehouse", "manufacturing", "medical_office", "hospital", "laboratory", "senior_living",
  "multifamily", "retail", "data_center", "parking_garage", "education", "public_safety", "other",
];

export default function HomePage() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<Opportunity | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pipeline, setPipeline] = useState<Pipeline>("full");
  const [estimateSource, setEstimateSource] = useState<"rfp" | "manual">("rfp");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const start = useMutation({
    mutationFn: () => api.startRun(text, pipeline, pipeline === "full"),
    onSuccess: ({ run_id }) => navigate(`/runs/${run_id}`),
  });

  const manualEstimate = pipeline === "estimator" && estimateSource === "manual";
  const option = RUN_OPTIONS.find((o) => o.value === pipeline)!;

  const pick = (o: Opportunity) => {
    setPicked(o);
    setText(o.notice_id);
    setDrawerOpen(false);
  };

  return (
    <div className="mx-auto max-w-3xl pt-6 sm:pt-12">
      <div className="text-center">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">What are we bidding on?</h1>
        <p className="mt-2 text-sm text-slate-500">Paste an RFP, a SAM.gov link, or a notice ID. The agents take it from there.</p>
      </div>

      <div className="mt-8 rounded-2xl border border-slate-200 bg-white shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100">
        {manualEstimate ? (
          <ManualEstimate />
        ) : (
          <>
            {picked && (
              <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
                <div className="min-w-0 text-sm">
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-400">Selected RFP</div>
                  <div className="truncate font-medium">{picked.title.replace(/^SAMPLE:\s*/, "")}</div>
                </div>
                <button
                  onClick={() => {
                    setPicked(null);
                    setText("");
                  }}
                  className="text-xs text-slate-500 hover:text-slate-800"
                >
                  Clear
                </button>
              </div>
            )}
            {!picked && (
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={6}
                placeholder="Paste the RFP text here, or a link like https://sam.gov/opp/…/view, or a notice ID"
                className="block w-full resize-y rounded-t-2xl border-0 bg-transparent px-4 py-4 text-sm focus:outline-none focus:ring-0"
              />
            )}
            {file && (
              <div className="mx-4 mb-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate font-medium">📄 {file.name}</span>
                  <button onClick={() => setFile(null)} className="shrink-0 text-amber-700 hover:text-amber-950">
                    Remove
                  </button>
                </div>
                <div className="mt-1">
                  Processing uploads hasn't been implemented yet, so this file will be ignored. Paste the RFP text instead.
                </div>
              </div>
            )}
          </>
        )}

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-3 py-2">
          {!manualEstimate && (
            <>
              <input
                ref={fileInput}
                type="file"
                accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                className="hidden"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  e.target.value = "";
                }}
              />
              <button
                onClick={() => fileInput.current?.click()}
                className="rounded-md px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
                title="Attach a PDF or Word document"
              >
                📎 Attach PDF / Word
              </button>
            </>
          )}
          <select
            value={pipeline}
            onChange={(e) => setPipeline(e.target.value as Pipeline)}
            className="ml-auto rounded-md border border-slate-200 bg-white px-2 py-1.5 text-sm"
          >
            {RUN_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {!manualEstimate && (
            <button
              onClick={() => start.mutate()}
              disabled={!text.trim() || start.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-brand-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40"
            >
              {start.isPending && <Spinner className="h-3 w-3 border-white border-t-transparent" />}
              Run
            </button>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-slate-500">
        <span>{option.hint}</span>
        {pipeline === "estimator" && (
          <div className="flex rounded-md border border-slate-200 bg-white p-0.5">
            {(["rfp", "manual"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setEstimateSource(s)}
                className={`rounded px-2 py-0.5 ${estimateSource === s ? "bg-brand-50 font-medium text-brand-700" : ""}`}
              >
                {s === "rfp" ? "From an RFP" : "Enter parameters"}
              </button>
            ))}
          </div>
        )}
      </div>

      {start.isError && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{(start.error as Error).message}</p>}

      {!manualEstimate && (
        <div className="mt-10 text-center">
          <button
            onClick={() => setDrawerOpen(true)}
            className="rounded-full border border-slate-200 bg-white px-4 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
          >
            Browse RFPs from SAM.gov
          </button>
        </div>
      )}

      <RfpDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onPick={pick} />
    </div>
  );
}

function ManualEstimate() {
  const [form, setForm] = useState<EstimateInputs>({
    building_type: "medical_office",
    gross_sf: 45000,
    sf_assumed: false,
    state: "MN",
    quality: "typical",
    construction_midpoint_year: 2027.5,
    design_build: false,
    premiums: [],
  });
  const [result, setResult] = useState<Estimate | null>(null);
  const run = useMutation({ mutationFn: () => api.estimate(form), onSuccess: setResult });
  const set = <K extends keyof EstimateInputs>(key: K, value: EstimateInputs[K]) => setForm((f) => ({ ...f, [key]: value }));
  const field = "w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm";

  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs text-slate-500">
          Building type
          <select value={form.building_type} onChange={(e) => set("building_type", e.target.value)} className={field}>
            {BUILDING_TYPES.map((b) => (
              <option key={b} value={b}>
                {b.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-500">
          Gross square feet
          <input type="number" min={1} value={form.gross_sf} onChange={(e) => set("gross_sf", Number(e.target.value))} className={field} />
        </label>
        <label className="text-xs text-slate-500">
          State
          <input value={form.state ?? ""} maxLength={2} onChange={(e) => set("state", e.target.value.toUpperCase() || null)} className={field} />
        </label>
        <label className="text-xs text-slate-500">
          Quality
          <select value={form.quality} onChange={(e) => set("quality", e.target.value as EstimateInputs["quality"])} className={field}>
            <option value="low">low</option>
            <option value="typical">typical</option>
            <option value="high">high</option>
          </select>
        </label>
        <label className="text-xs text-slate-500">
          Construction midpoint (year)
          <input type="number" step={0.5} value={form.construction_midpoint_year} onChange={(e) => set("construction_midpoint_year", Number(e.target.value))} className={field} />
        </label>
        <div className="flex flex-col justify-end gap-1 text-xs text-slate-600">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.sf_assumed} onChange={(e) => set("sf_assumed", e.target.checked)} /> Size is an assumption
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={form.design_build} onChange={(e) => set("design_build", e.target.checked)} /> Design-build
          </label>
        </div>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-slate-500">Runs the cost engine directly. No AI, no cost.</span>
        <button onClick={() => run.mutate()} disabled={run.isPending} className="rounded-md bg-brand-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40">
          Estimate
        </button>
      </div>
      {run.isError && <p className="text-sm text-rose-700">{(run.error as Error).message}</p>}
      {result && (
        <div className="border-t border-slate-100 pt-4">
          <EstimateResult est={result} expanded />
        </div>
      )}
    </div>
  );
}
