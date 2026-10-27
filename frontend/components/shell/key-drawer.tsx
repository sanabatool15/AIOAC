"use client";
import { useEffect, useState } from "react";
import { FolderOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import { getKeyDetail, setKeyAccess } from "@/lib/mock-api";
import type { ApiKey, KeyDetail } from "@/lib/types";

const providerLabel = {
  huggingface: "Hugging Face",
  kaggle: "Kaggle",
  openrouter: "OpenRouter",
  other: "Other",
};

// Screen 17b: key details drawer (400px, right). Status, facts and per-project access.
export function KeyDrawer({
  keyRow,
  onClose,
  onToggle,
  onAccess,
  onDelete,
}: {
  keyRow: ApiKey;
  onClose: () => void;
  onToggle: (on: boolean) => void;
  onAccess: (projects: "all" | string[]) => void;
  onDelete: () => void;
}) {
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(
    () => getKeyDetail(keyRow.id),
    keyRow.id,
  );
  const [detail, setDetail] = useState<KeyDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const d = detail ?? data;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) =>
      e.key === "Escape" &&
      !document.querySelector("[role=alertdialog]") &&
      onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function save(projects: "all" | string[]) {
    setBusy(true);
    try {
      const next = await setKeyAccess(keyRow.id, projects);
      setDetail(next);
      onAccess(next.projects);
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  }

  const allowAll = d ? d.projects === "all" : false;
  const allowedNames = d
    ? d.access.filter((a) => a.allowed).map((a) => a.project)
    : [];

  return (
    <aside
      aria-label={`${keyRow.name} details`}
      className="fixed right-0 top-0 z-40 flex h-full w-[400px] flex-col gap-3.5 overflow-y-auto border border-border bg-surface p-6 shadow-drawer"
    >
      <div className="flex items-center justify-between leading-[normal]">
        <h2 className="text-xl font-semibold whitespace-nowrap text-ink">
          {keyRow.name}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-muted hover:text-ink"
        >
          Close
        </button>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-px leading-[normal]">
          <span className="text-sm font-semibold text-ink">
            {keyRow.enabled ? "Key is on" : "Key is off"}
          </span>
          <span className="text-xs text-muted">
            {keyRow.enabled
              ? "The agent can use it"
              : "The agent cannot use it"}
          </span>
        </div>
        <Switch
          size="lg"
          label={`${keyRow.name} is on`}
          checked={keyRow.enabled}
          onCheckedChange={onToggle}
        />
      </div>

      {loading && !d ? (
        <div
          className="flex flex-col gap-3"
          aria-busy="true"
          aria-label="Loading key details"
        >
          <Skeleton className="h-32" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : error && !d ? (
        <ErrorState message={error.message} onRetry={retry} />
      ) : d ? (
        <>
          <dl className="flex flex-col text-sm leading-[normal]">
            {[
              ["Provider", providerLabel[d.provider]],
              ["Value", `••••••••••  ${d.last4}`],
              ["Created", d.createdLabel],
              ["Last used", d.lastUsedLabel],
            ].map(([k, v]) => (
              <div
                key={k}
                className="flex items-start gap-3 border-b border-border py-[9px]"
              >
                <dt className="w-[90px] shrink-0 font-semibold text-muted">
                  {k}
                </dt>
                <dd className="min-w-px flex-1 whitespace-pre-wrap text-ink">
                  {v}
                </dd>
              </div>
            ))}
          </dl>

          <h3 className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
            PROJECT ACCESS
          </h3>
          <div className="flex items-center rounded-[10px] p-3">
            <div className="flex min-w-px flex-1 flex-col gap-px leading-[normal]">
              <span className="text-sm font-semibold text-ink">
                Allow all projects
              </span>
              <span className="text-xs text-muted">
                Includes projects you create later
              </span>
            </div>
            <Switch
              size="lg"
              label="Allow all projects"
              checked={allowAll}
              disabled={busy}
              onCheckedChange={(on) => save(on ? "all" : allowedNames)}
            />
          </div>
          <ul aria-label="Project access" className="flex flex-col">
            {d.access.map((a) => (
              <li
                key={a.project}
                className="flex items-center gap-2.5 border-b border-border py-2.5"
              >
                <span
                  aria-hidden
                  className="flex size-[26px] shrink-0 items-center justify-center rounded-[7px] border border-border bg-surface text-ink-2"
                >
                  <FolderOpen size={14} />
                </span>
                <div className="flex min-w-px flex-1 flex-col gap-px leading-[normal]">
                  <span className="text-sm font-semibold whitespace-nowrap text-ink">
                    {a.project}
                  </span>
                  <span className="text-xs whitespace-nowrap text-muted">
                    {a.usedLabel}
                  </span>
                </div>
                <Switch
                  size="lg"
                  label={`Allow ${a.project}`}
                  checked={a.allowed}
                  disabled={busy}
                  onCheckedChange={(on) => {
                    const names = d.access
                      .filter((x) => (x.project === a.project ? on : x.allowed))
                      .map((x) => x.project);
                    save(names);
                  }}
                />
              </li>
            ))}
          </ul>
        </>
      ) : null}

      <div className="min-h-px flex-1" />
      <Button variant="outline" size="md" className="w-full" onClick={onDelete}>
        Delete key
      </Button>
    </aside>
  );
}
