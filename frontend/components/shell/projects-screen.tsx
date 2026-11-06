"use client";
import Link from "next/link";
import { FolderOpen } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Tag } from "@/components/ui/tag";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { useAsync } from "@/lib/hooks";
import { listProjects } from "@/lib/api-real";
import { cn } from "@/lib/utils";
import { TopBar } from "./top-bar";

// Projects page: the signed-in user's projects from GET /projects. Plan step 4 adds a status label helper and restyles it.
export function ProjectsScreen() {
  const { data, error, loading, retry } = useAsync(() => listProjects());

  return (
    <section aria-label="Projects" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar
        left={<h2 className="text-sm font-normal leading-[normal] text-muted">Projects</h2>}
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        <div className="flex items-center gap-4">
          <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
            <h1 className="text-[28px] font-semibold text-ink">Projects</h1>
            <p className="text-sm text-muted">Everything you have started, in one place.</p>
          </div>
          <Link href="/" className={cn(buttonVariants({ size: "md" }))}>
            New project
          </Link>
        </div>
        {loading && !data ? (
          <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading projects">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : !data || data.length === 0 ? (
          <EmptyState
            icon={<FolderOpen aria-hidden />}
            title="No projects yet"
            body="Describe what you want to predict to start one."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {data.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/c/${p.id}`}
                  className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4 hover:bg-surface"
                >
                  <span className="min-w-0 truncate text-sm font-medium text-ink">{p.goal}</span>
                  <Tag>{p.status.replace(/_/g, " ")}</Tag>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
