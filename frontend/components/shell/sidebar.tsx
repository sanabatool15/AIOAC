"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { CreditCard, FolderOpen, Gauge, MessageSquare, Plus } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { listProjects } from "@/lib/api-real";
import { useAsync, useRealUser } from "@/lib/hooks";
import { isCurrent, NAV_ITEMS } from "@/lib/nav";
import { statusLabel } from "@/lib/status";
import { cn } from "@/lib/utils";
import { UserMenu } from "./user-menu";

// The project page fires this when a status changes, so the list shows it without a reload.
export const PROJECTS_CHANGED = "aioac:projects-changed";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-xs font-medium leading-[17px] tracking-[0.2px] text-muted">{children}</p>;
}

// Left sidebar: new project, your projects from GET /projects (newest first, with a plain status), user menu.
// The list reloads when the route changes, so a new project or a new status shows up after you move around.
export function Sidebar() {
  const pathname = usePathname();
  const user = useRealUser();
  const { data, error, loading, retry } = useAsync(listProjects, `${pathname}|${user?.id ?? ""}`);
  useEffect(() => {
    window.addEventListener(PROJECTS_CHANGED, retry);
    return () => window.removeEventListener(PROJECTS_CHANGED, retry);
  }, [retry]);
  const active = pathname.startsWith("/c/") ? pathname.slice(3).split("/")[0] : null;

  return (
    <aside className="flex h-full w-[264px] shrink-0 flex-col gap-5 overflow-y-auto border-r border-border bg-surface p-4">
      <Link href="/" className="flex items-center gap-2.5 pl-1" aria-label="AIOAC home">
        <span className="flex size-7 items-center justify-center rounded-lg bg-brand-gradient-diag text-sm font-semibold text-white">
          A
        </span>
        <span className="text-base font-semibold leading-[23px] text-ink">AIOAC</span>
      </Link>

      <Link href="/" className={cn(buttonVariants({ variant: "primary" }), "w-full")}>
        <Plus aria-hidden />
        New project
      </Link>

      <nav aria-label="Main" className="flex flex-col gap-0.5">
        {NAV_ITEMS.map((n) => {
          const on = isCurrent(n.href, pathname);
          const Icon = n.href === "/projects" ? FolderOpen : n.href === "/account/usage" ? Gauge : CreditCard;
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={on ? "page" : undefined}
              className={cn(
                "flex items-center gap-2 rounded-lg border px-2 py-1.5 text-[13px] leading-5",
                on ? "border-brand-line bg-brand-tint font-semibold text-brand-ink" : "border-transparent font-medium text-ink hover:bg-white/60",
              )}
            >
              <Icon aria-hidden size={14} className="shrink-0" />
              {n.label}
            </Link>
          );
        })}
      </nav>

      <nav aria-label="Recent projects" className="flex min-h-0 flex-col gap-0.5">
        <SectionLabel>RECENT PROJECTS</SectionLabel>
        {loading && !data && (
          <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading projects">
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
          </div>
        )}
        {error && !data && <ErrorState message={error.message} onRetry={retry} className="px-2 py-6" />}
        {data && data.length === 0 && <p className="px-2 py-1.5 text-sm text-muted">Nothing yet. Start with a goal.</p>}
        {data?.slice(0, 30).map((p) => {
          const on = p.id === active;
          return (
            <Link
              key={p.id}
              href={`/c/${p.id}`}
              aria-current={on ? "page" : undefined}
              className={cn(
                "flex flex-col gap-px overflow-clip rounded-lg border px-2 py-1.5 leading-5",
                on ? "border-brand-line bg-brand-tint" : "border-transparent hover:bg-white/60",
              )}
            >
              <span className={cn("flex items-center gap-2 text-[13px]", on ? "font-semibold text-brand-ink" : "font-medium text-ink")}>
                <MessageSquare aria-hidden size={14} className="shrink-0" />
                <span className="min-w-px flex-1 truncate">{p.goal}</span>
              </span>
              <span className="truncate pl-[22px] text-xs text-muted">{statusLabel(p.status)}</span>
            </Link>
          );
        })}
      </nav>

      <div className="flex-1" />
      <UserMenu />
    </aside>
  );
}
