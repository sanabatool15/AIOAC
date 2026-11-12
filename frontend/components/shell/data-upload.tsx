"use client";
import { useEffect, useRef, useState } from "react";
import { FileSpreadsheet, FileUp, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/input";
import { csvColumns } from "@/lib/adapters";
import * as real from "@/lib/api-real";
import { cn } from "@/lib/utils";
import { ErrorLine, useAction } from "./step-parts";

function guessTarget(cols: string[]): string {
  const hint = cols.find((c) => /^(target|label|class|churn|outcome|y)$/i.test(c));
  return hint ?? cols[cols.length - 1] ?? "";
}

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Upload your own CSV: drop it or choose it, say which column holds the answer, then POST /data and /select.
// The click on "Use this data" is the user's approval of the choice (specs/api.md A0).
export function UploadPanel({ projectId, onChanged, onCancel, initialFile, needsTarget = true }: { projectId: string; onChanged: () => void | Promise<void>; onCancel?: () => void; initialFile?: File | null; needsTarget?: boolean }) {
  const { busy, error, run, setError } = useAction();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<{ name: string; size: number; text: string; cols: string[] } | null>(null);
  const [target, setTarget] = useState("");
  const [candidate, setCandidate] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  async function pick(f: File | undefined) {
    setError(null);
    setCandidate(null);
    if (!f) return;
    if (!/\.csv$/i.test(f.name)) return setError("Please choose a CSV file.");
    if (f.size > 20 * 1024 * 1024) return setError("That file is over 20 MB. Please use a smaller one.");
    const text = await f.text();
    const cols = csvColumns(text);
    if (cols.length < 2) return setError("We could not find column names in the first row of that file.");
    setFile({ name: f.name, size: f.size, text, cols });
    setTarget(guessTarget(cols));
  }

  const first = useRef(initialFile);
  useEffect(() => {
    if (first.current) void pick(first.current);
    first.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function clear() {
    setFile(null);
    setCandidate(null);
    setError(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <section aria-label="Upload your own data" className="flex flex-col gap-4">
      <input ref={fileRef} type="file" accept=".csv,text/csv" aria-label="CSV file" className="sr-only" onChange={(e) => void pick(e.target.files?.[0])} />
      {!file ? (
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setOver(false);
            void pick(e.dataTransfer.files?.[0]);
          }}
          className={cn(
            "flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
            over ? "border-brand bg-brand-tint" : "border-border bg-surface hover:border-brand",
          )}
        >
          <span className="flex size-10 items-center justify-center rounded-full bg-card text-brand shadow-card">
            <FileUp aria-hidden className="size-5" />
          </span>
          <span className="text-body font-medium text-ink">Drag and drop your CSV here</span>
          <span className="text-small text-muted">CSV file, up to 20 MB</span>
          <span className="mt-1 rounded-md border border-border bg-card px-3 py-1.5 text-body font-medium text-ink shadow-card">Browse files</span>
        </button>
      ) : (
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-brand-tint text-brand">
            <FileSpreadsheet aria-hidden className="size-5" />
          </span>
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-body font-medium text-ink">{file.name}</span>
            <span className="text-small text-muted">
              {sizeLabel(file.size)} · {file.cols.length} columns
            </span>
          </div>
          <Button type="button" variant="ghost" size="icon" aria-label="Remove file" disabled={busy} onClick={clear}>
            <X aria-hidden />
          </Button>
        </div>
      )}
      {file && (
        <>
          {needsTarget ? (
          <Field label="Which column should we predict?" htmlFor="target-col" hint="The column that holds the answer you want.">
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
          ) : (
            <p className="text-body text-ink-2">No answer column is needed: we look at all the columns together.</p>
          )}
          <div className="flex justify-end gap-2">
            {onCancel && (
              <Button type="button" variant="outline" disabled={busy} onClick={onCancel}>
                Cancel
              </Button>
            )}
            <Button
              disabled={busy || (needsTarget && !target)}
              onClick={() =>
                run(async () => {
                  let id = candidate;
                  if (!id) {
                    id = (await real.uploadCsv(projectId, file.name, file.text)).candidate_id;
                    setCandidate(id);
                  }
                  await real.selectDataset(projectId, id, needsTarget ? target : undefined);
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
