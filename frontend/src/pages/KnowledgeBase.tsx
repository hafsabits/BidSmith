import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, label, usd } from "../api";
import { Card, Empty, Pill, Spinner } from "../components/ui";
import { useProfile } from "../profile";

export default function KnowledgeBasePage() {
  const { profileId } = useProfile();
  const [owner, setOwner] = useState<string>(profileId);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: api.profiles });
  const { data, isFetching } = useQuery({
    queryKey: ["projects", owner, query],
    queryFn: () => api.projects(owner || undefined, query || undefined),
  });
  const profile = profiles?.find((p) => p.id === owner);

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <div className="mb-1 text-xs font-medium text-slate-500">Company</div>
            <select value={owner} onChange={(e) => setOwner(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1.5 text-sm">
              <option value="">All companies</option>
              {profiles?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <form
            className="flex flex-1 gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setQuery(draft);
            }}
          >
            <label className="flex-1 text-sm">
              <div className="mb-1 text-xs font-medium text-slate-500">Semantic search (local embeddings + pgvector)</div>
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="e.g. occupied courthouse renovation with security upgrades"
                className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              />
            </label>
            <button className="self-end rounded-md bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white">Search</button>
          </form>
        </div>
        {profile && (
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
            <span className="font-semibold text-slate-800">{profile.name}</span> — {profile.description}
            <div className="mt-2 flex flex-wrap gap-1">
              {profile.regions.map((r) => (
                <Pill key={r}>{r}</Pill>
              ))}
              <Pill tone="blue">bonding {usd(profile.bonding_capacity, true)}</Pill>
              {profile.set_aside_eligibility.map((s) => (
                <Pill key={s} tone="emerald">
                  {label(s)}
                </Pill>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card title={query ? `Most similar to “${query}”` : "Largest awards"} actions={isFetching ? <Spinner /> : null}>
        {!data || data.length === 0 ? (
          <Empty>No projects. Run `make ingest` to load the knowledge base.</Empty>
        ) : (
          <div className="-mx-5 -my-5 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-2">Project</th>
                  <th className="px-3 py-2">Owner</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">State</th>
                  <th className="px-3 py-2 text-right">Award</th>
                  {query && <th className="px-5 py-2 text-right">Similarity</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.map((p) => (
                  <tr key={p.id}>
                    <td className="max-w-md px-5 py-2.5">
                      <div className="font-medium">{p.title}</div>
                      <div className="truncate text-xs text-slate-500" title={p.description}>
                        {p.client} · {p.start_date?.slice(0, 4)}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs">{p.owner_company_id}</td>
                    <td className="px-3 py-2.5">
                      <Pill>{label(p.building_type)}</Pill>
                    </td>
                    <td className="px-3 py-2.5">{p.state}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">{usd(p.award_value, true)}</td>
                    {query && <td className="px-5 py-2.5 text-right tabular-nums">{p.similarity?.toFixed(2)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
