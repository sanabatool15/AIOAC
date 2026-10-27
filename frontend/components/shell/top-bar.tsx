"use client";
import { useState } from "react";
import { Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ShareDialog } from "./share-dialog";

// Shared top bar for chat screens: left slot (title / breadcrumb) + actions + Share.
// shareStyle "chip" = the plain pill used on chat-first screens (2, 3, 4); "button" = outline button with icon (screen 7).
export function TopBar({
  left,
  actions,
  shareStyle = "button",
  projectName = "Churn prediction",
}: {
  left: React.ReactNode;
  actions?: React.ReactNode;
  shareStyle?: "button" | "chip";
  projectName?: string; // what the Share dialog is about
}) {
  const [sharing, setSharing] = useState(false);
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-6">
      <div className="flex items-center gap-2.5">{left}</div>
      <div className="flex items-center gap-2">
        {actions}
        {shareStyle === "chip" ? (
          <Button
            variant="outline"
            onClick={() => setSharing(true)}
            className="rounded-2xl px-3.5 py-[7px] font-medium leading-[normal]"
          >
            Share
          </Button>
        ) : (
          <Button variant="outline" onClick={() => setSharing(true)}>
            <Share2 aria-hidden />
            Share
          </Button>
        )}
      </div>
      {sharing && (
        <ShareDialog
          projectName={projectName}
          onClose={() => setSharing(false)}
        />
      )}
    </header>
  );
}
