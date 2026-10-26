"use client";
import Link from "next/link";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

// Screen 32: every way money can go wrong has a calm message and a next step (reference sheet).
// Real screens show these cards in place; here the buttons are demos, or links where the target exists.
type Action =
  | { label: string; primary?: boolean; href: string }
  | { label: string; primary?: boolean; demo: true };

const STATES: {
  tag: string;
  variant: "amber" | "red" | "blue";
  title: string;
  body: string;
  actions: [Action, Action];
}[] = [
  {
    tag: "HOLD EXPIRED",
    variant: "amber",
    title: "Your PayPal hold ran out",
    body: "The hold expired before the job finished. Nothing was charged. Place a new hold to continue from where we stopped.",
    actions: [
      { label: "Place new hold", primary: true, demo: true },
      { label: "Cancel job", demo: true },
    ],
  },
  {
    tag: "CARD DECLINED",
    variant: "red",
    title: "Your card was declined",
    body: "Nothing was charged. Check the card details or try another payment method.",
    actions: [
      {
        label: "Try another method",
        primary: true,
        href: "/billing/payment?plan=pro&cycle=monthly",
      },
      { label: "Edit card", href: "/account/billing" },
    ],
  },
  {
    tag: "3D SECURE",
    variant: "blue",
    title: "Your bank needs one more check",
    body: "A secure window from your bank will open. Finish it to place the hold.",
    actions: [
      { label: "Continue", primary: true, demo: true },
      { label: "Cancel", demo: true },
    ],
  },
  {
    tag: "CARD EXPIRING",
    variant: "amber",
    title: "Your card expires next month",
    body: "Update it now so your next job can be held without interruption.",
    actions: [
      { label: "Update card", primary: true, href: "/account/billing" },
      { label: "Remind me later", demo: true },
    ],
  },
  {
    tag: "PAYPAL UNAVAILABLE",
    variant: "red",
    title: "PayPal is not responding",
    body: "We cannot place a hold right now. Your data and progress are safe. Try again in a minute.",
    actions: [
      { label: "Try again", primary: true, demo: true },
      { label: "Run free baseline only", href: "/c/baseline" },
    ],
  },
  {
    tag: "PLAN LIMIT",
    variant: "amber",
    title: "You reached your Starter limit",
    body: "Starter allows 3 projects. Upgrade to add more, or delete a finished one.",
    actions: [
      { label: "Upgrade plan", primary: true, href: "/billing/plan" },
      { label: "Manage projects", href: "/projects" },
    ],
  },
];

export function PaymentStates() {
  const toast = useToast();
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-5 overflow-y-auto bg-bg px-12 py-10">
      <h1 className="text-[28px] font-semibold leading-[normal] text-ink">
        Payment states
      </h1>
      <p className="text-sm leading-[normal] text-muted">
        Every way money can go wrong has a calm, clear message and a next step.
      </p>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] items-start gap-4">
        {STATES.map((s) => (
          <Card
            key={s.tag}
            variant={s.variant}
            role="group"
            aria-label={s.tag.toLowerCase()}
            className="max-w-[420px] gap-2.5 overflow-clip"
          >
            <Tag className="self-start">{s.tag}</Tag>
            <p className="text-base font-semibold leading-[normal] text-ink">
              {s.title}
            </p>
            <p className="text-sm leading-5 text-muted">{s.body}</p>
            <div className="flex items-start gap-2">
              {s.actions.map((a) => {
                const cls = a.primary ? "rounded-[9px]" : undefined;
                return "href" in a ? (
                  <Link
                    key={a.label}
                    href={a.href}
                    className={cn(
                      buttonVariants({
                        variant: a.primary ? "primary" : "outline",
                        size: "md",
                      }),
                      cls,
                    )}
                  >
                    {a.label}
                  </Link>
                ) : (
                  <Button
                    key={a.label}
                    variant={a.primary ? "primary" : "outline"}
                    size="md"
                    className={cls}
                    onClick={() => toast(`${a.label} (demo)`)}
                  >
                    {a.label}
                  </Button>
                );
              })}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
