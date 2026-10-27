"use client";
import type { Chat, Message, ResearchRun } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ExperimentCanvas } from "./experiment-canvas";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";

// Screen 9: agent researching public datasets while training runs. Opens on the Live view tab.
export function ResearchChat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const run = chat.research;
  if (!run) return null;
  return (
    <>
      <InlineChatFrame
        projectName={chat.projectName}
        stepLabel={`Step ${run.stepIndex} of ${run.totalSteps}`}
        width="narrow"
        onSend={onSend}
      >
        {messages.length === 0 ? (
          <EmptyThread />
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <UserBubble key={m.id} text={m.text} />
            ) : (
              <div key={m.id} className="contents">
                <AgentRow text={m.text} />
                {m.blocks?.includes("research") && <ToolCalls run={run} />}
              </div>
            ),
          )
        )}
      </InlineChatFrame>
      <ExperimentCanvas chat={chat} initialTab="live" />
    </>
  );
}

export function ToolCalls({ run }: { run: ResearchRun }) {
  return (
    <ul
      aria-label="Tool calls"
      className="flex w-full flex-col gap-[9px] overflow-clip rounded-xl border border-border p-3.5"
    >
      {run.steps.map((s) => (
        <li
          key={s.id}
          data-state={s.state}
          className="flex items-center gap-2.5"
        >
          <span
            aria-hidden
            className={cn(
              "size-[18px] shrink-0 rounded-[9px]",
              s.state === "done" && "bg-brand-gradient",
              s.state === "run" && "border-4 border-brand bg-white",
              s.state === "pending" &&
                "border border-dashed border-border bg-white",
            )}
          />
          <span
            className={cn(
              "min-w-px flex-1 text-sm leading-[normal]",
              s.state === "run" && "font-semibold text-ink",
              s.state === "done" && "text-ink",
              s.state === "pending" && "text-muted",
            )}
          >
            {s.label}
          </span>
          {s.meta && (
            <span className="shrink-0 text-sm leading-[normal] whitespace-nowrap text-muted">
              {s.meta}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
