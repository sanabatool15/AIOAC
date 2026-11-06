// Pure view rules for the restored screens (project detail, model, usage, billing history, sharing, welcome).
// Inputs are raw backend bodies (specs/api.md section D); money goes through adapters.dollars. No React, no fetch.
import { dollars, outOf100 } from "./adapters";
import type { BPublicResult, BAccountPayment, BActivityItem, BHistory, BModelColumn, BPredict, BUsage } from "./api";

// "2026-11-06T17:13:05.3" -> "Nov 6, 17:13". The server sends UTC; a value with no zone is read as UTC.
// `timeZone` is for tests; screens leave it out and show the viewer's own time.
export function formatWhen(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return "";
  const hasZone = /(Z|[+-]\d\d:?\d\d)$/.test(iso);
  const d = new Date(hasZone ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone,
  }).format(d);
}

// The payment state in plain words. A released hold with $0 charged says so.
export function paymentStateLabel(state: string, totalChargedCents = 0): string {
  switch (state) {
    case "none":
      return "Waiting for your PayPal approval";
    case "held":
      return "Held, nothing charged yet";
    case "compute_captured":
      return "Compute charged, finishing up";
    case "fee_captured":
      return "Finished: compute and success fee charged";
    case "fee_skipped":
      return "Finished: compute only, no success fee";
    case "released":
      return totalChargedCents > 0 ? "Finished: the rest was released" : "Nothing charged, hold released";
    case "voided":
      return "Cancelled, nothing charged";
    case "expired":
      return "Expired, nothing charged";
    case "declined":
      return "Declined by PayPal, nothing charged";
    default:
      return state.replace(/_/g, " ");
  }
}

export function runStatusLabel(status: string): string {
  switch (status) {
    case "running":
      return "Running";
    case "done":
      return "Finished";
    case "stopped":
      return "Stopped by you";
    case "failed":
      return "Stopped by an error on our side";
    default:
      return status.replace(/_/g, " ");
  }
}

export interface HistoryView {
  versions: { id: string; title: string; detail: string; when: string }[];
  runs: { id: string; status: string; when: string; cost: string; result: string; passed: boolean | null }[];
  quotes: { id: string; estimate: string; range: string; cap: string; approved: boolean; when: string }[];
  payment: { state: string; held: string; compute: string; fee: string; released: string; total: string } | null;
}

function quoteRange(low: number, high: number): string {
  return low === high ? dollars(low) : `${dollars(low)} to ${dollars(high)}`;
}

export function toHistory(h: BHistory | null | undefined): HistoryView {
  const pay = h?.payment ?? null;
  return {
    versions: (h?.versions ?? []).map((v) => ({
      id: v.id,
      title: v.parent_id ? "Cleaned version of your data" : "Your data",
      detail: `${v.rows.toLocaleString("en-US")} rows, ${v.columns} columns, predicting "${v.target_column}". Source: ${v.source}${v.license ? `, license: ${v.license}` : ""}.${v.notes ? ` ${v.notes}` : ""}`,
      when: formatWhen(v.created_at),
    })),
    runs: (h?.runs ?? []).map((r) => {
      const ver = r.result?.verification;
      let result = "No result saved.";
      if (ver) {
        result = `Checked once on test data we kept aside: about ${outOf100(ver.value)} right, target ${outOf100(ver.target)}. ${ver.passed ? "Target reached." : "Target not reached."}`;
      } else if (r.result?.accuracy !== undefined) {
        result = `About ${outOf100(r.result.accuracy)} right (an estimate).`;
      }
      return {
        id: r.id,
        status: runStatusLabel(r.status),
        when: formatWhen(r.finished_at ?? r.started_at),
        cost: dollars(r.cost_cents),
        result,
        passed: ver ? ver.passed === true : null,
      };
    }),
    quotes: (h?.quotes ?? []).map((q) => ({
      id: q.id,
      estimate: dollars(q.estimate_cents),
      range: quoteRange(q.low_cents, q.high_cents),
      cap: dollars(q.cap_cents),
      approved: q.approved,
      when: formatWhen(q.created_at),
    })),
    payment: pay
      ? {
          state: paymentStateLabel(pay.state, pay.total_charged_cents),
          held: dollars(pay.hold_cents),
          compute: dollars(pay.compute_captured_cents),
          fee: dollars(pay.fee_captured_cents),
          released: dollars(pay.released_cents),
          total: dollars(pay.total_charged_cents),
        }
      : null,
  };
}

