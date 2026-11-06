"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Tag } from "@/components/ui/tag";
import { dollars, toTraining } from "@/lib/adapters";
import { ApiError, type BProject, type BTraining } from "@/lib/api";
import * as real from "@/lib/api-real";
import { isFinal, nextPollDelay, STOP_CONFIRM_TEXT, stopErrorText } from "@/lib/training-poll";
import { ErrorLine, Row, useAction } from "./step-parts";

interface StepProps {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// paid: the server confirmed the hold, start the run. Normally the return page already did; this covers a reload.
export function PaidStep({ project, onChanged }: StepProps) {
  const { busy, error, run } = useAction();
  const started = useRef(false);
  const start = () =>
    run(async () => {
      try {
        await real.startTraining(project.id);
      } catch (e) {
        // 409 = already started (a reload or a second tab). Not an error for the user.
        if (!(e instanceof ApiError && e.status === 409)) throw e;
      }
      await onChanged();
    });
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <Card variant="green" aria-label="Payment confirmed" className="gap-3 p-5 shadow-card-tight">
      <h2 className="text-base font-semibold text-ink">Payment confirmed</h2>
      <p className="text-sm leading-5 text-ink-2">PayPal confirmed the hold. Nothing is charged yet. Starting your training run…</p>
      {error && (
        <div>
          <Button size="md" disabled={busy} onClick={start}>
            Try starting again
          </Button>
        </div>
      )}
      <ErrorLine message={error} />
    </Card>
  );
}

// training: poll while the project is `training`, show progress, Stop. No live chart: there is no honest step count.
export function TrainingStep({ project, onChanged }: StepProps) {
  const [t, setT] = useState<BTraining | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const { busy, error: stopError, run } = useAction();
  const reported = useRef(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function tick(last: BTraining | null) {
      let latest = last;
      try {
        const r = await real.getTraining(project.id);
        if (!alive) return;
        latest = r;
        setT(r);
        setError(null);
        if (isFinal(r) && !reported.current) {
          reported.current = true;
          await onChanged();
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : "Could not check progress.");
      }
      const delay = nextPollDelay(project.status, latest);
      if (alive && delay !== null) timer = setTimeout(() => void tick(latest), delay);
    }
    void tick(null);
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, project.status]);

  const v = toTraining(t);
  const starting = !v || v.status === "not_started";
  const hold = project.payment?.hold_cents;
  return (
    <>
      <Card variant="blue" aria-label="Training your model" data-testid="training-card" className="gap-3 p-5 shadow-card-tight">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold leading-[normal] text-ink">Training your model</h2>
          {!starting && <Tag variant="brand">{v.stopRequested ? "STOPPING" : "RUNNING"}</Tag>}
        </div>
        {starting ? (
          <p className="text-sm text-ink-2">Getting ready to start…</p>
        ) : (
          <>
            <p className="text-sm font-medium text-ink" aria-live="polite">
              {v.stopRequested ? "Stopping…" : v.stage}
            </p>
            <ProgressBar value={v.progress} label="Training progress" track="blue" />
            <dl className="flex flex-col gap-1.5">
              <Row label="Time so far" value={v.elapsed} />
              <Row label="Spent so far (estimate)" value={v.spend} />
              {v.eta && <Row label="Time left (estimate)" value={v.eta} />}
              <Row label="Compute limit (the cap)" value={v.cap} />
            </dl>
          </>
        )}
        <ErrorLine message={error} />
        {!confirming ? (
          <div>
            <Button variant="outline" size="md" disabled={starting || v?.stopRequested || v?.status !== "running"} onClick={() => setConfirming(true)}>
              Stop
            </Button>
          </div>
        ) : (
          <div role="alertdialog" aria-label="Stop the run" className="flex flex-col gap-2 rounded-lg border border-border bg-white p-3">
            <p className="text-sm leading-5 text-ink-2">{STOP_CONFIRM_TEXT}</p>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                size="md"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    try {
                      await real.stopTraining(project.id);
                    } catch (e) {
                      setConfirming(false);
                      await onChanged();
                      throw new Error(stopErrorText(e));
                    }
                    setConfirming(false);
                  })
                }
              >
                {busy ? "Stopping…" : "Yes, stop now"}
              </Button>
              <Button variant="outline" size="md" disabled={busy} onClick={() => setConfirming(false)}>
                Keep going
              </Button>
            </div>
            <ErrorLine message={stopError} />
          </div>
        )}
        <ErrorLine message={!confirming ? stopError : null} />
      </Card>
      {hold !== undefined && (
        <Card variant="peach" aria-label="Your PayPal hold" className="gap-1.5 p-4 shadow-card-tight">
          <p className="text-xs font-semibold leading-[normal] text-muted">YOUR PAYPAL HOLD</p>
          <p className="text-sm font-semibold text-ink">{dollars(hold)} is held. Nothing is charged until the run ends.</p>
          <p className="text-sm text-muted">Then we charge only the compute used and release the rest.</p>
        </Card>
      )}
    </>
  );
}
