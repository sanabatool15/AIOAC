"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { deleteModel } from "@/lib/mock-api";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Tag } from "@/components/ui/tag";
import type { Chat, Message, VerifiedRun } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "./confirm-dialog";
import { ExperimentCanvas } from "./experiment-canvas";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";
import { ToolStrip } from "./tool-strip";

// Screen 12: verified on the locked test set, target met, payment being captured.
export function VerifiedChat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const run = chat.verified;
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
                {m.blocks?.includes("verification") && (
                  <VerificationCard run={run} />
                )}
                {m.blocks?.includes("banner") && run.banner && (
                  <Banner text={run.banner} />
                )}
                {m.blocks?.includes("model") && run.bestModel && (
                  <BestModelCard
                    model={run.bestModel}
                    detail={run.bestModel.detail}
                    precision={run.metrics[0].value}
                  />
                )}
              </div>
            ),
          )
        )}
      </InlineChatFrame>
      <ExperimentCanvas chat={chat}>
        <VerifiedProgress run={run} />
      </ExperimentCanvas>
    </>
  );
}

export function VerificationCard({
  run,
  className,
}: {
  run: Pick<VerifiedRun, "metrics" | "heading" | "testSetNote">;
  className?: string;
}) {
  const allMet = run.metrics.every((m) => m.met);
  return (
    <Card
      variant={allMet ? "green" : "red"}
      className={cn("gap-3 overflow-clip p-5 shadow-card-tight", className)}
      data-testid="verification-card"
    >
      <Tag variant="muted" className="self-start">
        INDEPENDENT VERIFICATION
      </Tag>
      <p className="text-xl font-semibold leading-[normal] text-ink">
        {run.heading}
      </p>
      <div className="flex gap-3">
        {run.metrics.map((m) => (
          <div
            key={m.id}
            className="flex min-w-px flex-1 flex-col gap-[3px] overflow-clip rounded-xl bg-surface p-3.5 leading-[normal]"
            data-testid={`metric-${m.id}`}
          >
            <p className="text-xs font-semibold whitespace-nowrap text-muted">
              {m.label}
            </p>
            <p className="text-[28px] font-semibold whitespace-nowrap text-ink">
              {m.value}%
            </p>
            <div className="flex items-center gap-2">
              <span className="text-sm whitespace-nowrap text-muted">
                {m.ruleLabel}
              </span>
              <Tag variant={m.met ? "success" : "muted"}>
                {m.met ? "MET" : "NOT MET"}
              </Tag>
            </div>
          </div>
        ))}
      </div>
      <p className="text-sm leading-[normal] text-muted">{run.testSetNote}</p>
    </Card>
  );
}

function Banner({ text }: { text: string }) {
  return (
    <div
      role="status"
      className="flex w-full items-center overflow-clip rounded-lg border-2 border-brand bg-banner px-4 py-3 shadow-btn-neutral"
    >
      <p className="text-sm font-semibold leading-[normal] text-ink">{text}</p>
    </div>
  );
}

function BestModelCard({
  model,
  detail,
  precision,
}: {
  model: { title: string; tag: string };
  detail: string;
  precision: number;
}) {
  const router = useRouter();
  const toast = useToast();
  const [deleted, setDeleted] = useState(false);
  const [confirming, setConfirming] = useState(false);
  if (deleted) return null;
  return (
    <>
      <Card
        variant="mint"
        className="gap-2.5 overflow-clip p-4 shadow-card-tight"
        data-testid="best-model"
      >
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold leading-[normal] whitespace-nowrap text-ink">
            {model.title}
          </p>
          <Tag variant="muted">{model.tag}</Tag>
        </div>
        <p className="text-sm leading-[18px] text-muted">{detail}</p>
        <div className="flex items-start gap-2">
          <Button
            size="md"
            className="rounded-[9px]"
            onClick={() => router.push("/c/agreement")}
          >
            Keep and improve
          </Button>
          <Button
            variant="outline"
            size="md"
            onClick={() => router.push("/c/agreement")}
          >
            Try a lower target
          </Button>
          <Button
            variant="outline"
            size="md"
            onClick={() => setConfirming(true)}
          >
            Delete model
          </Button>
        </div>
      </Card>
      {confirming && (
        <ConfirmDialog
          title="Delete model v1?"
          body={`This is your best model so far (precision ${precision}%). Download is locked until a target is met, so deleting loses your progress.`}
          requireCheck="I understand I cannot get it back"
          confirmLabel="Delete model"
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            await deleteModel("v1");
            setConfirming(false);
            setDeleted(true);
            toast("Model deleted from your project.");
          }}
        />
      )}
    </>
  );
}

