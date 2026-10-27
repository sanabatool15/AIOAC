"use client";
import { FileText, Monitor, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/state";
import type { Job } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FilesTab } from "./canvas-files";
import { ProgressTab } from "./canvas-progress";

export type CanvasTab = "progress" | "files" | "live";

const tabs: { id: CanvasTab; label: string }[] = [
  { id: "progress", label: "Progress" },
  { id: "files", label: "Files & links" },
  { id: "live", label: "Live view" },
];

interface CanvasPanelProps {
  job?: Job;
  tab: CanvasTab;
  onTabChange: (t: CanvasTab) => void;
  onClose: () => void;
}

export function CanvasPanel({
  job,
  tab,
  onTabChange,
  onClose,
}: CanvasPanelProps) {
  return (
    <aside
      aria-label="Canvas"
      className="flex h-full w-[480px] shrink-0 flex-col border-l border-border bg-card"
    >
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-border pl-4 pr-3">
        <div
          role="tablist"
          aria-label="Canvas tabs"
          className="flex items-start gap-0.5 rounded-[10px] bg-surface p-[3px]"
        >
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => onTabChange(t.id)}
              className={cn(
                "min-h-[29px] rounded-[10px] px-2 py-1 text-sm font-medium leading-5 outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand",
                tab === t.id
                  ? "bg-brand-gradient text-white shadow-btn-primary"
                  : "text-ink",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Button
          variant="icon"
          size="icon"
          aria-label="Close panel"
          onClick={onClose}
        >
          <X />
        </Button>
      </div>
      <div
        role="tabpanel"
        className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5"
      >
        {tab === "progress" &&
          (job ? (
            <ProgressTab job={job} />
          ) : (
            <EmptyState
              icon={<FileText />}
              title="Nothing running yet"
              body="Progress shows up here once the agent starts a job."
            />
          ))}
        {tab === "files" &&
          (job ? (
            <FilesTab job={job} />
          ) : (
            <EmptyState
              icon={<FileText />}
              title="No files yet"
              body="Files and links show up here once the agent starts a job."
            />
          ))}
        {tab === "live" && (
          <EmptyState
            icon={<Monitor />}
            title="Live view"
            body="Screen 9 is not built yet."
          />
        )}
      </div>
    </aside>
  );
}
