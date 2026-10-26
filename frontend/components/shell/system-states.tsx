"use client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

// Screen 18: reference sheet of every system state (errors, warnings, empty, loading, success).
// Each card is the pattern the real screens follow; the buttons are demos.

function StateCard({
  tag,
  variant = "plain",
  children,
}: {
  tag: string;
  variant?: "red" | "amber" | "plain" | "green";
  children: React.ReactNode;
}) {
  return (
    <Card
      variant={variant}
      aria-label={tag.toLowerCase()}
      role="group"
      className="min-w-px flex-1 gap-2.5 overflow-clip p-[18px] shadow-card-tight"
    >
      <Tag className="self-start">{tag}</Tag>
      {children}
    </Card>
  );
}

const title = "text-sm font-semibold leading-[normal] text-ink";
const body = "text-sm leading-[19px] text-muted";

function Bar({ pct, tone }: { pct: number; tone: "brand" | "muted" }) {
  return (
    <div className="h-2 w-[300px] max-w-full overflow-clip rounded-[4px] bg-surface">
      <div
        className={cn(
          "h-2 rounded-[4px]",
          tone === "brand" ? "bg-brand-gradient" : "bg-bar-target",
        )}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function SystemStates() {
  const toast = useToast();
  const demo = (what: string) => () => toast(`${what} (demo)`);
  return (
    <div className="flex min-h-full flex-col gap-5 bg-bg px-10 py-9">
      <div className="flex flex-col gap-1 leading-[normal]">
        <h1 className="text-[28px] font-semibold text-ink">System states</h1>
        <p className="text-sm text-muted">
          Every moment where something is loading, failing or empty has a
          designed state.
        </p>
      </div>

      <div className="flex items-start gap-4">
        <StateCard tag="UPLOAD FAILED" variant="red">
          <p className={title}>churn.csv could not be read</p>
          <p className={body}>
            The file has no header row. Add one and try again.
          </p>
          <div className="flex gap-2">
            <Button size="md" onClick={demo("Fix and retry")}>
              Fix and retry
            </Button>
            <Button
              variant="outline"
              size="md"
              onClick={demo("Choose another")}
            >
              Choose another
            </Button>
          </div>
        </StateCard>
        <StateCard tag="CONNECTION ERROR" variant="red">
          <p className={title}>Kaggle token expired</p>
          <p className={body}>Reconnect to keep syncing. Retrying in 20 s.</p>
          <div>
            <Button size="md" onClick={demo("Reconnect")}>
              Reconnect
            </Button>
          </div>
        </StateCard>
        <StateCard tag="PAYPAL DECLINED" variant="red">
          <p className={title}>PayPal could not hold $40</p>
          <p className={body}>
            Nothing was charged. Try another payment method.
          </p>
          <div>
            <Button size="md" onClick={demo("Try again")}>
              Try again
            </Button>
          </div>
        </StateCard>
      </div>

      <div className="flex items-start gap-4">
        <StateCard tag="BUDGET ALMOST USED" variant="amber">
          <p className={cn(title, "leading-5")}>
            Experiment 1 used $13.20 of its $14 limit
          </p>
          <Bar pct={94} tone="brand" />
          <p className={body}>
            I will stop and decide. The backend blocks any overspend.
          </p>
        </StateCard>
        <StateCard tag="SLOW JOB" variant="amber">
          <p className={title}>Taking longer than expected</p>
          <p className={body}>
            Still running. New estimate: about 4 more minutes.
          </p>
          <Bar pct={70} tone="muted" />
          <div className="flex gap-2">
            <Button size="md" onClick={demo("Keep waiting")}>
              Keep waiting
            </Button>
            <Button variant="outline" size="md" onClick={demo("Stop job")}>
              Stop job
            </Button>
          </div>
        </StateCard>
        <StateCard tag="JOB FAILED" variant="red">
          <p className={title}>Training failed on our side</p>
          <p className={body}>
            Your hold was voided automatically. You pay $0.
          </p>
          <div>
            <Button size="md" onClick={demo("Retry for free")}>
              Retry for free
            </Button>
          </div>
        </StateCard>
      </div>

      <div className="flex items-start gap-4">
        <StateCard tag="EMPTY PROJECT">
          <div className="flex w-full flex-col items-center gap-1.5 rounded-[10px] border border-dashed border-border bg-surface p-4">
            <p className={title}>No chats yet</p>
            <Button size="md" onClick={demo("Try sample data")}>
              Try sample data
            </Button>
          </div>
        </StateCard>
        <StateCard tag="LOADING">
          <div aria-busy="true" className="flex flex-col gap-2.5">
            {[300, 240, 270, 165].map((w) => (
              <div
                key={w}
                className="h-2.5 max-w-full rounded-[5px] bg-surface"
                style={{ width: w }}
              />
            ))}
          </div>
          <p className="text-sm leading-[normal] text-muted">
            Loading results...
          </p>
        </StateCard>
        <StateCard tag="SUCCESS TOAST" variant="green">
          <div className="flex w-full items-center gap-2.5 rounded-[10px] bg-brand-gradient p-3 shadow-glow">
            <span
              aria-hidden
              className="size-2.5 shrink-0 rounded-[5px] bg-white"
            />
            <p className="min-w-px flex-1 text-sm font-semibold leading-[normal] text-white">
              Kaggle connected
            </p>
          </div>
          <p className="text-sm leading-[18px] text-muted">
            Toasts slide up from the bottom, stay 3 s, then fade.
          </p>
        </StateCard>
      </div>
    </div>
  );
}
