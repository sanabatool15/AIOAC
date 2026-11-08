import { cn } from "@/lib/utils";

// The AIOAC mark and wordmark. Same markup the sidebar uses (flat brand square with an "A").
export function Logo({ className, markOnly }: { className?: string; markOnly?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span aria-hidden className="flex size-7 items-center justify-center rounded-lg bg-brand text-small font-semibold text-on-brand">
        A
      </span>
      {!markOnly && <span className="text-section text-ink">AIOAC</span>}
    </span>
  );
}
