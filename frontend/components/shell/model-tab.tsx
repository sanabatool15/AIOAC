"use client";
import Link from "next/link";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { outOf100 } from "@/lib/adapters";
import type { BBatch, BModel, BModelColumn, BModelVersion, BPredict } from "@/lib/api";
import { downloadModel, getModel, getModelVersions, predictBatch, predictOne, switchModelVersion } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { batchProblem, buildRecord, cellText, columnTitle, compareLine, fileSize, formatWhen, sklearnNote, toPrediction, toVersions, type PredictionView } from "@/lib/screens";
import { ErrorLine, useAction } from "./step-parts";

type Available = Extract<BModel, { available: true }>;

export function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// The Model tab: use the trained model (free, no payment). Everything comes from GET /model, GET /model/versions and the predict routes.
export function ModelTab({ projectId }: { projectId: string }) {
  const [tryId, setTryId] = useState<string | undefined>(undefined); // undefined = the version in use
  const [bump, setBump] = useState(0);
  const model = useAsync(() => getModel(projectId, tryId), `${projectId}-${tryId ?? "current"}-${bump}`);
  const vers = useAsync(() => getModelVersions(projectId).catch(() => [] as BModelVersion[]), `${projectId}-${bump}`);
  const { data, error, loading, retry } = model;
  if (loading && !data) return <Skeleton className="h-40" />;
  if (error || !data) return <ErrorState message={error?.message ?? "The model could not be loaded."} onRetry={retry} />;
  if (!data.available) {
    return (
      <Card aria-label="No model yet" className="gap-2 p-5">
        <h2 className="text-base font-semibold text-ink">No trained model yet</h2>
        <p className="text-body text-ink-2">
          A model is saved when a paid run finishes. Go to the project chat to get there.
        </p>
        <div>
          <Link href={`/c/${projectId}`} className="text-body font-semibold text-brand-ink underline">
            Open the project chat
          </Link>
        </div>
      </Card>
    );
  }
  const list = vers.data ?? [];
  return (
    <>
      {list.length > 0 && (
        <VersionsCard
          projectId={projectId}
          list={list}
          onUsed={() => {
            setTryId(undefined);
            setBump((n) => n + 1);
          }}
        />
      )}
      <Available projectId={projectId} model={data} list={list} tryId={tryId} onPick={setTryId} />
    </>
  );
}

