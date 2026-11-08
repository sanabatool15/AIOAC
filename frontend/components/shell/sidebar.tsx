"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { MessageSquare, Plus } from "lucide-react";
import { LinkButton } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { listProjects } from "@/lib/api-real";
import { useAsync, useRealUser } from "@/lib/hooks";
import { activeProjectId, isCurrent, NAV_ITEMS } from "@/lib/nav";
import { statusLabel } from "@/lib/status";
import { cn } from "@/lib/utils";
import { UserMenu } from "./user-menu";

// The project page fires this when a status changes, so the list shows it without a reload.
export const PROJECTS_CHANGED = "aioac:projects-changed";

export function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 rounded-md pl-1" aria-label="AIOAC home">
      <span className="flex size-7 items-center justify-center rounded-md bg-brand text-small font-semibold text-on-brand">
        A
      </span>
      <span className="text-section text-ink">AIOAC</span>
    </Link>
  );
}

const rowClass = "flex items-center gap-2 rounded-md border px-2 py-1.5 text-small";

// Left sidebar: your projects from GET /projects (newest first, with a plain status), account pages, user menu.
// The list reloads when the route changes, so a new project or a new status shows up after you move around.
// `drawer` is the same content inside the narrow-screen drawer; `onNavigate` closes it when a link is used.
export function Sidebar({ drawer, onNavigate }: { drawer?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  const user = useRealUser();
  const { data, error, loading, retry } = useAsync(listProjects, `${pathname}|${user?.id ?? ""}`);
  useEffect(() => {
    window.addEventListener(PROJECTS_CHANGED, retry);
    return () => window.removeEventListener(PROJECTS_CHANGED, retry);
  }, [retry]);
  const active = activeProjectId(pathname);

  return (
    <aside
      className={cn(
        "flex h-full flex-col gap-5 overflow-y-auto bg-surface p-4",
        drawer ? "w-full" : "w-64 shrink-0 border-r border-border",
      )}
    >
      <div className={cn(drawer && "pr-10")}>
        <Logo />
      </div>

      <nav aria-label="Main" className="flex flex-col gap-0.5">
        {NAV_ITEMS.map((n) => {
          const on = isCurrent(n.href, pathname);
          const Icon = n.icon;
          const link = (
            <Link
              href={n.href}
              onClick={onNavigate}
              aria-current={on ? "page" : undefined}
              className={cn(
                rowClass,
                "min-w-0 flex-1",
                on ? "border-brand-line bg-brand-tint font-semibold text-brand-ink" : "border-transparent font-medium text-ink hover:bg-bg",
              )}
            >
              <Icon aria-hidden size={14} className="shrink-0" />
              {n.label}
            </Link>
          );
          if (n.href !== "/projects") return <div key={n.href}>{link}</div>;
          return (
            <div key={n.href} className="flex items-center gap-1">
              {link}
              <LinkButton
                href="/"
                variant="ghost"
                size="icon"
                aria-label="New project"
                title="New project"
                onClick={onNavigate}
                className="size-8 shrink-0"
              >
                <Plus aria-hidden />
              </LinkButton>
            </div>
          );
        })}
      </nav>

      <nav aria-labelledby="recent-projects-label" className="flex min-h-0 flex-col gap-0.5">
        <p id="recent-projects-label" className="px-2 pb-1 text-micro font-medium text-muted">
          Recent projects
        </p>
        {loading && !data && (
          <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading projects">
            <Skeleton className="h-9" />
            <Skeleton className="h-9" />
          </div>
        )}
        {error && !data && <ErrorState message={error.message} onRetry={retry} className="px-2 py-6" />}
        {data && data.length === 0 && (
          <p className="px-2 py-1.5 text-body text-muted">Nothing yet. Use + to start a project.</p>
        )}
        {data?.slice(0, 30).map((p) => {
          const on = p.id === active;
          return (
            <Link
              key={p.id}
              href={`/c/${p.id}`}
              onClick={onNavigate}
              aria-current={on ? "page" : undefined}
              className={cn(
                "flex flex-col gap-px overflow-clip rounded-md border px-2 py-1.5",
                on ? "border-brand-line bg-brand-tint" : "border-transparent hover:bg-bg",
              )}
            >
              <span className={cn("flex items-center gap-2 text-small", on ? "font-semibold text-brand-ink" : "font-medium text-ink")}>
                <MessageSquare aria-hidden size={14} className="shrink-0" />
                <span className="min-w-px flex-1 truncate">{p.goal}</span>
              </span>
              <span className="truncate pl-[22px] text-micro text-muted">{statusLabel(p.status)}</span>
            </Link>
          );
        })}
      </nav>

      <div className="flex-1" />
      <UserMenu />
    </aside>
  );
}
