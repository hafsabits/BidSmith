export type Decision = "bid" | "review" | "no_bid";

export interface Profile {
  id: string;
  name: string;
  description: string;
  regions: string[];
  building_types: string[];
  bonding_capacity: number;
  set_aside_eligibility: string[];
  is_demo_peer: boolean;
  project_count: number;
}

export interface Opportunity {
  notice_id: string;
  title: string;
  solicitation_number: string | null;
  agency: string | null;
  notice_type: string | null;
  posted_date: string | null;
  response_deadline: string | null;
  naics: string | null;
  set_aside: string | null;
  place_city: string | null;
  place_state: string | null;
  description: string;
  url: string | null;
}

export interface Project {
  id: string;
  owner_company_id: string;
  title: string;
  client: string | null;
  award_value: number | null;
  start_date: string | null;
  state: string | null;
  building_type: string;
  description: string;
  similarity?: number;
}

export interface CriterionScore {
  criterion: string;
  score: number;
  rationale: string;
  evidence_ids: string[];
}

export interface FitResult {
  total: number;
  decision: Decision;
  gates_triggered: string[];
  scores: CriterionScore[];
  summary: string;
  strengths: string[];
  concerns: string[];
}

export interface Estimate {
  inputs: Record<string, unknown>;
  aace_class: number;
  accuracy_low_pct: number;
  accuracy_high_pct: number;
  hard_cost: number;
  lines: { division: string; name: string; pct: number; amount: number }[];
  markups: { name: string; pct: number; amount: number }[];
  total: number;
  low: number;
  high: number;
  cost_per_sf: number;
  assumptions: string[];
}

export interface RiskItem {
  id: string;
  category: string;
  description: string;
  likelihood: number;
  impact: number;
  score: number;
  mitigation: string;
  source: "rule" | "llm";
}

export interface UsageRecord {
  node: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface RunState {
  analysis?: Record<string, unknown> & { scope_summary: string; building_type: string };
  own_projects?: Project[];
  comps?: Project[];
  fit?: FitResult;
  human_decision?: Decision;
  human_note?: string;
  estimate?: Estimate;
  estimator_notes?: string;
  risks?: RiskItem[];
  proposal_markdown?: string;
  proposal?: { placeholders: string[]; cited_project_ids: string[] };
  usage?: UsageRecord[];
  trace?: TraceItem[];
}

export type RunStatus = "running" | "waiting_review" | "done" | "error";

export interface RunResponse {
  id: string;
  notice_id: string;
  profile_id: string;
  status: RunStatus;
  error: string | null;
  state: RunState;
  total_cost_usd: number;
  total_tokens: number;
}

export interface TraceItem {
  node: string;
  message: string;
  detail?: string;
}

export interface RunEvent {
  seq: number;
  ts: number;
  type: "trace" | "node_done" | "status";
  node?: string;
  message?: string;
  detail?: string;
  status?: RunStatus;
  error?: string;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  profiles: () => http<Profile[]>("/api/profiles"),
  opportunities: () => http<Opportunity[]>("/api/opportunities"),
  opportunity: (id: string) => http<Opportunity>(`/api/opportunities/${id}`),
  projects: (owner?: string, q?: string) => {
    const params = new URLSearchParams();
    if (owner) params.set("owner", owner);
    if (q) params.set("q", q);
    params.set("limit", "60");
    return http<Project[]>(`/api/projects?${params}`);
  },
  startRun: (notice_id: string, profile_id: string) =>
    http<{ run_id: string }>("/api/runs", { method: "POST", body: JSON.stringify({ notice_id, profile_id }) }),
  run: (id: string) => http<RunResponse>(`/api/runs/${id}`),
  decide: (id: string, decision: Decision, note: string) =>
    http<{ ok: boolean }>(`/api/runs/${id}/decision`, { method: "POST", body: JSON.stringify({ decision, note }) }),
  proposalUrl: (id: string) => `/api/runs/${id}/proposal.md`,
  eventsUrl: (id: string) => `/api/runs/${id}/events`,
};

export const usd = (n: number | null | undefined, compact = false) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: compact ? 1 : 0,
        notation: compact ? "compact" : "standard",
      }).format(n);

export const daysUntil = (iso: string | null) =>
  iso ? Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000) : null;

export const label = (s: string) => s.replace(/_/g, " ");
