import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, daysUntil, Opportunity } from "../api";
import { DeadlinePill, Empty, Pill, Spinner } from "./ui";

const PAGE = 5;

function agencyName(agency: string | null) {
  if (!agency) return "";
  const parts = agency.split(".");
  return parts[parts.length - 1].replace(/\(sample\)/i, "").trim();
}

function Row({ o, onPick }: { o: Opportunity; onPick: (o: Opportunity) => void }) {
  return (
    <button onClick={() => onPick(o)} className="block w-full rounded-lg px-3 py-3 text-left hover:bg-slate-50">
      <div className="text-sm font-medium leading-snug">{o.title.replace(/^SAMPLE:\s*/, "")}</div>
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
        <span>{agencyName(o.agency)}</span>
        {o.place_state && <span>· {o.place_state}</span>}
        {o.posted_date && <span>· posted {o.posted_date}</span>}
        <DeadlinePill days={daysUntil(o.response_deadline)} />
        {o.set_aside && !/no set aside/i.test(o.set_aside) && <Pill tone="blue">{o.set_aside.replace(/\s*\(FAR[^)]*\)/i, "").trim()}</Pill>}
      </div>
    </button>
  );
}

export default function RfpDrawer({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (o: Opportunity) => void }) {
  const [tab, setTab] = useState<"sam" | "samples">("sam");
  const [items, setItems] = useState<Opportunity[]>([]);
  const [offset, setOffset] = useState(0);

  const page = useQuery({
    queryKey: ["sam-recent", offset],
    queryFn: () => api.samRecent(offset, PAGE),
    enabled: open && tab === "sam",
  });
  const samples = useQuery({ queryKey: ["samples"], queryFn: api.samples, enabled: open && tab === "samples" });

  useEffect(() => {
    if (page.data) setItems((prev) => [...prev.filter((p) => !page.data.items.some((n) => n.notice_id === p.notice_id)), ...page.data.items]);
  }, [page.data]);

  const older = useMutation({
    mutationFn: api.samOlder,
    onSuccess: () => setOffset((o) => o + PAGE), // show the first of the newly loaded, older notices
  });

  if (!open) return null;
  const data = page.data;

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/20" onClick={onClose}>
      <aside className="flex h-full w-full max-w-md flex-col bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <div className="flex gap-1">
            {(["sam", "samples"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-md px-3 py-1 text-sm font-medium ${tab === t ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}`}
              >
                {t === "sam" ? "Latest on SAM.gov" : "Samples"}
              </button>
            ))}
          </div>
          <button onClick={onClose} className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100" aria-label="Close">
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-2">
          {tab === "samples" ? (
            samples.isLoading ? (
              <Spinner className="m-4" />
            ) : (
              samples.data?.map((o) => <Row key={o.notice_id} o={o} onPick={onPick} />)
            )
          ) : items.length === 0 && page.isLoading ? (
            <Spinner className="m-4" />
          ) : items.length === 0 ? (
            <Empty>No RFPs saved yet. Add a SAM_API_KEY and load from SAM.gov.</Empty>
          ) : (
            items.map((o) => <Row key={o.notice_id} o={o} onPick={onPick} />)
          )}
        </div>

        {tab === "sam" && (
          <footer className="space-y-2 border-t border-slate-100 p-3 text-center">
            {data?.has_more_cached ? (
              <button onClick={() => setOffset(offset + PAGE)} className="w-full rounded-md border border-slate-200 py-1.5 text-sm font-medium hover:bg-slate-50">
                Load more
              </button>
            ) : data?.can_fetch_older ? (
              <button
                onClick={() => older.mutate()}
                disabled={older.isPending}
                className="w-full rounded-md border border-slate-200 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
              >
                {older.isPending ? "Asking SAM.gov…" : "Load older from SAM.gov (uses 1 request)"}
              </button>
            ) : (
              data && <div className="text-xs text-slate-400">That's everything saved.</div>
            )}
            {older.isError && <div className="text-xs text-rose-600">{(older.error as Error).message}</div>}
            <div className="text-[11px] text-slate-400">
              Newest first. Browsing is free; picking an RFP fetches its full text from SAM.gov (1 request).
            </div>
          </footer>
        )}
      </aside>
    </div>
  );
}
