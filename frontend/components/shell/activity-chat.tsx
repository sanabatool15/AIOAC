"use client";
import type { Chat, Message } from "@/lib/types";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";
import { ToolCalls } from "./research-chat";

// Screen 11 background: running experiment, chat only (680px thread, no canvas).
export function ActivityChat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const run = chat.activity;
  if (!run) return null;
  return (
    <InlineChatFrame
      projectName={chat.projectName}
      stepLabel={`Step ${run.stepIndex} of ${run.totalSteps}`}
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
  );
}
