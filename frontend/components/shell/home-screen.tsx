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
      <TopBar left={<p className="text-body text-muted">New chat</p>} />
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto px-4 py-8 sm:px-6">
        <div className="flex w-full max-w-chat flex-col gap-4 text-center">
          <header className="flex flex-col items-center gap-1.5">
            <h1 className="text-title text-ink motion-safe:animate-rise">What do you want to predict?</h1>
            <p className="max-w-md text-body text-muted motion-safe:animate-rise" style={{ animationDelay: "120ms" }}>
              Describe it in plain English. We run a free test first, and nothing is charged until you approve a price.
            </p>
          </header>
          <div className="text-left motion-safe:animate-rise" style={{ animationDelay: "260ms" }}>
          <Composer
            busy={busy}
            placeholder="e.g. Predict which customers may stop buying next month"
            onSend={(t) => void begin(t)}
          />
          </div>
          {error && (
            <p role="alert" className="text-body text-danger">
              {error}
            </p>
          )}
          <div className="flex flex-col items-center gap-2">
            <p className="text-small text-muted motion-safe:animate-rise" style={{ animationDelay: "400ms" }}>
              Or start from an example
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {examples.map((s, i) => (
                <Button key={s} variant="outline" size="sm" disabled={busy} onClick={() => void begin(s)} className="motion-safe:animate-rise" style={{ animationDelay: `${520 + i * 120}ms` }}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
