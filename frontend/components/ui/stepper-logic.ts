export type StepState = "done" | "current" | "upcoming";

/** State of each step for a 0-based current index. A current index past the end means all done. */
export function stepStates(count: number, current: number): StepState[] {
  return Array.from({ length: count }, (_, i) => (i < current ? "done" : i === current ? "current" : "upcoming"));
}

export function stepSummary(count: number, current: number): string {
  const n = Math.min(Math.max(current, 0), count - 1) + 1;
  return `Step ${n} of ${count}`;
}
