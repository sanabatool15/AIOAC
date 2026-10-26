"use client";
import { MessageSquare } from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { EmptyState } from "@/components/ui/state";
import { cn } from "@/lib/utils";
import { Composer } from "./composer";
import { TopBar } from "./top-bar";

// Shared frame for the chat-first screens (4, 5, 6): top bar with step tag, a centered thread, the composer.
// `wide` = 720px column (screens 5, 6); default 680px (screen 4).
export function InlineChatFrame({
  projectName,
  stepLabel,
  wide = false,
  width: widthProp,
  onSend,
  children,
}: {
  projectName: string;
  stepLabel?: string;
  wide?: boolean;
  width?: "narrow"; // 560px thread (screen 10, with the canvas open)
  onSend: (text: string) => void;
  children: React.ReactNode;
}) {
  const width =
    widthProp === "narrow" ? "w-[560px]" : wide ? "w-[720px]" : "w-[680px]";
  return (
    <section
      aria-label="Chat"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        shareStyle="chip"
        projectName={projectName}
        left={
          <h1 className="whitespace-pre text-sm font-normal leading-[normal] text-muted">{`${projectName}  /  Chat`}</h1>
        }
        actions={stepLabel ? <Tag variant="brand">{stepLabel}</Tag> : undefined}
      />
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto pb-2.5 pt-[26px]">
        <div
          className={cn(
            "flex h-fit max-w-[calc(100%-48px)] flex-col gap-[18px]",
            width,
          )}
        >
          {children}
        </div>
      </div>
      <div className="flex shrink-0 justify-center pb-[22px] pt-2">
        <div className={cn("max-w-[calc(100%-48px)]", width)}>
          <Composer
            onSend={onSend}
            placeholder="Ask AIOAC anything, or describe what to predict..."
          />
        </div>
      </div>
    </section>
  );
}

export function EmptyThread() {
  return (
    <EmptyState
      icon={<MessageSquare />}
      title="No messages yet"
      body="Start by telling AIOAC what you want to predict."
    />
  );
}

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="rounded-2xl bg-surface px-4 py-2.5">
        <p className="w-[360px] max-w-full text-sm leading-[22px] text-ink">
          {text}
        </p>
      </div>
    </div>
  );
}

export function AgentRow({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-3">
      <div
        aria-hidden
        className="size-6 shrink-0 rounded-xl bg-brand-gradient shadow-glow"
      />
      <p className="min-w-px flex-1 text-sm leading-[23px] text-ink">{text}</p>
    </div>
  );
}
