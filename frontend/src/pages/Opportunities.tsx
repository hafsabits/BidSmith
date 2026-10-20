import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, daysUntil, Opportunity } from "../api";
import { Card, DeadlinePill, Empty, Pill, Spinner } from "../components/ui";
import { useProfile } from "../profile";

function shortAgency(agency: string | null) {
  if (!agency) return "—";
  const parts = agency.split(".");
  return parts[parts.length - 1].replace(/\(sample\)/i, "").trim() || parts[0];
}

export default function OpportunitiesPage() {
  const { profileId } = useProfile();
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["opportunities"], queryFn: api.opportunities });
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [selected, setSelected] = useState<Opportunity | null>(null);

  const start = useMutation({
    mutationFn: (noticeId: string) => api.startRun(noticeId, profileId),
    onSuccess: ({ run_id }) => navigate(`/runs/${run_id}`),
  });

  const states = useMemo(() => [...new Set((data ?? []).map((o) => o.place_state).filter(Boolean))].sort() as string[], [data]);
  const rows = (data ?? []).filter(
    (o) =>
      (!state || o.place_state === state) &&
      (!query || `${o.title} ${o.agency} ${o.description}`.toLowerCase().includes(query.toLowerCase())),
  );

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <Card
        title={`Open opportunities (${rows.length})`}
        actions={
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search…"
              className="w-40 rounded-md border border-slate-300 px-2 py-1 text-sm sm:w-56"
            />
            <select value={state} onChange={(e) => setState(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1 text-sm">
              <option value="">All states</option>
              {states.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
        }
      >
        {isLoading ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <Empty>No opportunities. Run `make fetch-sam` to pull from SAM.gov.</Empty>
        ) : (
          <div className="-mx-5 -my-5 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-2">Opportunity</th>
                  <th className="px-3 py-2">Location</th>
                  <th className="px-3 py-2">Set-aside</th>
                  <th className="px-3 py-2">Due</th>
                  <th className="px-5 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((o) => (
                  <tr
                    key={o.notice_id}
                    onClick={() => setSelected(o)}
                    className={`cursor-pointer hover:bg-slate-50 ${selected?.notice_id === o.notice_id ? "bg-brand-50/50" : ""}`}
                  >
                    <td className="min-w-[280px] px-5 py-3">
                      <div className="font-medium text-slate-900">{o.title.replace(/^SAMPLE:\s*/, "")}</div>
                      <div className="text-xs text-slate-500">
                        {shortAgency(o.agency)} · NAICS {o.naics} {o.notice_id.startsWith("SAMPLE") && <Pill tone="amber">sample</Pill>}
                      </div>
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">{[o.place_city, o.place_state].filter(Boolean).join(", ")}</td>
                    <td className="px-3 py-3 text-xs">{o.set_aside ? <Pill tone="blue">{o.set_aside.split(" ")[0]}…</Pill> : "Full & open"}</td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      <DeadlinePill days={daysUntil(o.response_deadline)} />
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          start.mutate(o.notice_id);
                        }}
                        disabled={start.isPending}
                        className="rounded-md bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                      >
                        Analyze
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Solicitation" className="xl:sticky xl:top-20 xl:self-start">
        {selected ? (
          <div className="space-y-3 text-sm">
            <h3 className="font-semibold">{selected.title}</h3>
            <div className="flex flex-wrap gap-1.5">
              <Pill>{selected.notice_type}</Pill>
              <Pill>{selected.solicitation_number}</Pill>
              {selected.set_aside && <Pill tone="blue">{selected.set_aside}</Pill>}
            </div>
            <p className="max-h-[50vh] overflow-y-auto whitespace-pre-line leading-relaxed text-slate-700">{selected.description}</p>
            {selected.url && (
              <a href={selected.url} target="_blank" rel="noreferrer" className="text-brand-600 underline">
                View on SAM.gov
              </a>
            )}
          </div>
        ) : (
          <Empty>Select an opportunity to read it.</Empty>
        )}
        {start.isError && <p className="mt-3 text-sm text-rose-600">{String(start.error)}</p>}
      </Card>
    </div>
  );
}
