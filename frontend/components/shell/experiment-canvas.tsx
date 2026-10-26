"use client";
import { useState } from "react";
import { FileText } from "lucide-react";
import { EmptyState } from "@/components/ui/state";
import type { Chat } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FilesTab } from "./canvas-files";
import { LiveViewTab } from "./live-view-tab";
import { ModelTab } from "./model-tab";

// 500px canvas with underline tabs, shared by the experiment screens (10, 12, 13, 14).
type TabDef = { id: string; label: string };
const progressTabs: TabDef[] = [
  { id: "progress", label: "Progress" },
  { id: "files", label: "Files & links" },
  { id: "live", label: "Live view" },
];
const resultTabs: TabDef[] = [
  { id: "receipt", label: "Receipt" },
  { id: "model", label: "Model" },
  { id: "files", label: "Files & links" },
];

const useTabs: TabDef[] = [
  { id: "model", label: "Model" },
  { id: "receipt", label: "Receipt" },
  { id: "files", label: "Files & links" },
];

export function ExperimentCanvas({
  chat,
  children,
  variant = "progress",
  initialTab,
}: {
  chat: Chat;
  children?: React.ReactNode;
  variant?: "progress" | "result" | "use";
  initialTab?: "progress" | "files" | "live" | "receipt" | "model";
}) {
  const tabs =
    variant === "use"
      ? useTabs
      : variant === "result"
        ? resultTabs
        : progressTabs;
  const [tab, setTab] = useState<string>(initialTab ?? tabs[0].id);
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <aside
      aria-label="Canvas"
      className="flex h-full w-[500px] shrink-0 flex-col overflow-clip border-l border-border bg-surface"
    >
      <div className="flex h-14 shrink-0 items-center justify-between border-b border-border pl-5 pr-4">
        <div
          role="tablist"
          aria-label="Canvas tabs"
          className="flex items-start gap-[18px] self-stretch"
        >
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex flex-col items-start border-b-2 pb-[15px] pt-[19px] text-sm leading-[normal] whitespace-nowrap outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand",
                tab === t.id
                  ? "border-brand font-semibold text-ink"
                  : "border-transparent text-muted",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-sm leading-[normal] text-muted hover:text-ink"
        >
          Close
        </button>
      </div>
      <div
        role="tabpanel"
        className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5"
      >
        {(tab === "progress" || tab === "receipt") && children}
        {tab === "files" &&
          (chat.job ? (
            <FilesTab job={chat.job} />
          ) : (
            <EmptyState
              icon={<FileText />}
              title="No files yet"
              body="Files and links show up here once the agent starts a job."
            />
          ))}
        {tab === "live" && <LiveViewTab chatId={chat.id} />}
        {tab === "model" &&
          (chat.result ? (
            <ModelTab run={chat.result} />
          ) : (
            <EmptyState
              icon={<FileText />}
              title="No model yet"
              body="The model shows up here once a run passes its test."
            />
          ))}
      </div>
    </aside>
  );
}
