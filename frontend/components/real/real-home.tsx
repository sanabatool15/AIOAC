"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { startChat } from "@/lib/api-real";

const examples = ["Which customers may stop buying?", "Will this loan be repaid?"];

// Screen 2 in real mode: the goal creates a project on the backend, then the project page takes over.
export function RealHome() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function begin(goal: string) {
    if (!goal.trim()) return;
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
    <section aria-label="Chat home" className="flex h-full min-w-0 flex-1 flex-col items-center justify-center gap-5 bg-bg px-6">
      <h1 className="flex flex-wrap items-center justify-center gap-2.5 text-[28px] leading-[normal]">
        <span className="font-medium text-muted">Hello, what do you want to</span>
        <span className="font-semibold text-ink">predict?</span>
      </h1>
      <p className="text-center text-sm text-muted">
        Describe it in plain English. I will check your data and run a free test first.
      </p>
      <form
        className="flex w-[680px] max-w-full flex-col gap-2 rounded-2xl border border-border bg-card p-3 shadow-composer"
        onSubmit={(e) => {
          e.preventDefault();
          void begin(text);
        }}
      >
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Predict which customers may stop buying next month"
          aria-label="What do you want to predict?"
          className="w-full resize-none bg-transparent text-[15px] leading-[22px] text-ink outline-none placeholder:text-muted"
        />
        <div className="flex justify-end">
          <Button type="submit" size="md" disabled={busy || !text.trim()}>
            {busy ? "Starting…" : "Start"}
          </Button>
        </div>
      </form>
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
    </section>
  );
}
