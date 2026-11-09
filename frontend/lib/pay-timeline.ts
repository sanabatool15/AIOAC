import { dollars } from "./adapters";
import type { BProject, BReceipt } from "./api";

// The money story of one chat as five plain steps. Pure: every amount is the server's (quote, hold, receipt).
export type TimelineState = "done" | "current" | "todo" | "stopped";
export interface TimelineStep {
  id: "price" | "hold" | "train" | "verify" | "settle";
  label: string;
  detail: string;
  state: TimelineState;
}

const ENDED = ["declined", "expired", "voided"];

export function payTimeline(p: Pick<BProject, "status" | "quote" | "payment">, receipt: BReceipt | null): TimelineStep[] {
  const q = p.quote;
  const pay = receipt ?? p.payment;
  const heldState = pay?.state ?? "";
  const hasHold = !!pay && !ENDED.includes(heldState) && heldState !== "none";
  const trained = ["done", "stopped"].includes(p.status) || ["compute_captured", "fee_captured", "fee_skipped", "released"].includes(heldState);
  const training = p.status === "training";
  const verified = p.status === "done";
  const failed = ["voided", "failed", "stopped"].includes(p.status) || ENDED.includes(heldState);
  const finished = ["compute_captured", "fee_captured", "fee_skipped", "released"].includes(heldState);

  const price: TimelineStep = {
    id: "price",
    label: "Price",
    detail: q ? `The most you can be charged is ${dollars(q.cap_cents)}.` : "Your price appears here after the free test.",
    state: q ? "done" : "current",
  };
  const hold: TimelineStep = {
    id: "hold",
    label: "Hold on PayPal",
    detail: hasHold ? `${dollars(pay?.hold_cents)} is held. Nothing is charged yet.` : failed && pay ? "The hold ended. Nothing was charged." : "PayPal holds up to the cap. It is not a charge.",
    state: hasHold ? "done" : failed && pay ? "stopped" : q ? "current" : "todo",
  };
  const train: TimelineStep = {
    id: "train",
    label: "Training",
    detail: trained ? "The agent finished training." : training ? "The agent is training your model now." : "Starts once the hold is confirmed.",
    state: trained ? "done" : training ? "current" : failed && hasHold ? "stopped" : "todo",
  };
  const verify: TimelineStep = {
    id: "verify",
    label: "Independent test",
    detail: verified ? "A separate test on held-back data checked your target." : "A separate test checks your target. The agent cannot change it.",
    state: verified ? "done" : failed && trained ? "stopped" : trained ? "current" : "todo",
  };
  const settle: TimelineStep = {
    id: "settle",
    label: "Charge or release",
    detail: finished && receipt
      ? receipt.total_charged_cents > 0
        ? `Charged ${dollars(receipt.total_charged_cents)}: compute ${dollars(receipt.compute_captured_cents)} plus fee ${dollars(receipt.fee_captured_cents)}. ${dollars(receipt.released_cents)} released back to you.`
        : `Target missed. Charged ${dollars(0)}; ${dollars(receipt.released_cents)} released back to you.`
      : failed
        ? "The hold was released. You pay nothing for the result."
        : "Target met: you pay the compute used plus the fee, never above the cap. Missed: the hold is released.",
    state: finished ? "done" : failed && hasHold === false && pay ? "stopped" : verified ? "current" : "todo",
  };
  return [price, hold, train, verify, settle];
}

/** What the top-bar pill says, and how loud it is. */
export interface PayPill {
  label: string;
  tone: "quiet" | "primary" | "ok" | "warn";
}

export function payPill(p: Pick<BProject, "status" | "quote" | "payment">): PayPill {
  const s = p.payment?.state ?? "";
  if (["compute_captured", "fee_captured", "fee_skipped"].includes(s)) return { label: "Payment details", tone: "ok" };
  if (s === "released" || s === "voided") return { label: "Released, $0 charged", tone: "quiet" };
  if (s === "held") return { label: `Held ${dollars(p.payment?.hold_cents)}`, tone: "ok" };
  if (["declined", "expired"].includes(s)) return { label: "Payment: try again", tone: "warn" };
  if (p.status === "awaiting_payment") return { label: "Finish payment", tone: "primary" };
  if (p.quote) return { label: `Pay up to ${dollars(p.quote.cap_cents)}`, tone: "primary" };
  return { label: "Payment", tone: "quiet" };
}
