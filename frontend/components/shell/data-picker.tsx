"use client";
import { useState } from "react";
import { FileUp, Link2, Search } from "lucide-react";
import { LinkPanel } from "./link-panel";
import { UploadPanel } from "./data-upload";
import { NO_DATA_MESSAGE } from "@/lib/chat";
import type { ProjectChat } from "./project-chat";

type Choice = "upload" | "link";

// Three ways to bring data, shown before any search. Only "I have no data" lets the agent look for datasets; the server
// enforces that too (services/agent/data_choice.py). Upload does not need the AI assistant, so it works when chat is off.
export function DataPicker({ projectId, pc, onChanged }: { projectId: string; pc: ProjectChat; onChanged: () => void | Promise<void> }) {
  const [open, setOpen] = useState<Choice | null>(null);
  const chatOff = pc.state.unavailable;
  const busy = pc.state.busy || pc.state.items === null;
  const base = "flex flex-col items-start gap-1 rounded-xl border bg-white p-4 text-left text-sm transition-colors";
  const on = "border-brand ring-1 ring-brand";
  const off = "border-border hover:border-brand";

  return (
    <section aria-label="Bring your data" className="flex flex-col gap-3">
      <h2 className="text-sm font-medium text-ink">How do you want to bring your data?</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        <button type="button" aria-pressed={open === "upload"} className={`${base} ${open === "upload" ? on : off}`} onClick={() => setOpen(open === "upload" ? null : "upload")}>
          <FileUp aria-hidden className="size-5 text-brand" />
          <span className="font-medium text-ink">Upload your own CSV</span>
          <span className="text-muted">A table with one row per case.</span>
        </button>
        <button type="button" aria-pressed={open === "link"} className={`${base} ${open === "link" ? on : off}`} onClick={() => setOpen(open === "link" ? null : "link")}>
          <Link2 aria-hidden className="size-5 text-brand" />
          <span className="font-medium text-ink">Paste a link to an open dataset</span>
          <span className="text-muted">Hugging Face, UCI or OpenML.</span>
        </button>
        <button
          type="button"
          disabled={busy || chatOff}
          className={`${base} ${off} disabled:opacity-60`}
          onClick={() => void pc.chat.send(NO_DATA_MESSAGE)}
        >
          <Search aria-hidden className="size-5 text-brand" />
          <span className="font-medium text-ink">No data: let the agent find one</span>
          <span className="text-muted">{chatOff ? "The AI assistant is not set up on this server." : "It searches free open datasets for you."}</span>
        </button>
      </div>
      {open === "link" && <LinkPanel projectId={projectId} onChanged={onChanged} />}
      {open === "upload" && <UploadPanel projectId={projectId} onChanged={onChanged} />}
    </section>
  );
}
