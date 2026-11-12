// Small typed fetch client for the FastAPI backend (contract: specs/api.md section A).
import { API_BASE_URL } from "./config";
import { clearRealUser, redirectToLogin } from "./session";

// Raw backend shapes. snake_case, money in whole cents, rates 0 to 1. Convert only in adapters.ts.
// The kind of model a price or forecast is for, in plain words. `note` says it is only the type that was tested.
export interface BModelType {
  family: string;
  name: string;
  note: string;
}

export type TaskType = "classification" | "regression" | "forecast" | "grouping" | "unusual";

export interface BProject {
  id: string;
  goal: string;
  status: string;
  readiness_grade: string | null;
  trust_level: string | null;
  // The kind of prediction. Missing on old servers: read as a yes/no or group answer.
  task_type?: TaskType;
  task?: { id: TaskType; plain_name: string; needs_target: boolean; pays_success_fee: boolean };
  // `plain` is set only for a number, a forecast, groups or unusual records: the screen shows these words as they are.
  baseline: { accuracy: number; simple_guess_accuracy: number; plain?: { result: string; guess: string } } | null;
  quote: {
    id: string;
    estimate_cents: number;
    low_cents: number;
    high_cents: number;
    cap_cents: number;
    success_fee_max_cents: number;
    approved: boolean;
    model_type?: BModelType | null;
  } | null;
  dataset: {
    rows: number;
    columns: number;
    target: string;
    source: string;
    license: string | null;
    fixed?: boolean; // a guided data fix made this version
    notes?: string | null;
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
  model_type?: BModelType | null;
  task_type?: TaskType;
  // Ready-made words for a number, a forecast, groups or unusual records (all estimates).
  plain?: {
    typical_error_text?: string;
    band_text: string;
    target_text: string;
    confidence_text: string;
    simple_guess_error_text?: string;
    steadiness_text?: string;
  } | null;
  // The forecast made on the data BEFORE a guided fix; null when no fix was applied.
  before_fix?: {
    predicted_metric: number;
    band_low: number;
    band_high: number;
    confidence: number;
    target: number;
    eligible: boolean;
  } | null;
}

// A guided data fix: what it WOULD change (propose) and what it did (apply). specs/api.md section E.
export interface BFixProposal {
  available: boolean;
  version_id: string;
  message: string;
  rows_before: number;
  rows_after: number;
  columns_before: number;
  columns_after: number;
  rows_removed: number;
  columns_dropped: string[];
  steps: { kind: string; what: string; why: string }[];
  fixes_used: number;
  fixes_left: number;
  note: string;
}
export interface BFixResult {
  version_id: string;
  status: string;
  rows_before: number;
  rows_after: number;
  columns_before: number;
  columns_after: number;
  rows_removed: number;
  columns_dropped: string[];
  fixes_left: number;
  next: string;
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
  model_type?: BModelType | null;
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
    verification?: { value: number; target: number; passed: boolean; typical_error?: number };
    // A number, a forecast, groups or unusual records: the final check in plain words (an estimate).
    task_type?: TaskType;
    final_check_text?: string;
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
    round?: number; // 1 = the first attempt
    version_no?: number | null; // the model version this run saved
    dataset_version_id?: string | null;
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
  payments?: (BReceipt & { quote_id?: string | null; created_at?: string | null })[]; // every hold, oldest first
}

export interface BActivityItem {
  when: string;
  kind: string;
  text: string;
}

export interface BModelColumn {
  name: string;
  label: string | null; // plain-English label from the server, null when unknown (show the raw name only)
  kind: "number" | "text";
  example: number | string | null;
  choices: string[] | null;
}
export type BModel =
  | { available: false }
  | {
      available: true;
      model_id?: string;
      version_no?: number | null;
      is_current?: boolean;
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
      task_type?: TaskType;
      // a forecast only: how often the series repeats, how far ahead it was tested and where its history ends
      period?: string;
      horizon?: number | null;
      last_date?: string;
    };
// One saved model of a project (GET /projects/{id}/model/versions, newest first).
export interface BModelVersion {
  model_id: string;
  version_no: number;
  created_at: string;
  is_current: boolean;
  accuracy: number | null;
  simple_guess_accuracy: number | null;
  verified_value: number | null; // 0 to 1, score on rows the model never saw (an estimate)
  target: number | null;
  passed: boolean | null;
  dataset_version_id: string | null;
  dataset_rows: number | null;
  usable: boolean;
}
export interface BPredict {
  prediction: string | number | number[];
  probabilities: Record<string, number> | null;
  note: string;
  task_type?: TaskType;
  typical_error?: number | null; // a number or a forecast: how far off it usually is on rows it never saw
  dates?: string[]; // a forecast: the date of each predicted period
  period?: string; // a forecast: "month", "week" and so on
  group?: number; // grouping: which group, from 1
  looks_unusual?: boolean; // unusual records
  unusual_score?: number; // unusual records: 0 to 1
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

export interface BShare {
  enabled: boolean;
  token: string | null;
  created_at: string | null;
}
export interface BPublicResult {
  goal: string;
  status: string;
  dataset: { name: string; rows: number; target: string } | null;
  baseline: { accuracy: number; simple_guess_accuracy: number } | null;
  verification: { value: number; target: number; passed: boolean } | null;
  version_no?: number | null; // the version in use; no other version is ever shown
  finished_at: string | null;
  is_estimate_note: string;
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
  init: { method?: string; body?: unknown; timeoutMs?: number } = {},
): Promise<T> {
  // /public/* needs no login: send no cookies and never send the browser to the login screen.
  const isPublic = path.startsWith("/public/");
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method ?? (init.body === undefined ? "GET" : "POST"),
      credentials: isPublic ? "omit" : "include",
      headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      signal: init.timeoutMs ? AbortSignal.timeout(init.timeoutMs) : undefined,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") throw new ApiError("This is taking longer than expected. Nothing was charged. Reload the page to see if it finished, or try again.", 0);
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
    if (res.status === 401 && !isPublic && !path.startsWith("/auth/")) {
      clearRealUser();
      redirectToLogin();
    }
    throw new ApiError(detailMessage(body, res.status), res.status);
  }
  return body as T;
}
