// Small typed fetch client for the FastAPI backend (contract: specs/api.md section A).
import { API_BASE_URL } from "./config";
import { clearRealUser, redirectToLogin } from "./session";

// Raw backend shapes. snake_case, money in whole cents, rates 0 to 1. Convert only in adapters.ts.
export interface BProject {
  id: string;
  goal: string;
  status: string;
  readiness_grade: string | null;
  trust_level: string | null;
  baseline: { accuracy: number; simple_guess_accuracy: number } | null;
  quote: {
    id: string;
    estimate_cents: number;
    low_cents: number;
    high_cents: number;
    cap_cents: number;
    success_fee_max_cents: number;
    approved: boolean;
  } | null;
  dataset: {
    rows: number;
    columns: number;
    target: string;
    source: string;
    license: string | null;
  } | null;
  readiness: {
    grade: string;
    findings: { kind: string; text: string }[];
  } | null;
  forecast: BForecast | null;
  payment: {
    payment_id: string;
    state: string;
    approve_url: string | null;
    hold_cents: number;
  } | null;
  run: { run_id: string; status: string } | null;
}

export interface BForecast {
  forecast_id: string;
  metric: string;
  target: number;
  is_estimate: boolean;
  predicted_metric: number;
  band_low: number;
  band_high: number;
  confidence: number;
  eligible: boolean;
  reason: string | null;
  min_confidence: number;
  suggested_target: number | null;
  issues: string[];
  pilot?: unknown;
}

export interface BQuote {
  quote_id: string;
  is_estimate: boolean;
  estimate_cents: number;
  low_cents: number;
  high_cents: number;
  cap_cents: number;
  compute_estimate_cents: number;
  compute_cap_cents: number;
  success_fee_estimate_cents: number;
  success_fee_max_cents: number;
  forecast_confidence: number;
  target: number;
  terms: string;
}

export interface BOrder {
  payment_id: string;
  hold_cents: number;
  compute_max_cents: number;
  success_fee_max_cents: number;
  approve_url: string | null;
  state: string;
}

export interface BTraining {
  status: "not_started" | "running" | "done" | "stopped" | "failed";
  run_id?: string;
  stage?: string;
  fraction?: number;
  elapsed_seconds?: number;
  spend_so_far_cents?: number;
  spend_is_estimate?: boolean;
  cap_cents?: number;
  eta?: {
    low_seconds: number;
    high_seconds: number;
    is_estimate: boolean;
  } | null;
  stop_requested?: boolean;
  result?: {
    accuracy?: number;
    simple_guess_accuracy?: number;
    runtime_seconds?: number;
    verification?: { value: number; target: number; passed: boolean };
    error?: string;
    stopped_by_user?: boolean;
  } | null;
}

export interface BReceipt {
  payment_id: string;
  project_id?: string;
  state: string;
  hold_cents: number;
  compute_captured_cents: number;
  fee_captured_cents: number;
  released_cents: number;
  total_charged_cents: number;
  approve_url?: string | null;
}

// Screens on real data (specs/api.md section D).
export interface BHistory {
  versions: {
    id: string;
    parent_id: string | null;
    rows: number;
    columns: number;
    target_column: string;
    source: string;
    license: string | null;
    notes: string | null;
    created_at: string;
  }[];
  runs: {
    id: string;
    status: string;
    backend: string;
    cost_cents: number;
    started_at: string | null;
    finished_at: string | null;
    result: {
      accuracy?: number;
      simple_guess_accuracy?: number;
      verification?: { value: number; target: number; passed: boolean };
    } | null;
  }[];
  quotes: {
    id: string;
    estimate_cents: number;
    low_cents: number;
    high_cents: number;
    cap_cents: number;
    approved: boolean;
    created_at: string;
  }[];
  payment: BReceipt | null;
}

export interface BActivityItem {
  when: string;
  kind: string;
  text: string;
}

export interface BModelColumn {
  name: string;
  kind: "number" | "text";
  example: number | string | null;
  choices: string[] | null;
}
export type BModel =
  | { available: false }
  | {
      available: true;
      trained_at: string;
      target: string;
      accuracy: number | null;
      simple_guess_accuracy: number | null;
      is_estimate_note: string;
      sklearn_version: string | null;
      size_bytes: number;
      usable: boolean;
      unusable_reason: string | null;
      columns: BModelColumn[];
      classes: string[];
    };
export interface BPredict {
  prediction: string | number;
  probabilities: Record<string, number> | null;
  note: string;
}
export interface BBatch {
  rows: number;
  columns: string[];
  preview: Record<string, string | number | null>[];
  csv_text: string;
}

export interface BUsage {
  projects: number;
  training_runs: number;
  compute_charged_cents: number;
  success_fees_cents: number;
  released_cents: number;
  llm_tokens: number;
  llm_cost_micros: number;
  recent_activity: BActivityItem[];
}
export interface BAccountPayment extends BReceipt {
  project_id: string;
  goal: string;
  created_at: string;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// FastAPI sends {"detail": "text"}; a 422 sends {"detail": [{msg, loc}, ...]}.
export function detailMessage(body: unknown, status: number): string {
  const d =
    body && typeof body === "object" ? (body as { detail?: unknown }).detail : undefined;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length > 0) {
    const first = d[0] as { msg?: unknown };
    if (typeof first?.msg === "string") return `Please check your input: ${first.msg}`;
  }
  if (status === 404) return "We could not find that.";
  if (status >= 500) return "The server had a problem. Nothing was charged. Please try again.";
  return "Something went wrong. Please try again.";
}

export async function api<T>(
  path: string,
  init: { method?: string; body?: unknown } = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method ?? (init.body === undefined ? "GET" : "POST"),
      credentials: "include",
      headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError("We could not reach the server. Check that it is running, then try again.", 0);
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* empty or non-JSON body */
  }
  if (!res.ok) {
    // Signed out (or the cookie expired): forget the user and go to login. /auth/* answers are the screen's business.
    if (res.status === 401 && !path.startsWith("/auth/")) {
      clearRealUser();
      redirectToLogin();
    }
    throw new ApiError(detailMessage(body, res.status), res.status);
  }
  return body as T;
}
