"use client";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { pendingCard } from "@/lib/chat";
import { ChatController } from "@/lib/chat-controller";
import { thinkingMessage } from "@/lib/thinking";
import { ApprovalCard, ChatBlockView } from "./chat-blocks";
import { Composer } from "./composer";
import { AgentRow, UserBubble } from "./inline-chat";

// One chat per project, on every step. The controller keeps the rules (one call per action, no resend on reload).
export function useProjectChat(projectId: string, goal: string, status: string, onChanged: () => void | Promise<void>) {
  const chat = useMemo(() => new ChatController(projectId, goal, onChanged), [projectId, goal]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    chat.setOnChanged(onChanged);
  }, [chat, onChanged]);
  const state = useSyncExternalStore(chat.subscribe, chat.getState, chat.getState);
  useEffect(() => {
    void chat.open(status); // idempotent: strict mode and re-renders open the thread once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat]);
  return { chat, state };
}
export type ProjectChat = ReturnType<typeof useProjectChat>;

// Shown while a /chat call runs. A local timer only: it makes no network calls.
function Thinking({ findingData }: { findingData: boolean }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setSeconds((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <p role="status" aria-live="polite" className="flex items-center gap-2 pl-9 text-sm text-muted">
      <span aria-hidden className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span key={i} className="size-1.5 rounded-full bg-brand motion-safe:animate-pulse" style={{ animationDelay: `${i * 200}ms` }} />
        ))}
      </span>
      {thinkingMessage(seconds, findingData)}
    </p>
  );
}

export function ChatThread({ pc, projectStatus }: { pc: ProjectChat; projectStatus: string }) {
  const { chat, state } = pc;
  const waiting = state.items ? pendingCard(state.items, projectStatus) : null;
  const { error } = state;

  return (
    <section aria-label="Chat with the assistant" className="flex flex-col gap-[18px]">
      {state.items === null && <p className="text-sm text-muted">Opening your chat…</p>}
      {state.items?.map((m) =>
        m.role === "user" ? (
          <UserBubble key={m.id} text={m.text} />
        ) : (
          <AgentRow key={m.id} text={m.card ? "" : m.text}>
            {m.card && (
              <ApprovalCard
                card={m.card}
                pending={waiting?.id === m.id && !state.declined}
                busy={state.busy}
                onApprove={() => void chat.approve(m.card!)}
                onDecline={() => chat.decline()}
              />
            )}
            {m.blocks.map((b, i) => (
              <ChatBlockView key={i} b={b} />
            ))}
          </AgentRow>
        ),
      )}
      {state.busy && state.items !== null && <Thinking findingData={projectStatus === "described"} />}
      {state.declined && (
        <p className="pl-9 text-sm text-muted">No problem. Tell me what you would like instead, or upload your own file.</p>
      )}
      {error && (
        <div role="alert" className="flex flex-wrap items-center gap-3 pl-9 text-sm text-danger">
          <span>{error.text}</span>
          {error.busy && (
            <Button variant="outline" disabled={state.busy} onClick={() => void chat.checkAgain()}>
              Check again
            </Button>
          )}
          {chat.goalUnanswered() && (
            <Button variant="outline" disabled={state.busy} onClick={() => void chat.sendGoalAgain()}>
              Send my goal again
            </Button>
          )}
        </div>
      )}
    </section>
  );
}

// The input under the thread. Hidden (with a note) when the AI assistant is not set up on the server.
export function ChatComposer({ pc, onAttach }: { pc: ProjectChat; onAttach?: () => void }) {
  const { chat, state } = pc;
  if (state.unavailable) {
    return (
      <p className="rounded-xl border border-border bg-surface px-4 py-3 text-sm text-muted">
        The AI assistant is not set up on this server, so chat is off. You can still use the steps on this page.
      </p>
    );
  }
  return (
    <Composer
      busy={state.busy || state.items === null}
      onAttach={onAttach}
      onSend={(t) => void chat.send(t)}
      placeholder="Ask AIOAC anything about this project..."
    />
  );
}
