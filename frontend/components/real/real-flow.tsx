"use client";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { ApiError, type BProject } from "@/lib/api";
import { getProject, rememberProject } from "@/lib/api-real";
import { isSettling, screenFor, stepIndex } from "@/lib/status";
import { DescribeStep } from "./chat";
import { Stepper } from "./parts";
import {
  BaselineStep,
  History,
  IneligibleStep,
  PayStep,
  QuoteStep,
  ReadinessStep,
  TargetForm,
} from "./steps";
import { PaidStep, ResultStep, StoppedStep, TrainingStep, UnknownStep, VoidedStep } from "./steps-run";

// Demo path in real mode: ONE screen per project status (lib/status.ts), loaded from the server on every visit,
// so a reload at any step shows the right screen.
export function RealFlow({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<BProject | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);

  const load = useCallback(async () => {
    try {
      const p = await getProject(projectId);
      setProject(p);
      setError(null);
      rememberProject(projectId);
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Could not load this project."));
    }
  }, [projectId]);

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
  }, [load]);

  // While a run or a release is in motion, keep the page in step with the server.
  const settling = isSettling(project?.status);
  useEffect(() => {
    if (!settling) return;
    const id = setInterval(() => void load(), 3000);
    return () => clearInterval(id);
  }, [settling, load]);

  if (!project && !error) {
    return (
      <div className="flex min-w-0 flex-1 flex-col gap-4 p-8" aria-busy="true" aria-label="Loading project">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full max-w-[640px]" />
      </div>
    );
  }
  if (!project) {
    return (
      <div className="flex min-w-0 flex-1 items-center justify-center">
        <ErrorState message={error?.message ?? "Could not load this project."} onRetry={() => void load()} />
      </div>
    );
  }

  const screen = screenFor(project);
  const props = { project, onChanged: load };
  const showHistory = !["data", "unknown"].includes(screen);

  return (
    <section aria-label="Project" className="flex h-full min-w-0 flex-1 flex-col overflow-y-auto bg-bg">
      <div className="mx-auto flex w-full max-w-[680px] flex-col gap-4 px-4 py-8">
        <header className="flex flex-col gap-2">
          <h1 className="text-xl font-semibold leading-snug text-ink">{project.goal}</h1>
          <Stepper index={stepIndex(screen)} />
        </header>
        {error && (
          <p role="alert" className="flex items-center gap-3 text-sm text-danger">
            {error.message}
            <Button variant="outline" onClick={() => void load()}>
              Try again
            </Button>
          </p>
        )}
        {showHistory && <History project={project} />}
        {screen === "data" && <DescribeStep {...props} />}
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
      </div>
    </section>
  );
}
