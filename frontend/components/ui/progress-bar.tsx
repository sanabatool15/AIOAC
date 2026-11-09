import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number; // 0-100
  label: string; // accessible name
  /** @deprecated The track colour no longer varies. Ignored. */
  track?: "violet" | "blue" | "neutral";
  size?: "default" | "sm";
  className?: string;
}

export function ProgressBar({ value, label, size = "default", className }: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      className={cn("w-full overflow-clip rounded-full bg-brand-track", size === "sm" ? "h-1.5" : "h-2.5", className)}
    >
      <div className="h-full rounded-full bg-grad-brand-x" style={{ width: `${pct}%` }} />
    </div>
  );
}
