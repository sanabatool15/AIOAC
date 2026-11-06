"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useAsync } from "@/lib/hooks";
import * as real from "@/lib/api-real";
import { confirmReturn, type ReturnOutcome } from "@/lib/pay-flow";

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function Shell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section aria-label={label} className="flex h-full min-w-0 flex-1 items-start justify-center overflow-y-auto bg-bg p-8">
      <div className="flex w-full max-w-[520px] flex-col gap-4">
        <div className="flex items-center gap-3">
          <div aria-hidden className="size-6 shrink-0 rounded-xl bg-brand-gradient shadow-glow" />
          <p className="text-sm font-semibold text-ink">AIOAC</p>
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
        <Card variant="peach" aria-label="Almost there" className="gap-3 p-5 shadow-card-tight">
          <h2 className="text-base font-semibold text-ink">Almost there</h2>
          <p role="status" className="text-sm text-ink-2">
            {status}
          </p>
          <p className="text-xs text-muted">PayPal sandbox: test money only. Nothing is charged by this step.</p>
        </Card>
      )}
      {outcome?.kind === "stuck" && (
        <Card variant="amber" aria-label="We could not confirm the hold yet" className="gap-3 p-5 shadow-card-tight">
          <h2 className="text-base font-semibold text-ink">We could not confirm the hold yet</h2>
          <p role="alert" className="text-sm leading-5 text-ink-2">
            {outcome.text}
          </p>
          <div className="flex gap-3">
            <Button size="md" onClick={() => void go()}>
              Check again
            </Button>
            {outcome.projectId && (
              <Link href={`/c/${outcome.projectId}`} className="self-center text-sm font-semibold text-brand-ink underline">
                Back to my project
              </Link>
            )}
          </div>
        </Card>
      )}
      {outcome?.kind === "declined" && (
        <Card variant="red" aria-label="PayPal did not approve the hold" className="gap-3 p-5 shadow-card-tight">
          <h2 className="text-base font-semibold text-ink">PayPal did not approve the hold</h2>
          <p className="text-sm leading-5 text-ink-2">Nothing was charged. You can go back and try again.</p>
          <Link href={`/c/${outcome.projectId}`} className="text-sm font-semibold text-brand-ink underline">
            Back to my project
          </Link>
        </Card>
      )}
    </Shell>
  );
}

export function PayCancel() {
  const { data: pid } = useAsync(async () => real.recallPayment()?.projectId ?? real.recallProject());
  return (
    <Shell label="Payment cancelled">
      <Card variant="amber" aria-label="Nothing was held" className="gap-3 p-5 shadow-card-tight">
        <h2 className="text-base font-semibold text-ink">Nothing was held</h2>
        <p className="text-sm leading-5 text-ink-2">
          You left PayPal without approving, so nothing was held and nothing was charged.
        </p>
        <Link href={pid ? `/c/${pid}` : "/"} className="text-sm font-semibold text-brand-ink underline">
          {pid ? "Back to my price" : "Back to start"}
        </Link>
      </Card>
    </Shell>
  );
}
