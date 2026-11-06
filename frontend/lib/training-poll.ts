// Pure rules for the training screen (no React, no fetch). specs/api.md A2: GET /training, POST /training/stop.
import { ApiError, type BTraining } from "./api";

export const POLL_MS = 3000;

export const STOP_CONFIRM_TEXT =
  "Stop now? You pay for the compute used so far, no success fee, and the rest of the hold is released.";

// Poll only while the project is `training` and the last answer was not a final one.
// `not_started` is normal for a moment right after the hold is confirmed; keep polling through it.
export function nextPollDelay(projectStatus: string, last: Pick<BTraining, "status"> | null): number | null {
  if (projectStatus !== "training") return null;
  if (last && ["done", "stopped", "failed"].includes(last.status)) return null;
  return POLL_MS;
}

export const isFinal = (t: Pick<BTraining, "status"> | null) => !!t && ["done", "stopped", "failed"].includes(t.status);

// A stop that arrives after the run ended answers 409 (api.md). Say that plainly instead of a raw error.
export function stopErrorText(e: unknown): string {
  if (e instanceof ApiError && e.status === 409) return "There is nothing to stop right now. The run may have just finished.";
  return e instanceof Error ? e.message : "We could not stop the run. Please try again.";
}
