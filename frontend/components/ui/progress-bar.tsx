import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number; // 0-100
  label: string; // accessible name
  track?: "violet" | "blue" | "neutral";
  size?: "default" | "sm";
  className?: string;
}

export function ProgressBar({
  value,
  label,
  track = "violet",
  size = "default",
  className,
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      className={cn(
        "w-full overflow-clip",
        size === "sm" ? "h-1.5 rounded-[3px]" : "h-2.5 rounded-[5px]",
        track === "blue"
          ? "bg-track-blue"
          : track === "neutral"
            ? "bg-surface"
            : "bg-track",
        className,
      )}
    >
      <div
        className={cn(
          "bg-brand-gradient",
          size === "sm" ? "h-1.5 rounded-[3px]" : "h-2.5 rounded-[5px]",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