export interface ActivityView {
  key: string;
  when: string;
  text: string;
}
export function toActivity(items: BActivityItem[] | null | undefined): ActivityView[] {
  return (items ?? []).map((a, i) => ({ key: `${i}-${a.when}`, when: formatWhen(a.when), text: a.text }));
}

// The one-line summary on the Overview tab, from the project status. Plain words; the chat page does the work.
export function overviewLine(status: string): string {
  switch (status) {
    case "described":
      return "Next: choose the data to learn from.";
    case "data_chosen":
      return "Next: check the data is ready.";
    case "readiness_done":
      return "Next: run the free test.";
    case "baseline_done":
      return "Next: pick a target and see a price estimate.";
    case "quoted":
      return "A price estimate is ready for your approval.";
    case "awaiting_payment":
      return "Waiting for your PayPal approval. Nothing is charged yet.";
    case "paid":
      return "Your PayPal hold is confirmed. Training is about to start.";
    case "training":
      return "Training is running.";
    case "done":
      return "The run is finished.";
    case "stopped":
      return "The run was stopped. You paid for the compute used so far, no success fee.";
    case "voided":
    case "failed":
      return "This run did not go ahead. You paid $0.";
    default:
      return "";
  }
}

// ---------------------------------------------------------------- the model tab

export const MAX_BATCH_ROWS = 5000;

// What the user typed in the "try one record" form -> the body of POST /predict.
// Empty fields are left out (the model fills them in). A number column needs a number.
export function buildRecord(
  columns: Pick<BModelColumn, "name" | "kind">[],
  values: Record<string, string>,
): { record: Record<string, string | number>; error: string | null } {
  const record: Record<string, string | number> = {};
  for (const c of columns) {
    const raw = (values[c.name] ?? "").trim();
    if (raw === "") continue;
    if (c.kind === "number") {
      const n = Number(raw);
      if (!Number.isFinite(n)) return { record: {}, error: `"${c.name}" needs a number, for example 12 or 3.5.` };
      record[c.name] = n;
    } else {
      record[c.name] = raw;
    }
  }
  if (Object.keys(record).length === 0) return { record, error: "Fill in at least one field." };
  return { record, error: null };
}

export interface PredictionView {
  answer: string;
  rows: { label: string; text: string; share: number }[];
  note: string;
}
// Probabilities as "about N out of 100", biggest first. Always carries the "estimate, not a promise" note.
export function toPrediction(r: BPredict): PredictionView {
  const rows = Object.entries(r.probabilities ?? {})
    .map(([label, p]) => ({ label, text: `about ${Math.round(p * 100)} out of 100`, share: p }))
    .sort((a, b) => b.share - a.share);
  return { answer: String(r.prediction), rows, note: r.note || "an estimate, not a promise" };
}

