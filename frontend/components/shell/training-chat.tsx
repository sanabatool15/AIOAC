"use client";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { ProgressBar } from "@/components/ui/progress-bar";
import type { Chat, Message, TrainingRun } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ExperimentCanvas } from "./experiment-canvas";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";
import { ToolStrip } from "./tool-strip";

// Screen 10: training in progress. Chat column (560px) + 500px canvas with underline tabs.
export function TrainingChat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const run = chat.training;
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
                {m.blocks?.includes("chart") && <LiveChartCard run={run} />}
              </div>
            ),
          )
        )}
      </InlineChatFrame>
      <ExperimentCanvas chat={chat}>
        <ProgressBody run={run} />
      </ExperimentCanvas>
    </>
  );
}

const CHART_W = 520;
const CHART_H = 150;
const Y_TARGET = 42; // Figma: the 80% target line sits 42px from the top
const PX_PER_PCT = 3.2;

function LiveChartCard({ run }: { run: TrainingRun }) {
  const xs = run.series.map(
    (_, i) => 10 + (i * (CHART_W - 20)) / (run.series.length - 1),
  );
  const ys = run.series.map(
    (v) => Y_TARGET + (run.targetPrecision - v) * PX_PER_PCT,
  );
  const points = xs.map((x, i) => `${x},${ys[i]}`).join(" ");
  return (
    <div
      className="flex w-full flex-col gap-2.5 overflow-clip rounded-xl border border-border bg-card p-[18px] shadow-card-tight"
      data-testid="live-chart"
    >
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold leading-[normal] whitespace-nowrap text-ink">
          Validation precision during training
        </p>
        <Tag variant="brand">UPDATING</Tag>
      </div>
      <svg
        role="img"
        aria-label={`Validation precision rising to ${run.precisionNow}% against a ${run.targetPrecision}% target`}
        viewBox={`0 0 ${CHART_W} ${CHART_H}`}
        className="h-[150px] w-full max-w-[520px] rounded-lg bg-surface"
      >
        <line
          x1="0"
          x2={CHART_W}
          y1={Y_TARGET}
          y2={Y_TARGET}
          strokeDasharray="4 4"
          className="stroke-border"
          strokeWidth="1"
        />
        <polyline
          points={points}
          fill="none"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="stroke-ink-2"
        />
      </svg>
      <p className="text-xs leading-[normal] whitespace-nowrap text-muted">
        Dashed line: your {run.targetPrecision}% target
      </p>
    </div>
  );
}

function ProgressBody({ run }: { run: TrainingRun }) {
  return (
    <>
      <ToolStrip tools={run.tools} />
      <Card
        variant="blue"
        className="gap-2 overflow-clip p-[18px] shadow-card-tight"
        data-testid="eta-card"
      >
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
            ESTIMATED TIME LEFT
          </p>
          <Tag variant="brand">LIVE</Tag>
        </div>
        <p className="text-[28px] font-semibold leading-[normal] text-ink">
          {run.eta.headline}
        </p>
        <p className="text-sm leading-[normal] text-muted">{run.eta.detail}</p>
        <ProgressBar
          label="Training progress"
          value={run.eta.progress}
          track="neutral"
          size="sm"
          className="h-2 rounded-[4px]"
        />
      </Card>
      <div
        className="flex w-full flex-col gap-3 overflow-clip rounded-xl border border-border bg-card p-[18px] shadow-card-tight"
        aria-label="Stages"
      >
        <p className="text-sm font-semibold leading-[normal] text-ink">
          Stages
        </p>
        {run.stages.map((s) => (
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
            <span className="shrink-0 whitespace-nowrap text-muted">
              {s.time}
            </span>
          </div>
        ))}
      </div>
      <Card
        variant="violet"
        className="gap-1.5 overflow-clip p-[18px] shadow-card-tight"
        data-testid="decision-card"
      >
        <p className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
          NEXT DECISION
        </p>
        <p className="text-sm leading-[18px] text-ink">{run.decision}</p>
      </Card>
    </>
  );
}
