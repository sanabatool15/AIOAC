import { StatusIcon } from "@/components/ui/status-icon";
import type { Step, ToolId } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TraceCardProps {
  title: string;
  stepLabel: string;
  steps: Step[];
  filter?: ToolId | null;
}

export function TraceCard({ title, stepLabel, steps, filter }: TraceCardProps) {
  const shown = filter ? steps.filter((s) => s.tool === filter) : steps;
  return (
    <div className="flex w-full flex-col rounded-xl border border-trace-border bg-trace shadow-trace">
      <div className="flex items-center justify-between rounded-t-xl border-b border-border bg-trace-head px-4 py-3">
        <p className="text-sm font-semibold leading-5 text-brand-deep">
          {title}
        </p>
        <p className="text-xs leading-[17px] text-brand-mid">{stepLabel}</p>
      </div>
      <ul className="flex flex-col gap-0.5 p-2">
        {shown.length === 0 && (
          <li className="p-2 text-sm text-muted">
            No steps for this tool yet.
          </li>
        )}
        {shown.map((s) => (
          <li
            key={s.id}
            aria-current={s.status === "running" ? "step" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-lg border p-2",
              s.status === "running"
                ? "border-brand-line bg-brand-tint"
                : "border-transparent",
            )}
          >
            <StatusIcon status={s.status} />
            <span
              className={cn(
                "flex-1 text-sm leading-5",
                s.status === "pending" ? "text-muted" : "text-ink",
                s.status === "running" && "font-medium",
              )}
            >
              {s.label}
            </span>
            {s.meta && (
              <span className="whitespace-nowrap text-xs leading-[17px] text-muted">
                {s.meta}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
