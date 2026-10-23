import { Link, Outlet } from "react-router-dom";

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/" className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-900 text-sm font-bold text-white">B</div>
            <div>
              <div className="text-sm font-bold leading-tight">BidSmith</div>
              <div className="text-[11px] leading-tight text-slate-500">for Ryan Companies (demo)</div>
            </div>
          </Link>
          <Link to="/" className="rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100">
            New analysis
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
        <Outlet />
      </main>
      <footer className="mx-auto w-full max-w-5xl px-4 pb-6 text-center text-xs text-slate-400 sm:px-6">
        Portfolio project, not affiliated with Ryan Companies. Sample RFPs and cost data are illustrative.
      </footer>
    </div>
  );
}
