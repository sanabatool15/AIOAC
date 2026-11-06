// Backend project status -> which screen the demo path shows (specs/api.md B8).
// Pure and total: an unknown status gives "unknown", which renders a safe generic screen.
import type { BProject } from "./api";

export type DemoScreen =
  | "data" // described
  | "readiness" // data_chosen
  | "baseline" // readiness_done
  | "target" // baseline_done: pick a target, run the free pilot
  | "ineligible" // baseline_done / quoted with a forecast that cannot be sold
  | "quote" // baseline_done with an eligible forecast, or quoted
  | "pay" // awaiting_payment
  | "paid" // paid: hold confirmed, start the run
  | "training"
  | "result" // done
  | "stopped"
  | "voided" // voided or failed: our failure or a cancel
  | "unknown";

// 7 plain steps shown in the header. Index 0 to 6.
export const STEP_LABELS = [
  "Your data",
  "Check",
  "Free test",
  "Target and price",
  "Pay",
  "Train",
  "Result",
] as const;

export function screenFor(
  p: Pick<BProject, "status" | "forecast" | "quote"> | null | undefined,
): DemoScreen {
  switch (p?.status) {
    case "described":
      return "data";
    case "data_chosen":
      return "readiness";
    case "readiness_done":
      return "baseline";
    case "baseline_done":
      if (p.forecast && !p.forecast.eligible) return "ineligible";
      return p.forecast ? "quote" : "target";
    case "quoted":
      return p.forecast && !p.forecast.eligible ? "ineligible" : "quote";
    case "awaiting_payment":
      return "pay";
    case "paid":
      return "paid";
    case "training":
      return "training";
    case "done":
      return "result";
    case "stopped":
      return "stopped";
    case "voided":
    case "failed":
      return "voided";
    default:
      return "unknown";
  }
}

export function stepIndex(screen: DemoScreen): number {
  switch (screen) {
    case "data":
      return 0;
    case "readiness":
      return 1;
    case "baseline":
      return 2;
    case "target":
    case "ineligible":
    case "quote":
      return 3;
    case "pay":
    case "paid":
      return 4;
    case "training":
      return 5;
    case "result":
    case "stopped":
    case "voided":
      return 6;
    default:
      return 0;
  }
}

// A run that is still moving: keep polling the project until it settles.
export function isSettling(status: string | undefined): boolean {
  return status === "failed" || status === "training" || status === "paid";
}

// Plain-words label for a project status (sidebar and projects list). Unknown statuses fall back to the raw text.
const STATUS_LABELS: Record<string, string> = {
  described: "Choosing data",
  data_chosen: "Data chosen",
  readiness_done: "Data checked",
  baseline_done: "Free test done",
  quoted: "Price ready",
  awaiting_payment: "Waiting for PayPal",
  paid: "Payment confirmed",
  training: "Training",
  done: "Finished",
  failed: "Stopped by an error",
  stopped: "Stopped",
  voided: "Released, nothing charged",
};
export function statusLabel(status: string | null | undefined): string {
  if (!status) return "";
  return STATUS_LABELS[status] ?? status.replace(/_/g, " ");
}
