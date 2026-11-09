"use client";
import Link from "next/link";
import { useState } from "react";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { toBaseline, toForecast } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import { getActivity, getHistory, getProject } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { overviewLine, TABS, toActivity, toHistory, type TabId } from "@/lib/screens";
import { statusLabel } from "@/lib/status";
import { cn } from "@/lib/utils";
import { ModelTab } from "./model-tab";
import { ChatComposer, ChatThread, useProjectChat } from "./project-chat";
import { ShareButton } from "./share-dialog";
import { Row } from "./step-parts";
import { TopBar } from "./top-bar";


// Project detail page: goal and plain status, then Overview, History and Activity from the server.
export function ProjectDetail({ projectId, initialTab = "Overview" }: { projectId: string; initialTab?: TabId }) {
  const { data, error, loading, retry } = useAsync(() => getProject(projectId), projectId);
  const [tab, setTab] = useState<TabId>(initialTab);
  const name = data ? (data.goal.length > 48 ? `${data.goal.slice(0, 48)}…` : data.goal) : "";

  return (
    <section aria-label="Project" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar
        left={
          <h2 className="text-sm font-normal leading-[normal] whitespace-pre text-muted">
            <Link href="/projects" className="hover:text-ink">
              Projects
            </Link>
            {`  /  ${name}`}
          </h2>
        }
        actions={<ShareButton projectId={projectId} />}
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        {loading && !data ? (
          <div aria-busy="true" aria-label="Loading project" className="flex flex-col gap-5">
            <Skeleton className="h-14 w-96" />
            <Skeleton className="h-8 w-96" />
            <Skeleton className="h-[180px]" />
          </div>
        ) : error || !data ? (
          <ErrorState message={error?.message ?? "Project unavailable."} onRetry={retry} />
        ) : (
          <>
            <div className="flex items-center gap-4">
              <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
                <h1 className="text-[28px] font-semibold text-ink">{data.goal}</h1>
                <p className="text-sm text-muted">{overviewLine(data.status)}</p>
              </div>
              <Tag variant={data.status === "done" ? "success" : "brand"}>{statusLabel(data.status)}</Tag>
              <Link href={`/c/${data.id}`} className={cn(buttonVariants({ size: "md" }), "rounded-[9px] shadow-glow")}>
                Open chat
              </Link>
            </div>
            <div role="tablist" aria-label="Project tabs" className="flex gap-[22px] border-b border-border">
              {TABS.map((t) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  id={`tab-${t}`}
                  aria-selected={tab === t}
                  aria-controls="tabpanel"
                  onClick={() => setTab(t)}
                  className={cn(
                    "border-b-2 pb-2.5 pt-2 text-sm leading-[normal] whitespace-nowrap outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand",
                    tab === t ? "border-brand font-semibold text-ink" : "border-transparent text-muted",
                  )}
                >
                  {t}
                </button>
              ))}
            </div>
            <AskPanel project={data} onChanged={retry} />
            <div role="tabpanel" id="tabpanel" aria-labelledby={`tab-${tab}`} className="flex flex-col gap-4">
              {tab === "Overview" && <Overview project={data} />}
              {tab === "History" && <History projectId={projectId} />}
              {tab === "Activity" && <Activity projectId={projectId} />}
              {tab === "Model" && <ModelTab projectId={projectId} />}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

// A compact, collapsed chat on the project page: the same project chat (same messages, same approval cards).
// Nothing is loaded and no model is called until it is opened. It never blocks the tabs below it.
function AskPanel({ project, onChanged }: { project: BProject; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <section aria-label="Ask about this project" className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="ask-panel"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 text-left text-sm font-semibold text-ink outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand"
      >
        Ask about this project
        <span aria-hidden className="text-muted">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <div id="ask-panel" className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto">
          <AskChat project={project} onChanged={onChanged} />
        </div>
      )}
    </section>
  );
}

function AskChat({ project, onChanged }: { project: BProject; onChanged: () => void }) {
  const pc = useProjectChat(project.id, project.goal, project.status, onChanged);
  return (
    <>
      <ChatThread pc={pc} projectStatus={project.status} />
      <ChatComposer pc={pc} />
    </>
  );
}

function Overview({ project }: { project: BProject }) {
  const base = toBaseline(project);
  const fc = toForecast(project.forecast);
  return (
    <>
      <Card variant="violet" aria-label="Where this project is" className="gap-2.5 p-5">
        <p className="text-xs font-semibold text-muted">WHERE THIS PROJECT IS</p>
        <p className="text-base font-semibold text-ink">{statusLabel(project.status)}</p>
        <p className="text-sm leading-5 text-ink-2">{overviewLine(project.status)}</p>
        <div>
          <Link href={`/c/${project.id}`} className={buttonVariants({ size: "md" })}>
            Go to the chat
          </Link>
        </div>
      </Card>
      <Card aria-label="Summary" className="gap-2 p-5">
        <dl className="flex flex-col gap-1.5">
          <Row
            label="Data"
            value={
              project.dataset
                ? `${project.dataset.rows.toLocaleString("en-US")} rows, predicting "${project.dataset.target}"`
                : "Not chosen yet"
            }
          />
          <Row label="Data grade" value={project.readiness_grade ?? "Not checked yet"} />
          <Row
            label="Free test"
            value={base ? `about ${base.right} out of 100 right (a simple guess: ${base.guess})` : "Not run yet"}
          />
          <Row
            label="Target"
            value={fc ? `${fc.target ?? "—"} out of 100 (estimated chance ${fc.confidence ?? "—"} in 100)` : "Not set yet"}
          />
        </dl>
        <p className="text-xs text-muted">Results are estimates from held-back test rows, not promises.</p>
      </Card>
    </>
  );
}

function History({ projectId }: { projectId: string }) {
  const { data, error, loading, retry } = useAsync(() => getHistory(projectId), projectId);
  if (loading && !data) return <Skeleton className="h-40" />;
  if (error || !data) return <ErrorState message={error?.message ?? "History unavailable."} onRetry={retry} />;
  const h = toHistory(data);
  const empty = !h.versions.length && !h.runs.length && !h.quotes.length && !h.payment && !h.payments.length;
  // A project can have several holds (one per round). Older servers send only `payment`.
  const pays = h.payments.length ? h.payments : h.payment ? [{ ...h.payment, key: "latest", when: "" }] : [];
  if (empty)
    return <EmptyState icon={<span>·</span>} title="Nothing here yet" body="Versions, runs, price estimates and payments appear as you go." />;
  return (
    <>
      <Section title="Data versions" empty="No data chosen yet.">
        {h.versions.map((v) => (
          <Item key={v.id} title={v.title} meta={v.when} body={v.detail} />
        ))}
      </Section>
      <Section title="Runs" empty="No run yet.">
        {h.runs.map((r) => (
          <Item
            key={r.id}
            title={`${r.round ? `Round ${r.round}: ` : ""}${r.status}${r.versionNo ? ` · saved as version ${r.versionNo}` : ""}`}
            meta={r.when}
            body={`${r.result} Compute cost: ${r.cost}.`}
            tag={r.passed === null ? undefined : r.passed ? "VERIFIED" : "NOT MET"}
          />
        ))}
      </Section>
      <Section title="Price estimates" empty="No price estimate yet.">
        {h.quotes.map((q) => (
          <Item
            key={q.id}
            title={`Estimate ${q.estimate} (range ${q.range}), most it can charge ${q.cap}`}
            meta={q.when}
            body={q.approved ? "You approved this price." : "Not approved."}
          />
        ))}
      </Section>
      {pays.map((p, i) => (
        <Card key={p.key} variant="mint" aria-label="Payment" className="gap-2 p-5">
          <h2 className="text-sm font-semibold text-ink">
            {pays.length > 1 ? `Payment ${i + 1} of ${pays.length}` : "Payment"} (PayPal sandbox, test money){p.when ? ` · ${p.when}` : ""}
          </h2>
          <p className="text-sm text-ink-2">{p.state}</p>
          <dl className="flex flex-col gap-1.5">
            <Row label="Held" value={p.held} />
            <Row label="Compute charged" value={p.compute} />
            <Row label="Success fee charged" value={p.fee} />
            <Row label="Released" value={p.released} />
            <Row label="Total charged" value={p.total} strong />
          </dl>
        </Card>
      ))}
    </>
  );
}

function Section({ title, empty, children }: { title: string; empty: string; children: React.ReactNode[] }) {
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h2 className="text-xs font-semibold text-muted">{title.toUpperCase()}</h2>
      {children.length === 0 ? <p className="text-sm text-muted">{empty}</p> : <ul className="flex flex-col gap-2">{children}</ul>}
    </section>
  );
}