// Every saved version of the model, newest first. "Use this version" is free and changes which one is in use.
function VersionsCard({ projectId, list, onUsed }: { projectId: string; list: BModelVersion[]; onUsed: () => void }) {
  const views = toVersions(list);
  const line = compareLine(list);
  const { busy, error, run } = useAction();
  const [busyId, setBusyId] = useState<string | null>(null);
  return (
    <Card aria-label="Versions" className="gap-3 p-5">
      <h2 className="text-base font-semibold text-ink">Versions</h2>
      <p className="text-body text-ink-2">
        Each paid run saves a new version. A newer version that scored worse does not replace a better one by itself. Switching is free.
      </p>
      {line && (
        <p data-testid="compare-line" className="text-body font-semibold text-ink">
          {line}
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {views.map((v) => (
          <li key={v.id} aria-label={v.title} className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-body font-semibold text-ink">
                {v.title} <span className="font-normal text-muted">· {v.when}</span>
              </p>
              <div className="flex items-center gap-2">
                {v.reached !== null && <Tag variant={v.reached ? "success" : "neutral"}>{v.reached ? "Target reached" : "Target not reached"}</Tag>}
                {v.inUse && <Tag variant="success">In use</Tag>}
              </div>
            </div>
            <p className="text-body text-ink-2">{v.result}</p>
            <div className="flex gap-2">
              {!v.inUse && (
                <Button
                  size="md"
                  disabled={busy}
                  onClick={() => {
                    setBusyId(v.id);
                    void run(async () => {
                      await switchModelVersion(projectId, v.id);
                      onUsed();
                    });
                  }}
                >
                  {busy && busyId === v.id ? "Switching…" : "Use this version"}
                </Button>
              )}
              <Button
                variant="outline"
                size="md"
                disabled={busy}
                onClick={() => {
                  setBusyId(v.id);
                  void run(async () => {
                    const f = await downloadModel(projectId, v.id);
                    saveFile(f.blob, f.filename);
                  });
                }}
              >
                Download
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <ErrorLine message={error} />
    </Card>
  );
}

function Available({
  projectId,
  model,
  list,
  tryId,
  onPick,
}: {
  projectId: string;
  model: Available;
  list: BModelVersion[];
  tryId: string | undefined;
  onPick: (id: string | undefined) => void;
}) {
  const current = list.find((v) => v.is_current);
  return (
    <>
      <Card variant="highlight" aria-label="Your model" className="gap-2 p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold text-ink">
            {model.version_no ? `Version ${model.version_no} of your model` : "Your trained model"}
          </h2>
          <Tag variant={model.usable ? "success" : "neutral"}>{model.usable ? "Ready to use" : "Cannot run here"}</Tag>
        </div>
        <p className="text-body text-ink-2">
          {modelSummary(model)}
        </p>
        <p className="text-micro text-muted">{model.is_estimate_note}</p>
        {list.length > 1 && (
          <Field label="Which version to try" htmlFor="try-version">
            <select
              id="try-version"
              value={tryId ?? current?.model_id ?? ""}
              onChange={(e) => onPick(e.target.value === current?.model_id ? undefined : e.target.value)}
              className="w-full rounded-lg border border-border bg-white px-3.5 py-2.5 text-body text-ink shadow-btn-neutral outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
            >
              {list.map((v) => (
                <option key={v.model_id} value={v.model_id}>
                  Version {v.version_no}
                  {v.is_current ? " (in use)" : ""}
                </option>
              ))}
            </select>
          </Field>
        )}
      </Card>
      {model.usable && model.task_type === "forecast" ? (
        <ForecastAhead key={`ahead-${model.model_id ?? "m"}`} projectId={projectId} model={model} modelId={tryId} />
      ) : model.usable ? (
        <>
          <OneRecord key={`one-${model.model_id ?? "m"}`} projectId={projectId} columns={model.columns} modelId={tryId} />
          <BatchCard key={`batch-${model.model_id ?? "m"}`} projectId={projectId} modelId={tryId} />
        </>
      ) : (
        <Card variant="warning" aria-label="Why it cannot run here" className="gap-2 p-5">
          <h2 className="text-base font-semibold text-ink">This model cannot run here</h2>
          <p className="text-body text-ink-2">{model.unusable_reason ?? "The saved file could not be opened on this server."}</p>
          <p className="text-body text-ink-2">You can still download it and open it yourself.</p>
        </Card>
      )}
      <DownloadCard projectId={projectId} model={model} modelId={tryId} />
    </>
  );
}

function ColumnTitle({ column }: { column: BModelColumn }) {
  const { main, raw } = columnTitle(column);
  return (
    <>
      <span className={raw ? "text-ink" : undefined}>{main}</span>
      {raw && <span className="ml-1.5 text-micro font-normal text-muted">{raw}</span>}
    </>
  );
}

export function OneRecord({ projectId, columns, modelId }: { projectId: string; columns: BModelColumn[]; modelId?: string }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [result, setResult] = useState<PredictionView | null>(null);
  const { busy, error, run, setError } = useAction();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const { record, error: problem } = buildRecord(columns, values);
    if (problem) {
      setError(problem);
      return;
    }
    void run(async () => {
      setResult(null);
      setResult(toPrediction(await predictOne(projectId, record, modelId)));
    });
  }

  return (
    <Card aria-label="Try it on one record" className="gap-3 p-5">
      <h2 className="text-base font-semibold text-ink">Try it on one record</h2>
      <p className="text-body text-ink-2">
        Fill in what you know. You can leave fields empty; the model fills them in with typical values.
      </p>
      <form onSubmit={submit} noValidate className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          {columns.map((c) => (
            <Field key={c.name} label={<ColumnTitle column={c} />} htmlFor={`f-${c.name}`}>
              {c.choices && c.choices.length > 0 ? (
                <select
                  id={`f-${c.name}`}
                  value={values[c.name] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [c.name]: e.target.value }))}
                  className="w-full rounded-lg border border-border bg-white px-3.5 py-2.5 text-body text-ink shadow-btn-neutral outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
                >
                  <option value="">(leave empty)</option>
                  {c.choices.map((ch) => (
                    <option key={ch} value={ch}>
                      {ch}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id={`f-${c.name}`}
                  type={c.kind === "number" ? "number" : "text"}
                  step={c.kind === "number" ? "any" : undefined}
                  placeholder={c.example === null ? "" : `e.g. ${c.example}`}
                  value={values[c.name] ?? ""}
                  onChange={(e) => setValues((v) => ({ ...v, [c.name]: e.target.value }))}
                />
              )}
            </Field>
          ))}
        </div>
        <div>
          <Button type="submit" size="md" disabled={busy}>
            {busy ? "Predicting…" : "Predict"}
          </Button>
        </div>
      </form>
      <ErrorLine message={error} />
      {result && (
        <div aria-label="Prediction" data-testid="prediction" className="flex flex-col gap-2 rounded-xl bg-surface p-4">
          <p className="text-micro font-semibold text-muted">The model&apos;s answer</p>
          <p className="text-title font-semibold text-ink">{result.answer}</p>
          {result.rows.length > 0 && (
            <ul className="flex flex-col gap-1 text-body text-ink-2">
              {result.rows.map((r) => (
                <li key={r.label}>
                  {r.label}: {r.text}
                </li>
              ))}
            </ul>
          )}
          {result.extra.map((line) => (
            <p key={line} className="text-body text-ink-2">
              {line}
            </p>
          ))}
          <p className="text-micro text-muted">This is {result.note}.</p>
        </div>
      )}
    </Card>
  );
}

export function BatchCard({ projectId, modelId }: { projectId: string; modelId?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState("");
  const [out, setOut] = useState<BBatch | null>(null);
  const { busy, error, run, setError } = useAction();

  async function pick(file: File | undefined) {
    if (!file) return;
    try {
      setText(await file.text());
      setError(null);
    } catch {
      setError("We could not read that file. Try pasting its text instead.");
    }
  }
  function go() {
    const problem = batchProblem(text);
    if (problem) {
      setError(problem);
      return;
    }
    void run(async () => {
      setOut(null);
      setOut(await predictBatch(projectId, text, modelId));
    });
  }

  return (
    <Card aria-label="Run it on a CSV" className="gap-3 p-5">
      <h2 className="text-base font-semibold text-ink">Run it on a CSV</h2>
      <p className="text-body text-ink-2">
        Up to 5,000 rows. Use the same column names as above. Other columns, like an id, are kept in the results.
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="md" onClick={() => input.current?.click()}>
          Pick a CSV file
        </Button>
        <input ref={input} type="file" accept=".csv,text/csv" aria-label="CSV file" hidden onChange={(e) => void pick(e.target.files?.[0])} />
        <span className="text-micro text-muted">or paste the text below</span>
      </div>
      <textarea
        aria-label="CSV text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        placeholder={"months_active,plan\n12,basic\n30,pro"}
        className="w-full rounded-lg border border-border bg-white px-3.5 py-2.5 font-mono text-micro text-ink shadow-btn-neutral outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
      />
      <div>
        <Button size="md" disabled={busy} onClick={go}>
          {busy ? "Predicting…" : "Predict for every row"}
        </Button>
      </div>
      <ErrorLine message={error} />
      {out && (
        <div data-testid="batch-result" className="flex flex-col gap-2">
          <p className="text-body text-ink">
            Predicted {out.rows.toLocaleString("en-US")} rows. Showing the first {out.preview.length}. Predictions are estimates, not promises.
          </p>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left text-micro">
              <thead className="bg-surface text-muted">
                <tr>
                  {out.columns.map((c) => (
                    <th key={c} className="px-3 py-2 font-semibold">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {out.preview.map((row, i) => (
                  <tr key={i} className="border-t border-border">
                    {out.columns.map((c) => (
                      <td key={c} className="px-3 py-1.5 text-ink">
                        {cellText(row[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <Button variant="outline" size="md" onClick={() => saveFile(new Blob([out.csv_text], { type: "text/csv" }), "predictions.csv")}>
              Download results (CSV)
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

function DownloadCard({ projectId, model, modelId }: { projectId: string; model: Available; modelId?: string }) {
  const { busy, error, run } = useAction();
  const [note, setNote] = useState<string | null>(null);
  return (
    <Card aria-label="Download the model" className="gap-2 p-5">
      <h2 className="text-base font-semibold text-ink">Download the model</h2>
      <p className="text-body text-ink-2">
        The saved model file ({fileSize(model.size_bytes)}). {sklearnNote(model.sklearn_version)}
      </p>
      <div>
        <Button
          variant="outline"
          size="md"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const f = await downloadModel(projectId, modelId);
              saveFile(f.blob, f.filename);
              setNote(`Downloaded ${f.filename}. ${sklearnNote(f.sklearn ?? model.sklearn_version)}`);
            })
          }
        >
          {busy ? "Downloading…" : "Download the model"}
        </Button>
      </div>
      <ErrorLine message={error} />
      {note && <p className="text-body text-ink-2">{note}</p>}
    </Card>
  );
}


// One plain sentence about the model, per kind of prediction. Only a yes/no or group model has an "out of 100 right".
function modelSummary(model: Available): string {
  const when = `Trained ${formatWhen(model.trained_at)}.`;
  switch (model.task_type) {
    case "forecast":
      return `Forecasts "${model.target}" ahead${model.period ? `, one ${model.period} at a time` : ""}. Its history ends ${model.last_date ?? "at the last date in your data"}. ${when}`;
    case "grouping":
      return `Puts records into groups of similar ones. There is no right answer to check, so we only report how steady the groups are. ${when}`;
    case "unusual":
      return `Spots records that look unlike the rest. There is no right answer to check, so we only report how steady the flags are. ${when}`;
    case "regression":
      return `Predicts the number "${model.target}". ${when}`;
    default:
      return `Predicts "${model.target}". ${when} Free test: about ${outOf100(model.accuracy)} right, a simple guess: ${outOf100(model.simple_guess_accuracy)}.`;
  }
}

// A forecast has no row to fill in: ask for how many periods ahead and show a dated list. Every number is an estimate.
function ForecastAhead({ projectId, model, modelId }: { projectId: string; model: Available; modelId?: string }) {
  const [periods, setPeriods] = useState(String(model.horizon ?? 6));
  const [out, setOut] = useState<BPredict | null>(null);
  const { busy, error, run, setError } = useAction();
  function submit(e: React.FormEvent) {
    e.preventDefault();
    const n = Math.round(Number(periods));
    if (!Number.isFinite(n) || n < 1 || n > 36) return setError("Choose between 1 and 36 periods ahead.");
    void run(async () => {
      setOut(null);
      setOut(await predictOne(projectId, { periods: n }, modelId));
    });
  }
  const values = Array.isArray(out?.prediction) ? (out?.prediction as number[]) : [];
  return (
    <Card aria-label="Forecast ahead" className="gap-3 p-5">
      <h2 className="text-base font-semibold text-ink">Forecast ahead</h2>
      <p className="text-body text-ink-2">How many {model.period ?? "period"}s ahead do you want to see (1 to 36)?</p>
      <form onSubmit={submit} noValidate className="flex items-end gap-3">
        <div className="w-32">
          <Field label="Periods ahead" htmlFor="periods-ahead">
            <Input id="periods-ahead" type="number" min={1} max={36} inputMode="numeric" value={periods} onChange={(e) => setPeriods(e.target.value)} />
          </Field>
        </div>
        <Button type="submit" size="md" disabled={busy}>
          {busy ? "Forecasting…" : "Forecast"}
        </Button>
      </form>
      <ErrorLine message={error} />
      {out && values.length > 0 && (
        <div aria-label="Prediction" data-testid="prediction" className="flex flex-col gap-2 rounded-xl bg-surface p-4">
          <ul className="flex flex-col gap-1 text-body text-ink-2">
            {values.map((v, i) => (
              <li key={i} className="flex justify-between gap-3">
                <span>{out.dates?.[i] ?? `Period ${i + 1}`}</span>
                <span className="font-medium text-ink tabular-nums">{v.toLocaleString("en-US", { maximumFractionDigits: 2 })}</span>
              </li>
            ))}
          </ul>
          {out.typical_error != null && (
            <p className="text-body text-ink-2">
              On periods it never saw, it was typically off by about {Math.round(out.typical_error).toLocaleString("en-US")} (an estimate).
            </p>
          )}
          <p className="text-micro text-muted">This is {out.note}.</p>
        </div>
      )}
    </Card>
  );
}
