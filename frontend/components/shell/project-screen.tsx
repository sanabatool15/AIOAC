"use client";
import { useState } from "react";
import Link from "next/link";
import { MessageSquare, Play } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import { deleteProjectVersion, getProject } from "@/lib/mock-api";
import type { ModelVersion, ProjectDetail, ProjectRun } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "./confirm-dialog";
import { TopBar } from "./top-bar";

const TABS = ["Runs", "Models", "Data", "Chats", "Settings"] as const;
type TabId = (typeof TABS)[number];

const STATUS: Record<
  ProjectRun["status"],
  { label: string; variant: "brand" | "muted" | "success" }
> = {
  running: { label: "Running", variant: "brand" },
  missed: { label: "Missed", variant: "muted" },
  done: { label: "Done", variant: "muted" },
  met: { label: "Target met", variant: "success" },
};

// Screen 34: project page with runs, model versions, chats. Data and Settings tabs are not designed yet.
export function ProjectScreen({ projectId }: { projectId: string }) {
  const { data, error, loading, retry } = useAsync(
    () => getProject(projectId),
    projectId,
  );
  const [tab, setTab] = useState<TabId>("Runs");
  const [removed, setRemoved] = useState<string[]>([]);
  const [target, setTarget] = useState<ModelVersion | null>(null);
  const toast = useToast();
  const versions = (data?.versions ?? []).filter(
    (v) => !removed.includes(v.id),
  );

  return (
    <section
      aria-label="Project"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        shareStyle="chip"
        projectName={data?.name}
        left={
          <h2 className="text-sm font-normal leading-[normal] whitespace-pre text-muted">
            <Link href="/projects" className="hover:text-ink">
              Projects
            </Link>
            {`  /  ${data?.name ?? ""}`}
          </h2>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        {loading && !data ? (
          <div
            aria-busy="true"
            aria-label="Loading project"
            className="flex flex-col gap-5"
          >
            <Skeleton className="h-14 w-96" />
            <Skeleton className="h-8 w-96" />
            <Skeleton className="h-[180px]" />
          </div>
        ) : error || !data ? (
          <ErrorState
            message={error?.message ?? "Project unavailable."}
            onRetry={retry}
          />
        ) : (
          <>
            <div className="flex items-center gap-4">
              <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
                <h1 className="text-[28px] font-semibold text-ink">
                  {data.name}
                </h1>
                <p className="text-sm text-muted">{data.subtitle}</p>
              </div>
              {data.badge && <Tag variant="brand">{data.badge}</Tag>}
              <Link
                href={`/c/${data.openChatId}`}
                className={cn(
                  buttonVariants({ size: "md" }),
                  "rounded-[9px] shadow-glow",
                )}
              >
                Open chat
              </Link>
            </div>
            <div
              role="tablist"
              aria-label="Project tabs"
              className="flex gap-[22px] border-b border-border"
            >
              {TABS.map((t) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  aria-selected={tab === t}
                  onClick={() => setTab(t)}
                  className={cn(
                    "border-b-2 pb-2.5 pt-2 text-sm leading-[normal] whitespace-nowrap outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand",
                    tab === t
                      ? "border-brand font-semibold text-ink"
                      : "border-transparent text-muted",
                  )}
                >
                  {t}
                </button>
              ))}
            </div>
            <div role="tabpanel" className="flex items-start gap-4">
              {tab === "Runs" && (
                <>
                  <RunsTable runs={data.runs} />
                  <ModelVersions
                    data={data}
                    versions={versions}
                    onDelete={setTarget}
                    className="w-[340px] shrink-0"
                  />
                </>
              )}
              {tab === "Models" && (
                <ModelVersions
                  data={data}
                  versions={versions}
                  onDelete={setTarget}
                  className="min-w-px flex-1"
                />
              )}
              {tab === "Chats" &&
                (data.chats.length === 0 ? (
                  <EmptyState
                    icon={<MessageSquare />}
                    title="No chats yet"
                    body="Open a chat to start a run for this project."
                  />
                ) : (
                  <ul className="flex min-w-px flex-1 flex-col gap-2">
                    {data.chats.map((c) => (
                      <li key={c.id}>
                        <Link
                          href={`/c/${c.id}`}
                          className="flex items-center gap-2.5 rounded-xl border border-border bg-card px-4 py-3 text-sm leading-[normal] text-ink shadow-card-tight hover:bg-surface"
                        >
                          <MessageSquare
                            aria-hidden
                            size={14}
                            className="text-ink-2"
                          />
                          {c.title}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ))}
              {(tab === "Data" || tab === "Settings") && (
                <EmptyState
                  icon={<Play />}
                  title={`${tab} is not designed yet`}
                  body="This tab arrives with its own screen."
                />
              )}
            </div>
          </>
        )}
      </div>
      {target && data && (
        <ConfirmDialog
          title={`Delete model ${target.name}?`}
          body={`This removes ${target.name} (${target.metrics}) from your project. ${data.downloadNote} This cannot be undone.`}
          requireCheck="I understand I cannot get it back"
          confirmLabel="Delete model"
          onCancel={() => setTarget(null)}
          onConfirm={async () => {
            await deleteProjectVersion(data.id, target.id);
            setRemoved((r) => [...r, target.id]);
            setTarget(null);
            toast(`Model ${target.name} deleted.`);
          }}
        />
      )}
    </section>
  );
}

const cell = "px-3.5 py-[13px] text-sm leading-[normal]";

function RunsTable({ runs }: { runs: ProjectRun[] }) {
  if (runs.length === 0)
    return (
      <EmptyState
        icon={<Play />}
        title="No runs yet"
        body="Runs appear here once the agent starts training."
      />
    );
  return (
    <div className="min-w-px flex-1 overflow-clip rounded-xl border border-border bg-card shadow-card-tight">
      <table className="w-full table-fixed border-collapse text-left">
        <caption className="sr-only">Runs</caption>
        <thead className="bg-surface text-muted">
          <tr>
            <th scope="col" className={cn(cell, "w-20 font-semibold")}>
              Round
            </th>
            <th scope="col" className={cn(cell, "w-[120px] font-semibold")}>
              Date
            </th>
            <th scope="col" className={cn(cell, "font-semibold")}>
              Target
            </th>
            <th scope="col" className={cn(cell, "w-[130px] font-semibold")}>
              Result
            </th>
            <th scope="col" className={cn(cell, "w-[90px] font-semibold")}>
              Cost
            </th>
            <th scope="col" className={cn(cell, "w-[110px] font-semibold")}>
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr
              key={r.id}
              className="border-b border-border last:border-b-0 text-ink"
            >
              <td className={cell}>{r.round}</td>
              <td className={cell}>{r.date}</td>
              <td className={cell}>{r.target}</td>
              <td className={cell}>{r.result}</td>
              <td className={cell}>{r.cost}</td>
              <td className={cell}>
                <Tag variant={STATUS[r.status].variant}>
                  {STATUS[r.status].label}
                </Tag>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ModelVersions({
  data,
  versions,
  onDelete,
  className,
}: {
  data: ProjectDetail;
  versions: ModelVersion[];
  onDelete: (v: ModelVersion) => void;
  className?: string;
}) {
  return (
    <Card
      variant="violet"
      className={cn("gap-2.5 p-[18px]", className)}
      data-testid="model-versions"
    >
      <h2 className="text-xs font-semibold leading-[normal] text-muted">
        MODEL VERSIONS
      </h2>
      {versions.length === 0 && (
        <p className="text-sm leading-[normal] text-muted">
          No model versions yet.
        </p>
      )}
      {versions.map((v) => (
        <div
          key={v.id}
          className="flex items-center gap-2.5 border-b border-border py-2.5 text-sm leading-[normal]"
        >
          <div className="flex min-w-px flex-1 flex-col gap-px">
            <span className="font-semibold text-ink">{v.name}</span>
            <span className="text-muted">{v.metrics}</span>
          </div>
          {v.best && <Tag variant="brand">Best so far</Tag>}
          <button
            type="button"
            aria-label={`Delete model ${v.name}`}
            onClick={() => onDelete(v)}
            className="text-muted hover:text-ink"
          >
            Delete
          </button>
        </div>
      ))}
      <p className="text-sm leading-[normal] text-muted">{data.downloadNote}</p>
    </Card>
  );
}