function Item({ title, meta, body, tag }: { title: string; meta: string; body: string; tag?: string }) {
  return (
    <li className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4 shadow-card-tight">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-ink">{title}</p>
        <div className="flex items-center gap-2">
          {tag && <Tag variant={tag === "VERIFIED" ? "success" : "muted"}>{tag}</Tag>}
          <span className="text-xs text-muted">{meta}</span>
        </div>
      </div>
      <p className="text-sm leading-5 text-ink-2">{body}</p>
    </li>
  );
}

function Activity({ projectId }: { projectId: string }) {
  const { data, error, loading, retry } = useAsync(() => getActivity(projectId), projectId);
  if (loading && !data) return <Skeleton className="h-40" />;
  if (error || !data) return <ErrorState message={error?.message ?? "Activity unavailable."} onRetry={retry} />;
  const items = toActivity(data);
  return (
    <Card aria-label="What the agent did" className="gap-3 p-5">
      <h2 className="text-base font-semibold text-ink">What the agent did</h2>
      {items.length === 0 ? (
        <p className="text-sm text-muted">Nothing yet. Start in the chat.</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {items.map((a) => (
            <li key={a.key} className="flex items-start gap-3 text-sm leading-5">
              <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-[4px] bg-brand-gradient" />
              <span className="min-w-px flex-1 text-ink">{a.text}</span>
              <time className="shrink-0 text-xs text-muted">{a.when}</time>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
