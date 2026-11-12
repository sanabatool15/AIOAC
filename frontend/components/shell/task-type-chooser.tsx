"use client";
import { useState } from "react";
import { BarChart3, CalendarClock, Hash, Layers, SearchX } from "lucide-react";
import type { TaskType } from "@/lib/api";
import * as real from "@/lib/api-real";
import { cn } from "@/lib/utils";
import { ErrorLine, useAction } from "./step-parts";

export interface TaskChoice {
  id: TaskType;
  title: string;
  hint: string;
  needsTarget: boolean;
  icon: typeof Hash;
}

// What the user wants to find out, in plain words. The ids go to the server; nothing here says "regression" or "clustering".
export const TASK_CHOICES: TaskChoice[] = [
  { id: "classification", title: "A yes or no, or a few groups", hint: "Will this customer leave? Which type is it?", needsTarget: true, icon: BarChart3 },
  { id: "regression", title: "A number", hint: "What price will this sell for?", needsTarget: true, icon: Hash },
  { id: "forecast", title: "A number over time", hint: "How many will we sell next month? Needs a date column.", needsTarget: true, icon: CalendarClock },
  { id: "grouping", title: "Find natural groups", hint: "What kinds of customers do I have? No answer column needed.", needsTarget: false, icon: Layers },
  { id: "unusual", title: "Find unusual records", hint: "Which payments look strange? No answer column needed.", needsTarget: false, icon: SearchX },
];

// Pick the kind of prediction before bringing data. A click tells the server (free, and only possible before data is chosen).
export function TaskTypeChooser({ projectId, value, onChange }: { projectId: string; value: TaskType; onChange: (t: TaskChoice) => void }) {
  const { busy, error, run } = useAction();
  const [pending, setPending] = useState<TaskType | null>(null);
  return (
    <fieldset className="flex flex-col gap-2" disabled={busy} aria-label="What do you want to find out?">
      <legend className="mb-1 text-body font-medium text-ink">What do you want to find out?</legend>
      <div className="grid gap-2">
        {TASK_CHOICES.map((c) => {
          const on = (pending ?? value) === c.id;
          return (
            <label
              key={c.id}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border bg-card p-3 text-left transition-colors focus-within:ring-2 focus-within:ring-brand",
                on ? "border-brand bg-brand-tint" : "border-border hover:border-brand",
              )}
            >
              <input
                type="radio"
                name="task-type"
                className="sr-only"
                checked={on}
                onChange={() => {
                  setPending(c.id);
                  void run(async () => {
                    await real.setTaskType(projectId, c.id);
                    onChange(c);
                  }).finally(() => setPending(null));
                }}
              />
              <c.icon aria-hidden className="mt-0.5 size-5 shrink-0 text-brand" />
              <span className="flex min-w-0 flex-col">
                <span className="text-body font-medium text-ink">{c.title}</span>
                <span className="text-small text-muted">{c.hint}</span>
              </span>
            </label>
          );
        })}
      </div>
      <ErrorLine message={error} />
    </fieldset>
  );
}
