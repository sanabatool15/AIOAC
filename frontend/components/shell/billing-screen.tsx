"use client";
import Link from "next/link";
import { Receipt } from "lucide-react";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { getAccountPayments } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { toBilling } from "@/lib/screens";
import { TopBar } from "./top-bar";

const th = "px-3.5 py-2.5 text-xs font-semibold text-muted";
const td = "px-3.5 py-3 text-sm leading-[normal] text-ink";

// Billing history: one row per PayPal hold, from GET /account/payments. Read-only. No plans, cards or invoices.
export function BillingScreen() {
  const { data, error, loading, retry } = useAsync(() => getAccountPayments());
  const rows = toBilling(data);
  return (
    <section aria-label="Billing history" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<h2 className="text-sm font-normal leading-[normal] whitespace-pre text-muted">{"Account  /  Billing history"}</h2>} />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        <div className="flex flex-col gap-1 leading-[normal]">
          <h1 className="text-[28px] font-semibold text-ink">Billing history</h1>
          <p className="text-sm text-muted">
            Every PayPal hold, and what was charged and released. This is PayPal sandbox test money. A hold is not a charge.
          </p>
        </div>
        {loading && !data ? (
          <div aria-busy="true" aria-label="Loading billing history" className="flex flex-col gap-3">
            <Skeleton className="h-12" />
            <Skeleton className="h-12" />
          </div>
        ) : error ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<Receipt />}
            title="No payments yet"
            body="When you approve a price, the PayPal hold and what happened to it will show up here."
          />
        ) : (
          <div className="overflow-x-auto rounded-xl border border-border bg-card shadow-card-tight">
            <table className="w-full min-w-[820px] text-left" data-testid="billing-table">
              <thead className="bg-surface">
                <tr>
                  <th className={th}>Project</th>
                  <th className={th}>What happened</th>
                  <th className={th}>Held</th>
                  <th className={th}>Compute charged</th>
                  <th className={th}>Success fee</th>
                  <th className={th}>Released</th>
                  <th className={th}>Total charged</th>
                  <th className={th}>Date</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className={td}>
                      <Link href={`/projects/${r.projectId}`} className="font-semibold text-brand-ink underline">
                        {r.goal.length > 40 ? `${r.goal.slice(0, 40)}…` : r.goal}
                      </Link>
                    </td>
                    <td className={td}>{r.state}</td>
                    <td className={td}>{r.held}</td>
                    <td className={td}>{r.compute}</td>
                    <td className={td}>{r.fee}</td>
                    <td className={td}>{r.released}</td>
                    <td className={`${td} font-semibold`}>{r.total}</td>
                    <td className={`${td} text-muted`}>{r.when}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
