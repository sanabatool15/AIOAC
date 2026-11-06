// Plain messages shown while a slow chat turn runs (a first reply can take about a minute). Pure, no network.
// `findingData` is true on the first step, where the assistant usually looks for open datasets.
// `readingGoal` is true for the very first reply, which starts on its own right after the project is created.
export function thinkingMessage(elapsedSeconds: number, findingData: boolean, readingGoal = false): string {
  const s = Number.isFinite(elapsedSeconds) ? Math.max(0, elapsedSeconds) : 0;
  if (s < 5) return readingGoal ? "Reading your goal…" : "The assistant is working…";
  if (s >= 40) return "Still working, this can take up to a minute…";
  if (s >= 20) return "Checking the data…";
  return findingData ? "Looking for open datasets that fit your goal…" : "Thinking it through…";
}
