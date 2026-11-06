"use client";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { getUsage } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { toUsage } from "@/lib/screens";
import { TopBar } from "./top-bar";

// Usage: what the signed-in user has used, from GET /account/usage. Read-only, plain words.
export function UsageScreen() {
  const { data, error, loading, retry } = useAsync(() => getUsage());
  const v = toUsage(data);
  return (
    <section aria-label="Usage" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<h2 className="text-sm font-normal leading-[normal] whitespace-pre text-muted">{"Account  /  Usage"}</h2>} />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        <div className="flex items-center gap-4">
          <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
            <h1 className="text-[28px] font-semibold text-ink">Usage</h1>
            <p className="text-sm text-muted">What you have used so far. Payments here are PayPal sandbox test money.</p>
          </div>
          <Link href="/account/billing" className="text-sm font-semibold text-brand-ink underline">
            Billing history
          </Link>
        </div>
        {loading && !data ? (
          <div aria-busy="true" aria-label="Loading usage" className="grid grid-cols-3 gap-4">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-[104px]" />
            ))}
          </div>
        ) : error || !v ? (
          <ErrorState message={error?.message ?? "Usage unavailable."} onRetry={retry} />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="usage-tiles">
              {v.tiles.map((t, i) => (
                <Card key={t.label} variant={i === 2 || i === 3 ? "peach" : i === 4 ? "mint" : "plain"} className="gap-1 p-5">
                  <p className="text-xs font-semibold text-muted">{t.label.toUpperCase()}</p>
                  <p className="text-[28px] font-semibold leading-[normal] text-ink">{t.value}</p>
                  {t.note && <p className="text-xs text-muted">{t.note}</p>}
                </Card>
              ))}
            </div>
            <Card aria-label="Recent activity" className="gap-3 p-5">
              <h2 className="text-base font-semibold text-ink">Recent activity</h2>
              {v.activity.length === 0 ? (
                <EmptyState icon={<span>·</span>} title="Nothing yet" body="Start a project and it will show up here." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {v.activity.map((a) => (
                    <li key={a.key} className="flex items-start gap-3 text-sm leading-5">
                      <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-[4px] bg-brand-gradient" />
                      <span className="min-w-px flex-1 text-ink">{a.text}</span>
                      <time className="shrink-0 text-xs text-muted">{a.when}</time>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </>
        )}
      </div>
    </section>
  );
}
