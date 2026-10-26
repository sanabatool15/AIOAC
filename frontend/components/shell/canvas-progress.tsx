import { LoaderCircle, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { StatusIcon } from "@/components/ui/status-icon";
import type { HoldPart, Job } from "@/lib/types";
import { cn } from "@/lib/utils";

const swatch: Record<HoldPart["tone"], string> = {
  primary: "bg-brand",
  next: "bg-brand-edge",
  buffer: "bg-hold-buffer",
};

function TrainingCard({ job }: { job: Job }) {
  const { eta } = job;
  return (
    <Card variant="blue">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold leading-5 text-ink">
          Training model
        </h2>
        <Badge variant="outline">
          <LoaderCircle
            aria-hidden
            size={12}
            className="motion-safe:animate-spin"
          />
          Running
        </Badge>
      </div>
      <div className="flex flex-col gap-0.5">
        <p className="text-[28px] font-semibold leading-[34px] tracking-[-0.4px] text-ink">
          {eta.minLow} to {eta.minHigh} min left
        </p>
        <p className="text-[13px] leading-[19px] text-muted">
          Estimated finish about {eta.finishLabel} · range narrows as it runs
        </p>
      </div>
      <ProgressBar
        track="blue"
        label="Training progress"
        value={eta.progress * 100}
      />
      <ol className="flex items-start justify-between">
        {job.stages.map((s) => (
          <li key={s.name} className="flex flex-col items-center gap-1.5">
            <StatusIcon
              status={s.status}
              size={14}
              className={s.status === "pending" ? "text-ink" : undefined}
            />
            <span
              className={cn(
                "text-[11px] leading-4",
                s.status === "pending" ? "text-muted" : "text-ink",
                s.status === "running" && "font-semibold",
              )}
            >
              {s.name}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}

function HoldCard({ job }: { job: Job }) {
  const { hold } = job;
  return (
    <Card variant="peach">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold leading-5 text-ink">
          Where your ${hold.maxUsd} hold goes
        </h2>
        <Badge>Max ${hold.maxUsd}</Badge>
      </div>
      <div
        className="flex h-2.5 w-full gap-0.5 overflow-clip rounded-[5px]"
        role="img"
        aria-label="Hold split"
      >
        {hold.parts.map((p) => (
          <div
            key={p.id}
            style={{ flexGrow: p.capUsd }}
            className={cn(
              "h-2.5 min-w-px basis-0 rounded-[4px]",
              p.tone === "primary" ? "bg-brand-gradient" : swatch[p.tone],
            )}
          />
        ))}
      </div>
      <ul className="flex flex-col gap-3.5">
        {hold.parts.map((p) => (
          <li key={p.id} className="flex items-center gap-2">
            <span
              aria-hidden
              className={cn(
                "size-2 shrink-0 rounded-[2px] border border-border",
                swatch[p.tone],
              )}
            />
            <span className="text-[13px] font-medium leading-[19px] text-ink">
              {p.label}
            </span>
            <span className="flex-1" />
            <span className="text-xs leading-[17px] text-muted">{p.note}</span>
          </li>
        ))}
      </ul>
      <div className="flex items-center gap-2 border-t border-border pt-3">
        <ShieldCheck aria-hidden size={16} className="shrink-0 text-ink-2" />
        <p className="flex-1 text-xs leading-[17px] text-muted">{hold.note}</p>
      </div>
    </Card>
  );
}

function TargetCard({ job }: { job: Job }) {
  return (
    <Card variant="violet">
      <h2 className="text-sm font-semibold leading-5 text-ink">
        Target to verify
      </h2>
      {job.targets.map((t) => (
        <div key={t.metric} className="flex flex-col gap-2">
          <div className="flex items-center justify-between whitespace-nowrap">
            <span className="text-[13px] font-medium leading-[19px] text-ink">
              {t.metric}
            </span>
            <span className="flex items-center gap-1.5 text-xs leading-[17px]">
              <span className="text-muted">
                baseline {t.baseline.toFixed(1)}%
              </span>
              <span className="font-semibold text-ink">
                → target {t.target}%{t.qualifier ? ` ${t.qualifier}` : ""}
              </span>
            </span>
          </div>
          <ProgressBar
            label={`${t.metric} progress toward target`}
            value={(t.baseline / t.target) * 100}
          />
        </div>
      ))}
    </Card>
  );
}

export function ProgressTab({ job }: { job: Job }) {
  return (
    <>
      <TrainingCard job={job} />
      <HoldCard job={job} />
      <TargetCard job={job} />
    </>
  );
}
