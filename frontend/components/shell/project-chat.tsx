"use client";
import { Fragment, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { EstimateNote } from "@/components/ui/estimate-note";
import { askedForSearch, pendingCard } from "@/lib/chat";
import { ChatController } from "@/lib/chat-controller";
import { thinkingPhases } from "@/lib/thinking";
import { ApprovalCard, ChatBlockView } from "./chat-blocks";
import { Composer } from "./composer";
import { AgentTrace } from "@/components/ui/agent-trace";
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
  // Real steps from the server, newest last. Before the first one arrives, the line that says what it is reading or
  // checking stands in as the current step, so there is always something moving.
  const lines = steps.length > 0 ? steps : thinkingPhases(seconds, findingData, readingGoal);
  return (
    <div className="pl-9">
      <AgentTrace steps={lines} working seconds={seconds} title={steps.length > 1 ? `Working, ${steps.length} steps so far` : "Working on it"} className="rounded-xl border border-trace-line bg-grad-trace p-3 shadow-card" />
    </div>
  );
}

export function hasEstimateBlock(b: { type: string }): boolean {
  return b.type === "baseline" || b.type === "quote";
}

// The model sometimes offers its own "Upload a file / Share a link / I have no data" buttons. The screen already has the real
// ones under the chat (they open the upload and link panels), so the model's copy is hidden while no data is chosen.
function isStartChoices(b: { type: string; options?: unknown }): boolean {
  if (b.type !== "choices" || !Array.isArray(b.options)) return false;
  return b.options.some((o) => typeof o === "string" && /upload|link|no data/i.test(o));
}

export function ChatThread({ pc, projectStatus }: { pc: ProjectChat; projectStatus: string }) {
  const { chat, state } = pc;
  // Replies that arrive after the chat opened are typed out; the ones already there are not.
  const [seen, setSeen] = useState<Set<string> | null>(null);
  if (seen === null && state.items !== null) setSeen(new Set(state.items.map((m) => m.id)));
  const isNew = (id: string) => seen !== null && !seen.has(id);
  const waiting = state.items ? pendingCard(state.items, projectStatus) : null;
  const { error } = state;
  // One shared note for the whole thread instead of a repeated "estimate" sentence in each block.
  const hasEstimate = !!state.items?.some((m) => m.blocks.some((b) => hasEstimateBlock(b)));

  return (
    <section aria-label="Chat with the assistant" className="flex flex-col gap-4">
      {state.items === null && <p className="text-body text-muted">Opening your chat…</p>}
      {state.items?.map((m, mi) =>
        m.role === "user" ? (
          <UserBubble key={m.id} text={m.text} />
        ) : (
          <Fragment key={m.id}>
          {mi === state.items!.length - 1 && !state.busy && state.lastSteps.length > 0 && (
            <div className="pl-9">
              <AgentTrace steps={state.lastSteps} working={false} title={`Worked through ${state.lastSteps.length} ${state.lastSteps.length === 1 ? "step" : "steps"}`} className="rounded-xl border border-trace-line bg-grad-trace p-3 shadow-card" />
            </div>
          )}
          <AgentRow text={m.card ? "" : m.text} stream={!m.card && isNew(m.id)} waiting={!!m.card && waiting?.id === m.id && !chat.isDeclined(m.id)}>
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
            {m.blocks.filter((b) => !(projectStatus === "described" && isStartChoices(b))).map((b, i) => (
              <ChatBlockView key={i} b={b} onChoose={(t) => void chat.choose(t)} locked={state.busy || mi < state.items!.length - 1} />
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
export function ChatComposer({ pc, ...attach }: { pc: ProjectChat; onPickFile?: (f: File) => void; attachment?: File | null; onRemoveAttachment?: () => void; onSendWithFile?: (text: string) => void }) {
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
      {...attach}
      onSend={(t) => void chat.send(t)}
      placeholder="Ask AIOAC anything about this project..."
    />
  );
}
