// Pure logic of the PayPal return page (no React, no fetch): the page proves nothing; the SERVER confirms the hold.
// Order, once per visit: find the payment -> skip if the project is already past payment -> authorize (a few tries)
// -> only when held, POST /train exactly once -> go to the project page. specs/api.md A2 and A5.
import { ApiError } from "./api";

export const POLLS = 5;
export const WAIT_MS = 2000;
const PAST_PAYMENT = ["training", "done", "stopped", "failed", "voided"];

export interface ReturnDeps {
  recover: () => Promise<{ paymentId: string; projectId: string } | null>;
  getProjectStatus: (projectId: string) => Promise<string>;
  authorize: (paymentId: string) => Promise<{ held: boolean; state: string }>;
  startTraining: (projectId: string) => Promise<unknown>;
  forget: () => void;
  sleep: (ms: number) => Promise<void>;
}

export type ReturnOutcome =
  | { kind: "go"; projectId: string }
  | { kind: "declined"; projectId: string }
  | { kind: "stuck"; text: string; projectId?: string };

export async function confirmReturn(
  deps: ReturnDeps,
  onStatus: (text: string) => void = () => {},
  opts: { polls?: number; waitMs?: number } = {},
): Promise<ReturnOutcome> {
  const polls = opts.polls ?? POLLS;
  const waitMs = opts.waitMs ?? WAIT_MS;
  try {
    const mem = await deps.recover();
    if (!mem) return { kind: "stuck", text: "We could not find a payment to confirm. Nothing was charged." };
    if (PAST_PAYMENT.includes(await deps.getProjectStatus(mem.projectId))) return { kind: "go", projectId: mem.projectId };
    for (let i = 0; i < polls; i++) {
      const r = await deps.authorize(mem.paymentId);
      if (r.held) {
        onStatus("Hold confirmed. Starting your training run…");
        try {
          await deps.startTraining(mem.projectId);
        } catch (e) {
          if (!(e instanceof ApiError && e.status === 409)) throw e; // 409 = already started (a reload or a second tab)
        }
        deps.forget();
        return { kind: "go", projectId: mem.projectId };
      }
      if (r.state === "declined") return { kind: "declined", projectId: mem.projectId };
      onStatus("PayPal has not confirmed the hold yet. Checking again…");
      if (i < polls - 1) await deps.sleep(waitMs);
    }
    return {
      kind: "stuck",
      projectId: mem.projectId,
      text: "PayPal has not confirmed the hold yet. Nothing has been charged and no training has started. Try again in a moment.",
    };
  } catch (e) {
    return { kind: "stuck", text: e instanceof Error ? e.message : "Something went wrong. Nothing was charged." };
  }
}
