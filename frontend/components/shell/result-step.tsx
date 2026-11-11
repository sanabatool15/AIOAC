"use client";
import { useEffect, useState } from "react";
import { Button, LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EstimateNote } from "@/components/ui/estimate-note";
import { Tag } from "@/components/ui/tag";
import type { BProject, BReceipt, BTraining } from "@/lib/api";
import * as real from "@/lib/api-real";
import { improveStart, needsSettleRetry, OUR_FAILURE_TEXT, recapNote, toRecap, toResultView } from "@/lib/result-view";
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
    { label: "Held", value: r.held },
    { label: "Charged", value: r.charged },
    { label: "Released", value: r.released },
  ];
  return (
    <Card variant="plain" aria-label="What happened to the money" data-testid="money-recap" className="gap-2.5 p-4">
      <h2 className="text-section text-ink">What happened to the money</h2>
      <dl className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {items.map((i) => (
          <div key={i.label} className="flex min-w-0 flex-col gap-0.5 rounded-lg bg-surface p-3">
            <dt className="text-small text-muted">{i.label}</dt>
            <dd className="text-title text-ink tabular-nums">{i.value}</dd>
          </div>
        ))}
      </dl>
      {note && <p className="text-body text-muted">{note}</p>}
    </Card>
  );
}

export function ReceiptCard({ receipt }: { receipt: BReceipt | null }) {
  const r = toRecap(receipt);
  if (!r) return null;
  return (
    <Card variant="plain" aria-label="Receipt" data-testid="receipt" className="gap-2.5 p-4">
      <h2 className="text-section text-ink">Receipt</h2>
      <dl className="flex flex-col gap-1.5">
        <Row label="PayPal hold (the cap)" value={r.held} />
        <Row label="Compute charged" value={r.compute} />
        <Row label="Success fee charged" value={r.fee} />
        <Row label="Released back to you" value={r.released} />
        <Row label="Total charged" value={r.charged} strong />
      </dl>
      <p className="text-micro text-muted">PayPal sandbox: test money only.</p>
    </Card>
  );
}

// A payment whose last PayPal step did not finish. Safe to repeat: each step is saved before the next.
function RetrySettle({ project, receipt, refresh, onChanged }: { project: BProject; receipt: BReceipt | null; refresh: () => void; onChanged: () => void | Promise<void> }) {
  const { busy, error, run } = useAction();
  if (!needsSettleRetry(receipt)) return null;
  return (
    <Card variant="warning" aria-label="Finishing your payment" className="gap-3 p-4">
      <h2 className="text-body font-semibold text-ink">Finishing your payment</h2>
      <p className="text-body text-ink-2">
        The run is over but the last PayPal step has not finished yet. It is safe to try again. Nothing is charged twice.
      </p>
      <div>
        <Button
          variant="outline"
         
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
  const recap = toRecap(receipt);
  return (
    <>
      <Card
        variant={v.kind === "verified" ? "success" : v.kind === "missed" ? "warning" : "plain"}
        aria-label={v.title}
        data-testid={`result-${v.kind}`}
        className="gap-3 p-5"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-section text-ink">{v.title}</h2>
          {v.kind !== "unchecked" && <Tag variant={v.kind === "verified" ? "success" : "warning"}>{v.kind === "verified" ? "Verified" : "Not met"}</Tag>}
        </div>
        {v.kind !== "unchecked" && (
          <div className="flex gap-3">
            <Figure label="Verified result" value={`${v.value} out of 100`} />
            <Figure label="Your target" value={`${v.target} out of 100`} />
          </div>
        )}
        <p className="text-body text-ink-2">{v.body}</p>
        {recap && (
          <p className="text-body text-ink-2">
            {recapNote(v.kind, recap)} Charged {recap.charged}. Released back to you {recap.released}.
          </p>
        )}
        <EstimateNote>One check on data the model never saw. A measured result for this data, not a promise for new data.</EstimateNote>
      </Card>
      <ReceiptCard receipt={receipt} />
      <RetrySettle project={project} receipt={receipt} refresh={refresh} onChanged={onChanged} />
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

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-0.5 rounded-lg bg-card p-3">
      <p className="text-small text-muted">{label}</p>
      <p className="text-section text-ink tabular-nums">{value}</p>
    </div>
  );
}

// stopped by the user: compute used so far, no fee.
export function StoppedStep({ project, onChanged }: StepProps) {
  const { receipt, refresh } = useReceipt(project);
  return (
    <>
      <Card variant="warning" aria-label="You stopped the run" className="gap-3 p-5">
        <h2 className="text-section text-ink">You stopped the run</h2>
        <p className="text-body text-ink-2">
          You pay for the compute used so far. There is no success fee, and the rest of the PayPal hold is released.
        </p>
      </Card>
      <MoneyRecap receipt={receipt} />
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
      <Card variant="danger" aria-label="Nothing was charged" className="gap-3 p-5">
        <h2 className="text-section text-ink">{cancelled ? "Nothing was charged" : "Something went wrong on our side"}</h2>
        <p className="text-body text-ink-2">
          {cancelled
            ? "This run did not go ahead. You pay $0. The whole hold was released."
            : releasing
              ? "We are releasing your PayPal hold now. You pay $0."
              : OUR_FAILURE_TEXT}
        </p>
        <div>
          <LinkButton href="/" variant="outline" size="sm">
            Start a new chat
          </LinkButton>
        </div>
      </Card>
      <MoneyRecap receipt={receipt} />
    </>
  );
}

export function UnknownStep({ project }: StepProps) {
  return (
    <Card aria-label="Unknown state" className="gap-3 p-5">
      <h2 className="text-section text-ink">We are not sure what to show here</h2>
      <p className="text-body text-ink-2">
        This project is in a state this page does not know ({project.status}). Nothing has been charged by this page.
      </p>
      <div>
        <LinkButton href="/" variant="outline" size="sm">
          Back to start
        </LinkButton>
      </div>
    </Card>
  );
}
