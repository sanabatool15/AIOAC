"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ChevronDown, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Switch } from "@/components/ui/switch";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import {
  addKey,
  deleteKey,
  getKeys,
  revealKey,
  setKeyEnabled,
} from "@/lib/mock-api";
import type { ApiKey, KeyProvider } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "./confirm-dialog";
import { KeyDrawer } from "./key-drawer";
import { TopBar } from "./top-bar";

const providers: { id: KeyProvider; label: string; access: string }[] = [
  {
    id: "huggingface",
    label: "Hugging Face",
    access: "private Hugging Face data",
  },
  { id: "kaggle", label: "Kaggle", access: "Kaggle datasets" },
  { id: "openrouter", label: "OpenRouter", access: "OpenRouter models" },
  { id: "other", label: "Other", access: "this service" },
];

const navItems = [
  { label: "Profile" },
  { label: "API keys", active: true },
  { label: "Connections" },
  { label: "Notifications" },
  { label: "Danger zone", muted: true },
];

const scopeLabel = (k: ApiKey) =>
  k.projects === "all"
    ? "All projects"
    : k.projects.length === 1
      ? k.projects[0]
      : `${k.projects.length} projects`;

// Screen 17: Settings > API keys (Colab-style): table with on/off, reveal, copy, delete + an add-key card.
export function KeysScreen() {
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(() => getKeys());
  const [local, setLocal] = useState<ApiKey[] | null>(null);
  const [revealed, setRevealed] = useState<Record<string, string>>({});
  const [target, setTarget] = useState<ApiKey | null>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const keys = local ?? data ?? [];
  const router = useRouter();
  const detailsId = useSearchParams().get("details");
  const open = keys.find((k) => k.id === detailsId) ?? null;

  async function toggle(k: ApiKey, enabled: boolean) {
    setLocal(keys.map((x) => (x.id === k.id ? { ...x, enabled } : x)));
    try {
      await setKeyEnabled(k.id, enabled);
    } catch {
      setLocal(keys); // roll back
      toast("Could not change that key. Try again.", "error");
    }
  }

  async function reveal(k: ApiKey) {
    if (revealed[k.id]) {
      setRevealed((r) => {
        const next = { ...r };
        delete next[k.id];
        return next;
      });
      return;
    }
    try {
      const r = await revealKey(k.id);
      setRevealed((v) => ({ ...v, [k.id]: r.value }));
    } catch (e) {
      toast((e as Error).message, "error");
    }
  }

  async function copy(k: ApiKey) {
    try {
      const { value } = await revealKey(k.id);
      await navigator.clipboard.writeText(value);
      toast(`Copied "${k.name}".`);
    } catch {
      toast("Could not copy that key.", "error");
    }
  }

  return (
    <section
      aria-label="Settings"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        shareStyle="chip"
        left={
          <h2 className="whitespace-pre text-sm font-normal leading-[normal] text-muted">{`Settings  /  API keys`}</h2>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        <h1 className="text-[28px] font-semibold leading-[normal] text-ink">
          Settings
        </h1>
        <div className="flex items-start gap-6">
          <nav
            aria-label="Settings sections"
            className="flex w-[190px] shrink-0 flex-col gap-0.5"
          >
            {navItems.map((n) =>
              n.active ? (
                <span
                  key={n.label}
                  aria-current="page"
                  className="rounded-lg bg-surface px-3 py-[9px] text-sm font-semibold leading-[normal] text-ink"
                >
                  {n.label}
                </span>
              ) : (
                <span
                  key={n.label}
                  aria-disabled="true"
                  title="Not designed yet"
                  className={cn(
                    "rounded-lg px-3 py-[9px] text-sm leading-[normal]",
                    n.muted ? "text-muted" : "text-ink",
                  )}
                >
                  {n.label}
                </span>
              ),
            )}
          </nav>

          <div className="flex min-w-px flex-1 flex-col gap-3.5">
            <div className="flex items-center">
              <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
                <h2 className="text-xl font-semibold text-ink">API keys</h2>
                <p className="text-sm text-muted">
                  Private keys the agent can use. Choose which projects each key
                  can reach.
                </p>
              </div>
              <Button
                size="md"
                className="rounded-[9px] shadow-glow"
                onClick={() => nameRef.current?.focus()}
              >
                + Add new key
              </Button>
            </div>

            {loading && !data ? (
              <div
                aria-busy="true"
                aria-label="Loading keys"
                className="flex flex-col gap-2"
              >
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
              </div>
            ) : error && !local ? (
              <ErrorState message={error.message} onRetry={retry} />
            ) : keys.length === 0 ? (
              <EmptyState
                icon={<KeyRound />}
                title="No keys yet"
                body="Add a key below so the agent can reach private data and models."
              />
            ) : (
              <div className="overflow-clip rounded-xl border border-border bg-white shadow-card-tight">
                <table className="w-full table-fixed text-left text-sm leading-[normal]">
                  <colgroup>
                    <col className="w-16" />
                    <col className="w-[140px]" />
                    <col className="w-[170px]" />
                    <col className="w-[140px]" />
                    <col />
                  </colgroup>
                  <thead className="bg-surface text-muted">
                    <tr>
                      {["On", "Name", "Value", "Projects", "Actions"].map(
                        (h) => (
                          <th
                            key={h}
                            scope="col"
                            className="px-3.5 py-[13px] font-semibold"
                          >
                            {h}
                          </th>
                        ),
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((k) => (
                      <tr
                        key={k.id}
                        className="border-b border-border text-ink"
                      >
                        <td className="px-3.5 py-[13px]">
                          <Switch
                            size="lg"
                            label={`${k.name} enabled`}
                            checked={k.enabled}
                            onCheckedChange={(on) => toggle(k, on)}
                          />
                        </td>
                        <td className="truncate px-3.5 py-[13px]">{k.name}</td>
                        <td className="whitespace-pre-wrap px-3.5 py-[13px] break-all">
                          {revealed[k.id] ?? `••••••••••  ${k.last4}`}
                        </td>
                        <td className="px-3.5 py-[13px]">
                          <Tag className="max-w-full truncate">
                            {scopeLabel(k)}
                          </Tag>
                        </td>
                        <td className="px-3.5 py-[13px]">
                          <span className="flex flex-wrap gap-x-1">
                            <Link
                              href={`/settings/keys?details=${k.id}`}
                              aria-label={`Details for ${k.name}`}
                              className="hover:underline"
                            >
                              Details
                            </Link>
                            <span aria-hidden>·</span>
                            <button
                              type="button"
                              aria-label={`${revealed[k.id] ? "Hide" : "Reveal"} ${k.name}`}
                              onClick={() => reveal(k)}
                              className="hover:underline"
                            >
                              {revealed[k.id] ? "Hide" : "Reveal"}
                            </button>
                            <span aria-hidden>·</span>
                            <button
                              type="button"
                              aria-label={`Copy ${k.name}`}
                              onClick={() => copy(k)}
                              className="hover:underline"
                            >
                              Copy
                            </button>
                            <span aria-hidden>·</span>
                            <button
                              type="button"
                              aria-label={`Delete ${k.name}`}
                              onClick={() => setTarget(k)}
                              className="hover:underline"
                            >
                              Delete
                            </button>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <AddKeyCard
              nameRef={nameRef}
              onAdded={(k) => {
                setLocal([...keys, k]);
                toast(`Key "${k.name}" saved.`);
              }}
            />
          </div>
        </div>
      </div>

      {open && (
        <KeyDrawer
          keyRow={open}
          onClose={() => router.replace("/settings/keys")}
          onToggle={(on) => toggle(open, on)}
          onAccess={(projects) =>
            setLocal(
              keys.map((k) => (k.id === open.id ? { ...k, projects } : k)),
            )
          }
          onDelete={() => setTarget(open)}
        />
      )}
      {target && (
        <ConfirmDialog
          title={`Delete key "${target.name}"?`}
          body={`${
            target.projects === "all"
              ? "Every project uses"
              : `${target.projects.length} ${target.projects.length === 1 ? "project uses" : "projects use"}`
          } this key. The agent will lose access to ${
            providers.find((p) => p.id === target.provider)?.access
          } until you add a new key.`}
          confirmLabel="Delete key"
          onCancel={() => setTarget(null)}
          onConfirm={async () => {
            await deleteKey(target.id);
            setLocal(keys.filter((k) => k.id !== target.id));
            if (detailsId === target.id) router.replace("/settings/keys");
            setTarget(null);
            toast(`Key "${target.name}" deleted.`);
          }}
        />
      )}
    </section>
  );
}

function AddKeyCard({
  nameRef,
  onAdded,
}: {
  nameRef: React.RefObject<HTMLInputElement | null>;
  onAdded: (k: ApiKey) => void;
}) {
  const [name, setName] = useState("");
  const [provider, setProvider] = useState<KeyProvider>("kaggle");
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onAdded(await addKey({ name, provider, value }));
      setName("");
      setValue("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const field = "flex min-w-px flex-1 flex-col gap-1.5";
  const label =
    "text-sm font-semibold leading-[normal] whitespace-nowrap text-muted";
  return (
    <form
      noValidate
      onSubmit={save}
      aria-label="Add a new key"
      className="surface-violet flex flex-col gap-3 overflow-clip rounded-xl border p-5 shadow-card-tight"
    >
      <h3 className="text-sm font-semibold leading-[normal] text-ink">
        Add a new key
      </h3>
      <div className="flex items-start gap-3">
        <div className={field}>
          <label htmlFor="key-name" className={label}>
            Name
          </label>
          <Input
            id="key-name"
            ref={nameRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. MY_KAGGLE_KEY"
            autoComplete="off"
            className="px-3.5 py-2.5"
          />
        </div>
        <div className={field}>
          <label htmlFor="key-provider" className={label}>
            Provider
          </label>
          <div className="relative">
            <select
              id="key-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value as KeyProvider)}
              className="w-full appearance-none rounded-lg border border-border bg-white py-2.5 pl-3.5 pr-9 text-sm leading-[normal] text-ink shadow-btn-neutral outline-none focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge"
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
            <ChevronDown
              aria-hidden
              size={14}
              className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-muted"
            />
          </div>
        </div>
        <div className={field}>
          <label htmlFor="key-value" className={label}>
            Value
          </label>
          <Input
            id="key-value"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Paste key here..."
            autoComplete="off"
            className="px-3.5 py-2.5"
          />
        </div>
      </div>
      {error && (
        <p role="alert" className="text-sm leading-[normal] text-danger">
          {error}
        </p>
      )}
      <div className="flex items-center gap-2.5">
        <Button
          type="submit"
          size="md"
          className="rounded-[9px] shadow-glow"
          disabled={busy}
        >
          Save key
        </Button>
        <p className="min-w-px flex-1 text-sm leading-[normal] text-muted">
          Names cannot contain spaces. Values are encrypted. The agent can only
          use keys that are on.
        </p>
      </div>
    </form>
  );
}
