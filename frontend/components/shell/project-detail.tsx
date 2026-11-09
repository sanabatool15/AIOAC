"use client";
import Link from "next/link";
import { History as HistoryIcon } from "lucide-react";
import { useState } from "react";
import { LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EstimateNote } from "@/components/ui/estimate-note";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tabs } from "@/components/ui/tabs";
import { Tag } from "@/components/ui/tag";
import { toBaseline, toForecast } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import { getHistory, getProject } from "@/lib/api-real";
import { ActivityCard } from "./activity-card";
import { truncateGoal } from "@/lib/goal";
import { useAsync } from "@/lib/hooks";
import { overviewLine, TABS, toHistory, type TabId } from "@/lib/screens";
import { statusLabel } from "@/lib/status";
import { ModelTab } from "./model-tab";
import { ShareButton } from "./share-dialog";
import { Row } from "./step-parts";
import { TopBar } from "./top-bar";

const TAB_ITEMS = TABS.map((t) => ({ id: t, label: t }));

// Project detail page: goal and plain status, then Overview, History and Activity from the server.
export function ProjectDetail({ projectId, initialTab = "Overview" }: { projectId: string; initialTab?: TabId }) {
  const { data, error, loading, retry } = useAsync(() => getProject(projectId), projectId);
  const [tab, setTab] = useState<TabId>(initialTab);

  return (
    <section aria-label="Project" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar
        left={
          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-body text-muted">
            <Link href="/projects" className="hover:text-ink">
              Projects
            </Link>
            {data && (
              <>
                <span aria-hidden>/</span>
                <span title={data.goal} className="truncate" aria-current="page">
                  {truncateGoal(data.goal)}
                </span>
              </>
            )}
          </nav>
        }
        actions={<ShareButton projectId={projectId} />}
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 sm:p-8">
        {loading && !data ? (
          <div aria-busy="true" aria-label="Loading project" className="flex flex-col gap-5">
            <Skeleton className="h-14 w-96 max-w-full" />
            <Skeleton className="h-8 w-96 max-w-full" />
            <Skeleton className="h-44" />
          </div>
        ) : error || !data ? (
          <ErrorState message={error?.message ?? "Chat unavailable."} onRetry={retry} />
        ) : (
          <>
            <PageHeader
              clampTitle
              title={<span title={data.goal}>{data.goal}</span>}
              subtitle={overviewLine(data.status)}
              actions={
                <>
                  <Tag variant={data.status === "done" ? "success" : "brand"}>{statusLabel(data.status)}</Tag>
                  <LinkButton href={`/c/${data.id}`}>Open chat</LinkButton>
                </>
              }
            />
            <Tabs
              label="Chat tabs"
              tabs={TAB_ITEMS}
              value={tab}
              onValueChange={(id) => setTab(TABS.find((t) => t === id) ?? "Overview")}
            >
              <div className="flex flex-col gap-4">
                {tab === "Overview" && <Overview project={data} />}
                {tab === "History" && <History projectId={projectId} />}
                {tab === "Activity" && <Activity projectId={projectId} />}
                {tab === "Model" && <ModelTab projectId={projectId} />}
              </div>
            </Tabs>
          </>
        )}
      </div>
    </section>
  );
}

function Overview({ project }: { project: BProject }) {
  const base = toBaseline(project);
  const fc = toForecast(project.forecast);
  return (
    <Card aria-label="Where this chat is" className="gap-3 p-5">
      <h2 className="text-section text-ink">Where this chat is</h2>
      <dl className="flex flex-col gap-1.5">
        <Row label="Goal" value={project.goal} />
        <Row label="Status" value={statusLabel(project.status)} />
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
      <EstimateNote>Results are estimates from held-back test rows, not promises.</EstimateNote>
    </Card>
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
    return <EmptyState icon={HistoryIcon} title="Nothing here yet" body="Versions, runs, price estimates and payments appear as you go." />;
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
        <Card key={p.key} aria-label="Payment" className="gap-2 p-5">
          <h2 className="text-section text-ink">
            {pays.length > 1 ? `Payment ${i + 1} of ${pays.length}` : "Payment"} (PayPal sandbox, test money){p.when ? ` · ${p.when}` : ""}
          </h2>
          <p className="text-body text-ink-2">{p.state}</p>
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
      <h2 className="text-section text-ink">{title}</h2>
      {children.length === 0 ? <p className="text-body text-muted">{empty}</p> : <ul className="flex flex-col gap-2">{children}</ul>}
    </section>
  );
}

function Item({ title, meta, body, tag }: { title: string; meta: string; body: string; tag?: string }) {
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <p className="text-body font-semibold text-ink">{title}</p>
        <div className="flex items-center gap-2">
          {tag && <Tag variant={tag === "VERIFIED" ? "success" : "warning"}>{tag}</Tag>}
          <span className="text-micro text-muted">{meta}</span>
        </div>
      </div>
      <p className="text-body text-ink-2">{body}</p>
    </li>
  );
}

function Activity({ projectId }: { projectId: string }) {
  return <ActivityCard projectId={projectId} />;
}
