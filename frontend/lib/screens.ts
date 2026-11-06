// Pure view rules for the restored screens (project detail, model, usage, billing history, sharing, welcome).
// Inputs are raw backend bodies (specs/api.md section D); money goes through adapters.dollars. No React, no fetch.
import { dollars, outOf100 } from "./adapters";
import type { BActivityItem, BHistory } from "./api";

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
