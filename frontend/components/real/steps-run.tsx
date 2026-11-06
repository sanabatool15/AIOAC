"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { toReceipt, toTraining, type ReceiptView } from "@/lib/adapters";
import { type BProject, type BReceipt, type BTraining } from "@/lib/api";
import * as real from "@/lib/api-real";
import { ErrorLine, Panel, Row, useAction } from "@/components/shell/step-parts";
import { TargetAction } from "@/components/shell/step-actions";

interface StepProps {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

const FINAL_STATES = ["released", "voided", "expired", "declined"];

// ---- receipt ----
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

export function Receipt({ r, note }: { r: ReceiptView; note?: string }) {
  return (
    <Panel title="Receipt" variant="mint">
      <dl className="flex flex-col gap-1.5">
        <Row label="PayPal hold (the cap)" value={r.held} />
        <Row label="Compute charged" value={r.compute} />
        <Row label="Success fee charged" value={r.fee} />
        <Row label="Released back to you" value={r.released} />
        <Row label="Total charged" value={r.total} strong />
      </dl>
      {note && <p className="text-sm leading-5 text-ink-2">{note}</p>}
    </Panel>
  );
}

function FinishingNote({ project, receipt, refresh, onChanged }: {
  project: BProject;
  receipt: BReceipt | null;
  refresh: () => void;
  onChanged: () => void | Promise<void>;
}) {
  const { busy, error, run } = useAction();
  if (!receipt || FINAL_STATES.includes(receipt.state)) return null;
  return (
    <Panel title="Finishing your payment" variant="amber">
      <p className="text-sm leading-5 text-ink-2">
        The run is over but the last PayPal step has not finished yet. It is safe to check again.
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
          {busy ? "Checking…" : "Check again"}
        </Button>
      </div>
      <ErrorLine message={error} />
    </Panel>
  );
}

// ---- result (done) ----
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
  const v = toTraining(t);
  const r = toReceipt(receipt);
  const passed = v?.passed ?? null;
  return (
    <>
      {passed === true ? (
        <Panel title="Target reached" variant="green">
          <p className="text-sm leading-5 text-ink-2">
            Checked once on data the model never saw: about{" "}
            <strong>{v?.verified?.value} out of 100</strong> right, against your target of{" "}
            {v?.verified?.target} out of 100.
          </p>
        </Panel>
      ) : passed === false ? (
        <Panel title="Target not reached" variant="amber">
          <p className="text-sm leading-5 text-ink-2">
            Checked once on data the model never saw: about{" "}
            <strong>{v?.verified?.value} out of 100</strong> right, below your target of{" "}
            {v?.verified?.target} out of 100. You paid for compute only. There was no success fee. We
            kept the best model.
          </p>
        </Panel>
      ) : (
        <Panel title="Run finished">
          <p className="text-sm text-ink-2">The run is finished. Details are in the receipt below.</p>
        </Panel>
      )}
      {r && (
        <Receipt
          r={r}
          note={
            passed === true
              ? "You paid compute plus the success fee, because the result was verified. The rest of the hold was released."
              : "You pay compute either way. The success fee is charged only if the result is verified."
          }
        />
      )}
      <FinishingNote project={project} receipt={receipt} refresh={refresh} onChanged={onChanged} />
      {passed === false && (
        <TargetAction
          project={project}
          onChanged={onChanged}
          initial={v?.verified?.value ?? null}
          intro="Want to try again? A new free pilot with another target costs nothing. A new run needs a new PayPal hold."
        />
      )}
    </>
  );
}

// ---- stopped by the user ----
export function StoppedStep({ project, onChanged }: StepProps) {
  const { receipt, refresh } = useReceipt(project);
  const r = toReceipt(receipt);
  return (
    <>
      <Panel title="You stopped the run" variant="amber">
        <p className="text-sm leading-5 text-ink-2">
          You pay for the compute used so far. There is no success fee, and the rest of the PayPal hold
          is released.
        </p>
      </Panel>
      {r && <Receipt r={r} />}
      <FinishingNote project={project} receipt={receipt} refresh={refresh} onChanged={onChanged} />
    </>
  );
}

// ---- voided or failed: our failure or a cancel ----
export function VoidedStep({ project }: StepProps) {
  const { receipt } = useReceipt(project);
  const r = toReceipt(receipt);
  const failing = project.status === "failed";
  return (
    <>
      <Panel title={failing ? "Something went wrong on our side" : "Nothing was charged"} variant="red">
        <p className="text-sm leading-5 text-ink-2">
          {failing
            ? "We are releasing your PayPal hold now. You pay $0."
            : "This run did not go ahead. The whole PayPal hold was released, so you pay $0."}
        </p>
        <div>
          <Link href="/" className="text-sm font-semibold text-brand-ink underline">
            Start a new project
          </Link>
        </div>
      </Panel>
      {r && <Receipt r={r} />}
    </>
  );
}

export function UnknownStep({ project }: StepProps) {
  return (
    <Panel title="We are not sure what to show here">
      <p className="text-sm leading-5 text-ink-2">
        This project is in a state this page does not know ({project.status}). Nothing has been charged
        by this page.
      </p>
      <Link href="/" className="text-sm font-semibold text-brand-ink underline">
        Back to start
      </Link>
    </Panel>
  );
}
