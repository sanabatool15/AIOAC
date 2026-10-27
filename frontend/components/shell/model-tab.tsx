"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { predictBatch } from "@/lib/mock-api";
import type { BatchResult, ResultRun } from "@/lib/types";
import { cn } from "@/lib/utils";

const cardClass =
  "flex w-full flex-col gap-2.5 overflow-clip rounded-xl border border-border bg-white p-4 shadow-card-tight";

// Screen 30: three ways to use the verified model (download, API, batch file).
export function ModelTab({ run }: { run: ResultRun }) {
  const toast = useToast();
  const m = run.model;
  return (
    <>
      <section className={cardClass} aria-label="Download">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold leading-[normal] text-ink">
            {m.name}
          </h3>
          <Tag variant="brand">{m.badge}</Tag>
        </div>
        <p className="text-sm leading-[normal] text-muted">{m.summary}</p>
        <div className="flex gap-2">
          <Button
            size="md"
            disabled={!run.canDownloadModel}
            onClick={() =>
              toast(
                "Model download (.pkl) is mocked. The real file comes from the backend.",
              )
            }
          >
            Download (.pkl)
          </Button>
          <Button
            variant="outline"
            size="md"
            disabled={!run.canDownloadModel}
            onClick={() =>
              toast(
                "Model download (ONNX) is mocked. The real file comes from the backend.",
              )
            }
          >
            Download (ONNX)
          </Button>
        </div>
      </section>

      <section className={cardClass} aria-label="API">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold leading-[normal] text-ink">
            Call it from your app
          </h3>
          <Tag>{m.keyOn ? "API KEY ON" : "API KEY OFF"}</Tag>
        </div>
        <pre className="flex w-full flex-col gap-1 overflow-clip rounded-[10px] bg-code p-3.5 font-sans text-xs leading-[17px] font-normal whitespace-pre-wrap text-white">
          {m.apiLines.map((l) => (
            <code key={l} className="block font-sans break-all">
              {l}
            </code>
          ))}
        </pre>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="md"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(m.apiLines.join("\n"));
                toast("Snippet copied. Replace YOUR_KEY with your key.");
              } catch {
                toast(
                  "Could not copy. Select the snippet and copy it.",
                  "error",
                );
              }
            }}
          >
            Copy snippet
          </Button>
          <Link
            href="/settings/keys"
            className={cn(buttonVariants({ variant: "outline", size: "md" }))}
          >
            Manage key
          </Link>
        </div>
        <p className="text-sm leading-[normal] text-muted">{m.usage}</p>
      </section>

      <BatchCard />
    </>
  );
}

function BatchCard() {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<BatchResult | null>(null);
  const toast = useToast();

  async function run(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      setDone(await predictBatch(file));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Batch prediction failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={cn(cardClass, "gap-2")} aria-label="Batch">
      <h3 className="text-sm font-semibold leading-[normal] text-ink">
        Predict for a file
      </h3>
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          void run(e.dataTransfer.files[0]);
        }}
        className={cn(
          "flex w-full flex-col items-center rounded-[10px] border border-dashed border-border bg-surface p-5 text-sm leading-[normal] font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:opacity-60",
          over && "border-brand bg-brand-tint",
        )}
      >
        {busy ? "Predicting…" : "Drop a CSV here"}
      </button>
      <input
        ref={input}
        type="file"
        accept=".csv,text/csv"
        aria-label="Choose a CSV file"
        className="sr-only"
        onChange={(e) => {
          void run(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {error && (
        <p role="alert" className="text-sm leading-[normal] text-danger">
          {error}
        </p>
      )}
      {done && (
        <div
          className="flex items-center justify-between gap-3 text-sm leading-[normal]"
          data-testid="batch-done"
        >
          <span className="min-w-px flex-1 text-ink">
            {done.fileName} · {done.rows.toLocaleString("en-US")} rows,{" "}
            {done.flagged} flagged
          </span>
          <Button
            variant="outline"
            size="md"
            onClick={() => toast("Predictions download is mocked.")}
          >
            Download
          </Button>
        </div>
      )}
    </section>
  );
}
