// The free-test chart: bars on a fixed 0 to 100 scale (out of 100 right), so heights are proportional and honest.

export const AXIS_TICKS = [0, 25, 50, 75, 100] as const;

/** Bar height as a percentage of the chart height. Clamped to 0..100, one decimal. */
export function barPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.round(Math.min(100, Math.max(0, value)) * 10) / 10;
}
