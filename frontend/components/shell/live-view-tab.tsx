"use client";
import { Monitor } from "lucide-react";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { useAsync } from "@/lib/hooks";
import { getLiveView } from "@/lib/mock-api";
import { ToolStrip } from "./tool-strip";

// Screen 9: Live view tab. Tool strip, a mock browser window showing what the agent is reading, research notes.
export function LiveViewTab({ chatId }: { chatId: string }) {
  const { data, error, loading, retry } = useAsync(
    () => getLiveView(chatId),
    chatId,
  );

  if (loading && !data) {
    return (
      <div
        className="flex flex-col gap-4"
        aria-busy="true"
        aria-label="Loading live view"
      >
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }
  if (error || !data) {
    return (
      <ErrorState
        message={error?.message ?? "Live view unavailable."}
        onRetry={retry}
      />
    );
  }
  if (!data.url) {
    return (
      <EmptyState
        icon={<Monitor />}
        title="Nothing to watch yet"
        body="The agent's browser shows up here when it starts reading pages."
      />
    );
  }
  return (
    <>
      <ToolStrip tools={data.tools} />
      <div
        data-testid="browser-window"
        className="flex w-full flex-col overflow-clip rounded-xl border border-border bg-white shadow-card-tight"
      >
        <div className="flex items-center gap-2 bg-surface p-2.5">
          <span aria-hidden className="size-2 rounded-[4px] bg-bar-target" />
          <span aria-hidden className="size-2 rounded-[4px] bg-bar-target" />
          <p
            aria-label="Page address"
            className="min-w-px flex-1 overflow-clip rounded-lg bg-white px-2.5 py-[5px] text-xs leading-[normal] whitespace-nowrap text-muted"
          >
            {data.url}
          </p>
        </div>
        <div className="flex flex-col gap-2 p-4">
          <h2 className="text-sm font-semibold leading-[normal] whitespace-nowrap text-ink">
            {data.pageTitle}
          </h2>
          {data.lineWidths.map((w, i) => (
            <div
              key={i}
              aria-hidden
              style={{ width: w }}
              className={`h-2 max-w-full rounded-[4px] ${i === 1 ? "bg-border" : "bg-surface"}`}
            />
          ))}
          <div className="flex flex-col overflow-clip rounded-lg border border-dashed border-brand bg-surface p-2.5">
            <p className="w-full text-sm font-semibold leading-[normal] text-ink">
              {data.highlight}
            </p>
          </div>
        </div>
      </div>
      <h3 className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
        RESEARCH NOTES
      </h3>
      <ul aria-label="Research notes" className="flex flex-col gap-2">
        {data.notes.map((n) => (
          <li key={n} className="flex items-center gap-2.5">
            <span
              aria-hidden
              className="size-1.5 shrink-0 rounded-[3px] bg-brand-gradient"
            />
            <span className="min-w-px flex-1 text-sm leading-[normal] text-ink">
              {n}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}
