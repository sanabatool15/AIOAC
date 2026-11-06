"use client";
import type { BProject } from "@/lib/api";
import type { DemoScreen } from "@/lib/status";
import { PayStep, QuoteStep } from "./quote-step";
import { ResultStep, StoppedStep, UnknownStep, VoidedStep } from "./result-step";
import { PaidStep, TrainingStep } from "./training-step";
import { FreeTestAction, ReadinessAction, TargetAction } from "./step-actions";
import { DatasetCard, EligibilityCard, History, ReadinessCard } from "./step-cards";

// What the project page shows under the chat for the current status.
export function StepArea({ screen, project, onChanged }: { screen: DemoScreen; project: BProject; onChanged: () => void | Promise<void> }) {
  const props = { project, onChanged };
  switch (screen) {
    case "readiness":
      return (
        <>
          <DatasetCard project={project} />
          <ReadinessAction {...props} />
        </>
      );
    case "baseline":
      return (
        <>
          <DatasetCard project={project} />
          <ReadinessCard project={project} />
          <FreeTestAction {...props} />
        </>
      );
    case "target":
      return (
        <>
          <History project={project} />
          <TargetAction {...props} />
        </>
      );
    case "ineligible":
      return (
        <>
          <History project={project} />
          <EligibilityCard {...props} />
          <TargetAction
            {...props}
            initial={project.forecast?.suggested_target ? Math.round(project.forecast.suggested_target * 100) : null}
            intro="Or choose a lower target of your own. Another pilot is free."
          />
        </>
      );
    case "data":
      return null;
    default:
      return (
        <>
          <History project={project} />
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
}
