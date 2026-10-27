"use client";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import type { BaselineRun, Chat, Message } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";

// Screen 4: chat-first layout (no canvas). The agent's work shows up as inline cards in the thread.
export function BaselineChat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const run = chat.baseline;
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
              {m.blocks?.includes("steps") && <StepsCard run={run} />}
              {m.blocks?.includes("readiness") && <ReadinessCard run={run} />}
              {m.blocks?.includes("result") && <ResultCard run={run} />}
            </div>
          ),
        )
      )}
    </InlineChatFrame>
  );
}

function StepsCard({ run }: { run: BaselineRun }) {
  return (
    <div
      className="flex w-full flex-col gap-[9px] overflow-clip rounded-xl border border-border bg-card p-3.5"
      aria-label="Steps"
    >
      {run.steps.map((s) => (
        <div
          key={s.id}
          className="flex items-center gap-2.5 text-sm leading-[normal]"
        >
          <span
            aria-hidden
            className="size-[18px] shrink-0 rounded-[9px] bg-brand-gradient"
          />
          <span className="sr-only">Done: </span>
          <span className="min-w-px flex-1 text-ink">{s.label}</span>
          <span className="shrink-0 whitespace-nowrap text-muted">
            {s.seconds}s
          </span>
        </div>
      ))}
    </div>
  );
}

function ReadinessCard({ run }: { run: BaselineRun }) {
  const r = run.readiness;
  return (
    <Card
      variant="green"
      className="flex-row items-center gap-4 overflow-clip p-3.5 shadow-card-tight"
      data-testid="readiness-card"
    >
      <div className="flex size-[54px] shrink-0 items-center justify-center rounded-xl bg-brand-gradient text-[28px] font-semibold leading-[normal] text-white shadow-glow">
        {r.grade}
      </div>
      <div className="flex min-w-px flex-1 flex-col gap-0.5 overflow-clip text-sm leading-[normal]">
        <p className="font-semibold text-ink">{r.title}</p>
        <p className="text-muted">{r.detail}</p>
      </div>
      <Tag variant="brand">{r.tag}</Tag>
    </Card>
  );
}

const BAR_PX_PER_PCT = 1.0845; // Figma: 71% = 77px, 80% = 86px (bar height = pct * ~1.08)

function ResultCard({ run }: { run: BaselineRun }) {
  const { precision, recall, targetPrecision } = run.result;
  return (
    <Card
      variant="blue"
      className="gap-3 overflow-clip p-[18px] shadow-card-tight"
      data-testid="baseline-result"
    >
      <p className="text-sm font-semibold leading-[normal] text-ink">
        Free baseline results
      </p>
      <div className="flex items-end gap-7">
        <div className="flex min-w-px flex-1 gap-7 leading-[normal]">
          <Metric
            value={precision}
            label="Right when we flag someone"
          />
          <Metric value={recall} label="Leavers we catch" />
        </div>
        <div className="flex items-end gap-[22px] pt-1.5">
          <Bar pct={precision} label="Baseline" className="bg-bar-baseline" />
          <Bar pct={targetPrecision} label="Target" className="bg-bar-target" />
        </div>
      </div>
    </Card>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex w-[150px] flex-col gap-0.5">
      <p className="text-[28px] font-semibold text-ink">{value}%</p>
      <p className="text-sm text-muted">{label}</p>
    </div>
  );
}

function Bar({
  pct,
  label,
  className,
}: {
  pct: number;
  label: string;
  className: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5 leading-[normal]">
      <p className="text-sm font-semibold text-ink">{pct}%</p>
      <div
        role="img"
        aria-label={`${label} ${pct}%`}
        className={cn("w-[52px] rounded-md", className)}
        style={{ height: Math.round(pct * BAR_PX_PER_PCT) }}
      />
      <p className="text-xs text-muted">{label}</p>
    </div>
  );
}
