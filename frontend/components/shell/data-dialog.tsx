"use client";
import { useState } from "react";
import { Modal } from "@/components/ui/modal";
import { cn } from "@/lib/utils";
import { UploadPanel } from "./data-upload";
import { LinkPanel } from "./link-panel";

export type AddDataKind = "upload" | "link";

const TABS: { id: AddDataKind; label: string }[] = [
  { id: "upload", label: "Upload" },
  { id: "link", label: "Paste a link" },
];

// "Add data": one pop-up with two ways in, upload a CSV or paste a link to an open dataset. Opened from the data tiles
// and from the Files and links tab. When the data is accepted the chat is read again and the pop-up closes.
export function AddDataDialog({
  projectId,
  kind,
  file,
  onClose,
  onChanged,
}: {
  projectId: string;
  kind: AddDataKind | null;
  file?: File | null; // a file dropped on the chat: the upload opens with it already picked
  onClose: () => void;
  onChanged: () => void | Promise<void>;
}) {
  const [picked, setPicked] = useState<AddDataKind | null>(null);
  const active = picked ?? kind ?? "upload";
  const close = () => {
    setPicked(null);
    onClose();
  };
  const done = async () => {
    close();
    await onChanged();
  };
  return (
    <Modal open={kind !== null} onClose={close} title="Add data" size="md">
      <div className="flex flex-col gap-4">
        <div role="tablist" aria-label="How to add data" className="grid grid-cols-2 gap-1 rounded-lg bg-surface p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active === t.id}
              onClick={() => setPicked(t.id)}
              className={cn(
                "rounded-md py-1.5 text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
                active === t.id ? "bg-card text-ink shadow-card" : "text-muted hover:text-ink",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        {active === "upload" ? (
          <UploadPanel projectId={projectId} onChanged={done} onCancel={close} initialFile={file} />
        ) : (
          <LinkPanel projectId={projectId} onChanged={done} onCancel={close} />
        )}
        <p className="text-small text-muted">Your data stays private to this chat and is never used to train anything else.</p>
      </div>
    </Modal>
  );
}
