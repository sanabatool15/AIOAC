"use client";
import { Lock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tag } from "@/components/ui/tag";
import { Skeleton } from "@/components/ui/state";
import { ApiError } from "@/lib/api";
import { getPublicResult } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { PUBLIC_NOT_AVAILABLE, toPublic } from "@/lib/screens";

// Public, view-only result page (/s/<token>). No sidebar, no login, no money or personal data.
export function PublicResultScreen({ token }: { token: string }) {
  const { data, error, loading, retry } = useAsync(() => getPublicResult(token), token);
  const v = data ? toPublic(data) : null;
  const gone = error instanceof ApiError && error.status === 404;

  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-surface px-8">
        <div className="flex items-center gap-2.5">
          <span aria-hidden className="size-6 rounded-md bg-brand" />
          <span className="text-section text-ink">AIOAC</span>
        </div>
        <Tag variant="neutral">Shared result · read only</Tag>
      </header>
      <main className="flex flex-1 justify-center px-6 pb-10 pt-8">
        <div className="flex w-full max-w-chat flex-col gap-4">
          {loading && !data ? (
            <div aria-busy="true" aria-label="Loading shared result" className="flex flex-col gap-4">
              <Skeleton className="h-14 w-72" />
              <Skeleton className="h-36" />
              <Skeleton className="h-28" />
            </div>
          ) : gone ? (
            <Card aria-label={PUBLIC_NOT_AVAILABLE} className="items-center gap-2 p-8 text-center">
              <Lock aria-hidden className="size-6 text-muted" />
              <h1 className="text-section text-ink">{PUBLIC_NOT_AVAILABLE}</h1>
              <p className="text-body text-muted">It may have been turned off by its owner, or the address is wrong.</p>
            </Card>
          ) : error || !v ? (
            <Card role="alert" className="items-center gap-3 p-8 text-center">
              <h1 className="text-section text-ink">We could not load this result</h1>
              <p className="text-body text-muted">{error?.message ?? "Please try again."}</p>
              <Button type="button" variant="outline" size="sm" onClick={retry}>
                Try again
              </Button>
            </Card>
          ) : (
            <>
              <div className="flex flex-col gap-1">
                <h1 className="text-title text-ink">{v.goal}</h1>
                <p className="text-body text-muted">A result shared with you. You can look, but not change anything.</p>
              </div>
              <Card aria-label="The data" className="gap-1.5 p-5">
                <p className="text-small font-medium text-muted">The data</p>
                <p className="text-section text-ink">{v.dataset ?? "Not chosen yet"}</p>
                {v.answerColumn && (
                  <p className="text-body text-ink-2">
                    Predicting: <span className="font-semibold">{v.answerColumn}</span>
                  </p>
                )}
              </Card>
              <Card aria-label="Free test" className="gap-1.5 p-5">
                <p className="text-small font-medium text-muted">Free test</p>
                <p className="text-body text-ink">{v.freeTest ? `On rows it had not seen: ${v.freeTest}.` : "The free test has not run yet."}</p>
              </Card>
              {v.verified ? (
                <Card variant={v.verified.passed ? "success" : "warning"} aria-label="Verified result" className="gap-2 p-5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-small font-medium text-muted">Verified result{v.versionLabel ? ` · ${v.versionLabel}` : ""}</p>
                    <Tag variant={v.verified.passed ? "success" : "warning"}>{v.verified.passed ? "Target reached" : "Target not reached"}</Tag>
                  </div>
                  <div className="flex gap-3">
                    <div className="flex min-w-px flex-1 flex-col gap-0.5 rounded-lg bg-surface p-3.5">
                      <p className="text-small font-medium text-muted">Checked result</p>
                      <p className="text-title text-ink">{v.verified.value}</p>
                    </div>
                    <div className="flex min-w-px flex-1 flex-col gap-0.5 rounded-lg bg-surface p-3.5">
                      <p className="text-small font-medium text-muted">Target</p>
                      <p className="text-title text-ink">{v.verified.target}</p>
                    </div>
                  </div>
                  <p className="text-body text-ink-2">
                    Checked once on test data the model never saw{v.finished ? `, ${v.finished}` : ""}.
                  </p>
                </Card>
              ) : (
                <Card aria-label="Verified result" className="gap-1.5 p-5">
                  <p className="text-small font-medium text-muted">Verified result</p>
                  <p className="text-body text-ink">There is no verified result yet.</p>
                </Card>
              )}
              <div className="flex items-center gap-2.5 rounded-lg border border-border bg-card p-3.5">
                <Lock aria-hidden size={16} className="shrink-0 text-muted" />
                <p className="min-w-px flex-1 text-body text-muted">{v.note}</p>
              </div>
            </>
          )}
          <p className="pt-2 text-center text-micro text-muted">Built with AIOAC</p>
        </div>
      </main>
    </div>
  );
}
