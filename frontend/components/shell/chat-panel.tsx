"use client";
import { useState } from "react";
import { LoaderCircle, MessageSquare, PanelRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/state";
import type { Chat, Message, ToolId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Composer } from "./composer";
import { TopBar } from "./top-bar";
import { TraceCard } from "./trace-card";

const toolLabels: { id: ToolId; label: string }[] = [
  { id: "tools", label: "Tools" },
  { id: "research", label: "Research" },
  { id: "training", label: "Training" },
  { id: "payment", label: "Payment" },
];

function AgentAvatar() {
  return (
    <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand-gradient-diag text-[13px] font-semibold text-white">
      A
    </div>
  );
}

interface ChatPanelProps {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
  canvasOpen: boolean;
  onOpenCanvas: () => void;
}

export function ChatPanel({
  chat,
  messages,
  onSend,
  canvasOpen,
  onOpenCanvas,
}: ChatPanelProps) {
  const [filter, setFilter] = useState<ToolId | null>(null);
  const job = chat.job;
  const lastAgentId = [...messages]
    .reverse()
    .find((m) => m.role === "agent")?.id;

  return (
    <section
      aria-label="Chat"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        projectName={chat.projectName}
        left={
          <>
            <h1 className="text-[15px] font-semibold leading-[22px] text-ink">
              {chat.projectName}
            </h1>
            {job?.state === "running" && (
              <Badge variant="brand">
                <LoaderCircle
                  aria-hidden
                  size={12}
                  className="motion-safe:animate-spin"
                />
                {job.title} running
              </Badge>
            )}
          </>
        }
        actions={
          !canvasOpen && (
            <Button
              variant="outline"
              size="icon"
              aria-label="Open progress panel"
              onClick={onOpenCanvas}
            >
              <PanelRight />
            </Button>
          )
        }
      />

      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto px-6 pb-4 pt-8">
        {messages.length === 0 ? (
          <EmptyState
            icon={<MessageSquare />}
            title="No messages yet"
            body="Start by telling AIOAC what you want to train and what you will pay."
          />
        ) : (
          <div className="flex h-fit w-full max-w-[560px] flex-col gap-5">
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex flex-col items-end">
                  <p className="w-[420px] max-w-full rounded-2xl bg-brand-soft px-4 py-2.5 text-sm leading-5 text-ink">
                    {m.text}
                  </p>
                </div>
              ) : (
                <div key={m.id} className="flex items-start gap-3">
                  <AgentAvatar />
                  <div className="flex min-w-0 flex-1 flex-col gap-3">
                    <p className="text-[15px] leading-[23px] text-ink">
                      {m.text}
                    </p>
                    {job && m.id === lastAgentId && (
                      <>
                        <div
                          className="flex items-start gap-1.5"
                          role="group"
                          aria-label="Filter steps by tool"
                        >
                          {toolLabels.map(({ id, label }) => {
                            const running = job.tools[id] === "running";
                            return (
                              <button
                                key={id}
                                type="button"
                                aria-pressed={filter === id}
                                onClick={() =>
                                  setFilter((f) => (f === id ? null : id))
                                }
                                className={cn(
                                  "inline-flex items-center justify-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold leading-4 outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand",
                                  running
                                    ? "bg-brand text-white"
                                    : "bg-secondary text-secondary-fg",
                                  filter === id && "ring-2 ring-brand-edge",
                                )}
                              >
                                {running && (
                                  <LoaderCircle
                                    aria-hidden
                                    size={12}
                                    className="motion-safe:animate-spin"
                                  />
                                )}
                                {label}
                              </button>
                            );
                          })}
                        </div>
                        <TraceCard
                          title={job.title}
                          stepLabel={`Step ${job.stepIndex} of ${job.totalSteps}`}
                          steps={job.steps}
                          filter={filter}
                        />
                      </>
                    )}
                  </div>
                </div>
              ),
            )}
          </div>
        )}
      </div>

      <div className="flex shrink-0 justify-center px-6 pb-6">
        <div className="w-full max-w-[560px]">
          <Composer onSend={(text) => onSend(text)} />
        </div>
      </div>
    </section>
  );
}
