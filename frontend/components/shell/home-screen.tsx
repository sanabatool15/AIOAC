"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { startChat } from "@/lib/api-real";
import { Composer } from "./composer";
import { TopBar } from "./top-bar";

const examples = ["Which customers may stop buying?", "Will this loan be repaid?"];

// Chat home: the goal creates a project on the backend, then the project page takes over (and the assistant answers there).
export function HomeScreen() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function begin(goal: string) {
    if (!goal.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const { id } = await startChat(goal.trim());
      router.push(`/c/${id}`);
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : "Could not start. Please try again.");
    }
  }

  return (
    <section aria-label="Chat home" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar left={<h2 className="text-sm font-normal leading-[normal] text-muted">New project</h2>} />
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-5 px-6">
        <h1 className="flex flex-wrap items-center justify-center gap-2.5 text-[28px] leading-[normal]">
          <span className="font-medium text-muted">Hello, what do you want to</span>
          <span className="bg-brand-gradient bg-clip-text font-semibold text-transparent">predict?</span>
        </h1>
        <p className="max-w-[560px] text-center text-sm text-muted">
          Describe it in plain English. I will find or check your data and run a free test first. Nothing is
          charged until you approve a price.
        </p>
        <div className="w-[680px] max-w-full">
          <Composer
            busy={busy}
            placeholder="e.g. Predict which customers may stop buying next month"
            onSend={(t) => void begin(t)}
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div className="flex flex-wrap justify-center gap-2">
          {examples.map((s) => (
            <Button key={s} variant="outline" disabled={busy} onClick={() => void begin(s)}>
              {s}
            </Button>
          ))}
        </div>
      </div>
    </section>
  );
}
