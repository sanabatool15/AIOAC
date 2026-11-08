"use client";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { csvColumns } from "@/lib/adapters";
import * as real from "@/lib/api-real";
import { ErrorLine, Panel, useAction } from "./step-parts";

function guessTarget(cols: string[]): string {
  const hint = cols.find((c) => /^(target|label|class|churn|outcome|y)$/i.test(c));
  return hint ?? cols[cols.length - 1] ?? "";
}

// The secondary way to bring data: upload your own CSV, say which column holds the answer, then POST /data and /select.
// The click on "Use this data" is the user's approval of the choice (specs/api.md A0).
export function UploadPanel({ projectId, onChanged }: { projectId: string; onChanged: () => void | Promise<void> }) {
  const { busy, error, run, setError } = useAction();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; text: string; cols: string[] } | null>(null);
  const [target, setTarget] = useState("");
  const [candidate, setCandidate] = useState<string | null>(null);

  async function pick(f: File | undefined) {
    setError(null);
    setCandidate(null);
    if (!f) return;
    if (!/\.csv$/i.test(f.name)) return setError("Please choose a CSV file.");
    if (f.size > 20 * 1024 * 1024) return setError("That file is over 20 MB. Please use a smaller one.");
    const text = await f.text();
    const cols = csvColumns(text);
    if (cols.length < 2) return setError("We could not find column names in the first row of that file.");
    setFile({ name: f.name, text, cols });
    setTarget(guessTarget(cols));
  }

  return (
    <Panel title="Upload your own data" label="Upload your own data">
      <p className="text-body text-ink-2">
        A CSV is a table with a header row and one row per case. Then pick the column holding the answer.
      </p>
      <input
        ref={fileRef}
        type="file"
        accept=".csv,text/csv"
        aria-label="CSV file"
        className="text-body"
        onChange={(e) => void pick(e.target.files?.[0])}
      />
      {file && (
        <>
          <Field label="Which column should we predict?" htmlFor="target-col">
            <select
              id="target-col"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="w-full rounded-md border border-border bg-card px-3.5 py-2.5 text-body text-ink focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
            >
              {file.cols.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <Button
            
            disabled={busy || !target}
            onClick={() =>
              run(async () => {
                let id = candidate;
                if (!id) {
                  id = (await real.uploadCsv(projectId, file.name, file.text)).candidate_id;
                  setCandidate(id);
                }
                await real.selectDataset(projectId, id, target);
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
