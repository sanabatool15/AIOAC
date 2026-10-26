"use client";
import { useState } from "react";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { useAsync, usePersistedState } from "@/lib/hooks";
import { getChat, sendMessage } from "@/lib/mock-api";
import type { Message } from "@/lib/types";
import { CanvasPanel, type CanvasTab } from "./canvas-panel";
import { AgreementChat } from "./agreement-chat";
import { BaselineChat } from "./baseline-chat";
import { IneligibleChat } from "./ineligible-chat";
import { Round2Chat } from "./round2-chat";
import { ResultChat } from "./result-chat";
import { VerifiedChat } from "./verified-chat";
import { ActivityChat } from "./activity-chat";
import { ResearchChat } from "./research-chat";
import { TrainingChat } from "./training-chat";
import { ChatPanel } from "./chat-panel";

// Route body for /c/[chatId]: chat column + canvas column, with loading / error / empty / retry.
export function ChatScreen({
  chatId,
  phase = "agreement",
  agreementId,
}: {
  chatId: string;
  phase?: "agreement" | "pay";
  agreementId?: string;
}) {
  const { data: chat, error, loading, retry } = useAsync(() => getChat(chatId));
  const [sent, setSent] = useState<Message[]>([]);
  const [canvasOpen, setCanvasOpen] = usePersistedState(
    "aioac.canvas.open",
    true,
  );
  const [tab, setTab] = usePersistedState<CanvasTab>(
    "aioac.canvas.tab",
    "progress",
  );

  if (loading && !chat) {
    return (
      <div
        className="flex min-w-0 flex-1"
        aria-busy="true"
        aria-label="Loading chat"
      >
        <div className="flex flex-1 flex-col gap-5 p-8">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-12 w-[420px] self-end" />
          <Skeleton className="h-24 w-full max-w-[560px]" />
        </div>
        <div className="flex w-[480px] flex-col gap-4 border-l border-border bg-card p-5">
          <Skeleton className="h-36" />
          <Skeleton className="h-44" />
          <Skeleton className="h-32" />
        </div>
      </div>
    );
  }

  if (error || !chat) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center">
        <ErrorState
          message={error?.message ?? "Chat not found."}
          onRetry={retry}
        />
      </div>
    );
  }

  const messages = [...chat.messages, ...sent];

  async function handleSend(text: string) {
    const msg = await sendMessage(chatId, text);
    setSent((s) => [...s, { id: msg.id, role: "user", text: msg.text }]);
  }

  if (chat.agreement)
    return (
      <AgreementChat
        chat={chat}
        messages={messages}
        onSend={handleSend}
        phase={phase}
        agreementId={agreementId}
      />
    );
  if (chat.round2)
    return <Round2Chat chat={chat} messages={messages} onSend={handleSend} />;
  if (chat.ineligible)
    return (
      <IneligibleChat chat={chat} messages={messages} onSend={handleSend} />
    );
  if (chat.result)
    return <ResultChat chat={chat} messages={messages} onSend={handleSend} />;
  if (chat.verified)
    return <VerifiedChat chat={chat} messages={messages} onSend={handleSend} />;
  if (chat.activity)
    return <ActivityChat chat={chat} messages={messages} onSend={handleSend} />;
  if (chat.research)
    return <ResearchChat chat={chat} messages={messages} onSend={handleSend} />;
  if (chat.training)
    return <TrainingChat chat={chat} messages={messages} onSend={handleSend} />;
  if (chat.baseline)
    return <BaselineChat chat={chat} messages={messages} onSend={handleSend} />;

  return (
    <>
      <ChatPanel
        chat={chat}
        messages={messages}
        onSend={handleSend}
        canvasOpen={canvasOpen}
        onOpenCanvas={() => setCanvasOpen(true)}
      />
      {canvasOpen && (
        <CanvasPanel
          job={chat.job}
          tab={tab}
          onTabChange={setTab}
          onClose={() => setCanvasOpen(false)}
        />
      )}
    </>
  );
}
