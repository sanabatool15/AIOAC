"use client";
import { Lock } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
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
          <span aria-hidden className="size-[26px] rounded-[7px] bg-brand-gradient shadow-glow" />
          <span className="text-base font-semibold leading-[normal] text-ink">AIOAC</span>
        </div>
        <Tag variant="muted">SHARED RESULT · READ ONLY</Tag>
      </header>
      <main className="flex flex-1 justify-center px-6 pb-10 pt-9">
        <div className="flex w-[720px] max-w-full flex-col gap-4">
          {loading && !data ? (
            <div aria-busy="true" aria-label="Loading shared result" className="flex flex-col gap-4">
              <Skeleton className="h-14 w-72" />
              <Skeleton className="h-[140px]" />
              <Skeleton className="h-[110px]" />
            </div>
          ) : gone ? (
            <Card aria-label={PUBLIC_NOT_AVAILABLE} className="items-center gap-2 p-8 text-center">
              <Lock aria-hidden className="size-6 text-pending" />
              <h1 className="text-xl font-semibold text-ink">{PUBLIC_NOT_AVAILABLE}</h1>
              <p className="text-sm text-muted">It may have been turned off by its owner, or the address is wrong.</p>
            </Card>
          ) : error || !v ? (
            <Card role="alert" className="items-center gap-3 p-8 text-center">
              <h1 className="text-xl font-semibold text-ink">We could not load this result</h1>
              <p className="text-sm text-muted">{error?.message ?? "Please try again."}</p>
              <button type="button" onClick={retry} className="text-sm font-semibold text-brand-ink underline">
                Try again
              </button>
            </Card>
          ) : (
            <>
              <div className="flex flex-col gap-1 leading-[normal]">
                <h1 className="text-[28px] font-semibold text-ink">{v.goal}</h1>
                <p className="text-sm text-muted">A result shared with you. You can look, but not change anything.</p>
              </div>
              <Card aria-label="The data" className="gap-1.5 p-5">
                <p className="text-xs font-semibold text-muted">THE DATA</p>
                <p className="text-base font-semibold text-ink">{v.dataset ?? "Not chosen yet"}</p>
                {v.answerColumn && (
                  <p className="text-sm text-ink-2">
                    Predicting: <span className="font-semibold">{v.answerColumn}</span>
                  </p>
                )}
              </Card>
              <Card aria-label="Free test" className="gap-1.5 p-5">
                <p className="text-xs font-semibold text-muted">FREE TEST</p>
                <p className="text-sm text-ink">{v.freeTest ? `On rows it had not seen: ${v.freeTest}.` : "The free test has not run yet."}</p>
              </Card>
              {v.verified ? (
                <Card variant={v.verified.passed ? "green" : "amber"} aria-label="Verified result" className="gap-2 p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold text-muted">VERIFIED RESULT{v.versionLabel ? ` · ${v.versionLabel.toUpperCase()}` : ""}</p>
                    <Tag variant={v.verified.passed ? "success" : "muted"}>{v.verified.passed ? "TARGET REACHED" : "TARGET NOT REACHED"}</Tag>
                  </div>
                  <div className="flex gap-3">
                    <div className="flex min-w-px flex-1 flex-col gap-0.5 rounded-xl bg-surface p-3.5">
                      <p className="text-xs font-semibold text-muted">CHECKED RESULT</p>
                      <p className="text-xl font-semibold text-ink">{v.verified.value}</p>
                    </div>
                    <div className="flex min-w-px flex-1 flex-col gap-0.5 rounded-xl bg-surface p-3.5">
                      <p className="text-xs font-semibold text-muted">TARGET</p>
                      <p className="text-xl font-semibold text-ink">{v.verified.target}</p>
                    </div>
                  </div>
                  <p className="text-sm text-ink-2">
                    Checked once on test data the model never saw{v.finished ? `, ${v.finished}` : ""}.
                  </p>
                </Card>
              ) : (
                <Card aria-label="Verified result" className="gap-1.5 p-5">
                  <p className="text-xs font-semibold text-muted">VERIFIED RESULT</p>
                  <p className="text-sm text-ink">There is no verified result yet.</p>
                </Card>
              )}
              <div className="flex items-center gap-2.5 rounded-lg border border-border bg-card p-3.5 shadow-btn-neutral">
                <Lock aria-hidden size={16} className="shrink-0 text-muted" />
                <p className="min-w-px flex-1 text-sm leading-[normal] text-muted">{v.note}</p>
              </div>
            </>
          )}
          <p className="pt-2 text-center text-xs text-muted">Built with AIOAC</p>
        </div>
      </main>
    </div>
  );
}
