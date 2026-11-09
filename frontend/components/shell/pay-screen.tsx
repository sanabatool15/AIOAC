"use client";
import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, Check, Circle, Loader2, X } from "lucide-react";
import { Button, LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EstimateNote } from "@/components/ui/estimate-note";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { StatusChip } from "@/components/ui/status-chip";
import { dollars, quoteFromProject } from "@/lib/adapters";
import * as real from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { phaseView, projectMoney } from "@/lib/money-summary";
import { payTimeline, type TimelineState } from "@/lib/pay-timeline";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "./confirm-dialog";
import { Row, ErrorLine, useAction } from "./step-parts";
import { MoneyTriplet } from "./step-cards";
import { TopBar } from "./top-bar";

const DOT: Record<TimelineState, string> = {
  done: "bg-success-soft text-success border-success-line",
  current: "bg-brand-tint text-brand border-brand-line",
  stopped: "bg-danger-soft text-danger border-danger-line",
  todo: "bg-surface text-muted border-border",
};

function Dot({ state }: { state: TimelineState }) {
  return (
    <span aria-hidden className={cn("flex size-7 shrink-0 items-center justify-center rounded-full border", DOT[state])}>
      {state === "done" ? <Check className="size-4" strokeWidth={3} /> : state === "current" ? <Loader2 className="size-4 motion-safe:animate-spin" /> : state === "stopped" ? <X className="size-4" /> : <Circle className="size-3" />}
    </span>
  );
}

const STATE_WORD: Record<TimelineState, string> = { done: "Done", current: "Now", stopped: "Stopped", todo: "Later" };

// One place for the money of a chat: what you could pay, where it stands, what happens next. Every figure is the server's.
export function PayScreen({ chatId }: { chatId: string }) {
  const project = useAsync(() => real.getProject(chatId), chatId);
  const p = project.data;
  const receipt = useAsync(() => (p?.payment ? real.getProjectPayment(chatId).catch(() => null) : Promise.resolve(null)), `${chatId}:${p?.status}:${p?.payment?.state ?? ""}`);
  const { busy, error, run } = useAction();
  const [cancelling, setCancelling] = useState(false);

  const back = (
    <Link href={`/c/${chatId}`} className="flex items-center gap-1.5 rounded-sm text-body text-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">
      <ArrowLeft aria-hidden className="size-4" />
      Back to chat
    </Link>
  );
  const q = p ? quoteFromProject(p) : null;
  const money = p ? projectMoney(p) : null;
  const phase = money ? phaseView(money.phase) : null;
  const pay = p?.payment ?? null;
  const ended = !!pay && ["declined", "expired", "voided"].includes(pay.state);
  const canPay = !!p && !!q && !ended && ["quoted", "awaiting_payment"].includes(p.status);
  const steps = p ? payTimeline(p, receipt.data ?? null) : [];

  return (
    <section aria-label="Payment" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={back} />
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto px-4 py-8 sm:px-8">
        <div className="flex h-fit w-full max-w-3xl flex-col gap-6">
          <header className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-col gap-1">
              <h1 className="text-title text-ink">Payment</h1>
              <p className="text-body text-muted">Train with proof, pay for results. PayPal sandbox: test money only.</p>
            </div>
            {phase && <StatusChip tone={phase.tone}>{phase.label}</StatusChip>}
          </header>

          {project.loading && !p ? (
            <div aria-busy="true" aria-label="Loading payment" className="flex flex-col gap-3">
              <Skeleton className="h-28" />
              <Skeleton className="h-64" />
            </div>
          ) : project.error || !p ? (
            <ErrorState message={project.error?.message ?? "This chat could not be loaded."} onRetry={project.retry} />
          ) : !q && !pay ? (
            <EmptyState title="No price yet" body="Your price appears here after the free test and your target. Go back to the chat to carry on." action={<LinkButton href={`/c/${chatId}`} variant="outline">Back to chat</LinkButton>} />
          ) : (
            <>
              {money && <MoneyTriplet summary={money} />}

              <Card aria-label="How the money moves" className="gap-4 p-5">
                <h2 className="text-section text-ink">How the money moves</h2>
                <ol className="flex flex-col">
                  {steps.map((s, i) => (
                    <li key={s.id} className="flex gap-3">
                      <div className="flex flex-col items-center">
                        <Dot state={s.state} />
                        {i < steps.length - 1 && <span aria-hidden className="my-1 w-px flex-1 bg-border" />}
                      </div>
                      <div className="flex min-w-0 flex-col gap-0.5 pb-5">
                        <p className="flex items-center gap-2 text-body font-semibold text-ink">
                          {s.label}
                          <span className="text-micro font-medium text-muted">{STATE_WORD[s.state]}</span>
                        </p>
                        <p className="text-body text-ink-2">{s.detail}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>

              {q && (
                <Card aria-label="Price details" className="gap-2 p-5">
                  <h2 className="text-section text-ink">Price details</h2>
                  <dl className="flex flex-col gap-1.5">
                    <Row label="Estimated total (estimate)" value={q.estimate} strong />
                    <Row label="Likely range (estimate)" value={q.range} />
                    <Row label="Compute, up to" value={q.computeMax} />
                    <Row label="Success fee, up to (only if verified)" value={q.feeMax} />
                    <Row label="Most you can be charged (cap)" value={q.cap} strong />
                  </dl>
                  <EstimateNote>Figures are estimates, except the cap, which is a limit. The server sets and checks every amount.</EstimateNote>
                </Card>
              )}

              {receipt.data && ["compute_captured", "fee_captured", "fee_skipped", "released"].includes(receipt.data.state) && (
                <Card variant="success" aria-label="Receipt" className="gap-2 p-5">
                  <h2 className="text-section text-ink">Receipt</h2>
                  <dl className="flex flex-col gap-1.5">
                    <Row label="Held" value={dollars(receipt.data.hold_cents)} />
                    <Row label="Compute charged" value={dollars(receipt.data.compute_captured_cents)} />
                    <Row label="Success fee charged" value={dollars(receipt.data.fee_captured_cents)} />
                    <Row label="Released back to you" value={dollars(receipt.data.released_cents)} />
                    <Row label="Total charged" value={dollars(receipt.data.total_charged_cents)} strong />
                  </dl>
                </Card>
              )}

              <div className="flex flex-wrap gap-2">
                {canPay && (
                  <Button
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        const url = await real.startPayment(chatId);
                        window.location.assign(url);
                      })
                    }
                  >
                    {busy ? "Opening PayPal…" : p.status === "awaiting_payment" ? "Open PayPal" : "Approve and pay"}
                  </Button>
                )}
                {ended && (
                  <Button
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        await real.createQuote(chatId);
                        await project.retry();
                      })
                    }
                  >
                    Get a new price
                  </Button>
                )}
                {canPay && pay && (
                  <Button variant="outline" disabled={busy} onClick={() => setCancelling(true)}>
                    Cancel
                  </Button>
                )}
                <LinkButton href="/account/billing" variant="outline">
                  Billing history
                </LinkButton>
              </div>
              <ErrorLine message={error} />
              {cancelling && (
                <ConfirmDialog
                  title="Cancel this run"
                  body="Cancel this run? Nothing has been charged. If PayPal placed a hold, the whole hold is released and you pay $0."
                  confirmLabel="Yes, cancel"
                  busyLabel="Cancelling…"
                  onCancel={() => setCancelling(false)}
                  onConfirm={async () => {
                    await real.cancelHold(chatId);
                    setCancelling(false);
                    await project.retry();
                  }}
                />
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
