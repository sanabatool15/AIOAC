"use client";
import { Inbox } from "lucide-react";
import { Card, type CardProps } from "@/components/ui/card";
import { LinkButton } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { getUsage } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { toUsage } from "@/lib/screens";
import { TopBar } from "./top-bar";

// Colour carries meaning: money taken is highlighted, money given back is success, counts stay plain.
const TILE_VARIANT: Record<string, CardProps["variant"]> = {
  "Released back to you": "success",
};

// Usage: what the signed-in user has used, from GET /account/usage. Read-only, plain words.
export function UsageScreen() {
  const { data, error, loading, retry } = useAsync(() => getUsage());
  const v = toUsage(data);
  return (
    <section aria-label="Usage" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-body text-muted"><span>Account</span><span aria-hidden>/</span><span aria-current="page" className="text-ink">Usage</span></nav>} />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 sm:p-8">
        <PageHeader
          title="Usage"
          subtitle="What you have used so far. Payments here are PayPal sandbox test money."
          actions={
            <LinkButton href="/account/billing" variant="outline" size="sm">
              Billing history
            </LinkButton>
          }
        />
        {loading && !data ? (
          <div aria-busy="true" aria-label="Loading usage" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : error || !v ? (
          <ErrorState message={error?.message ?? "Usage unavailable."} onRetry={retry} />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="usage-tiles">
              {v.tiles.map((t) => (
                <Card key={t.label} variant={TILE_VARIANT[t.label] ?? "plain"} className="gap-1 p-5">
                  <p className="text-small text-muted">{t.label}</p>
                  <p className="text-title text-ink tabular-nums">{t.value}</p>
                  {t.note && <p className="text-micro text-muted">{t.note}</p>}
                </Card>
              ))}
            </div>
            <Card aria-label="Recent activity" className="gap-3 p-5">
              <h2 className="text-section text-ink">Recent activity</h2>
              {v.activity.length === 0 ? (
                <EmptyState icon={Inbox} title="Nothing yet" body="Start a chat and it will show up here." />
              ) : (
                <ul className="flex flex-col gap-2">
                  {v.activity.map((a) => (
                    <li key={a.key} className="flex items-start gap-3 text-body">
                      <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-sm bg-brand" />
                      <span className="min-w-0 flex-1 text-ink">{a.text}</span>
                      <time className="shrink-0 text-micro text-muted">{a.when}</time>
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