// Rows in pasted or picked CSV text (header not counted, blank lines ignored).
export function csvRowCount(text: string): number {
  const lines = text.split(/\r?\n/).filter((l) => l.trim() !== "");
  return Math.max(0, lines.length - 1);
}
export function batchProblem(text: string): string | null {
  if (text.trim() === "") return "Paste CSV text or pick a CSV file first.";
  const n = csvRowCount(text);
  if (n < 1) return "The CSV needs a header line and at least one row.";
  if (n > MAX_BATCH_ROWS) return `That file has ${n.toLocaleString("en-US")} rows. The limit is ${MAX_BATCH_ROWS.toLocaleString("en-US")}. Please use a smaller file.`;
  return null;
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function sklearnNote(version: string | null | undefined): string {
  return version
    ? `To open this file you need scikit-learn ${version} (use joblib.load). Another version may not load it.`
    : "To open this file you need the same scikit-learn version it was trained with.";
}

export function cellText(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return "";
  return typeof v === "number" && !Number.isInteger(v) ? String(Math.round(v * 10000) / 10000) : String(v);
}

// ---------------------------------------------------------------- project tabs

export const TABS = ["Overview", "History", "Activity", "Model"] as const;
export type TabId = (typeof TABS)[number];
// ?tab=model on /projects/{id} opens the Model tab. Anything else opens Overview.
export function tabFromQuery(raw: string | undefined): TabId {
  return TABS.find((t) => t.toLowerCase() === raw?.toLowerCase()) ?? "Overview";
}

// ---------------------------------------------------------------- account: usage and billing history

export interface UsageView {
  tiles: { label: string; value: string; note?: string }[];
  llmCost: string | null; // shown only when the model service reported a cost
  activity: ActivityView[];
}

// AI model cost is in millionths of a dollar. Shown only when above zero, and always called an estimate.
export function llmCostText(micros: number | null | undefined): string | null {
  if (!micros || micros <= 0) return null;
  return `$${(micros / 1_000_000).toFixed(micros >= 10_000 ? 2 : 4)}`;
}

export function toUsage(u: BUsage | null | undefined): UsageView | null {
  if (!u) return null;
  const llmCost = llmCostText(u.llm_cost_micros);
  return {
    tiles: [
      { label: "Projects", value: u.projects.toLocaleString("en-US") },
      { label: "Training runs", value: u.training_runs.toLocaleString("en-US") },
      { label: "Compute charged", value: dollars(u.compute_charged_cents), note: "PayPal sandbox, test money" },
      { label: "Success fees charged", value: dollars(u.success_fees_cents), note: "Only when a result was verified" },
      { label: "Released back to you", value: dollars(u.released_cents), note: "Holds not used" },
      {
        label: "AI assistant tokens",
        value: u.llm_tokens.toLocaleString("en-US"),
        note: llmCost ? `Estimated cost ${llmCost}` : undefined,
      },
    ],
    llmCost,
    activity: toActivity(u.recent_activity),
  };
}

export interface BillingRow {
  id: string;
  projectId: string;
  goal: string;
  state: string;
  held: string;
  compute: string;
  fee: string;
  released: string;
  total: string;
  when: string;
}
export function toBilling(list: BAccountPayment[] | null | undefined): BillingRow[] {
  return (list ?? []).map((p) => ({
    id: p.payment_id,
    projectId: p.project_id,
    goal: p.goal,
    state: paymentStateLabel(p.state, p.total_charged_cents),
    held: dollars(p.hold_cents),
    compute: dollars(p.compute_captured_cents),
    fee: dollars(p.fee_captured_cents),
    released: dollars(p.released_cents),
    total: dollars(p.total_charged_cents),
    when: formatWhen(p.created_at),
  }));
}

// ---------------------------------------------------------------- sharing

// The link a person copies. Built from the page's own origin, so it works on any host.
export function shareLink(origin: string, token: string): string {
  return `${origin.replace(/\/+$/, "")}/s/${token}`;
}

export interface PublicView {
  goal: string;
  dataset: string | null;
  answerColumn: string | null;
  freeTest: string | null;
  verified: { value: string; target: string; passed: boolean } | null;
  finished: string;
  note: string;
}
// The public page shows results only. This reads exactly the keys the server sends and nothing else.
export function toPublic(r: BPublicResult): PublicView {
  return {
    goal: r.goal,
    dataset: r.dataset ? `${r.dataset.name} (${r.dataset.rows.toLocaleString("en-US")} rows)` : null,
    answerColumn: r.dataset?.target ?? null,
    freeTest: r.baseline
      ? `about ${outOf100(r.baseline.accuracy)} right, a simple guess gets ${outOf100(r.baseline.simple_guess_accuracy)}`
      : null,
    verified: r.verification
      ? { value: outOf100(r.verification.value), target: outOf100(r.verification.target), passed: r.verification.passed === true }
      : null,
    finished: formatWhen(r.finished_at),
    note: r.is_estimate_note || "These numbers are estimates, not a promise about future results.",
  };
}
export const PUBLIC_NOT_AVAILABLE = "This link is not available";
