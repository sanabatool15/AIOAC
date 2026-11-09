"use client";
import Link from "next/link";
import { FolderOpen } from "lucide-react";
import { LinkButton } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Tag } from "@/components/ui/tag";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { useAsync } from "@/lib/hooks";
import { listProjects } from "@/lib/api-real";
import { statusLabel } from "@/lib/status";
import { TopBar } from "./top-bar";

// Projects page: the signed-in user's projects from GET /projects.
export function ProjectsScreen() {
  const { data, error, loading, retry } = useAsync(() => listProjects());

  return (
    <section aria-label="Chats" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<p className="text-body text-muted">Chats</p>} />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 sm:p-8">
        <PageHeader
          title="Chats"
          subtitle="Everything you have started, in one place."
          actions={<LinkButton href="/">New chat</LinkButton>}
        />
        {loading && !data ? (
          <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading chats">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={FolderOpen}
            title="No chats yet"
            body="Describe what you want to predict to start one."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {data.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/c/${p.id}`}
                  className="flex items-center justify-between gap-4 rounded-lg border border-border bg-card p-4 hover:bg-surface"
                >
                  <span title={p.goal} className="min-w-0 truncate text-body font-medium text-ink">
                    {p.goal}
                  </span>
                  <Tag>{statusLabel(p.status)}</Tag>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
