"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { toFix, type FixView } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import * as real from "@/lib/api-real";
import { ErrorLine, Row, useAction } from "./step-parts";

interface Props {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// "Try a fix": a free look at what one safe change to the data would do, then the user's OK. Nothing is charged and
// nothing is promised: the pilot is run again afterwards to see whether the estimate moved.
export function FixPanel({ project, onChanged }: Props) {
  const { busy, error, run } = useAction();
  const [fix, setFix] = useState<FixView | null>(null);

  if (!fix) {
    return (
      <div className="flex flex-col gap-1.5">
        <div>
          <Button
            variant="outline"
            size="md"
            disabled={busy}
            onClick={() =>
              run(async () => {
                setFix(toFix(await real.proposeFix(project.id)));
              })
            }
          >
            {busy ? "Looking at your data…" : "Try a fix (free)"}
          </Button>
        </div>
        <p className="text-xs text-muted">We look for repeated rows and mostly empty columns. Nothing changes until you say yes.</p>
        <ErrorLine message={error} />
      </div>
    );
  }

  if (!fix.available) {
    return (
      <div role="status" aria-label="No fix available" className="flex flex-col gap-2 rounded-lg border border-border bg-white p-3">
        <p className="text-sm leading-5 text-ink-2">{fix.message}</p>
        <div>
          <Button variant="outline" size="md" onClick={() => setFix(null)}>
            Close
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div role="group" aria-label="Confirm the data fix" data-testid="fix-confirm" className="flex flex-col gap-2.5 rounded-lg border border-border bg-white p-3">
      <h3 className="text-sm font-semibold text-ink">Change your data?</h3>
      <p className="text-sm leading-5 text-ink-2">{fix.message}</p>
      <dl className="flex flex-col gap-1.5">
        <Row label="Rows" value={fix.rows} />
        <Row label="Columns" value={fix.columns} />
        {fix.columnsDropped.length > 0 && <Row label="Columns removed" value={fix.columnsDropped.join(", ")} />}
      </dl>
      <ul className="flex flex-col gap-1 text-xs leading-4 text-muted">
        {fix.steps.map((s, i) => (
          <li key={i}>
            {s.what}. {s.why}
          </li>
        ))}
      </ul>
      <p className="text-xs leading-4 text-muted">
        Your original data stays saved, and the rows we keep aside for the final check do not change. {fix.note}
      </p>
      <p className="text-xs text-muted">
        {fix.fixesLeft === 1 ? "This is the last free fix we try on this data." : `${fix.fixesLeft} free fixes left on this data.`}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          size="md"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await real.applyFix(project.id, fix.versionId);
              setFix(null);
              await onChanged();
            })
          }
        >
          {busy ? "Changing your data…" : "Yes, change my data"}
        </Button>
        <Button variant="outline" size="md" disabled={busy} onClick={() => setFix(null)}>
          No thanks
        </Button>
      </div>
      <ErrorLine message={error} />
    </div>
  );
}
