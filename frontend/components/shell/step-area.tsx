"use client";
import type { BProject } from "@/lib/api";
import type { DemoScreen } from "@/lib/status";
import { History, IneligibleStep, PayStep, QuoteStep, ReadinessStep, BaselineStep, TargetForm } from "@/components/real/steps";
import { PaidStep, ResultStep, StoppedStep, TrainingStep, UnknownStep, VoidedStep } from "@/components/real/steps-run";

// What the project page shows above the chat for the current status. Steps 6 to 9 of the plan replace these pieces one by one.
export function StepArea({ screen, project, onChanged }: { screen: DemoScreen; project: BProject; onChanged: () => void | Promise<void> }) {
  const props = { project, onChanged };
  return (
    <>
      {!["data", "unknown"].includes(screen) && <History project={project} />}
      {screen === "readiness" && <ReadinessStep {...props} />}
      {screen === "baseline" && <BaselineStep {...props} />}
      {screen === "target" && <TargetForm {...props} />}
      {screen === "ineligible" && <IneligibleStep {...props} />}
      {screen === "quote" && <QuoteStep {...props} />}
      {screen === "pay" && <PayStep {...props} />}
      {screen === "paid" && <PaidStep {...props} />}
      {screen === "training" && <TrainingStep {...props} />}
      {screen === "result" && <ResultStep {...props} />}
      {screen === "stopped" && <StoppedStep {...props} />}
      {screen === "voided" && <VoidedStep {...props} />}
      {screen === "unknown" && <UnknownStep {...props} />}
    </>
  );
}
