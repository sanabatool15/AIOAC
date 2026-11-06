// Plain messages shown while a slow chat turn runs (a first reply can take about a minute). Pure, no network.
// `findingData` is true on the first step, where the assistant usually looks for open datasets.
export function thinkingMessage(elapsedSeconds: number, findingData: boolean): string {
  const s = Number.isFinite(elapsedSeconds) ? Math.max(0, elapsedSeconds) : 0;
  if (s < 5) return "The assistant is working…";
  if (s >= 40) return "Still working, this can take up to a minute…";
  if (s >= 20) return "Checking the data…";
  return findingData ? "Looking for open datasets that fit your goal…" : "Thinking it through…";
}
