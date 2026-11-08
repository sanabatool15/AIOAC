"use client";
import { Fragment, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { EstimateNote } from "@/components/ui/estimate-note";
import { askedForSearch, pendingCard } from "@/lib/chat";
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
  useEffect(() => () => chat.dispose(), [chat]); // leaving the screen: stop polling
  useEffect(() => {
    void chat.open(status); // idempotent: strict mode and re-renders open the thread once
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chat]);
  return { chat, state };
}
export type ProjectChat = ReturnType<typeof useProjectChat>;

// Shown while a /chat call runs. With live steps (from the controller's activity poll) it lists them; otherwise it shows
// the rotating text, which is a local timer only. This component itself makes no network calls.
function Thinking({
  findingData,
  readingGoal,
  since,
  steps,
}: {
  findingData: boolean;
  readingGoal: boolean;
  since: number | null;
  steps: string[];
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const seconds = since === null ? 0 : Math.max(0, Math.floor((now - since) / 1000));
  const dots = (
    <span aria-hidden className="flex gap-1">
      {[0, 1, 2].map((i) => (
        <span key={i} className="size-1.5 rounded-full bg-brand motion-safe:animate-pulse" style={{ animationDelay: `${i * 200}ms` }} />
      ))}
    </span>
  );
  if (steps.length > 0) {
    return (
      <div role="status" aria-live="polite" aria-label="What the assistant is doing" className="flex flex-col gap-1 pl-9 text-body text-muted">
        <ul className="flex flex-col gap-1">
          {steps.map((t, i) => (
            <li key={`${i}-${t}`} className="flex items-center gap-2" data-live-step>
              {i === steps.length - 1 ? dots : <span aria-hidden className="min-w-6 text-center text-success">✓</span>}
              {t}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <p role="status" aria-live="polite" className="flex items-center gap-2 pl-9 text-body text-muted">
      {dots}
      {thinkingMessage(seconds, findingData, readingGoal)}
    </p>
  );
}

export function hasEstimateBlock(b: { type: string }): boolean {
  return b.type === "baseline" || b.type === "quote";
}

export function ChatThread({ pc, projectStatus }: { pc: ProjectChat; projectStatus: string }) {
  const { chat, state } = pc;
  const waiting = state.items ? pendingCard(state.items, projectStatus) : null;
  const { error } = state;
  // One shared note for the whole thread instead of a repeated "estimate" sentence in each block.
  const hasEstimate = !!state.items?.some((m) => m.blocks.some((b) => hasEstimateBlock(b)));

  return (
    <section aria-label="Chat with the assistant" className="flex flex-col gap-4">
      {state.items === null && <p className="text-body text-muted">Opening your chat…</p>}
      {state.items?.map((m) =>
        m.role === "user" ? (
          <UserBubble key={m.id} text={m.text} />
        ) : (
          <Fragment key={m.id}>
          <AgentRow text={m.card ? "" : m.text}>
            {m.card && (
              <ApprovalCard
                card={m.card}
                pending={waiting?.id === m.id && !chat.isDeclined(m.id)}
                declined={chat.isDeclined(m.id)}
                busy={state.busy}
                onApprove={() => void chat.approve(m.card!)}
                onDecline={() => chat.decline(m.id)}
              />
            )}
            {m.blocks.map((b, i) => (
              <ChatBlockView key={i} b={b} />
            ))}
          </AgentRow>
          {m.card && chat.isDeclined(m.id) && (
            <p className="pl-9 text-body text-muted">No problem. Tell me what you would like instead, or upload your own file.</p>
          )}
          </Fragment>
        ),
      )}
      {hasEstimate && <EstimateNote className="pl-9" />}
      {state.busy && state.items !== null && (
        <Thinking
          findingData={projectStatus === "described" && askedForSearch(state.items)}
          readingGoal={state.items.length === 1 && state.items[0].role === "user"}
          since={state.busySince}
          steps={state.liveSteps}
        />
      )}
      {error && (
        <div role="alert" className="flex flex-wrap items-center gap-3 pl-9 text-body text-danger">
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
      <p className="rounded-lg border border-border bg-surface px-4 py-3 text-body text-muted">
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
