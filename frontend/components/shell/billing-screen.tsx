"use client";
import { useState } from "react";
import { Receipt } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Chip } from "@/components/ui/chip";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import { getBilling } from "@/lib/mock-api";
import type { BillingRow, BillingStatus } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PaymentMethodsTab } from "./payment-methods-tab";
import { TopBar } from "./top-bar";

const TABS = ["Invoices and receipts", "Payment methods"] as const;
const FILTERS = ["All", "Plan invoices", "Job receipts", "Voided"] as const;
type Filter = (typeof FILTERS)[number];

const STATUS: Record<
  BillingStatus,
  { label: string; variant: "success" | "muted" }
> = {
  paid: { label: "Paid", variant: "success" },
  captured: { label: "Captured", variant: "success" },
  voided: { label: "Voided", variant: "muted" },
  released: { label: "Released", variant: "muted" },
  free: { label: "Free", variant: "muted" },
};
const matches = (r: BillingRow, f: Filter) =>
  f === "All" ||
  (f === "Plan invoices" && r.type === "plan") ||
  (f === "Job receipts" && r.type === "job") ||
  (f === "Voided" && (r.status === "voided" || r.status === "released"));

const cell = "px-3.5 py-[13px] text-sm leading-[normal]";

// Screen 26 (invoices and receipts tab) + 33 (payment methods tab) of Billing and invoices.
export function BillingScreen() {
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(() => getBilling());
  const [tab, setTab] = useState<(typeof TABS)[number]>(TABS[0]);
  const [filter, setFilter] = useState<Filter>("All");
  const [picked, setPicked] = useState<string | null>(null);

  const rows = (data?.rows ?? []).filter((r) => matches(r, filter));
  const selectedId = picked ?? data?.selectedId ?? "";
  const detail = data?.details[selectedId];

  function exportCsv() {
    if (!data) return;
    const head = "Date,Type,Description,Amount,Status";
    const body = data.rows.map((r) =>
      [r.date, r.typeLabel, r.description, r.amount, STATUS[r.status].label]
        .map((v) => `"${v.replaceAll('"', '""')}"`)
        .join(","),
    );
    const url = URL.createObjectURL(
      new Blob([[head, ...body].join("\n")], { type: "text/csv" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "aioac-billing.csv";
    a.click();
    URL.revokeObjectURL(url);
    toast(`Exported ${data.rows.length} rows.`);
  }

  return (
    <section
      aria-label="Billing and invoices"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        shareStyle="chip"
        left={
          <h2 className="text-sm font-normal leading-[normal] whitespace-pre text-muted">
            {"Account  /  Billing and invoices"}
          </h2>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-8">
        <div className="flex items-center gap-4">
          <div className="flex min-w-px flex-1 flex-col gap-1 leading-[normal]">
            <h1 className="text-[28px] font-semibold text-ink">
              Billing and invoices
            </h1>
            <p className="text-sm text-muted">
              Plan invoices, job receipts and saved payment methods.
            </p>
          </div>
          {tab === TABS[1] && (
            <Button
              size="md"
              className="rounded-[9px]"
              onClick={() =>
                toast("Adding a method opens PayPal's hosted form (mocked).")
              }
            >
              + Add payment method
            </Button>
          )}
          {tab === TABS[0] && (
            <Button
              variant="outline"
              size="md"
              disabled={!data || data.rows.length === 0}
              onClick={exportCsv}
            >
              Download all (CSV)
            </Button>
          )}
        </div>
        <div
          role="tablist"
          aria-label="Billing tabs"
          className="flex gap-[22px] border-b border-border"
        >
          {TABS.map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={cn(
                "border-b-2 pb-2.5 pt-2 text-sm leading-[normal] whitespace-nowrap outline-offset-2 focus-visible:outline-2 focus-visible:outline-brand",
                tab === t
                  ? "border-brand font-semibold text-ink"
                  : "border-transparent text-muted hover:text-ink",
              )}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === TABS[1] ? (
          <PaymentMethodsTab />
        ) : loading && !data ? (
          <div
            aria-busy="true"
            aria-label="Loading billing"
            className="flex flex-col gap-4"
          >
            <Skeleton className="h-9 w-80" />
            <Skeleton className="h-[260px]" />
          </div>
        ) : error || !data ? (
          <ErrorState
            message={error?.message ?? "Billing unavailable."}
            onRetry={retry}
          />
        ) : data.rows.length === 0 ? (
          <EmptyState
            icon={<Receipt />}
            title="No invoices yet"
            body="Plan invoices and job receipts appear here."
          />
        ) : (
          <>
            <div
              role="group"
              aria-label="Filter"
              className="flex items-start gap-2"
            >
              {FILTERS.map((f) => (
                <Chip
                  key={f}
                  variant={filter === f ? "primary" : "outline"}
                  aria-pressed={filter === f}
                  onClick={() => setFilter(f)}
                >
                  {f}
                </Chip>
              ))}
            </div>
            <div className="flex items-start gap-4">
              <div className="min-w-px flex-1 overflow-clip rounded-xl border border-border bg-card shadow-card">
                {rows.length === 0 ? (
                  <EmptyState
                    icon={<Receipt />}
                    title="Nothing here"
                    body="No rows match this filter."
                  />
                ) : (
                  <table className="w-full table-fixed border-collapse text-left">
                    <caption className="sr-only">Invoices and receipts</caption>
                    <thead className="bg-surface text-muted">
                      <tr>
                        {[
                          ["Date", "w-[116px]"],
                          ["Type", "w-[116px]"],
                          ["Description", ""],
                          ["Amount", "w-[84px]"],
                          ["Status", "w-[96px]"],
                          ["File", "w-[72px]"],
                        ].map(([h, w]) => (
                          <th
                            key={h}
                            scope="col"
                            className={cn(cell, "font-semibold", w)}
                          >
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr
                          key={r.id}
                          data-selected={selectedId === r.id}
                          className={cn(
                            "border-b border-border text-ink last:border-b-0",
                            selectedId === r.id && "bg-surface/60",
                          )}
                        >
                          <td className={cell}>
                            <button
                              type="button"
                              aria-pressed={selectedId === r.id}
                              aria-label={`Show receipt for ${r.description}`}
                              onClick={() => setPicked(r.id)}
                              className="rounded text-left outline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-brand"
                            >
                              {r.date}
                            </button>
                          </td>
                          <td className={cell}>{r.typeLabel}</td>
                          <td className={cell}>{r.description}</td>
                          <td className={cell}>{r.amount}</td>
                          <td className={cell}>
                            <Tag variant={STATUS[r.status].variant}>
                              {STATUS[r.status].label}
                            </Tag>
                          </td>
                          <td className={cell}>
                            <button
                              type="button"
                              aria-label={`Download PDF for ${r.description}`}
                              onClick={() =>
                                toast("PDF download is mocked in this build.")
                              }
                              className="rounded outline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-brand"
                            >
                              PDF
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              {detail && (
                <Card
                  variant="mint"
                  className="w-[300px] shrink-0 gap-1.5 overflow-clip"
                  aria-label="Receipt detail"
                  data-testid="receipt-detail"
                >
                  <h2 className="text-xs font-semibold leading-[normal] text-muted">
                    RECEIPT DETAIL
                  </h2>
                  <p className="text-base font-semibold leading-[normal] text-ink">
                    {detail.title}
                  </p>
                  <p className="text-sm leading-[normal] text-muted">
                    {detail.subtitle}
                  </p>
                  <hr className="h-px border-0 bg-border" />
                  <dl>
                    {detail.rows.map(([k, v]) => (
                      <div
                        key={k}
                        className={cn(
                          "flex items-start justify-between py-[5px] text-sm leading-[normal] whitespace-nowrap",
                          k === detail.strong && "font-semibold text-ink",
                        )}
                      >
                        <dt className={k === detail.strong ? "" : "text-muted"}>
                          {k}
                        </dt>
                        <dd
                          className={
                            k === detail.strong ? "" : "font-medium text-ink"
                          }
                        >
                          {v}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  <Button
                    variant="outline"
                    size="md"
                    className="w-full"
                    onClick={() =>
                      toast("PDF download is mocked in this build.")
                    }
                  >
                    Download PDF
                  </Button>
                </Card>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
