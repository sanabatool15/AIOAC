"use client";
import { useState } from "react";
import { Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tag } from "@/components/ui/tag";
import { Field } from "@/components/ui/input";
import * as real from "@/lib/api-real";
import { checkLink, guessAnswerColumn } from "@/lib/dataset-link";
import { ErrorLine, useAction } from "./step-parts";

// Paste the page address of an open dataset (Hugging Face, UCI or OpenML). The server fetches it under the same size
// limits as a dataset the agent found. Choosing it is the user's click on "Use this data".
export function LinkPanel({ projectId, onChanged, onCancel }: { projectId: string; onChanged: () => void | Promise<void>; onCancel?: () => void }) {
  const { busy, error, run, setError } = useAction();
  const [url, setUrl] = useState("");
  const [found, setFound] = useState<{ id: string; rows: number; cols: string[]; suggested?: string } | null>(null);
  const [target, setTarget] = useState("");

  function fetchIt() {
    const c = checkLink(url);
    if (!c.ok) return setError(c.message);
    void run(async () => {
      const r = await real.addDatasetLink(projectId, c.url);
      setFound({ id: r.candidate_id, rows: r.rows, cols: r.columns, suggested: r.suggested_target });
      setTarget(guessAnswerColumn(r.columns, r.suggested_target));
    });
  }

  return (
    <section aria-label="Paste a link to an open dataset" className="flex flex-col gap-4">
      <Field label="Dataset link" htmlFor="dataset-link">
        <input
          id="dataset-link"
          type="url"
          inputMode="url"
          value={url}
          disabled={busy || !!found}
          placeholder="https://huggingface.co/datasets/owner/name"
          onChange={(e) => {
            setUrl(e.target.value);
            setError(null);
          }}
          className="w-full rounded-md border border-border bg-card px-3.5 py-2.5 text-body text-ink focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
        />
      </Field>
      {!found && (
        <Button disabled={busy || !url.trim()} onClick={fetchIt}>
          {busy ? "Getting the dataset…" : "Get this dataset"}
        </Button>
      )}
      {!found && (
        <p className="text-small text-muted">Works with Hugging Face, UCI and OpenML dataset pages.</p>
      )}
      {found && (
        <>
          <div className="flex items-center gap-3 rounded-lg border border-success-line bg-success-soft p-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-card text-success">
              <Database aria-hidden className="size-5" />
            </span>
            <div className="flex min-w-0 flex-1 flex-col">
              <span className="text-body font-medium text-ink">Dataset found</span>
              <span className="text-small text-ink-2">
                {found.rows.toLocaleString("en-US")} rows · {found.cols.length} columns
              </span>
            </div>
            <Tag variant="success">Found</Tag>
          </div>
          <Field label="Which column should we predict?" htmlFor="link-target-col">
            <select
              id="link-target-col"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full rounded-md border border-border bg-card px-3.5 py-2.5 text-body text-ink focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
            >
              {found.cols.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex justify-end gap-2">
            {onCancel && (
              <Button type="button" variant="outline" disabled={busy} onClick={onCancel}>
                Cancel
              </Button>
            )}
            <Button
              disabled={busy || !target}
              onClick={() =>
              void run(async () => {
                await real.selectDataset(projectId, found.id, target);
                await onChanged();
              })
            }
          >
            {busy ? "Saving your data…" : "Use this data"}
          </Button>
          </div>
        </>
      )}
      <ErrorLine message={error} />
    </section>
  );
}
