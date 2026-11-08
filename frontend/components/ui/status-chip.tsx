import { cn } from "@/lib/utils";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE: Record<StatusTone, { chip: string; dot: string }> = {
  neutral: { chip: "border-border bg-surface text-ink-2", dot: "bg-muted" },
  info: { chip: "border-brand-line bg-brand-tint text-brand-ink", dot: "bg-brand" },
  success: { chip: "border-success-line bg-success-soft text-success", dot: "bg-success" },
  warning: { chip: "border-warning-line bg-warning-soft text-warning", dot: "bg-warning" },
  danger: { chip: "border-danger-line bg-danger-soft text-danger", dot: "bg-danger" },
};

/** A status with a dot and a word, so colour is never the only signal. */
export function StatusChip({
  tone = "neutral",
  children,
  className,
}: {
  tone?: StatusTone;
  children: React.ReactNode;
  className?: string;
}) {
  const t = TONE[tone];
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-micro font-medium", t.chip, className)}>
      <span aria-hidden className={cn("size-1.5 rounded-full", t.dot)} />
      {children}
    </span>
  );
}
