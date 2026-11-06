"use client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { quoteFromProject, toForecast } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { ForecastCard } from "@/components/shell/step-cards";
import { ErrorLine, Panel, Row, useAction } from "@/components/shell/step-parts";

interface StepProps {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// ---- 5. quote ----
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
        <Panel title="Your price">
          <p className="text-sm leading-5 text-ink-2">
            The pilot looks good enough to offer a run. I will work out one price for the full run.
          </p>
          <div>{requote}</div>
          <ErrorLine message={error} />
        </Panel>
      ) : (
        <Panel title="Your price (estimate)" variant="peach">
          <dl className="flex flex-col gap-1.5">
            <Row label="Estimated total" value={q.estimate} strong />
            <Row label="Likely range (estimate)" value={q.range} />
            <Row label="Most you can ever be charged (the cap)" value={q.cap} strong />
            <Row label="Compute, up to" value={q.computeMax} />
            <Row label="Success fee, up to (only if verified)" value={q.feeMax} />
          </dl>
          <p className="text-sm leading-5 text-ink-2">
            You pay compute either way. The success fee only if the target is verified on data the model
            never saw. PayPal holds the cap but charges nothing until the run is done; anything unused is
            released. This is PayPal sandbox test money only.
          </p>
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
              {busy ? "Opening PayPal…" : "Approve and hold with PayPal"}
            </Button>
            {requote}
          </div>
          <ErrorLine message={error} />
        </Panel>
      )}
    </>
  );
}

// ---- 6. pay (awaiting_payment) ----
export function PayStep({ project, onChanged }: StepProps) {
  const router = useRouter();
  const { busy, error, run } = useAction();
  const pay = project.payment;
  const dead = pay && ["declined", "expired", "voided"].includes(pay.state);
  const q = quoteFromProject(project);
  return (
    <Panel title="Waiting for your PayPal approval" variant="peach">
      {dead ? (
        <p className="text-sm leading-5 text-ink-2">
          That PayPal hold did not go through ({pay?.state}). Nothing was charged. Get a new price to
          try again.
        </p>
      ) : (
        <p className="text-sm leading-5 text-ink-2">
          PayPal will hold up to {q?.cap ?? "the cap"} and charge nothing yet. Approve it on PayPal, then
          come back here. If you already approved it, press &quot;Check my approval&quot;.
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
          </>
        )}
      </div>
      <ErrorLine message={error} />
    </Panel>
  );
}
