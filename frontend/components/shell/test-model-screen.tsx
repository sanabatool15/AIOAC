"use client";
import { useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { EstimateNote } from "@/components/ui/estimate-note";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { outOf100 } from "@/lib/adapters";
import { getModel } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { BatchCard, OneRecord } from "./model-tab";
import { TopBar } from "./top-bar";

type Way = "one" | "csv";

const WAYS: { id: Way; label: string; hint: string }[] = [
  { id: "one", label: "One record", hint: "Fill in a single case and see the answer." },
  { id: "csv", label: "A CSV file", hint: "Upload many cases and download the answers." },
];

// Its own page: the model, then a way to try it. The form is built from the model's own columns, so it fits whatever was
// trained. Nothing here is charged.
export function TestModelScreen({ chatId }: { chatId: string }) {
  const { data, error, loading, retry } = useAsync(() => getModel(chatId), chatId);
  const [way, setWay] = useState<Way>("one");
  return (
    <section aria-label="Test your model" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar
        left={
          <Link href={`/c/${chatId}`} className="flex items-center gap-1.5 rounded-sm text-body text-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">
            <ArrowLeft aria-hidden className="size-4" />
            Back to chat
          </Link>
        }
      />
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto px-4 py-8 sm:px-8">
        <div className="flex h-fit w-full max-w-3xl flex-col gap-6">
          <header className="flex flex-col gap-1">
            <h1 className="text-title text-ink">Test your model</h1>
            <p className="text-body text-muted">Free. Nothing is charged for testing.</p>
          </header>
          {loading && !data ? (
            <div aria-busy="true" aria-label="Loading your model" className="flex flex-col gap-3">
              <Skeleton className="h-24" />
              <Skeleton className="h-64" />
            </div>
          ) : error || !data ? (
            <ErrorState message={error?.message ?? "The model could not be loaded."} onRetry={retry} />
          ) : !data.available ? (
            <EmptyState title="No model yet" body="A model is saved here when a training run finishes." />
          ) : !data.usable ? (
            <EmptyState title="This model cannot be tested here" body={`${data.unusable_reason ?? "The saved model could not be opened on this server."} You can still download it from the chat.`} />
          ) : (
            <>
              <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-5">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-section text-ink">Predicts &quot;{data.target}&quot;</h2>
                  <Tag variant="success">Ready</Tag>
                </div>
                <p className="text-body text-ink-2">
                  On test data it got about {outOf100(data.accuracy)} right. A simple guess gets {outOf100(data.simple_guess_accuracy)}.
                </p>
                <EstimateNote>Measured on held-back test rows. An estimate, not a promise.</EstimateNote>
              </div>
              <div role="tablist" aria-label="How to test" className="grid grid-cols-2 gap-1 rounded-lg bg-surface p-1">
                {WAYS.map((w) => (
                  <button
                    key={w.id}
                    type="button"
                    role="tab"
                    aria-selected={way === w.id}
                    onClick={() => setWay(w.id)}
                    className={cn(
                      "rounded-md py-2 text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
                      way === w.id ? "bg-card text-ink shadow-card" : "text-muted hover:text-ink",
                    )}
                  >
                    {w.label}
                  </button>
                ))}
              </div>
              <p className="-mt-3 text-small text-muted">{WAYS.find((w) => w.id === way)?.hint}</p>
              {way === "one" ? <OneRecord key="one" projectId={chatId} columns={data.columns} /> : <BatchCard key="csv" projectId={chatId} />}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
