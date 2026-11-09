import { dollars } from "./adapters";

// Cap / Held / Charged for the price and pay steps. Every figure comes from the server (quote cap, hold, receipt).
// What the server has not told us yet is shown as "Not yet", never as a guess.

export type HoldPhase = "none" | "waiting" | "approved" | "finished" | "declined" | "expired" | "cancelled";

const NOT_YET = "Not yet";

export function holdPhase(state: string | null | undefined): HoldPhase {
  switch (state) {
    case "none":
      return "waiting";
    case "held":
      return "approved";
    case "compute_captured":
    case "fee_captured":
    case "fee_skipped":
    case "released":
      return "finished";
    case "declined":
      return "declined";
    case "expired":
      return "expired";
    case "voided":
      return "cancelled";
    default:
      return "none";
  }
}

export interface PhaseView {
  label: string;
  tone: "neutral" | "info" | "success" | "warning" | "danger";
}

export function phaseView(phase: HoldPhase): PhaseView {
  switch (phase) {
    case "waiting":
      return { label: "Waiting for your approval", tone: "warning" };
    case "approved":
      return { label: "Hold approved, nothing charged yet", tone: "success" };
    case "finished":
      return { label: "Finished", tone: "success" };
    case "declined":
      return { label: "Declined by PayPal", tone: "danger" };
    case "expired":
      return { label: "Hold expired", tone: "danger" };
    case "cancelled":
      return { label: "Cancelled, hold released", tone: "neutral" };
    default:
      return { label: "No hold yet", tone: "neutral" };
  }
}

export interface MoneySummary {
  cap: string;
  held: string;
  charged: string;
  phase: HoldPhase;
}

export function moneySummary(
  capCents: number | null | undefined,
  pay: { state: string; hold_cents: number; total_charged_cents?: number | null } | null | undefined,
): MoneySummary {
  const phase = holdPhase(pay?.state);
  const cap = capCents !== null && capCents !== undefined ? dollars(capCents) : pay ? dollars(pay.hold_cents) : NOT_YET;
  let held = NOT_YET;
  let charged = NOT_YET;
  switch (phase) {
    case "approved":
      held = dollars(pay?.hold_cents);
      break;
    case "finished":
      held = dollars(pay?.hold_cents);
      charged = dollars(pay?.total_charged_cents);
      break;
    case "declined":
    case "expired":
      held = "Nothing held";
      charged = dollars(0);
      break;
    case "cancelled":
      held = "Released";
      charged = dollars(0);
      break;
    default:
      break;
  }
  return { cap, held, charged, phase };
}

/** Cap / Held / Charged for a project. `withPayment: false` ignores the stored hold (a fresh quote has none yet). */
export function projectMoney(
  p: { quote: { cap_cents: number } | null; payment: { state: string; hold_cents: number } | null },
  withPayment = true,
): MoneySummary {
  return moneySummary(p.quote?.cap_cents, withPayment ? p.payment : null);
}
