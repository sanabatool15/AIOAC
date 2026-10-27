"use client";
import { useState } from "react";
import { FolderOpen } from "lucide-react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tag } from "@/components/ui/tag";
import { cn } from "@/lib/utils";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import { deleteProject, getShell, renameProject } from "@/lib/mock-api";
import type { ProjectSummary } from "@/lib/types";
import { ConfirmDialog } from "./confirm-dialog";
import { TopBar } from "./top-bar";

// Screen 16 (page behind the Share dialog) + screen 31 delete flow: card grid with Rename / Delete per project.
export function ProjectsScreen() {
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(() => getShell());
  const [removed, setRemoved] = useState<string[]>([]);
  const [names, setNames] = useState<Record<string, string>>({});
  const [target, setTarget] = useState<ProjectSummary | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const projects = (data?.projects ?? []).filter(
    (p) => !removed.includes(p.id),
  );

  async function rename(p: ProjectSummary, value: string) {
    const name = value.trim();
    setRenaming(null);
    if (!name || name === (names[p.id] ?? p.name)) return;
    try {
      await renameProject(p.id, name);
      setNames((n) => ({ ...n, [p.id]: name }));
      toast("Project renamed.");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  }

  return (
    <section
      aria-label="Projects"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        shareStyle="chip"
        left={
          <h2 className="text-sm font-normal leading-[normal] text-muted">
            Projects
          </h2>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        <div className="flex items-center gap-4">
          <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
            <h1 className="text-[28px] font-semibold text-ink">Projects</h1>
            <p className="text-sm text-muted">
              Everything you have trained, in one place.
            </p>
          </div>
          <Link
            href="/"
            className={cn(
              buttonVariants({ size: "md" }),
              "rounded-[9px] shadow-glow",
            )}
          >
            + New project
          </Link>
        </div>
        {loading && !data ? (
          <div
            aria-busy="true"
            aria-label="Loading projects"
            className="grid grid-cols-3 gap-4"
          >
            <Skeleton className="h-[170px]" />
            <Skeleton className="h-[170px]" />
            <Skeleton className="h-[170px]" />
          </div>
        ) : error || !data ? (
          <ErrorState
            message={error?.message ?? "Projects unavailable."}
            onRetry={retry}
          />
        ) : projects.length === 0 ? (
          <EmptyState
            icon={<FolderOpen />}
            title="No projects yet"
            body="Start a new chat and your first project appears here."
          />
        ) : (
          <ul className="grid grid-cols-3 gap-4">
            {projects.map((p) => {
              const name = names[p.id] ?? p.name;
              const running = p.status === "running";
              return (
                <li
                  key={p.id}
                  className={cn(
                    "flex min-w-px flex-col gap-2.5 overflow-clip rounded-xl border p-5 shadow-card-tight",
                    running ? "surface-blue" : "border-border bg-card",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span
                      aria-hidden
                      className="flex size-[34px] items-center justify-center rounded-[9px] border border-border bg-surface text-ink-2"
                    >
                      <FolderOpen size={16} />
                    </span>
                    <Tag variant={running ? "brand" : "muted"}>
                      {running ? "RUNNING" : "DONE"}
                    </Tag>
                  </div>
                  {renaming === p.id ? (
                    <Input
                      autoFocus
                      aria-label={`New name for ${name}`}
                      defaultValue={name}
                      className="px-2.5 py-1.5 font-semibold"
                      onBlur={(e) => rename(p, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") e.currentTarget.blur();
                        if (e.key === "Escape") setRenaming(null);
                      }}
                    />
                  ) : (
                    <h3 className="text-base font-semibold leading-[normal] text-ink">
                      <Link
                        href={`/projects/${p.id}`}
                        className="hover:underline focus-visible:outline-2 focus-visible:outline-brand"
                      >
                        {name}
                      </Link>
                    </h3>
                  )}
                  <p className="text-sm leading-[normal] text-muted">
                    {p.subtitle ?? `${p.chats.length} chats`}
                  </p>
                  <div className="flex items-center justify-between pt-1.5 text-sm leading-[normal] whitespace-nowrap text-muted">
                    <span>
                      {p.members && p.members > 1
                        ? `You + ${p.members - 1}`
                        : "You"}
                    </span>
                    <span>
                      <button
                        type="button"
                        aria-label={`Rename project ${name}`}
                        onClick={() => setRenaming(p.id)}
                        className="hover:text-ink"
                      >
                        Rename
                      </button>
                      {" · "}
                      <button
                        type="button"
                        aria-label={`Delete project ${name}`}
                        onClick={() => setTarget({ ...p, name })}
                        className="hover:text-ink"
                      >
                        Delete
                      </button>
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {target && (
        <ConfirmDialog
          title={`Delete "${target.name}"?`}
          body={`This removes ${target.chats.length} chats, ${target.dataFiles ?? 0} data files and ${target.models ?? 0} model versions. Receipts stay in Billing. This cannot be undone.`}
          requireText={{
            label: "Type the project name to confirm",
            value: target.name,
          }}
          confirmLabel="Delete project"
          onCancel={() => setTarget(null)}
          onConfirm={async () => {
            await deleteProject(target.id);
            setRemoved((r) => [...r, target.id]);
            setTarget(null);
            toast(`Project "${target.name}" deleted.`);
          }}
        />
      )}
    </section>
  );
}
