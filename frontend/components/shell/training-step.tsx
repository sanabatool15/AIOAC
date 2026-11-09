"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { Tag } from "@/components/ui/tag";
import { projectMoney } from "@/lib/money-summary";
import { ConfirmDialog } from "./confirm-dialog";
import { MoneyTriplet } from "./step-cards";
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
    <Card variant="success" aria-label="Payment confirmed" className="gap-3 p-5">
      <h2 className="text-section text-ink">Payment confirmed</h2>
      <p className="text-body text-ink-2">PayPal confirmed the hold. Nothing is charged yet. Starting your training run…</p>
      {error && (
        <div>
          <Button disabled={busy} onClick={start}>
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
  const [stopError, setStopError] = useState<string | null>(null);
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
      <Card variant="live" aria-label="Training your model" data-testid="training-card" className="gap-3 p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-section text-ink">Training your model</h2>
          {!starting && <Tag variant="brand">{v.stopRequested ? "Stopping" : "Running"}</Tag>}
        </div>
        {starting ? (
          <p className="text-body text-ink-2">Getting ready to start…</p>
        ) : (
          <>
            <p className="text-body font-medium text-ink" aria-live="polite">
              {v.stopRequested ? "Stopping…" : v.stage}
            </p>
            <ProgressBar value={v.progress} label="Training progress" />
            <dl className="flex flex-col gap-1.5">
              <Row label="Time so far" value={v.elapsed} />
              <Row label="Spent so far (estimate)" value={v.spend} />
              {v.eta && <Row label="Time left (estimate)" value={v.eta} />}
              <Row label="Compute limit (the cap)" value={v.cap} />
            </dl>
          </>
        )}
        <ErrorLine message={error} />
        <div>
          <Button variant="outline" disabled={starting || v?.stopRequested || v?.status !== "running"} onClick={() => setConfirming(true)}>
            Stop
          </Button>
        </div>
        <ErrorLine message={stopError} />
        {confirming && (
          <ConfirmDialog
            title="Stop the run"
            body={STOP_CONFIRM_TEXT}
            confirmLabel="Yes, stop now"
            busyLabel="Stopping…"
            onCancel={() => setConfirming(false)}
            onConfirm={async () => {
              setStopError(null);
              try {
                await real.stopTraining(project.id);
              } catch (e) {
                setStopError(stopErrorText(e));
                await onChanged();
              }
              setConfirming(false);
            }}
          />
        )}
      </Card>
      {hold !== undefined && (
        <Card variant="money" aria-label="Your PayPal hold" className="gap-2 p-4">
          <h2 className="text-section text-ink">Your PayPal hold</h2>
          <MoneyTriplet summary={projectMoney(project)} />
          <p className="text-small text-muted">
            {dollars(hold)} is held, not charged. When the run ends we charge only the compute used and release the rest.
          </p>
        </Card>
      )}
    </>
  );
}
