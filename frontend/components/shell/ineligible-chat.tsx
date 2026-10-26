"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import type {
  Chat,
  IneligibleCheck,
  IneligibleOption,
  Message,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";

// Screen 28: the free check says the guarantee is not available as-is; pick a way forward.
export function IneligibleChat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const check = chat.ineligible;
  if (!check) return null;
  return (
    <InlineChatFrame projectName={chat.projectName} onSend={onSend}>
      {messages.length === 0 ? (
        <EmptyThread />
      ) : (
        messages.map((m) =>
          m.role === "user" ? (
            <UserBubble key={m.id} text={m.text} />
          ) : (
            <div key={m.id} className="contents">
              <AgentRow text={m.text} />
              {m.blocks?.includes("ineligible") && (
                <EligibilityCard check={check} />
              )}
            </div>
          ),
        )
      )}
    </InlineChatFrame>
  );
}

function EligibilityCard({ check }: { check: IneligibleCheck }) {
  const router = useRouter();
  const toast = useToast();
  const recommended =
    check.options.find((o) => o.recommended) ?? check.options[0];
  const [picked, setPicked] = useState<IneligibleOption["id"]>(recommended.id);

  function proceed() {
    if (picked === "upgrade") return router.push("/billing/plan");
    toast(
      picked === "sample"
        ? "Using a 500 MB sample. Review the agreement next."
        : "Target lowered to precision 74%. Review the agreement next.",
    );
    router.push("/c/agreement");
  }

  return (
    <>
      <Card
        variant="amber"
        className="gap-3 overflow-clip p-5 shadow-card-tight"
        data-testid="eligibility-card"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold leading-[normal] text-ink">
            Not eligible for a guaranteed price
          </h2>
          <Tag>{check.checkedLabel}</Tag>
        </div>
        <p className="text-xs font-semibold leading-[normal] text-muted">
          REASONS
        </p>
        <ul className="flex flex-col gap-3">
          {check.reasons.map((r) => (
            <li
              key={r}
              className="flex items-center gap-2.5 text-sm leading-[normal] text-ink"
            >
              <span
                aria-hidden
                className="size-2 shrink-0 rounded-full bg-brand-gradient"
              />
              <span className="min-w-px flex-1">{r}</span>
            </li>
          ))}
        </ul>
        <p className="text-xs font-semibold leading-[normal] text-muted">
          WHAT YOU CAN DO
        </p>
        <div
          role="radiogroup"
          aria-label="What you can do"
          className="flex flex-col gap-3"
        >
          {check.options.map((o) => {
            const on = o.id === picked;
            return (
              <button
                key={o.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setPicked(o.id)}
                className={cn(
                  "flex w-full items-center gap-3 overflow-clip rounded-xl p-3.5 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
                  on
                    ? "border-2 border-brand bg-surface"
                    : "border border-border bg-white",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "flex size-5 shrink-0 items-center justify-center rounded-full border",
                    on ? "border-brand bg-white" : "border-border bg-white",
                  )}
                >
                  {on && <span className="size-2.5 rounded-full bg-brand" />}
                </span>
                <span className="flex min-w-px flex-1 flex-col gap-0.5 text-sm leading-[normal]">
                  <span className="font-semibold text-ink">{o.title}</span>
                  <span className="text-muted">{o.detail}</span>
                </span>
                {o.recommended && <Tag variant="brand">RECOMMENDED</Tag>}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="md" onClick={proceed}>
            Continue with sample
          </Button>
          <Button
            variant="outline"
            size="action"
            onClick={() => router.push("/billing/plan")}
          >
            Upgrade plan
          </Button>
          <Button
            variant="outline"
            size="action"
            onClick={() => router.push("/c/baseline")}
          >
            Run free baseline only
          </Button>
        </div>
      </Card>
      <p className="text-sm leading-[normal] text-muted">{check.footnote}</p>
    </>
  );
}
