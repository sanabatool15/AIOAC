"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { createAgreement, holdAgreement } from "@/lib/mock-api";
import type { Chat, Message, Round2Plan } from "@/lib/types";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";

// Screen 29: keep v1 and improve. A new agreement and a new PayPal hold are needed for round 2.
export function Round2Chat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const plan = chat.round2;
  if (!plan) return null;
  return (
    <InlineChatFrame
      projectName={chat.projectName}
      stepLabel="Round 2"
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
              {m.blocks?.includes("round2") && (
                <>
                  <ChangesCard plan={plan} />
                  <AgreementCard chatId={chat.id} plan={plan} />
                </>
              )}
            </div>
          ),
        )
      )}
    </InlineChatFrame>
  );
}

function ChangesCard({ plan }: { plan: Round2Plan }) {
  return (
    <Card
      variant="blue"
      className="gap-3 overflow-clip p-5 shadow-card-tight"
      data-testid="round2-changes"
    >
      <h2 className="text-xs font-semibold leading-[normal] text-muted">
        WHAT I WILL TRY DIFFERENTLY
      </h2>
      <ul className="flex flex-col gap-3">
        {plan.changes.map((c) => (
          <li
            key={c}
            className="flex items-center gap-2.5 text-sm leading-[normal] text-ink"
          >
            <span
              aria-hidden
              className="size-[18px] shrink-0 rounded-full bg-brand-gradient"
            />
            <span className="min-w-px flex-1">{c}</span>
          </li>
        ))}
      </ul>
      <div className="flex gap-3 leading-[normal] whitespace-nowrap">
        {[plan.round1, plan.goal].map((c) => (
          <div
            key={c.label}
            className="flex min-w-px flex-1 flex-col gap-[3px] rounded-xl bg-surface p-3.5"
          >
            <span className="text-xs font-semibold text-muted">{c.label}</span>
            <span className="text-xl font-semibold text-ink">{c.value}</span>
            <span className="text-sm text-muted">{c.note}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function AgreementCard({ chatId, plan }: { chatId: string; plan: Round2Plan }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      const agreement = await createAgreement(chatId, plan.target);
      const { approvalUrl } = await holdAgreement(agreement.id);
      router.push(approvalUrl);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not start the PayPal authorization. Nothing was held.",
      );
      setBusy(false);
    }
  }

  return (
    <Card
      variant="violet"
      className="gap-2 overflow-clip p-5 shadow-card-tight"
      data-testid="round2-agreement"
    >
      <h2 className="text-xs font-semibold leading-[normal] text-muted">
        ROUND 2 AGREEMENT
      </h2>
      <dl className="flex flex-col">
        {plan.terms.map(([k, v]) => (
          <div
            key={k}
            className="flex items-start justify-between py-[5px] text-sm leading-[normal] whitespace-nowrap"
          >
            <dt className="text-muted">{k}</dt>
            <dd className="font-medium text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      {error && (
        <p role="alert" className="text-sm leading-[normal] text-danger">
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="md" disabled={busy} onClick={approve}>
          {busy ? "Opening PayPal…" : "Approve and authorize with PayPal"}
        </Button>
        <Button
          variant="outline"
          size="md"
          disabled={busy}
          onClick={() => router.push("/c/agreement")}
        >
          Change target
        </Button>
      </div>
    </Card>
  );
}
