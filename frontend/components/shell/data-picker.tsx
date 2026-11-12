"use client";
import { useState } from "react";
import { AddDataDialog, type AddDataKind } from "./data-dialog";
import { NO_DATA_MESSAGE } from "@/lib/chat";
import type { ProjectChat } from "./project-chat";

// Three ways to bring data, shown before any search. Only "I have no data" lets the agent look for datasets; the server
// enforces that too (services/agent/data_choice.py). Upload does not need the AI assistant, so it works when chat is off.
export function DataPicker({ projectId, pc, onChanged }: { projectId: string; pc: ProjectChat; onChanged: () => void | Promise<void> }) {
  const [open, setOpen] = useState<AddDataKind | null>(null);
  const chatOff = pc.state.unavailable;
  const busy = pc.state.busy || pc.state.items === null;

  const chip = "inline-flex items-center rounded-lg border border-border bg-card px-3.5 py-2 text-body font-medium text-ink shadow-card transition-colors hover:border-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-60";
  return (
    <section aria-label="Bring your data" className="flex items-start gap-3">
      <span aria-hidden className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-grad-brand text-small font-semibold text-on-brand">A</span>
      <div className="flex flex-col gap-2.5 pt-1">
        <p className="text-body text-ink">How do you want to start?</p>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={chip} onClick={() => setOpen("upload")}>Upload a file</button>
          <button type="button" className={chip} onClick={() => setOpen("link")}>Paste a link</button>
          <button type="button" disabled={busy || chatOff} className={chip} onClick={() => void pc.chat.send(NO_DATA_MESSAGE)}
            title={chatOff ? "The AI assistant is not set up on this server." : "It searches free open datasets for you."}>
            I have no data
          </button>
        </div>
      </div>
      <AddDataDialog projectId={projectId} kind={open} onClose={() => setOpen(null)} onChanged={onChanged} />
    </section>
  );
}
