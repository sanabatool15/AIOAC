"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
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
        <div className="flex w-full max-w-chat flex-col gap-4">
          <PageHeader
            title="What do you want to predict?"
            subtitle="Describe it in plain English. We run a free test first, and nothing is charged until you approve a price."
          />
          <Composer
            busy={busy}
            placeholder="e.g. Predict which customers may stop buying next month"
            onSend={(t) => void begin(t)}
          />
          {error && (
            <p role="alert" className="text-body text-danger">
              {error}
            </p>
          )}
          <div className="flex flex-col gap-2">
            <p className="text-small text-muted">Or start from an example</p>
            <div className="flex flex-wrap gap-2">
              {examples.map((s) => (
                <Button key={s} variant="outline" size="sm" disabled={busy} onClick={() => void begin(s)}>
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
