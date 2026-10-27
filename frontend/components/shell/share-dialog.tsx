"use client";
import { useEffect, useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import {
  getShare,
  inviteMember,
  removeMember,
  setResultLink,
} from "@/lib/mock-api";
import type { ShareRole, ShareState } from "@/lib/types";

const roleLabel = { owner: "Owner", editor: "Editor", viewer: "Viewer" };

// Screen 16: invite people + view-only result link. Opened from every Share button.
export function ShareDialog({
  projectName,
  onClose,
}: {
  projectName: string;
  onClose: () => void;
}) {
  const uid = useId();
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(
    () => getShare(projectName),
    projectName,
  );
  const [override, setOverride] = useState<ShareState | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<ShareRole>("editor");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const state = override ?? data;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function run(fn: () => Promise<ShareState>, ok?: string) {
    setBusy(true);
    setFormError(null);
    try {
      setOverride(await fn());
      if (ok) toast(ok);
      return true;
    } catch (e) {
      setFormError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    if (await run(() => inviteMember(projectName, email, role))) setEmail("");
  }

  async function copy() {
    if (!state) return;
    try {
      await navigator.clipboard.writeText(`https://${state.link.url}`);
      toast("Link copied.");
    } catch {
      toast("Could not copy. Select the link and copy it yourself.", "error");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-overlay p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${uid}-t`}
        className="flex w-[540px] max-w-full flex-col gap-3.5 rounded-2xl bg-white p-6"
      >
        <div className="flex items-center justify-between leading-[normal]">
          <h2 id={`${uid}-t`} className="text-xl font-semibold text-ink">
            Share &quot;{projectName}&quot;
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-muted hover:text-ink"
          >
            Close
          </button>
        </div>

        {loading && !state ? (
          <div
            className="flex flex-col gap-3"
            aria-busy="true"
            aria-label="Loading sharing"
          >
            <Skeleton className="h-10" />
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : error && !state ? (
          <ErrorState message="Sharing options unavailable." onRetry={retry} />
        ) : state ? (
          <>
            <p className="text-xs font-semibold leading-[normal] text-muted">
              INVITE PEOPLE
            </p>
            <form
              noValidate
              onSubmit={invite}
              className="flex items-center gap-2"
            >
              <Input
                type="email"
                aria-label="Email to invite"
                aria-invalid={formError ? true : undefined}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                autoComplete="off"
                className="min-w-px flex-1 rounded-[9px] px-3.5 py-2.5 shadow-none"
              />
              <label className="relative shrink-0">
                <span className="sr-only">Role</span>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as ShareRole)}
                  className="h-full appearance-none rounded-[9px] border border-border bg-white py-2.5 pl-3.5 pr-9 text-sm leading-[normal] text-ink outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
                >
                  <option value="editor">Editor</option>
                  <option value="viewer">Viewer</option>
                </select>
                <ChevronDown
                  aria-hidden
                  size={12}
                  className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted"
                />
              </label>
              <Button
                type="submit"
                size="md"
                className="rounded-[9px]"
                disabled={busy || email.trim() === ""}
              >
                Invite
              </Button>
            </form>
            {formError && (
              <p role="alert" className="text-sm leading-[normal] text-danger">
                {formError}
              </p>
            )}

            <ul aria-label="People with access" className="flex flex-col">
              {state.members.map((m) => (
                <li
                  key={m.id}
                  className="flex items-center gap-3 border-b border-border py-2"
                >
                  <span
                    aria-hidden
                    className="size-7 shrink-0 rounded-[14px] bg-bar-target"
                  />
                  <div className="flex min-w-px flex-1 flex-col leading-[normal]">
                    <span className="truncate text-sm font-semibold text-ink">
                      {m.name}
                    </span>
                    <span className="text-xs text-muted">
                      {roleLabel[m.role]}
                      {m.status ? ` · ${m.status}` : ""}
                    </span>
                  </div>
                  {m.role !== "owner" && (
                    <button
                      type="button"
                      disabled={busy}
                      aria-label={`Remove ${m.name}`}
                      onClick={() =>
                        run(
                          () => removeMember(projectName, m.id),
                          "Access removed.",
                        )
                      }
                      className="text-sm leading-[normal] whitespace-nowrap text-muted hover:text-ink disabled:opacity-50"
                    >
                      Remove
                    </button>
                  )}
                </li>
              ))}
            </ul>

            <p className="text-xs font-semibold leading-[normal] text-muted">
              RESULT LINK (VIEW ONLY)
            </p>
            <div className="flex items-center gap-2.5">
              <div className="flex min-w-px flex-1 flex-col gap-0.5 leading-[normal]">
                <span className="text-sm font-semibold text-ink">
                  Anyone with the link can see results and the receipt
                </span>
                <span className="text-xs text-muted">
                  No data files, no API keys, no chat history.
                </span>
              </div>
              <Switch
                size="lg"
                label="Result link"
                checked={state.link.enabled}
                disabled={busy}
                onCheckedChange={(on) =>
                  run(
                    () => setResultLink(projectName, on),
                    on ? "Result link is on." : "Result link is off.",
                  )
                }
              />
            </div>
            <div className="flex items-center gap-2">
              <p
                aria-label="Result link address"
                className="min-w-px flex-1 overflow-clip rounded-[9px] border border-border bg-surface px-3.5 py-2.5 text-sm leading-[normal] whitespace-nowrap text-muted"
              >
                {state.link.enabled ? state.link.url : "Link is off"}
              </p>
              <Button
                variant="outline"
                size="md"
                disabled={!state.link.enabled}
                onClick={copy}
              >
                Copy link
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
