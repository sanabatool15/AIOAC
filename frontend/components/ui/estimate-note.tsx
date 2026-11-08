import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

export const ESTIMATE_NOTE_TEXT = "These figures are estimates, not promises.";

/** The one place a screen says its numbers are estimates. Use once per screen. */
export function EstimateNote({ children = ESTIMATE_NOTE_TEXT, className }: { children?: React.ReactNode; className?: string }) {
  return (
    <p className={cn("flex items-start gap-1.5 text-small text-muted", className)}>
      <Info aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      <span>{children}</span>
    </p>
  );
}
