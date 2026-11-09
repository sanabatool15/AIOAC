import { cn } from "@/lib/utils";

/** A ring that pops in, then a tick that draws itself. Motion is skipped for people who ask for less. */
export function SuccessCheck({ className }: { className?: string }) {
  return (
    <span aria-hidden className={cn("flex size-16 items-center justify-center rounded-full bg-success-soft text-success motion-safe:animate-pop", className)}>
      <svg viewBox="0 0 24 24" className="size-9" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 12.5l4.5 4.5L19 7.5" pathLength={1} strokeDasharray={1} className="motion-safe:animate-draw" />
      </svg>
    </span>
  );
}
