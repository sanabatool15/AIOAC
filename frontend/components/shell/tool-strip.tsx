import type { ToolId, ToolState } from "@/lib/types";
import { cn } from "@/lib/utils";

const TOOLS: { id: ToolId; label: string }[] = [
  { id: "tools", label: "Tools" },
  { id: "browser", label: "Browser" },
  { id: "research", label: "Research" },
  { id: "training", label: "Training" },
  { id: "payment", label: "Payment" },
];

// Pills showing which agent tools are idle / running / done (screens 8 and 10).
export function ToolStrip({ tools }: { tools: Record<ToolId, ToolState> }) {
  return (
    <ul
      aria-label="Tool activity"
      className="flex flex-wrap content-start items-start gap-2"
    >
      {TOOLS.map(({ id, label }) => {
        const state = tools[id];
        return (
          <li
            key={id}
            data-state={state}
            className={cn(
              "flex items-center overflow-clip px-3 py-1.5 text-sm font-semibold leading-[normal] whitespace-nowrap",
              state === "running" &&
                "rounded-2xl border-4 border-border bg-brand-gradient text-white shadow-glow",
              state === "done" &&
                "rounded-2xl border border-brand bg-surface text-ink",
              state !== "running" &&
                state !== "done" &&
                "rounded-[14.5px] border border-border bg-white text-muted shadow-btn-neutral",
            )}
          >
            {label}
          </li>
        );
      })}
    </ul>
  );
}
