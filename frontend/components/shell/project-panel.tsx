"use client";
import { useState } from "react";
import { Database, FileSpreadsheet, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ProgressBar } from "@/components/ui/progress-bar";
import { EmptyState } from "@/components/ui/state";
import { Tabs } from "@/components/ui/tabs";
import { toBaseline, toForecast } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import { JourneyCard } from "./journey-card";
import { ModelPanel } from "./model-panel";
import { AddDataDialog, type AddDataKind } from "./data-dialog";
import { Row } from "./step-parts";

const TABS = [
  { id: "progress", label: "Progress" },
  { id: "files", label: "Files and links" },
];
const MODEL_TAB = { id: "model", label: "Test your model" };

// Free test result against the target the person chose. Both come from the server; nothing is guessed.
function TargetCard({ project }: { project: BProject }) {
  const base = toBaseline(project)?.right ?? null;
  const target = toForecast(project.forecast)?.target ?? null;
  if (base === null || target === null) return null;
  return (
    <Card aria-label="Target to verify" className="gap-3 p-4">
      <h2 className="text-section text-ink">Target to verify</h2>
      <div className="flex flex-col gap-1.5">
        <Row label="Free test result" value={`${base} out of 100`} />
        <ProgressBar value={base} label={`Free test result: ${base} out of 100`} size="sm" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Row label="Your target" value={`${target} out of 100`} strong />
        <ProgressBar value={target} label={`Your target: ${target} out of 100`} size="sm" />
      </div>
      <p className="text-micro text-muted">You are charged only if the independent test reaches your target.</p>
    </Card>
  );
}

// The right pane, as in the design: Progress (the current step, then the target) and Files and links (the data the
// chat is built on, with a button to bring more). There is no live view: nothing in the product shows one.
export function ProjectPanel({
  project,
  index,
  showTarget,
  onChanged,
  children,
}: {
  project: BProject;
  index: number;
  showTarget: boolean;
  onChanged: () => void | Promise<void>;
  children: React.ReactNode;
}) {
  const [tab, setTab] = useState("progress");
  const [adding, setAdding] = useState<AddDataKind | null>(null);
  const d = project.dataset;
  return (
    <>
      <Tabs
        label="Chat panel"
        tabs={project.run ? [...TABS, MODEL_TAB] : TABS}
        value={tab}
        onValueChange={setTab}
        panels={{
          progress: (
            <div className="flex flex-col gap-4">
              <JourneyCard project={project} index={index} />
              {children}
              {showTarget && <TargetCard project={project} />}
            </div>
          ),
          model: <ModelPanel projectId={project.id} />,
          files: d ? (
            <Card aria-label="Your data" className="gap-3 p-4">
              <h2 className="text-section text-ink">Your data</h2>
              <ul className="flex flex-col gap-2">
                <li className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-brand-tint text-brand">
                    <FileSpreadsheet aria-hidden className="size-5" />
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-body font-medium text-ink">{d.source}</span>
                    <span className="text-small text-muted">
                      {d.rows.toLocaleString("en-US")} rows · {d.columns} columns · predicting &quot;{d.target}&quot;
                    </span>
                  </div>
                </li>
              </ul>
            </Card>
          ) : (
            <EmptyState
              icon={Database}
              title="No data yet"
              body="Add a file or a link to an open dataset."
              action={
                <Button type="button" onClick={() => setAdding("upload")}>
                  <Plus aria-hidden />
                  Add data
                </Button>
              }
            />
          ),
        }}
      />
      <AddDataDialog projectId={project.id} kind={adding} onClose={() => setAdding(null)} onChanged={onChanged} />
    </>
  );
}
