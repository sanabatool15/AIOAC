"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import type { BProject, BReceipt, BTraining } from "@/lib/api";
import * as real from "@/lib/api-real";
import { higherStart, improveStart, needsSettleRetry, OUR_FAILURE_TEXT, recapNote, toRecap, toResultView } from "@/lib/result-view";
import { cn } from "@/lib/utils";
import { TargetAction } from "./step-actions";
import { ErrorLine, Row, useAction } from "./step-parts";

interface StepProps {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

function useReceipt(project: BProject) {
  const [receipt, setReceipt] = useState<BReceipt | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    real
      .getProjectPayment(project.id)
      .then((r) => alive && setReceipt(r))
      .catch(() => alive && setReceipt(null));
    return () => {
      alive = false;
    };
  }, [project.id, project.status, tick]);
  return { receipt, refresh: () => setTick((n) => n + 1) };
}

// Held, charged, released: what happened to the money, from the server receipt.
export function MoneyRecap({ receipt, note }: { receipt: BReceipt | null; note?: string }) {
  const r = toRecap(receipt);
  if (!r) return null;
  const items = [
    { label: "HELD", value: r.held },
    { label: "CHARGED", value: r.charged },
    { label: "RELEASED", value: r.released },
  ];
  return (
    <Card variant="peach" aria-label="What happened to the money" data-testid="money-recap" className="gap-2.5 p-[18px] leading-[normal] shadow-card-tight">
      <p className="text-xs font-semibold whitespace-nowrap text-muted">WHAT HAPPENED TO THE MONEY</p>
      <div className="flex items-start gap-2.5 font-semibold whitespace-nowrap">
        {items.map((i) => (
          <div key={i.label} className="flex min-w-px flex-1 flex-col gap-0.5 overflow-clip rounded-[10px] bg-surface p-3">
            <p className="text-xs text-muted">{i.label}</p>
            <p className="text-xl text-ink">{i.value}</p>
          </div>
        ))}
      </div>
      {note && <p className="text-sm font-normal text-muted">{note}</p>}
    </Card>
  );
}

export function ReceiptCard({ receipt }: { receipt: BReceipt | null }) {
  const r = toRecap(receipt);
  if (!r) return null;
  return (
    <Card variant="mint" aria-label="Receipt" data-testid="receipt" className="gap-2.5 p-4 shadow-card-tight">
      <h2 className="text-sm font-semibold text-ink">Receipt</h2>
      <dl className="flex flex-col gap-1.5">
        <Row label="PayPal hold (the cap)" value={r.held} />
        <Row label="Compute charged" value={r.compute} />
        <Row label="Success fee charged" value={r.fee} />
        <Row label="Released back to you" value={r.released} />
        <Row label="Total charged" value={r.charged} strong />
      </dl>
      <p className="text-xs text-muted">PayPal sandbox: test money only.</p>
    </Card>
  );
}

// A payment whose last PayPal step did not finish. Safe to repeat: each step is saved before the next.
function RetrySettle({ project, receipt, refresh, onChanged }: { project: BProject; receipt: BReceipt | null; refresh: () => void; onChanged: () => void | Promise<void> }) {
  const { busy, error, run } = useAction();
  if (!needsSettleRetry(receipt)) return null;
  return (
    <Card variant="amber" aria-label="Finishing your payment" className="gap-3 p-4 shadow-card-tight">
      <h2 className="text-sm font-semibold text-ink">Finishing your payment</h2>
      <p className="text-sm leading-5 text-ink-2">
        The run is over but the last PayPal step has not finished yet. It is safe to try again. Nothing is charged twice.
      </p>
      <div>
        <Button
          variant="outline"
          size="md"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await real.retrySettle(project.id);
              refresh();
              await onChanged();
            })
          }
        >
          {busy ? "Trying…" : "Try the payment step again"}
        </Button>
      </div>
      <ErrorLine message={error} />
    </Card>
  );
}

