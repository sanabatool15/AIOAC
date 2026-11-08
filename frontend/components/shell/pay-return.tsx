"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatusChip } from "@/components/ui/status-chip";
import { useAsync } from "@/lib/hooks";
import * as real from "@/lib/api-real";
import { confirmReturn, type ReturnOutcome } from "@/lib/pay-flow";

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function Shell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section aria-label={label} className="flex h-full min-w-0 flex-1 items-start justify-center overflow-y-auto bg-bg p-8">
      <div className="flex w-full max-w-form flex-col gap-4">
        <div className="flex items-center gap-3">
          <span aria-hidden className="flex size-7 items-center justify-center rounded-lg bg-brand text-sm font-semibold text-on-brand">
            A
          </span>
          <p className="text-section text-ink">AIOAC</p>
        </div>
        {children}
      </div>
    </section>
  );
}

// PayPal sends the buyer back here. The page proves nothing: the SERVER confirms the hold (authorize), and only a
// confirmed hold lets us start the run (the backend refuses /train otherwise).
export function PayReturn() {
  const router = useRouter();
  const [status, setStatus] = useState("Confirming your PayPal approval…");
  const [outcome, setOutcome] = useState<ReturnOutcome | null>(null);
  const started = useRef(false);

  const go = useCallback(async () => {
    setOutcome(null);
    setStatus("Confirming your PayPal approval…");
    const o = await confirmReturn(
      {
        recover: real.recoverPayment,
        getProjectStatus: async (id) => (await real.getProject(id)).status,
        authorize: real.authorizePayment,
        startTraining: real.startTraining,
        forget: real.forgetPayment,
        sleep,
      },
      setStatus,
    );
    if (o.kind === "go") router.replace(`/c/${o.projectId}`);
    else setOutcome(o);
  }, [router]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void go();
  }, [go]);

  return (
    <Shell label="Payment">
      {!outcome && (
        <Card variant="highlight" aria-label="Almost there" className="gap-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-section text-ink">Almost there</h2>
            <StatusChip tone="info">Waiting for PayPal</StatusChip>
          </div>
          <p role="status" className="text-sm text-ink-2">
            {status}
          </p>
          <p className="text-small text-muted">PayPal sandbox: test money only. Confirming a hold charges nothing.</p>
        </Card>
      )}
      {outcome?.kind === "stuck" && (
        <Card variant="warning" aria-label="We could not confirm the hold yet" className="gap-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-section text-ink">We could not confirm the hold yet</h2>
            <StatusChip tone="warning">Not confirmed</StatusChip>
          </div>
          <p role="alert" className="text-sm leading-5 text-ink-2">
            {outcome.text}
          </p>
          <div className="flex gap-3">
            <Button onClick={() => void go()}>
              Check again
            </Button>
            {outcome.projectId && (
              <LinkButton href={`/c/${outcome.projectId}`} variant="outline">
                Back to my project
              </LinkButton>
            )}
          </div>
        </Card>
      )}
      {outcome?.kind === "declined" && (
        <Card variant="danger" aria-label="PayPal did not approve the hold" className="gap-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-section text-ink">PayPal did not approve the hold</h2>
            <StatusChip tone="danger">Declined</StatusChip>
          </div>
          <p className="text-sm leading-5 text-ink-2">Nothing was held and nothing was charged. You can go back and try again.</p>
          <div>
            <LinkButton href={`/c/${outcome.projectId}`} variant="outline">
              Back to my project
            </LinkButton>
          </div>
        </Card>
      )}
    </Shell>
  );
}

export function PayCancel() {
  const { data: pid } = useAsync(async () => real.recallPayment()?.projectId ?? real.recallProject());
  return (
    <Shell label="Payment cancelled">
      <Card variant="warning" aria-label="Nothing was held" className="gap-3 p-5">
        <h2 className="text-section text-ink">Nothing was held</h2>
        <p className="text-sm leading-5 text-ink-2">
          You left PayPal without approving, so nothing was held and nothing was charged.
        </p>
        <div>
          <LinkButton href={pid ? `/c/${pid}` : "/"} variant="outline">
            {pid ? "Back to my price" : "Back to start"}
          </LinkButton>
        </div>
      </Card>
    </Shell>
  );
}
