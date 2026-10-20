import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api";
import { useProfile } from "../profile";

const links = [
  { to: "/", label: "Opportunities" },
  { to: "/knowledge", label: "Knowledge Base" },
  { to: "/compare", label: "Compare" },
];

export default function Layout() {
  const { profileId, setProfileId } = useProfile();
  const { data: profiles } = useQuery({ queryKey: ["profiles"], queryFn: api.profiles });

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-900 text-sm font-bold text-white">B</div>
            <div>
              <div className="text-sm font-bold leading-tight">BidSmith</div>
              <div className="text-[11px] leading-tight text-slate-500">Multi-agent bid / no-bid & proposals</div>
            </div>
          </div>
          <nav className="flex gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium ${isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100"}`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <label className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-slate-500">Bidding as</span>
            <select
              value={profileId}
              onChange={(e) => setProfileId(e.target.value)}
              className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm font-medium"
            >
              {profiles?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.project_count} projects
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-400 sm:px-6">
        Portfolio project. Not affiliated with any company named. Sample opportunities and cost data are illustrative.
      </footer>
    </div>
  );
}
