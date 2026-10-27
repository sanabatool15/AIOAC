import type { BillingCycle, PlanId, PlanReceipt } from "./types";

// Wizard state kept in sessionStorage (this tab only). Never holds a full card number: brand + last 4 only.
export interface FlowState {
  method?: "paypal" | "card";
  cardLast4?: string;
  cardBrand?: string;
  receipt?: PlanReceipt;
}
const KEY = "aioac.billing";

export function loadFlow(): FlowState {
  try {
    return JSON.parse(sessionStorage.getItem(KEY) ?? "{}") as FlowState;
  } catch {
    return {};
  }
}
export function saveFlow(patch: FlowState) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ ...loadFlow(), ...patch }));
  } catch {
    /* storage unavailable: the wizard still works within the page */
  }
}
export function clearFlow() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export function parseChoice(sp: { plan?: string; cycle?: string }): {
  plan: PlanId;
  cycle: BillingCycle;
} {
  return {
    plan: sp.plan === "team" ? "team" : "pro",
    cycle: sp.cycle === "yearly" ? "yearly" : "monthly",
  };
}
export const choiceQuery = (c: { plan: PlanId; cycle: BillingCycle }) =>
  `plan=${c.plan}&cycle=${c.cycle}`;
