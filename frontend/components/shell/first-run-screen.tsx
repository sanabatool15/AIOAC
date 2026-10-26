"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { startChat } from "@/lib/mock-api";
import { setFirstRun } from "@/lib/session";
import { cn } from "@/lib/utils";
import { Composer } from "./composer";

const examples = [
  "Which customers will churn?",
  "Score my sales leads",
  "Will this loan be repaid?",
  "Forecast next month demand",
];

const steps = [
  {
    n: 1,
    title: "Add data",
    body: "Upload, link or connect",
    tone: "surface-violet",
  },
  {
    n: 2,
    title: "Agree a target",
    body: "And a maximum price",
    tone: "surface-blue",
  },
  {
    n: 3,
    title: "Pay only if verified",
    body: "Independent test decides",
    tone: "surface-mint",
  },
];

// Screen 35: what a brand-new user sees on "/" (no projects yet): examples, sample data, how it works.
export function FirstRunScreen() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState<(() => void) | null>(null);

  function begin(text: string, opts: { sample?: boolean } = {}) {
    setBusy(true);
    setRetry(null);
    startChat(text, opts)
      .then(({ id }) => {
        setFirstRun(false);
        router.push(`/c/${id}`);
      })
      .catch(() => {
        setBusy(false);
        setRetry(() => () => begin(text, opts));
      });
  }

  return (
    <section
      aria-label="First run"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <header className="flex h-14 shrink-0 items-center border-b border-border px-6">
        <h2 className="text-sm font-normal leading-[normal] text-muted">
          New chat
        </h2>
      </header>
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto pb-2.5 pt-[90px]">
        <div className="flex h-fit w-[680px] max-w-[calc(100%-48px)] flex-col gap-[18px]">
          <div className="flex flex-col items-center gap-2 text-center leading-[normal]">
            <h1 className="text-[28px] font-semibold text-ink">
              What do you want to predict?
            </h1>
            <p className="text-sm text-muted">
              Describe it, add your data, and agree a target. You pay only if
              the result is verified.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {examples.map((e) => (
              <Chip key={e} disabled={busy} onClick={() => begin(e)}>
                {e}
              </Chip>
            ))}
          </div>
          {retry && (
            <p
              role="alert"
              className="flex items-center gap-3 text-sm text-danger"
            >
              Could not start the chat.
              <Button variant="outline" onClick={retry}>
                Try again
              </Button>
            </p>
          )}
          <div
            className="surface-peach flex w-full flex-col gap-2.5 rounded-xl border border-dashed p-[18px] shadow-card-tight"
            data-testid="sample-card"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold leading-[normal] text-ink">
                No data yet? Try a sample.
              </h2>
              <Button
                size="md"
                disabled={busy}
                className="rounded-[9px] shadow-glow"
                onClick={() =>
                  begin("Use the sample telco churn data", { sample: true })
                }
              >
                Use telco churn sample
              </Button>
            </div>
            <p className="text-sm leading-[normal] text-muted">
              7,043 customers · 21 columns · safe public dataset
            </p>
          </div>
          <ol className="flex gap-3" aria-label="How it works">
            {steps.map((s) => (
              <li
                key={s.n}
                className={cn(
                  "flex min-w-px flex-1 flex-col gap-1 rounded-xl border p-4 leading-[normal] shadow-card-tight",
                  s.tone,
                )}
              >
                <span
                  aria-hidden
                  className="flex size-6 items-center justify-center rounded-full bg-brand-gradient text-xs font-semibold text-white shadow-glow"
                >
                  {s.n}
                </span>
                <span className="text-sm font-semibold text-ink">
                  {s.title}
                </span>
                <span className="text-sm text-muted">{s.body}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <div className="flex shrink-0 justify-center pb-[22px] pt-2">
        <div className="w-[680px] max-w-[calc(100%-48px)]">
          <Composer
            busy={busy}
            onSend={(text) => begin(text)}
            placeholder="Ask AIOAC anything, or describe what to predict..."
          />
        </div>
      </div>
    </section>
  );
}
