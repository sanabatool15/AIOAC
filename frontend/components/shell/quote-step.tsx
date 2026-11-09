"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EstimateNote } from "@/components/ui/estimate-note";
import { StatusChip } from "@/components/ui/status-chip";
import { Tag } from "@/components/ui/tag";
import { quoteFromProject, toForecast } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { phaseView, projectMoney } from "@/lib/money-summary";
import { ConfirmDialog } from "./confirm-dialog";
import { ErrorLine, Row, useAction } from "./step-parts";
import { ForecastCard, MoneyTriplet } from "./step-cards";

interface StepProps {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// Step 7 of the plan. Quote and pay. Every figure is an estimate except the cap, which is a limit.

export function QuoteStep({ project, onChanged }: StepProps) {
  const f = toForecast(project.forecast);
  // Only a quote made for this round counts; after an Improve pilot the old quote is stale.
  const q = project.status === "quoted" ? quoteFromProject(project) : null;
  const { busy, error, run } = useAction();
  const requote = (
    <Button
      variant="outline"
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
      {f && <ForecastCard f={f} note={!q} />}
      {!q ? (
        <Card aria-label="Your price" className="gap-3 p-4">
          <h2 className="text-section text-ink">Your price</h2>
          <p className="text-body text-ink-2">
            The pilot looks good enough to offer a run. Working out one price for the full run is free.
          </p>
          <div>{requote}</div>
          <ErrorLine message={error} />
        </Card>
      ) : (
        <Card variant="highlight" aria-label="Your price (estimate)" data-testid="quote-card" className="gap-3 p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-section text-ink">Your price</h2>
            <Tag>Estimate</Tag>
          </div>
          <MoneyTriplet summary={projectMoney(project, false)} />
          <dl className="flex flex-col gap-1.5">
            <Row label="Estimated total (estimate)" value={q.estimate} strong />
            <Row label="Likely range (estimate)" value={q.range} />
            {q.modelType && <Row label="Model type" value={q.modelType.name} />}
            <Row label="Compute, up to" value={q.computeMax} />
            <Row label="Success fee, up to (only if verified)" value={q.feeMax} />
          </dl>
          {q.modelType && <p className="text-micro text-muted">{q.modelType.note}</p>}
          <p className="text-body text-ink-2">
            PayPal holds {q.cap} (the cap) and charges nothing yet. When the run ends we charge the compute actually used
            and release the rest. {q.terms}
          </p>
          <EstimateNote>PayPal sandbox: test money only. Figures are estimates, except the cap, which is a limit.</EstimateNote>
          <div className="flex flex-wrap gap-2">
            <Button
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

// What happened to a hold that is no longer usable. Nothing is charged in any of these cases.
function deadTitle(state: string | undefined): string {
  if (state === "expired") return "Your PayPal hold expired";
  if (state === "declined") return "PayPal declined the hold";
  return "The PayPal hold was cancelled";
}
function deadBody(state: string | undefined): string {
  if (state === "expired") return "The hold ran out before it was used. Nothing was charged. Get a new price to place a new hold.";
  if (state === "declined") return "PayPal did not approve the hold. Nothing was charged. Check your PayPal sandbox account, then get a new price to try again.";
  return "The hold was cancelled. Nothing was charged. Get a new price to try again.";
}

// awaiting_payment: waiting for the buyer on PayPal. A reload lands here, so it can resume or check the approval.
export function PayStep({ project, onChanged }: StepProps) {
  const router = useRouter();
  const { busy, error, run } = useAction();
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const pay = project.payment;
  const dead = pay && ["declined", "expired", "voided"].includes(pay.state);
  const q = quoteFromProject(project);
  const summary = projectMoney(project);
  const phase = phaseView(summary.phase);
  return (
    <Card variant={dead ? "danger" : "highlight"} aria-label="Waiting for your PayPal approval" className="gap-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-section text-ink">{dead ? deadTitle(pay?.state) : "Waiting for your PayPal approval"}</h2>
        <StatusChip tone={phase.tone}>{phase.label}</StatusChip>
      </div>
      <MoneyTriplet summary={summary} />
      {dead ? (
        <p className="text-body text-ink-2">{deadBody(pay?.state)}</p>
      ) : (
        <p className="text-body text-ink-2">
          PayPal will hold up to {q?.cap ?? "the cap"} and charge nothing yet. Approve it on PayPal (sandbox, no real
          money), then come back here. Already approved? Press &quot;Check my approval&quot;.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {dead ? (
          <Button
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
            <Button variant="outline" disabled={busy} onClick={() => setConfirmingCancel(true)}>
              Cancel
            </Button>
          </>
        )}
      </div>
      {confirmingCancel && (
        <ConfirmDialog
          title="Cancel this run"
          body="Cancel this run? Nothing has been charged. If PayPal placed a hold, the whole hold is released and you pay $0."
          confirmLabel="Yes, cancel"
          busyLabel="Cancelling…"
          onCancel={() => setConfirmingCancel(false)}
          onConfirm={async () => {
            await real.cancelHold(project.id);
            setConfirmingCancel(false);
            await onChanged();
          }}
        />
      )}
      <ErrorLine message={error} />
    </Card>
  );
}
