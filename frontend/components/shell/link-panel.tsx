"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import * as real from "@/lib/api-real";
import { checkLink, guessAnswerColumn } from "@/lib/dataset-link";
import { ErrorLine, Panel, useAction } from "./step-parts";

// Paste the page address of an open dataset (Hugging Face, UCI or OpenML). The server fetches it under the same size
// limits as a dataset the agent found. Choosing it is the user's click on "Use this data".
export function LinkPanel({ projectId, onChanged }: { projectId: string; onChanged: () => void | Promise<void> }) {
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
    <Panel title="Paste a link to an open dataset" label="Paste a link to an open dataset">
      <p className="text-sm leading-5 text-ink-2">
        We accept dataset pages on Hugging Face, UCI and OpenML. Other web addresses are not used.
      </p>
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
          className="w-full rounded-lg border border-border bg-white px-3 py-2.5 text-sm text-ink"
        />
      </Field>
      {!found && (
        <Button size="md" disabled={busy || !url.trim()} onClick={fetchIt}>
          {busy ? "Getting the dataset…" : "Get this dataset"}
        </Button>
      )}
      {found && (
        <>
          <p className="text-sm text-ink-2">Found a table with {found.rows.toLocaleString()} rows.</p>
          <Field label="Which column should we predict?" htmlFor="link-target-col">
            <select
              id="link-target-col"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full rounded-lg border border-border bg-white px-3 py-2.5 text-sm text-ink"
            >
              {found.cols.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <Button
            size="md"
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
        </>
      )}
      <ErrorLine message={error} />
    </Panel>
  );
}
