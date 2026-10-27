"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { useToast } from "@/components/ui/toast";
import { predictChurn } from "@/lib/mock-api";
import type {
  Chat,
  Message,
  PredictionInput,
  PredictionResult,
  ResultRun,
} from "@/lib/types";
import { ExperimentCanvas } from "./experiment-canvas";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";
import { ToolStrip } from "./tool-strip";

// Screen 14: your model is ready. Live prediction + receipt and downloads.
export function ResultChat({
  chat,
  messages,
  onSend,
}: {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
}) {
  const run = chat.result;
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
                {m.blocks?.includes("prediction") && (
                  <PredictionCard run={run} />
                )}
                {m.blocks?.includes("ways") && <WaysCard run={run} />}
                {m.blocks?.includes("quick-replies") && (
                  <QuickReplies run={run} />
                )}
              </div>
            ),
          )
        )}
      </InlineChatFrame>
      <ExperimentCanvas
        chat={chat}
        variant={chat.id === "use-model" ? "use" : "result"}
      >
        <ReceiptTab run={run} />
      </ExperimentCanvas>
    </>
  );
}

const CONTRACTS: PredictionInput["contract"][] = [
  "Month-to-month",
  "One year",
  "Two year",
];
const fieldClass =
  "appearance-none " +
  "w-full rounded-[9px] border border-border bg-card px-3 py-2.5 text-sm leading-[normal] text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge";

function PredictionCard({ run }: { run: ResultRun }) {
  const [input, setInput] = useState<PredictionInput>(run.defaults);
  const [result, setResult] = useState<PredictionResult>(run.initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function predict() {
    setBusy(true);
    setError(null);
    try {
      setResult(await predictChurn(input));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Prediction failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="flex w-full flex-col gap-3 overflow-clip rounded-xl border border-border bg-card p-5 shadow-card-tight"
      data-testid="prediction-card"
    >
      <p className="text-base font-semibold leading-[normal] whitespace-nowrap text-ink">
        Try a prediction
      </p>
      <div className="flex items-start gap-3">
        <label className="flex min-w-px flex-1 flex-col gap-1.5">
          <span className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
            Contract
          </span>
          <select
            className={fieldClass}
            value={input.contract}
            onChange={(e) =>
              setInput({
                ...input,
                contract: e.target.value as PredictionInput["contract"],
              })
            }
          >
            {CONTRACTS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="flex min-w-px flex-1 flex-col gap-1.5">
          <span className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
            Months as customer
          </span>
          <input
            className={fieldClass}
            inputMode="numeric"
            value={input.months}
            onChange={(e) =>
              setInput({
                ...input,
                months: Number(e.target.value.replace(/\D/g, "")),
              })
            }
          />
        </label>
        <label className="flex min-w-px flex-1 flex-col gap-1.5">
          <span className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
            Monthly charge
          </span>
          <input
            className={fieldClass}
            inputMode="numeric"
            value={`$${input.monthlyCharge}`}
            onChange={(e) =>
              setInput({
                ...input,
                monthlyCharge: Number(e.target.value.replace(/\D/g, "")),
              })
            }
          />
        </label>
      </div>
      <Button
        size="md"
        className="self-start rounded-[9px]"
        onClick={predict}
        disabled={busy}
      >
        {busy ? "Predicting…" : "Predict"}
      </Button>
      {error && (
        <p role="alert" className="text-sm leading-[normal] text-danger">
          {error}{" "}
          <button
            type="button"
            className="font-semibold underline"
            onClick={predict}
          >
            Try again
          </button>
        </p>
      )}
      <div
        className="flex flex-col gap-1.5 overflow-clip rounded-[10px] bg-surface p-3.5"
        aria-live="polite"
        data-testid="prediction-result"
      >
        <p className="text-xl font-semibold leading-[normal] text-ink">
          {result.probability}% likely to stop buying
        </p>
        <ProgressBar
          label="Chance to stop buying"
          value={result.probability}
          track="neutral"
          className="w-[300px] max-w-full"
        />
        <p className="text-sm leading-[18px] text-muted">
          Main reasons: {result.reasons.join(", ")}.
        </p>
      </div>
    </div>
  );
}

function QuickReplies({ run }: { run: ResultRun }) {
  const router = useRouter();
  const toast = useToast();
  return (
    <div className="flex items-start gap-2">
      <Chip
        variant="primary"
        disabled={!run.canDownloadModel}
        onClick={() =>
          toast(
            "Model download is mocked. The real file comes from the backend.",
          )
        }
      >
        Download model
      </Chip>
      <Chip onClick={() => toast("Share link copied (mock).")}>
        Share results
      </Chip>
      <Chip onClick={() => router.push("/")}>Train another</Chip>
    </div>
  );
}

function ReceiptTab({ run }: { run: ResultRun }) {
  const toast = useToast();
  return (
    <>
      <ToolStrip tools={run.tools} />
      <Card
        variant="mint"
        className="gap-1.5 overflow-clip p-[18px] text-sm shadow-card-tight"
        data-testid="receipt-card"
      >
        <p className="font-semibold leading-[normal] text-ink">
          Financial receipt
        </p>
        {run.receipt.map((r) => (
          <div
            key={r.id}
            className="flex items-start gap-4 border-b border-border py-[9px]"
          >
            <p className="w-[140px] shrink-0 font-semibold leading-[normal] text-muted">
              {r.label}
            </p>
            <p className="min-w-px flex-1 leading-[19px] text-ink">{r.value}</p>
          </div>
        ))}
      </Card>
      <div className="flex w-full flex-col gap-2">
        <Button
          size="md"
          className="w-full rounded-[9px]"
          onClick={() =>
            toast("Receipt PDF is mocked. The backend will generate it.")
          }
        >
          Download receipt (PDF)
        </Button>
        <Button
          variant="outline"
          size="md"
          className="w-full"
          disabled={!run.canDownloadModel}
          onClick={() => toast("Model download is mocked.")}
        >
          Download model
        </Button>
        <Button
          variant="outline"
          size="md"
          className="w-full"
          onClick={() => toast("Training log is mocked.")}
        >
          View training log
        </Button>
      </div>
      <p className="text-sm leading-[18px] text-muted">{run.note}</p>
    </>
  );
}

function WaysCard({ run }: { run: ResultRun }) {
  return (
    <Card
      variant="violet"
      className="gap-2.5 overflow-clip p-4 shadow-card-tight"
      data-testid="ways-card"
    >
      <h2 className="text-xs font-semibold leading-[normal] text-muted">
        THREE WAYS TO USE IT
      </h2>
      <ul className="flex flex-col gap-2.5">
        {run.ways.map((w) => (
          <li
            key={w}
            className="flex items-center gap-2.5 text-sm leading-[normal] text-ink"
          >
            <span
              aria-hidden
              className="size-[18px] shrink-0 rounded-full bg-brand-gradient"
            />
            <span className="min-w-px flex-1">{w}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
