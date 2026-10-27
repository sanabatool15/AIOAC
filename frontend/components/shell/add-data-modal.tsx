"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { CircleCheck, CloudUpload, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input, Field } from "@/components/ui/input";
import { ProgressBar } from "@/components/ui/progress-bar";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import {
  addDatasets,
  connectIntegration,
  detectLink,
  getIntegrations,
  markSynced,
  uploadFile,
  validateDataFile,
  type DetectedDataset,
  type Integration,
} from "@/lib/mock-api";
import { cn } from "@/lib/utils";

export type AddDataTab = "upload" | "link" | "connect";

const TABS: { id: AddDataTab; label: string }[] = [
  { id: "upload", label: "Upload" },
  { id: "link", label: "Paste a link" },
  { id: "connect", label: "Connect an account" },
];

const WORKS_WITH = [
  "Hugging Face",
  "Kaggle",
  "Google Drive",
  "Dropbox",
  "GitHub (raw)",
  "Amazon S3 link",
  "Any CSV or Parquet URL",
];

interface Props {
  initialTab: AddDataTab;
  onClose: () => void;
  onAdded: () => void;
}

export function AddDataModal({ initialTab, onClose, onAdded }: Props) {
  const toast = useToast();
  const [tab, setTab] = useState<AddDataTab>(initialTab);
  const [uploadsDone, setUploadsDone] = useState(0);
  const [uploadsBusy, setUploadsBusy] = useState(false);
  const [detected, setDetected] = useState<DetectedDataset | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const onSummary = useCallback((done: number, busy: boolean) => {
    setUploadsDone(done);
    setUploadsBusy(busy);
  }, []);

  const canAdd =
    tab === "upload"
      ? uploadsDone > 0 && !uploadsBusy
      : tab === "link"
        ? detected !== null
        : true;

  async function add() {
    setSaving(true);
    setSaveError(null);
    try {
      const count = tab === "upload" ? uploadsDone : 1;
      await addDatasets(tab === "upload" ? "upload" : "link", count);
      toast(
        count === 1
          ? "1 dataset added to your project"
          : `${count} datasets added to your project`,
      );
      onAdded();
      onClose();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Could not add your data.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-overlay p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-data-title"
        className="flex w-[680px] max-w-full flex-col gap-4 rounded-2xl bg-white p-6"
      >
        <div className="flex items-center justify-between leading-[normal]">
          <h2 id="add-data-title" className="text-xl font-semibold text-ink">
            Add data
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="rounded text-sm text-muted hover:text-ink"
          >
            Close
          </button>
        </div>

        <div
          role="tablist"
          aria-label="Add data from"
          className="flex gap-0.5 rounded-[10px] bg-surface p-[3px]"
        >
          {TABS.map((t) => {
            const active = t.id === tab;
            return (
              <button
                key={t.id}
                role="tab"
                type="button"
                aria-selected={active}
                onClick={() => setTab(t.id)}
                className={cn(
                  "flex min-w-px flex-1 items-center justify-center rounded-lg border py-[9px] text-sm leading-[normal]",
                  active
                    ? "border-border bg-white font-semibold text-ink shadow-btn-neutral"
                    : "border-transparent font-medium text-muted hover:text-ink",
                )}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Panels stay mounted so an in-flight upload or a detected link survives tab switches. */}
        <div
          role="tabpanel"
          hidden={tab !== "upload"}
          className="flex flex-col gap-4"
        >
          <UploadPanel onSummary={onSummary} />
        </div>
        <div
          role="tabpanel"
          hidden={tab !== "link"}
          className="flex flex-col gap-4"
        >
          <LinkPanel detected={detected} onDetected={setDetected} />
        </div>
        <div
          role="tabpanel"
          hidden={tab !== "connect"}
          className="flex flex-col gap-4"
        >
          <ConnectPanel />
        </div>

        {tab === "upload" && (
          <p className="text-sm leading-[normal] text-muted">
            Your data stays private to your project and is never used to train
            anything else.
          </p>
        )}
        {tab === "link" && (
          <p className="text-sm leading-[normal] text-muted">
            Private links need a connected account or key. We never store the
            link contents outside your project.
          </p>
        )}

        {saveError && (
          <p role="alert" className="text-sm text-danger">
            {saveError}
          </p>
        )}

        <div className="flex justify-end gap-2.5">
          <Button variant="outline" size="md" onClick={onClose}>
            Cancel
          </Button>
          {tab === "connect" ? (
            <Button size="md" className="rounded-[9px]" onClick={onClose}>
              Done
            </Button>
          ) : (
            <Button
              size="md"
              className="rounded-[9px]"
              onClick={add}
              disabled={!canAdd || saving}
            >
              {saving ? "Adding..." : "Add to project"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------- 3a Upload ----------

interface UploadItem {
  key: string;
  name: string;
  pct: number;
  status: "uploading" | "done" | "error";
  error?: string;
  file: File;
  ctrl: AbortController;
}

function UploadPanel({
  onSummary,
}: {
  onSummary: (done: number, busy: boolean) => void;
}) {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const [rejected, setRejected] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const itemsRef = useRef(items);
  useEffect(() => {
    itemsRef.current = items;
    onSummary(
      items.filter((i) => i.status === "done").length,
      items.some((i) => i.status === "uploading"),
    );
  }, [items, onSummary]);

  useEffect(() => () => itemsRef.current.forEach((i) => i.ctrl.abort()), []);

  const patch = useCallback(
    (key: string, p: Partial<UploadItem>) =>
      setItems((list) => list.map((i) => (i.key === key ? { ...i, ...p } : i))),
    [],
  );

  const start = useCallback(
    (item: UploadItem) => {
      uploadFile(item.file, (pct) => patch(item.key, { pct }), item.ctrl.signal)
        .then(() => patch(item.key, { pct: 100, status: "done" }))
        .catch(
          (e: Error) =>
            e.name !== "AbortError" &&
            patch(item.key, {
              status: "error",
              error: e.message || "Upload failed.",
            }),
        );
    },
    [patch],
  );

  function addFiles(files: FileList | File[]) {
    setRejected(null);
    const next: UploadItem[] = [];
    const problems: string[] = [];
    for (const file of Array.from(files)) {
      const err = validateDataFile(file);
      if (err) {
        problems.push(`${file.name}: ${err}`);
        continue;
      }
      next.push({
        key: `${file.name}-${file.size}-${Date.now()}-${next.length}`,
        name: file.name,
        pct: 0,
        status: "uploading",
        file,
        ctrl: new AbortController(),
      });
    }
    if (problems.length) setRejected(problems.join(" "));
    if (next.length) {
      setItems((list) => [...list, ...next]);
      next.forEach(start);
    }
  }

  function retry(item: UploadItem) {
    const fresh = {
      ...item,
      pct: 0,
      status: "uploading" as const,
      error: undefined,
      ctrl: new AbortController(),
    };
    setItems((list) => list.map((i) => (i.key === item.key ? fresh : i)));
    start(fresh);
  }

  function remove(item: UploadItem) {
    item.ctrl.abort();
    setItems((list) => list.filter((i) => i.key !== item.key));
  }

  return (
    <>
      <div
        onDragOver={(e) => (e.preventDefault(), setDragging(true))}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex flex-col items-center gap-2 overflow-clip rounded-[14px] border border-dashed bg-surface p-9",
          dragging ? "border-brand" : "border-border",
        )}
      >
        <div
          aria-hidden
          className="flex size-11 items-center justify-center rounded-[22px] border border-border bg-white shadow-btn-neutral"
        >
          <CloudUpload size={20} className="text-brand" />
        </div>
        <p className="text-base font-semibold leading-[normal] text-ink">
          Drag and drop files here
        </p>
        <p className="text-sm leading-[normal] text-muted">
          CSV, Parquet or Excel · up to 200 MB
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".csv,.parquet,.xls,.xlsx"
          className="sr-only"
          aria-label="Choose data files"
          tabIndex={-1}
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <Button
          variant="outline"
          size="md"
          onClick={() => inputRef.current?.click()}
        >
          Browse files
        </Button>
      </div>

      {rejected && (
        <p
          role="alert"
          className="flex items-center gap-1.5 text-sm text-danger"
        >
          <TriangleAlert aria-hidden size={14} /> {rejected}
        </p>
      )}

      {items.map((item) => (
        <div
          key={item.key}
          className="flex items-center gap-3 overflow-clip rounded-[10px] border border-border p-3"
          data-testid="upload-row"
        >
          <div
            aria-hidden
            className="size-8 shrink-0 rounded-[7px] border border-border bg-surface"
          />
          <div className="flex min-w-px flex-1 flex-col gap-[5px] overflow-clip">
            <div className="flex items-start justify-between gap-3 text-sm leading-[normal]">
              <span className="truncate font-semibold text-ink">
                {item.name}
              </span>
              <span className="flex shrink-0 items-center gap-2 text-muted">
                {item.status === "done" && (
                  <CircleCheck
                    aria-label="Uploaded"
                    size={14}
                    className="text-success"
                  />
                )}
                <span>
                  {item.status === "error" ? "Failed" : `${item.pct}%`}
                </span>
                {item.status !== "done" && (
                  <button
                    type="button"
                    onClick={() => remove(item)}
                    className="text-xs hover:text-ink"
                    aria-label={`Cancel ${item.name}`}
                  >
                    {item.status === "uploading" ? "Cancel" : "Remove"}
                  </button>
                )}
              </span>
            </div>
            {item.status === "error" ? (
              <p
                role="alert"
                className="flex items-center gap-2 text-xs text-danger"
              >
                {item.error}
                <button
                  type="button"
                  onClick={() => retry(item)}
                  className="font-semibold underline"
                >
                  Try again
                </button>
              </p>
            ) : (
              <ProgressBar
                value={item.pct}
                label={`Uploading ${item.name}`}
                size="sm"
                track="neutral"
              />
            )}
          </div>
        </div>
      ))}
    </>
  );
}

// ---------- 3b Paste a link ----------

function LinkPanel({
  detected,
  onDetected,
}: {
  detected: DetectedDataset | null;
  onDetected: (d: DetectedDataset | null) => void;
}) {
  const [url, setUrl] = useState("");
  const [state, setState] = useState<"idle" | "detecting" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const runId = useRef(0);

  const detect = useCallback(
    async (value: string) => {
      const id = ++runId.current;
      onDetected(null);
      if (!value.trim()) {
        setState("idle");
        setError(null);
        return;
      }
      setState("detecting");
      setError(null);
      try {
        const d = await detectLink(value);
        if (id !== runId.current) return;
        onDetected(d);
        setState("idle");
      } catch (e) {
        if (id !== runId.current) return;
        setState("error");
        setError(e instanceof Error ? e.message : "Could not check that link.");
      }
    },
    [onDetected],
  );

  // Check shortly after typing or pasting stops.
  useEffect(() => {
    const t = setTimeout(() => void detect(url), 450);
    return () => clearTimeout(t);
  }, [url, detect]);

  return (
    <>
      <Field label="Dataset link" htmlFor="dataset-link">
        <Input
          id="dataset-link"
          inputMode="url"
          autoComplete="off"
          placeholder="https://huggingface.co/datasets/scikit-learn/telco-churn"
          value={url}
          aria-invalid={state === "error"}
          className="py-2.5"
          onChange={(e) => setUrl(e.target.value)}
        />
      </Field>

      {state === "detecting" && <Skeleton className="h-[110px] rounded-xl" />}

      {state === "error" && error && (
        <ErrorState
          message={error}
          onRetry={() => void detect(url)}
          className="rounded-xl border border-border px-4 py-5"
        />
      )}

      {detected && state !== "detecting" && (
        <div
          className="surface-detected flex flex-col gap-2.5 overflow-clip rounded-xl border p-4 shadow-card-tight"
          data-testid="detected-card"
        >
          <div className="flex items-center gap-2.5">
            <div
              aria-hidden
              className="size-[34px] shrink-0 rounded-lg border border-border bg-surface"
            />
            <div className="flex min-w-px flex-1 flex-col gap-px overflow-clip leading-[normal]">
              <p className="truncate text-sm font-semibold text-ink">
                {detected.title}
              </p>
              <p className="truncate text-xs text-muted">{detected.subtitle}</p>
            </div>
            <Tag variant="brand">FOUND</Tag>
          </div>
          <dl className="flex gap-6 leading-[normal]">
            {[
              [detected.rows, "rows"],
              [detected.columns, "columns"],
              [detected.size, "size"],
              [detected.target, "suggested target"],
            ].map(([value, label]) => (
              <div
                key={label}
                className="flex flex-col gap-px whitespace-nowrap"
              >
                <dt className="order-2 text-xs text-muted">{label}</dt>
                <dd className="text-base font-semibold text-ink">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      <p className="text-xs font-semibold leading-[normal] text-muted">
        WORKS WITH
      </p>
      <div className="flex flex-wrap content-start gap-2">
        {WORKS_WITH.map((w) => (
          <Tag key={w}>{w}</Tag>
        ))}
      </div>
    </>
  );
}

// ---------- 3c Connect an account ----------

function ConnectPanel() {
  const toast = useToast();
  const [version, setVersion] = useState(0);
  const { data, error, loading, retry } = useAsync(getIntegrations, version);
  const [busy, setBusy] = useState<string | null>(null);
  const [progress, setProgress] = useState<Record<string, number>>({});

  // Kaggle-style syncing rows: tick the bar locally, then tell the backend it finished (real API pushes this over SSE).
  const syncing = data?.filter((i) => i.state === "syncing") ?? [];
  const syncKey = syncing.map((i) => i.id).join(",");
  useEffect(() => {
    if (!syncKey) return;
    const timer = setInterval(() => {
      setProgress((p) => {
        const next = { ...p };
        for (const id of syncKey.split(",")) {
          const cur = next[id] ?? data?.find((i) => i.id === id)?.syncPct ?? 0;
          next[id] = Math.min(100, cur + 6);
          if (next[id] >= 100) {
            markSynced(id as Integration["id"]);
            setVersion((v) => v + 1);
          }
        }
        return next;
      });
    }, 700);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [syncKey]);

  async function connect(row: Integration) {
    setBusy(row.id);
    try {
      await connectIntegration(row.id);
      toast(`${row.name} connected`);
      setVersion((v) => v + 1);
    } catch (e) {
      toast(
        e instanceof Error ? e.message : `Could not connect ${row.name}.`,
        "error",
      );
    } finally {
      setBusy(null);
    }
  }

  if (loading && !data)
    return (
      <div
        className="flex flex-col gap-2"
        aria-busy="true"
        aria-label="Loading accounts"
      >
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-[68px] rounded-xl" />
        ))}
      </div>
    );
  if (error && !data)
    return (
      <ErrorState message={error.message} onRetry={retry} className="py-8" />
    );

  return (
    <div className="flex flex-col gap-2">
      {data?.map((row) => {
        const pct = progress[row.id] ?? row.syncPct ?? 0;
        return (
          <div
            key={row.id}
            className="flex items-center gap-3.5 overflow-clip rounded-xl border border-border p-3"
            data-testid={`source-${row.id}`}
          >
            <div
              aria-hidden
              className="size-[34px] shrink-0 rounded-lg border border-border bg-surface"
            />
            <div className="flex min-w-px flex-1 flex-col gap-0.5 overflow-clip leading-[normal]">
              <p className="text-sm font-semibold text-ink">{row.name}</p>
              <p className="text-xs text-muted">
                {row.state === "syncing" ? row.description : row.description}
              </p>
            </div>
            {row.state === "connected" && <Tag variant="brand">Connected</Tag>}
            {row.state === "syncing" && (
              <div className="flex w-[120px] shrink-0 flex-col gap-1 overflow-clip">
                <p className="text-xs font-semibold leading-[normal] whitespace-nowrap text-ink">
                  Syncing... {pct}%
                </p>
                <ProgressBar
                  value={pct}
                  label={`${row.name} sync`}
                  size="sm"
                  track="neutral"
                />
              </div>
            )}
            {row.state === "expired" && (
              <>
                <Tag variant="dashed">Token expired</Tag>
                <Button
                  size="md"
                  className="rounded-[9px]"
                  disabled={busy === row.id}
                  onClick={() => connect(row)}
                >
                  {busy === row.id ? "Connecting..." : "Reconnect"}
                </Button>
              </>
            )}
            {row.state === "disconnected" && (
              <Button
                variant="outline"
                size="md"
                disabled={busy === row.id}
                onClick={() => connect(row)}
              >
                {busy === row.id ? "Connecting..." : "Connect"}
              </Button>
            )}
            {row.state === "soon" && <Tag>COMING SOON</Tag>}
          </div>
        );
      })}
    </div>
  );
}
