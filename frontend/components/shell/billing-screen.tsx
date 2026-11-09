"use client";
import Link from "next/link";
import { Receipt } from "lucide-react";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { StatusChip } from "@/components/ui/status-chip";
import { getAccountPayments } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { holdPhase, phaseView } from "@/lib/money-summary";
import { toBilling, type BillingRow } from "@/lib/screens";
import { TopBar } from "./top-bar";

const th = "px-3.5 py-2.5 text-small font-semibold text-muted";
const td = "px-3.5 py-3 text-body text-ink align-top";
const money = "text-right tabular-nums";

function goalText(goal: string) {
  return goal.length > 40 ? `${goal.slice(0, 40)}…` : goal;
}

function Status({ row, state }: { row: BillingRow; state: string | undefined }) {
  return <StatusChip tone={phaseView(holdPhase(state)).tone}>{row.state}</StatusChip>;
}

// What the compute and the success fee were, shown small under the total instead of as two more columns.
function Split({ r }: { r: BillingRow }) {
  return (
    <span className="block text-micro font-normal text-muted">
      Compute {r.compute} + success fee {r.fee}
    </span>
  );
}

// Billing history: one row per PayPal hold, from GET /account/payments. Read-only. No plans, cards or invoices.
export function BillingScreen() {
  const { data, error, loading, retry } = useAsync(() => getAccountPayments());
  const rows = toBilling(data);
  return (
    <section aria-label="Billing history" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-body text-muted"><span>Account</span><span aria-hidden>/</span><span aria-current="page" className="text-ink">Billing history</span></nav>} />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 sm:p-8">
        <PageHeader
          title="Billing history"
          subtitle="Every PayPal hold, and what was charged and released. This is PayPal sandbox test money. A hold is not a charge."
        />
        {loading && !data ? (
          <div aria-busy="true" aria-label="Loading billing history" className="flex flex-col gap-3">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={Receipt}
            title="No payments yet"
            body="When you approve a price, the PayPal hold and what happened to it will show up here."
          />
        ) : (
          <>
            <div className="hidden overflow-x-auto rounded-xl border border-trace-line bg-grad-trace shadow-card shadow-card md:block">
              <table className="w-full text-left" data-testid="billing-table">
                <thead className="bg-surface">
                  <tr>
                    <th className={th}>Chat</th>
                    <th className={th}>Status</th>
                    <th className={`${th} ${money}`}>Held</th>
                    <th className={`${th} ${money}`}>Total charged</th>
                    <th className={`${th} ${money}`}>Released</th>
                    <th className={th}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.id} className="border-t border-border">
                      <td className={td}>
                        <Link href={`/c/${r.projectId}`} className="font-semibold text-brand-ink underline">
                          {goalText(r.goal)}
                        </Link>
                      </td>
                      <td className={td}>
                        <Status row={r} state={data?.[i]?.state} />
                      </td>
                      <td className={`${td} ${money}`}>{r.held}</td>
                      <td className={`${td} ${money} font-semibold`}>
                        {r.total}
                        <Split r={r} />
                      </td>
                      <td className={`${td} ${money}`}>{r.released}</td>
                      <td className={`${td} text-muted`}>{r.when}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul aria-label="Payments" className="flex flex-col gap-3 md:hidden" data-testid="billing-cards">
              {rows.map((r, i) => (
                <li key={r.id}>
                  <Card className="gap-2 p-4">
                    <Link href={`/c/${r.projectId}`} className="text-body font-semibold text-brand-ink underline">
                      {goalText(r.goal)}
                    </Link>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Status row={r} state={data?.[i]?.state} />
                      <span className="text-small text-muted">{r.when}</span>
                    </div>
                    <dl className="grid grid-cols-3 gap-2 text-body">
                      <div>
                        <dt className="text-small text-muted">Held</dt>
                        <dd className="tabular-nums text-ink">{r.held}</dd>
                      </div>
                      <div>
                        <dt className="text-small text-muted">Charged</dt>
                        <dd className="font-semibold tabular-nums text-ink">{r.total}</dd>
                      </div>
                      <div>
                        <dt className="text-small text-muted">Released</dt>
                        <dd className="tabular-nums text-ink">{r.released}</dd>
                      </div>
                    </dl>
                    <Split r={r} />
                  </Card>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
