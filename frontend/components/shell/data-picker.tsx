"use client";
import { useState } from "react";
import { FileUp, Link2, Search } from "lucide-react";
import { AddDataDialog, type AddDataKind } from "./data-dialog";
import { NO_DATA_MESSAGE } from "@/lib/chat";
import type { ProjectChat } from "./project-chat";

// Three ways to bring data, shown before any search. Only "I have no data" lets the agent look for datasets; the server
// enforces that too (services/agent/data_choice.py). Upload does not need the AI assistant, so it works when chat is off.
export function DataPicker({ projectId, pc, onChanged }: { projectId: string; pc: ProjectChat; onChanged: () => void | Promise<void> }) {
  const [open, setOpen] = useState<AddDataKind | null>(null);
  const chatOff = pc.state.unavailable;
  const busy = pc.state.busy || pc.state.items === null;
  const base = "flex flex-col items-start gap-1 rounded-lg border bg-card p-4 text-left text-body transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand";
  const off = "border-border hover:border-brand";

  return (
    <section aria-label="Bring your data" className="flex flex-col gap-3">
      <h2 className="text-section text-ink">How do you want to bring your data?</h2>
      <div className="grid gap-3">
        <button type="button" className={`${base} ${off}`} onClick={() => setOpen("upload")}>
          <FileUp aria-hidden className="size-5 text-brand" />
          <span className="font-medium text-ink">Upload your own CSV</span>
          <span className="text-muted">A table with one row per case.</span>
        </button>
        <button type="button" className={`${base} ${off}`} onClick={() => setOpen("link")}>
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
      <AddDataDialog projectId={projectId} kind={open} onClose={() => setOpen(null)} onChanged={onChanged} />
    </section>
  );
}
