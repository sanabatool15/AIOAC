"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import * as real from "@/lib/api-real";
import { Panel } from "@/components/shell/step-parts";

const POLLS = 5;
const WAIT_MS = 2000;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type View =
  | { kind: "working"; text: string }
  | { kind: "stuck"; text: string; projectId?: string }
  | { kind: "declined"; projectId: string };

// PayPal sends the buyer back here. The page proves nothing: the SERVER confirms the hold (authorize),
// and only a confirmed hold lets us start the run (the backend refuses /train otherwise).
export function PayReturn() {
  const router = useRouter();
  const [view, setView] = useState<View>({ kind: "working", text: "Confirming your PayPal approval…" });
  const started = useRef(false);

  const go = useCallback(async () => {
    setView({ kind: "working", text: "Confirming your PayPal approval…" });
    try {
      const mem = await real.recoverPayment();
      if (!mem) {
        setView({ kind: "stuck", text: "We could not find a payment to confirm. Nothing was charged." });
        return;
      }
      // Reload safety: if the project is already past payment, just go to it.
      const p = await real.getProject(mem.projectId);
      if (["training", "done", "stopped", "failed", "voided"].includes(p.status)) {
        router.replace(`/c/${mem.projectId}`);
        return;
      }
      let state = "none";
      for (let i = 0; i < POLLS; i++) {
        const r = await real.authorizePayment(mem.paymentId);
        state = r.state;
        if (r.held) {
          setView({ kind: "working", text: "Hold confirmed. Starting your training run…" });
          try {
            await real.startTraining(mem.projectId);
          } catch (e) {
            if (!(e instanceof ApiError && e.status === 409)) throw e;
          }
          real.forgetPayment();
          router.replace(`/c/${mem.projectId}`);
          return;
        }
        if (state === "declined") {
          setView({ kind: "declined", projectId: mem.projectId });
          return;
        }
        setView({ kind: "working", text: "PayPal has not confirmed the hold yet. Checking again…" });
        await sleep(WAIT_MS);
      }
      setView({
        kind: "stuck",
        projectId: mem.projectId,
        text: "PayPal has not confirmed the hold yet. Nothing has been charged and no training has started. Try again in a moment.",
      });
    } catch (e) {
      setView({
        kind: "stuck",
        text: e instanceof Error ? e.message : "Something went wrong. Nothing was charged.",
      });
    }
  }, [router]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void go();
  }, [go]);

  return (
    <section aria-label="Payment" className="flex h-full min-w-0 flex-1 items-start justify-center overflow-y-auto bg-bg p-8">
      <div className="w-full max-w-[520px]">
        {view.kind === "working" && (
          <Panel title="Almost there" variant="peach">
            <p role="status" className="text-sm text-ink-2">
              {view.text}
            </p>
          </Panel>
        )}
        {view.kind === "stuck" && (
          <Panel title="We could not confirm the hold yet" variant="amber">
            <p role="alert" className="text-sm leading-5 text-ink-2">
              {view.text}
            </p>
            <div className="flex gap-2">
              <Button size="md" onClick={() => void go()}>
                Check again
              </Button>
              {view.projectId && (
                <Link href={`/c/${view.projectId}`} className="self-center text-sm font-semibold text-brand-ink underline">
                  Back to my project
                </Link>
              )}
            </div>
          </Panel>
        )}
        {view.kind === "declined" && (
          <Panel title="PayPal did not approve the hold" variant="red">
            <p className="text-sm leading-5 text-ink-2">Nothing was charged. You can go back and try again.</p>
            <Link href={`/c/${view.projectId}`} className="text-sm font-semibold text-brand-ink underline">
              Back to my project
            </Link>
          </Panel>
        )}
      </div>
    </section>
  );
}

export function PayCancel() {
  const { data: pid } = useAsync(async () => real.recallPayment()?.projectId ?? real.recallProject());
  return (
    <section aria-label="Payment cancelled" className="flex h-full min-w-0 flex-1 items-start justify-center overflow-y-auto bg-bg p-8">
      <div className="w-full max-w-[520px]">
        <Panel title="Nothing was held" variant="amber">
          <p className="text-sm leading-5 text-ink-2">
            You left PayPal without approving, so nothing was held and nothing was charged.
          </p>
          <Link
            href={pid ? `/c/${pid}` : "/"}
            className="text-sm font-semibold text-brand-ink underline"
          >
            {pid ? "Back to my price" : "Back to start"}
          </Link>
        </Panel>
      </div>
    </section>
  );
}
