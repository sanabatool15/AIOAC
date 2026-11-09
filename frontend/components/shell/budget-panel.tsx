"use client";
import Link from "next/link";
import { Wallet } from "lucide-react";
import type { BProject } from "@/lib/api";
import { payPill } from "@/lib/pay-timeline";
import { cn } from "@/lib/utils";

const TONE = {
  primary: "border-brand bg-brand text-on-brand hover:opacity-90",
  ok: "border-success-line bg-success-soft text-success",
  warn: "border-warning-line bg-warning-soft text-warning",
  quiet: "border-border bg-card text-ink-2 hover:bg-surface",
} as const;

// Always in the top bar. It says where the money stands and takes you to the payment page. It never moves money itself.
export function BudgetButton({ project }: { project: BProject }) {
  const pill = payPill(project);
  return (
    <Link
      href={`/c/${project.id}/pay`}
      aria-label={`Payment: ${pill.label}`}
      className={cn("inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-body font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand", TONE[pill.tone])}
    >
      <Wallet aria-hidden className="size-4" />
      {pill.label}
    </Link>
  );
}