function VerifiedProgress({ run }: { run: VerifiedRun }) {
  const done = run.steps.filter((s) => s.state === "done").length;
  const pay = run.payment;
  const recap = run.recap;
  return (
    <>
      <ToolStrip tools={run.tools} />
      {recap && <MoneyRecap recap={recap} />}
      <div
        className="flex w-full flex-col gap-2.5 overflow-clip rounded-xl border border-border bg-card p-[18px] shadow-card-tight"
        aria-label={pay ? "Overall progress" : "Steps"}
      >
        {pay ? (
          <>
            <div className="flex items-start justify-between text-sm leading-[normal] whitespace-nowrap">
              <p className="font-semibold text-ink">Overall progress</p>
              <p className="text-muted">
                {run.stepIndex} of {run.totalSteps} steps
              </p>
            </div>
            <ProgressBar
              label="Overall progress"
              value={(run.stepIndex / run.totalSteps) * 100}
              track="neutral"
              size="sm"
              className="h-2 rounded-[4px]"
            />
          </>
        ) : (
          <p className="text-sm font-semibold leading-[normal] whitespace-nowrap text-ink">
            Steps
          </p>
        )}
        <div className={cn("flex flex-col gap-2.5", pay && "pt-1")}>
          {run.steps.map((s) => (
            <div
              key={s.id}
              data-state={s.state}
              className="flex items-center gap-2.5 text-sm leading-[normal]"
            >
              <span
                aria-hidden
                className={cn(
                  "size-[18px] shrink-0 rounded-[9px]",
                  s.state === "done" && "bg-brand-gradient",
                  s.state === "run" && "border-4 border-brand bg-card",
                  s.state === "pending" &&
                    "border border-dashed border-border bg-card",
                )}
              />
              <span
                className={cn(
                  "min-w-px flex-1",
                  s.state === "run"
                    ? "font-semibold text-ink"
                    : s.state === "done"
                      ? "text-ink"
                      : "text-muted",
                )}
              >
                {s.label}
              </span>
            </div>
          ))}
        </div>
        <span className="sr-only">{done} steps done</span>
      </div>
      {pay && (
        <Card
          variant="peach"
          className="gap-1.5 overflow-clip p-[18px] shadow-card-tight"
          data-testid="payment-card"
        >
          <p className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
            PAYMENT
          </p>
          <p className="text-sm font-semibold leading-[normal] text-ink">
            Capturing ${pay.capturedUsd.toFixed(2)} of your $
            {pay.heldUsd.toFixed(2)} hold
          </p>
          <ProgressBar
            label="Captured share of hold"
            value={(pay.capturedUsd / pay.heldUsd) * 100}
            track="neutral"
            size="sm"
            className="h-2 rounded-[4px]"
          />
          <p className="text-sm leading-[normal] text-muted">
            Remaining ${pay.releasedUsd.toFixed(2)} is released. {pay.note}
          </p>
        </Card>
      )}
    </>
  );
}

export function MoneyRecap({
  recap,
  title = "WHAT HAPPENED TO THE MONEY",
  className,
}: {
  recap: NonNullable<VerifiedRun["recap"]>;
  title?: string;
  className?: string;
}) {
  const items = [
    { label: "HELD", value: recap.heldUsd },
    { label: "CHARGED", value: recap.chargedUsd },
    { label: "RELEASED", value: recap.releasedUsd },
  ];
  return (
    <Card
      variant="peach"
      className={cn(
        "gap-2.5 overflow-clip p-[18px] leading-[normal] shadow-card-tight",
        className,
      )}
      data-testid="money-recap"
    >
      <p className="text-xs font-semibold whitespace-nowrap text-muted">
        {title}
      </p>
      <div className="flex items-start gap-2.5 font-semibold whitespace-nowrap">
        {items.map((i) => (
          <div
            key={i.label}
            className="flex min-w-px flex-1 flex-col gap-0.5 overflow-clip rounded-[10px] bg-surface p-3"
          >
            <p className="text-xs text-muted">{i.label}</p>
            <p className="text-xl text-ink">${i.value.toFixed(2)}</p>
          </div>
        ))}
      </div>
      <p className="text-sm font-normal text-muted">{recap.note}</p>
    </Card>
  );
}