// done: verified or missed, the money, and (after a miss) a free Improve round.
export function ResultStep({ project, onChanged }: StepProps) {
  const [t, setT] = useState<BTraining | null>(null);
  const { receipt, refresh } = useReceipt(project);
  useEffect(() => {
    let alive = true;
    real.getTraining(project.id).then((r) => alive && setT(r)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [project.id]);
  const v = toResultView(t);
  return (
    <>
      <Card
        variant={v.kind === "verified" ? "green" : v.kind === "missed" ? "amber" : "plain"}
        aria-label={v.title}
        data-testid={`result-${v.kind}`}
        className="gap-3 p-5 shadow-card-tight"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold leading-[normal] text-ink">{v.title}</h2>
          {v.kind !== "unchecked" && <Tag variant={v.kind === "verified" ? "success" : "muted"}>{v.kind === "verified" ? "VERIFIED" : "NOT MET"}</Tag>}
        </div>
        {v.kind !== "unchecked" && (
          <div className="flex gap-3">
            <Figure label="VERIFIED RESULT" value={`${v.value} out of 100`} />
            <Figure label="YOUR TARGET" value={`${v.target} out of 100`} />
          </div>
        )}
        <p className="text-sm leading-5 text-ink-2">{v.body}</p>
        <p className="text-xs text-muted">One check on data the model never saw. A measured result for this data, not a promise for new data.</p>
      </Card>
      <MoneyRecap receipt={receipt} note={recapNote(v.kind, toRecap(receipt))} />
      <ReceiptCard receipt={receipt} />
      <RetrySettle project={project} receipt={receipt} refresh={refresh} onChanged={onChanged} />
      <ModelLink projectId={project.id} />
      {v.kind === "verified" && <HigherTarget project={project} reached={v.target} onChanged={onChanged} />}
      {v.kind === "missed" && (
        <TargetAction
          project={project}
          onChanged={onChanged}
          initial={improveStart(project.forecast?.suggested_target, v.target)}
          intro="Improve (free): try another target. A new free pilot costs nothing. A new run needs a new price and a new PayPal hold."
        />
      )}
    </>
  );
}

// After a verified run: a new round at a higher target. Free to start; a new run needs a new price and a new PayPal hold.
function HigherTarget({ project, reached, onChanged }: { project: BProject; reached: number | null; onChanged: () => void | Promise<void> }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <Card variant="violet" aria-label="Try a higher target" data-testid="higher-target" className="gap-2 p-4 shadow-card-tight">
        <h2 className="text-sm font-semibold text-ink">Want a higher result?</h2>
        <p className="text-sm leading-5 text-ink-2">Pick a higher target and we run a free small test first. Nothing is charged until you approve a new price and a new PayPal hold.</p>
        <div>
          <Button variant="outline" size="md" onClick={() => setOpen(true)}>
            Try a higher target
          </Button>
        </div>
      </Card>
    );
  }
  return (
    <TargetAction
      project={project}
      onChanged={onChanged}
      initial={higherStart(reached)}
      title="Try a higher target"
      mustBeAbove={reached}
      buttonLabel="Run the free small test"
      intro={`You reached ${reached ?? "your target"} out of 100. Pick a higher number. The free small test gives an estimate of the chance a new run gets there. It is an estimate, not a promise. Your earlier model and receipt stay as they are.`}
    />
  );
}

// Shown only when a model has been saved for this project (GET /model says available).
function ModelLink({ projectId }: { projectId: string }) {
  const [has, setHas] = useState(false);
  useEffect(() => {
    let alive = true;
    real.getModel(projectId).then((m) => alive && setHas(m.available)).catch(() => {});
    return () => {
      alive = false;
    };
  }, [projectId]);
  if (!has) return null;
  return (
    <Card variant="violet" aria-label="Use your model" data-testid="model-link" className="gap-2 p-4 shadow-card-tight">
      <h2 className="text-sm font-semibold text-ink">Use your model</h2>
      <p className="text-sm leading-5 text-ink-2">Try it on one record, run it on a CSV, or download it. This is free.</p>
      <div>
        <Link href={`/projects/${projectId}?tab=model`} className="text-sm font-semibold text-brand-ink underline">
          Open the model
        </Link>
      </div>
    </Card>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className={cn("flex min-w-px flex-1 flex-col gap-[3px] rounded-xl bg-surface p-3.5 leading-[normal]")}>
      <p className="text-xs font-semibold text-muted">{label}</p>
      <p className="text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}

// stopped by the user: compute used so far, no fee.
export function StoppedStep({ project, onChanged }: StepProps) {
  const { receipt, refresh } = useReceipt(project);
  return (
    <>
      <Card variant="amber" aria-label="You stopped the run" className="gap-3 p-5 shadow-card-tight">
        <h2 className="text-base font-semibold text-ink">You stopped the run</h2>
        <p className="text-sm leading-5 text-ink-2">
          You pay for the compute used so far. There is no success fee, and the rest of the PayPal hold is released.
        </p>
      </Card>
      <MoneyRecap receipt={receipt} />
      <ReceiptCard receipt={receipt} />
      <RetrySettle project={project} receipt={receipt} refresh={refresh} onChanged={onChanged} />
    </>
  );
}

// voided or failed: our failure or a cancel. The user pays $0.
export function VoidedStep({ project }: StepProps) {
  const { receipt } = useReceipt(project);
  const releasing = project.status === "failed";
  // A void with no run behind it is a cancel before training; otherwise the run broke on our side.
  const cancelled = project.status === "voided" && !project.run;
  return (
    <>
      <Card variant="red" aria-label="Nothing was charged" className="gap-3 p-5 shadow-card-tight">
        <h2 className="text-base font-semibold text-ink">{cancelled ? "Nothing was charged" : "Something went wrong on our side"}</h2>
        <p className="text-sm leading-5 text-ink-2">
          {cancelled
            ? "This run did not go ahead. You pay $0. The whole hold was released."
            : releasing
              ? "We are releasing your PayPal hold now. You pay $0."
              : OUR_FAILURE_TEXT}
        </p>
        <Link href="/" className="text-sm font-semibold text-brand-ink underline">
          Start a new project
        </Link>
      </Card>
      <MoneyRecap receipt={receipt} />
    </>
  );
}

export function UnknownStep({ project }: StepProps) {
  return (
    <Card aria-label="Unknown state" className="gap-3 p-5">
      <h2 className="text-base font-semibold text-ink">We are not sure what to show here</h2>
      <p className="text-sm leading-5 text-ink-2">
        This project is in a state this page does not know ({project.status}). Nothing has been charged by this page.
      </p>
      <Link href="/" className="text-sm font-semibold text-brand-ink underline">
        Back to start
      </Link>
    </Card>
  );
}
