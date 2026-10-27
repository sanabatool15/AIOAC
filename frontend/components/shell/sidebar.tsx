"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Database,
  Folder,
  FolderOpen,
  KeyRound,
  MessageSquare,
  Plus,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { useAsync, usePersistedState } from "@/lib/hooks";
import { getShell, setKeyEnabled } from "@/lib/mock-api";
import { cn } from "@/lib/utils";
import { useAddData } from "./add-data-provider";
import { BudgetCard } from "./budget-card";
import { UserMenu } from "./user-menu";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-medium leading-[17px] tracking-[0.2px] text-muted">
      {children}
    </p>
  );
}

const row = "flex w-full items-center rounded-lg px-2 py-1.5 text-left";

export function Sidebar() {
  const addData = useAddData();
  const { data, error, loading, retry } = useAsync(getShell, addData.version);
  const pathname = usePathname();
  const segments = pathname.startsWith("/c/")
    ? pathname.slice(3).split("/")
    : [];
  const activeChat = segments[0] ?? null;
  const onPlainPage =
    pathname.startsWith("/settings") ||
    pathname.startsWith("/projects") ||
    pathname.startsWith("/account") ||
    pathname.startsWith("/billing");
  const budgetKey = onPlainPage
    ? "page"
    : activeChat && segments[1] === "pay"
      ? `${activeChat}:pay`
      : activeChat;
  const [open, setOpen] = usePersistedState<Record<string, boolean>>(
    "aioac.folders",
    { churn: true },
  );
  const [keyOverrides, setKeyOverrides] = useState<Record<string, boolean>>({});

  async function toggleKey(id: string, next: boolean) {
    setKeyOverrides((o) => ({ ...o, [id]: next })); // optimistic
    try {
      await setKeyEnabled(id, next);
    } catch {
      setKeyOverrides((o) => ({ ...o, [id]: !next })); // roll back
    }
  }

  return (
    <aside className="flex h-full w-[264px] shrink-0 flex-col gap-5 overflow-y-auto border-r border-border bg-surface p-4">
      <div className="flex items-center gap-2.5 pl-1">
        <div className="flex size-7 items-center justify-center rounded-lg bg-brand-gradient-diag text-sm font-semibold text-white">
          A
        </div>
        <span className="text-base font-semibold leading-[23px] text-ink">
          AIOAC
        </span>
      </div>

      <BudgetCard key={budgetKey ?? "none"} chatId={budgetKey} />

      {loading && !data && (
        <div
          className="flex flex-col gap-3"
          aria-busy="true"
          aria-label="Loading sidebar"
        >
          <Skeleton className="h-8" />
          <Skeleton className="h-24" />
          <Skeleton className="h-20" />
        </div>
      )}

      {error && !data && (
        <ErrorState
          message={error.message}
          onRetry={retry}
          className="px-2 py-6"
        />
      )}

      {data && (
        <>
          <Link
            href="/"
            className={cn(buttonVariants({ variant: "primary" }), "w-full")}
          >
            <Plus aria-hidden />
            New chat
          </Link>

          <nav aria-label="Projects" className="flex flex-col gap-0.5">
            <SectionLabel>PROJECTS</SectionLabel>
            {data.projects.map((p) => {
              const isOpen = !!open[p.id];
              return (
                <div key={p.id} className="flex flex-col gap-0.5">
                  <button
                    type="button"
                    aria-expanded={isOpen}
                    onClick={() => setOpen((o) => ({ ...o, [p.id]: !o[p.id] }))}
                    className={cn(row, "gap-1.5 hover:bg-white/60")}
                  >
                    {isOpen ? (
                      <ChevronDown
                        aria-hidden
                        size={14}
                        className="text-ink-2"
                      />
                    ) : (
                      <ChevronRight
                        aria-hidden
                        size={14}
                        className="text-ink-2"
                      />
                    )}
                    {isOpen ? (
                      <FolderOpen
                        aria-hidden
                        size={16}
                        className="text-ink-2"
                      />
                    ) : (
                      <Folder aria-hidden size={16} className="text-ink-2" />
                    )}
                    <span
                      className={cn(
                        "flex-1 text-sm leading-5 text-ink",
                        isOpen ? "font-medium" : "font-normal",
                      )}
                    >
                      {p.name}
                    </span>
                  </button>
                  {isOpen && p.chats.length > 0 && (
                    <div className="flex flex-col gap-0.5 border-l-[1.5px] border-brand-line pl-[15px]">
                      {p.chats.map((c) => {
                        const active =
                          c.id ===
                          (activeChat === "training" ||
                          activeChat === "ineligible" ||
                          activeChat === "round2" ||
                          activeChat === "use-model" ||
                          activeChat === "research" ||
                          activeChat === "budget" ||
                          activeChat === "verified" ||
                          activeChat === "missed" ||
                          activeChat === "result"
                            ? "exp-1"
                            : activeChat);
                        return (
                          <Link
                            key={c.id}
                            href={`/c/${c.id}`}
                            aria-current={active ? "page" : undefined}
                            className={cn(
                              "flex h-[30px] items-center gap-2 overflow-clip rounded-lg border px-2 text-[13px] leading-5",
                              active
                                ? "border-brand-line bg-brand-tint font-semibold text-brand-ink"
                                : "border-transparent font-medium text-ink-2 hover:bg-white/60",
                            )}
                          >
                            <MessageSquare aria-hidden size={14} />
                            <span className="flex-1 truncate">{c.title}</span>
                          </Link>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>

          <section aria-label="Data sources" className="flex flex-col gap-1">
            <SectionLabel>DATA SOURCES</SectionLabel>
            {data.sources.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() =>
                  addData.open(s.id === "uploads" ? "upload" : "connect")
                }
                className={cn(row, "gap-2.5 hover:bg-white/60")}
              >
                <Database aria-hidden size={16} className="text-ink-2" />
                <span className="flex-1 text-sm leading-5 text-ink">
                  {s.name}
                </span>
                <span className="text-xs leading-[17px] text-muted">
                  {s.status}
                </span>
              </button>
            ))}
          </section>

          <section aria-label="API keys" className="flex flex-col gap-1">
            <SectionLabel>API KEYS</SectionLabel>
            {data.keys.map((k) => (
              <div key={k.id} className={cn(row, "gap-2.5")}>
                <KeyRound aria-hidden size={16} className="text-ink-2" />
                <span className="flex-1 text-sm leading-5 text-ink">
                  {k.name}
                </span>
                <Switch
                  label={`${k.name} enabled`}
                  checked={keyOverrides[k.id] ?? k.enabled}
                  onCheckedChange={(v) => toggleKey(k.id, v)}
                />
              </div>
            ))}
          </section>

          <div className="flex-1" />

          <UserMenu user={data.user} />
        </>
      )}
    </aside>
  );
}
