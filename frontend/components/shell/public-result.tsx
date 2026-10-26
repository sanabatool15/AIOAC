"use client";
import Link from "next/link";
import { Lock } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useAsync } from "@/lib/hooks";
import { getPublicResult } from "@/lib/mock-api";
import { cn } from "@/lib/utils";
import { MoneyRecap, VerificationCard } from "./verified-chat";

// Screen 27: public, view-only result page. No sidebar, no sign-in. Shows results only.
export function PublicResultScreen({ shareId }: { shareId: string }) {
  const { data, error, loading, retry } = useAsync(
    () => getPublicResult(shareId),
    shareId,
  );

  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-surface px-8">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="size-[26px] rounded-[7px] bg-brand-gradient shadow-glow"
          />
          <span className="text-base font-semibold leading-[normal] text-ink">
            AIOAC
          </span>
          <Tag variant="muted">SHARED RESULT · VIEW ONLY</Tag>
        </div>
        <div className="flex items-center gap-2.5">
          <Link
            href="/login"
            className={buttonVariants({ variant: "outline", size: "md" })}
          >
            Log in
          </Link>
          <Link
            href="/signup"
            className={cn(buttonVariants({ size: "md" }), "rounded-[9px]")}
          >
            Train your own
          </Link>
        </div>
      </header>
      <main className="flex flex-1 justify-center px-6 pb-10 pt-9">
        <div className="flex w-[760px] max-w-full flex-col gap-4">
          {loading && !data ? (
            <div
              aria-busy="true"
              aria-label="Loading shared result"
              className="flex flex-col gap-4"
            >
              <Skeleton className="h-14 w-72" />
              <Skeleton className="h-[184px]" />
              <Skeleton className="h-[116px]" />
              <Skeleton className="h-[128px]" />
            </div>
          ) : error || !data ? (
            <ErrorState
              message={error?.message ?? "This shared result is unavailable."}
              onRetry={retry}
            />
          ) : (
            <>
              <div className="flex items-center gap-3">
                <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
                  <h1 className="text-[28px] font-semibold text-ink">
                    {data.title}
                  </h1>
                  <p className="text-sm text-muted">{data.byline}</p>
                </div>
                <Tag variant="brand">{data.badge}</Tag>
              </div>
              <VerificationCard run={data.verification} />
              <MoneyRecap
                recap={data.money}
                title="THE MONEY, IN PLAIN NUMBERS"
                className="gap-2.5 p-5"
              />
              <section
                aria-label="How it was checked"
                className="flex flex-col gap-2 overflow-clip rounded-xl border border-border bg-card p-5 shadow-card-tight"
              >
                <h2 className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
                  HOW IT WAS CHECKED
                </h2>
                {data.checks.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center gap-2.5 text-sm leading-[normal] text-ink"
                  >
                    <span
                      aria-hidden
                      className="size-[18px] shrink-0 rounded-[9px] bg-brand-gradient"
                    />
                    <span className="min-w-px flex-1">{c.label}</span>
                  </div>
                ))}
              </section>
              <div className="flex items-center gap-2.5 overflow-clip rounded-lg border border-border bg-card p-3.5 shadow-btn-neutral">
                <Lock aria-hidden size={16} className="shrink-0 text-muted" />
                <p className="min-w-px flex-1 text-sm leading-[normal] text-muted">
                  {data.privacyNote}
                </p>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
