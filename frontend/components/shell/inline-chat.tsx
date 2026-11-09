"use client";
import { useEffect, useState } from "react";
import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Orb } from "@/components/ui/thinking-orbs";
import { Composer } from "./composer";
import { MarkdownText } from "./markdown-text";
import { TopBar } from "./top-bar";

// Shared frame for the project chat. Two panes on a wide screen: the conversation on the left (newest message last, right
// above the composer) and the canvas on the right (progress and the current step). Cards never mix into the thread, so
// the thread only ever grows downward. On a narrow screen the canvas sits above the conversation.
export function InlineChatFrame({
  projectName,
  onSend,
  composer,
  canvas,
  progress,
  panelOpen = true,
  onTogglePanel,
  onDropFile,
  extraActions,
  children,
}: {
  projectName: string;
  onSend?: (text: string) => void;
  composer?: React.ReactNode; // replaces the default composer (the project chat brings its own)
  canvas?: React.ReactNode; // the current step, right pane
  progress?: React.ReactNode; // the progress strip, top of the right pane
  panelOpen?: boolean; // the right pane can be closed; the top bar button toggles it
  onTogglePanel?: () => void;
  extraActions?: React.ReactNode; // next to the panel button, e.g. Budget
  onDropFile?: (file: File) => void; // a file dropped on the conversation
  children: React.ReactNode; // the conversation
}) {
  return (
    <section aria-label="Chat" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar
        left={<h1 className="min-w-0 truncate text-body font-medium text-ink">{projectName}</h1>}
        actions={
          <>
            {extraActions}
            {canvas !== undefined && onTogglePanel ? (
            <Button variant="ghost" size="sm" aria-expanded={panelOpen} aria-label={panelOpen ? "Hide progress panel" : "Show progress panel"} onClick={onTogglePanel}>
              {panelOpen ? <PanelRightClose aria-hidden /> : <PanelRightOpen aria-hidden />}
              {panelOpen ? "Hide panel" : "Show panel"}
            </Button>
            ) : null}
          </>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        {canvas !== undefined && panelOpen && (
          <aside
            aria-label="Project steps"
            className="flex max-h-[45%] min-h-0 shrink-0 flex-col border-b border-border bg-surface lg:order-2 lg:max-h-none lg:w-full lg:max-w-form lg:border-b-0 lg:border-l"
          >
            {progress && <div className="shrink-0 border-b border-border px-4 py-3 sm:px-6">{progress}</div>}
            <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 py-4 sm:px-6">{canvas}</div>
          </aside>
        )}
        <div
          className="flex min-h-0 min-w-0 flex-1 flex-col lg:order-1"
          onDragOver={onDropFile ? (e) => e.preventDefault() : undefined}
          onDrop={
            onDropFile
              ? (e) => {
                  e.preventDefault();
                  const f = e.dataTransfer.files?.[0];
                  if (f) onDropFile(f);
                }
              : undefined
          }
        >
          <div className="flex min-h-0 flex-1 justify-center overflow-y-auto px-4 pb-2.5 pt-6 sm:px-6">
            <div className="flex h-fit w-full max-w-chat flex-col gap-6">{children}</div>
          </div>
          <div className="flex shrink-0 justify-center px-4 pb-5 pt-2 sm:px-6">
            <div className="w-full max-w-chat">
              {composer ??
                (onSend && <Composer onSend={onSend} placeholder="Ask AIOAC anything, or describe what to predict..." />)}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="rounded-xl bg-surface px-4 py-2.5">
        <p className="max-w-sm text-body text-ink">
          {text}
        </p>
      </div>
    </div>
  );
}

// Types a new reply out a few characters at a time. Replies that were already there when the chat opened show at once,
// and so does everything when the reader asks for reduced motion.
function useTypewriter(text: string, on: boolean): string {
  const [n, setN] = useState(() =>
    on && !(typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) ? 0 : text.length,
  );
  useEffect(() => {
    if (!on || n >= text.length) return;
    const id = setInterval(() => setN((v) => Math.min(text.length, v + 3)), 18);
    return () => clearInterval(id);
  }, [on, n, text.length]);
  return on ? text.slice(0, n) : text;
}

export function AgentRow({ text, stream = false, waiting = false, children }: { text: string; stream?: boolean; waiting?: boolean; children?: React.ReactNode }) {
  const shown = useTypewriter(text, stream);
  return (
    <div className="flex items-start gap-3">
      <Orb state={waiting ? "waiting" : "base"} size={24} className="shrink-0 text-brand" />
      <div className="flex min-w-px flex-1 flex-col gap-3">
        {shown && <MarkdownText text={shown} />}
        {children}
      </div>
    </div>
  );
}
