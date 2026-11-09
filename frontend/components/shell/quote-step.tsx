"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { quoteFromProject, toForecast } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { ErrorLine, Row, useAction } from "./step-parts";
import { ForecastCard } from "./step-cards";

interface StepProps {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// Step 7 of the plan. Quote and pay on the polished cards. Every figure is an estimate except the cap, which is a limit.

export function QuoteStep({ project, onChanged }: StepProps) {
  const f = toForecast(project.forecast);
  // Only a quote made for this round counts; after an Improve pilot the old quote is stale.
  const q = project.status === "quoted" ? quoteFromProject(project) : null;
  const { busy, error, run } = useAction();
  const requote = (
    <Button
      variant="outline"
      size="md"
      disabled={busy}
      onClick={() =>
        run(async () => {
          await real.createQuote(project.id);
          await onChanged();
        })
      }
    >
      {q ? "Get a new price" : busy ? "Working out the price…" : "Get my price"}
    </Button>
  );
  return (
    <>
      {f && <ForecastCard f={f} />}
      {!q ? (
        <Card aria-label="Your price" className="gap-3 p-4">
          <h2 className="text-base font-semibold leading-[normal] text-ink">Your price</h2>
          <p className="text-sm leading-5 text-ink-2">
            The pilot looks good enough to offer a run. I will work out one price for the full run. This is free.
          </p>
          <div>{requote}</div>
          <ErrorLine message={error} />
        </Card>
      ) : (
        <Card variant="peach" aria-label="Your price (estimate)" data-testid="quote-card" className="gap-3 p-5 shadow-card-tight">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-semibold leading-[normal] text-ink">Your price</h2>
            <Tag>ESTIMATE</Tag>
          </div>
          <dl className="flex flex-col gap-1.5">
            <Row label="Estimated total (estimate)" value={q.estimate} strong />
            <Row label="Likely range (estimate)" value={q.range} />
            {q.modelType && <Row label="Model type" value={q.modelType.name} />}
            <Row label="Compute, up to" value={q.computeMax} />
            <Row label="Success fee, up to (only if verified)" value={q.feeMax} />
            <Row label="The most you can ever be charged (the cap)" value={q.cap} strong />
          </dl>
          {q.modelType && <p className="text-xs text-muted">{q.modelType.note}</p>}
          <p className="text-sm leading-5 text-ink-2">
            PayPal will hold {q.cap} (the cap) and charge nothing yet. When the run is over, we charge the compute
            actually used and release the rest of the hold. {q.terms}
          </p>
          <p className="text-xs text-muted">PayPal sandbox: this is test money, no real money is used.</p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="md"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const url = await real.startPayment(project.id);
                  window.location.assign(url);
                })
              }
            >
              {busy ? "Opening PayPal…" : "Approve and pay"}
            </Button>
            {requote}
          </div>
          <ErrorLine message={error} />
        </Card>
      )}
    </>
  );
}

// awaiting_payment: waiting for the buyer on PayPal. A reload lands here, so it can resume or check the approval.
export function PayStep({ project, onChanged }: StepProps) {
  const router = useRouter();
  const { busy, error, run } = useAction();
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const pay = project.payment;
  const dead = pay && ["declined", "expired", "voided"].includes(pay.state);
  const q = quoteFromProject(project);
  return (
    <Card variant="peach" aria-label="Waiting for your PayPal approval" className="gap-3 p-5 shadow-card-tight">
      <h2 className="text-base font-semibold leading-[normal] text-ink">Waiting for your PayPal approval</h2>
      {dead ? (
        <p className="text-sm leading-5 text-ink-2">
          That PayPal hold did not go through ({pay?.state}). Nothing was charged. Get a new price to try again.
        </p>
      ) : (
        <p className="text-sm leading-5 text-ink-2">
          PayPal will hold up to {q?.cap ?? "the cap"} and charge nothing yet. Approve it on PayPal (sandbox, no real
          money), then come back here. If you already approved it, press &quot;Check my approval&quot;.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {dead ? (
          <Button
            size="md"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await real.createQuote(project.id);
                await onChanged();
              })
            }
          >
            Get a new price
          </Button>
        ) : (
          <>
            <Button
              size="md"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  const url = await real.startPayment(project.id);
                  window.location.assign(url);
                })
              }
            >
              Open PayPal
            </Button>
            <Button
              variant="outline"
              size="md"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  if (pay) real.rememberPayment({ paymentId: pay.payment_id, projectId: project.id });
                  router.push("/pay/return");
                })
              }
            >
              Check my approval
            </Button>
            <Button variant="outline" size="md" disabled={busy} onClick={() => setConfirmingCancel(true)}>
              Cancel
            </Button>
          </>
        )}
      </div>
      {confirmingCancel && (
        <div role="alertdialog" aria-label="Cancel this run" className="flex flex-col gap-2 rounded-lg border border-border bg-white p-3">
          <p className="text-sm leading-5 text-ink-2">
            Cancel this run? Nothing has been charged. If PayPal placed a hold, the whole hold is released and you pay $0.
          </p>
          <div className="flex gap-2">
            <Button
              variant="destructive"
              size="md"
              disabled={busy}
              onClick={() =>
                run(async () => {
                  await real.cancelHold(project.id);
                  setConfirmingCancel(false);
                  await onChanged();
                })
              }
            >
              {busy ? "Cancelling…" : "Yes, cancel"}
            </Button>
            <Button variant="outline" size="md" disabled={busy} onClick={() => setConfirmingCancel(false)}>
              Keep it
            </Button>
          </div>
        </div>
      )}
      <ErrorLine message={error} />
    </Card>
  );
}
