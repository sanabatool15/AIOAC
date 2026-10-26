"use client";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { startChat } from "@/lib/mock-api";
import { getFirstRunSnapshot, subscribeSession } from "@/lib/session";
import { FirstRunScreen } from "./first-run-screen";
import { Composer } from "./composer";
import { TopBar } from "./top-bar";

const suggestions = [
  "Which customers may stop buying?",
  "Will this loan be repaid?",
];

// Screen 2: Chat home. Any prompt (typed or from a chip) starts a new chat and opens it.
export function HomeScreen() {
  // New users (just signed up, nothing started yet) get the first-run layout (screen 35).
  const firstRun = useSyncExternalStore(
    subscribeSession,
    getFirstRunSnapshot,
    () => false,
  );
  return firstRun ? <FirstRunScreen /> : <ReturningHome />;
}

function ReturningHome() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState<(() => void) | null>(null);

  function begin(text: string, opts: { sample?: boolean } = {}) {
    setBusy(true);
    setRetry(null);
    startChat(text, opts)
      .then(({ id }) => router.push(`/c/${id}`))
      .catch(() => {
        setBusy(false);
        setRetry(() => () => begin(text, opts));
      });
  }

  return (
    <section
      aria-label="Chat home"
      className="flex h-full min-w-0 flex-1 flex-col bg-bg"
    >
      <TopBar
        shareStyle="chip"
        left={
          <p className="flex items-center gap-2 whitespace-pre text-sm text-muted">
            Churn prediction<span aria-hidden> / </span>New chat
          </p>
        }
      />
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-[22px] overflow-y-auto px-6">
        {/* Figma node "Orb placeholder" (76:451) image, public/images/avatar-1.png */}
        <div className="size-[110px] shrink-0 overflow-hidden rounded-full bg-orb-bg">
          <Image
            src="/images/avatar-1.png"
            alt=""
            width={110}
            height={110}
            priority
            className="size-full rounded-full object-cover"
          />
        </div>
        <h1 className="flex flex-wrap items-center justify-center gap-2.5 text-[28px] leading-[normal]">
          <span className="font-medium text-muted">
            Hello, what do you want to
          </span>
          <span className="font-semibold text-ink">predict?</span>
        </h1>
        <p className="text-center text-sm leading-[normal] text-muted">
          Describe it in plain English. I will check your data and train a free
          baseline first.
        </p>
        <div className="w-[680px] max-w-full">
          <Composer
            busy={busy}
            placeholder="e.g. Predict which customers may stop buying next month"
            onSend={(text) => begin(text)}
          />
        </div>
        {retry && (
          <p
            role="alert"
            className="flex items-center gap-3 text-sm text-danger"
          >
            Could not start the chat.
            <Button variant="outline" onClick={retry}>
              Try again
            </Button>
          </p>
        )}
        <div className="flex flex-wrap items-start justify-center gap-2">
          {suggestions.map((s) => (
            <Chip key={s} disabled={busy} onClick={() => begin(s)}>
              {s}
            </Chip>
          ))}
          <Chip
            variant="primary"
            disabled={busy}
            onClick={() =>
              begin("Use the sample telco churn data", { sample: true })
            }
          >
            Try sample data
          </Chip>
        </div>
      </div>
    </section>
  );
}
