"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, Input } from "@/components/ui/input";
import { choiceQuery, saveFlow } from "@/lib/billing-flow";
import type { BillingCycle, PlanId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BillingFrame } from "./billing-frame";
import { OrderSummary } from "./order-summary";

type Method = "paypal" | "card";

function luhn(digits: string) {
  let sum = 0;
  for (let i = 0; i < digits.length; i++) {
    let d = Number(digits[digits.length - 1 - i]);
    if (i % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
  }
  return sum % 10 === 0;
}
const brandOf = (d: string) =>
  d.startsWith("4")
    ? "Visa"
    : /^5[1-5]|^2[2-7]/.test(d)
      ? "Mastercard"
      : /^3[47]/.test(d)
        ? "American Express"
        : "Card";

// Screen 23: billing step 2, payment method. Card fields stay in this component; only brand + last 4 move on.
// In production the card form is PayPal's hosted fields, so AIOAC never sees the number.
export function PaymentStep({
  choice,
}: {
  choice: { plan: PlanId; cycle: BillingCycle };
}) {
  const router = useRouter();
  const [method, setMethod] = useState<Method>("card");
  const [form, setForm] = useState({
    number: "",
    expiry: "",
    cvc: "",
    name: "David",
    country: "Pakistan",
    postal: "46000",
  });
  const [saveDefault, setSaveDefault] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const q = choiceQuery(choice);
  const set =
    (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  function validate() {
    const digits = form.number.replace(/\s/g, "");
    const e: Record<string, string> = {};
    if (!/^\d{13,19}$/.test(digits) || !luhn(digits))
      e.number = "Enter a valid card number.";
    const m = /^(\d{2})\s*\/\s*(\d{2})$/.exec(form.expiry.trim());
    if (!m || Number(m[1]) < 1 || Number(m[1]) > 12) e.expiry = "Use MM / YY.";
    else if (
      new Date(2000 + Number(m[2]), Number(m[1]), 0) < new Date("2026-10-24")
    )
      e.expiry = "This card has expired.";
    if (!/^\d{3,4}$/.test(form.cvc)) e.cvc = "Enter the 3 or 4 digit code.";
    if (!form.name.trim()) e.name = "Enter the name on the card.";
    if (!form.country.trim()) e.country = "Enter a country.";
    if (!form.postal.trim()) e.postal = "Enter a postal code.";
    return e;
  }

  function next() {
    if (method === "paypal") {
      saveFlow({
        method: "paypal",
        cardLast4: undefined,
        cardBrand: undefined,
      });
      return router.push(`/billing/review?${q}`);
    }
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) return;
    const digits = form.number.replace(/\s/g, "");
    saveFlow({
      method: "card",
      cardLast4: digits.slice(-4),
      cardBrand: brandOf(digits),
    });
    router.push(`/billing/review?${q}`);
  }

  const err = (k: string) =>
    errors[k] && (
      <p role="alert" className="text-xs leading-[normal] text-danger">
        {errors[k]}
      </p>
    );
  const input = (
    k: keyof typeof form,
    label: string,
    extra: React.InputHTMLAttributes<HTMLInputElement> = {},
  ) => (
    <div className="flex min-w-px flex-1 flex-col gap-1.5">
      <Field label={label} htmlFor={`pm-${k}`}>
        <Input
          id={`pm-${k}`}
          value={form[k]}
          onChange={set(k)}
          aria-invalid={!!errors[k]}
          {...extra}
        />
      </Field>
      {err(k)}
    </div>
  );

  return (
    <BillingFrame step={2}>
      <div className="flex w-[620px] max-w-full flex-col gap-4">
        <h1 className="text-[28px] font-semibold leading-[normal] text-ink">
          Add a payment method
        </h1>
        <p className="text-sm leading-[normal] text-muted">
          Used for your plan and for PayPal holds on jobs. Handled securely by
          PayPal.
        </p>
        <div
          role="radiogroup"
          aria-label="Payment method"
          className="flex flex-col gap-4"
        >
          {(
            [
              [
                "paypal",
                "PayPal account",
                "Log in with PayPal. No card number needed.",
                "Recommended",
              ],
              [
                "card",
                "Debit or credit card",
                "Visa, Mastercard, American Express",
                "",
              ],
            ] as const
          ).map(([id, title, sub, aside]) => (
            <label
              key={id}
              className={cn(
                "flex cursor-pointer items-center gap-3.5 rounded-xl p-4 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand",
                method === id
                  ? "border-2 border-brand bg-surface"
                  : "border border-border bg-card shadow-card",
              )}
            >
              <input
                type="radio"
                name="method"
                value={id}
                checked={method === id}
                onChange={() => setMethod(id)}
                className="peer sr-only"
              />
              <span
                aria-hidden
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full border bg-white",
                  method === id ? "border-brand" : "border-border",
                )}
              >
                {method === id && (
                  <span className="size-2.5 rounded-full bg-brand" />
                )}
              </span>
              <span className="flex min-w-px flex-1 flex-col gap-0.5 text-sm leading-[normal]">
                <span className="font-semibold text-ink">{title}</span>
                <span className="text-muted">{sub}</span>
              </span>
              {aside && (
                <span className="text-sm leading-[normal] text-muted">
                  {aside}
                </span>
              )}
            </label>
          ))}
        </div>
        {method === "card" && (
          <form
            aria-label="Card details"
            noValidate
            onSubmit={(e) => {
              e.preventDefault();
              next();
            }}
            className="flex flex-col gap-3.5 overflow-clip rounded-xl border border-border bg-card p-5 shadow-card"
          >
            {input("number", "Card number", {
              placeholder: "1234 5678 9012 3456",
              inputMode: "numeric",
              autoComplete: "cc-number",
            })}
            <div className="flex gap-3">
              {input("expiry", "Expiry", {
                placeholder: "MM / YY",
                autoComplete: "cc-exp",
              })}
              {input("cvc", "CVC", {
                placeholder: "123",
                inputMode: "numeric",
                autoComplete: "cc-csc",
              })}
            </div>
            {input("name", "Name on card", { autoComplete: "cc-name" })}
            <div className="flex gap-3">
              {input("country", "Country")}
              {input("postal", "Postal code")}
            </div>
            <Checkbox
              id="save-default"
              checked={saveDefault}
              onCheckedChange={setSaveDefault}
            >
              Save as my default payment method
            </Checkbox>
          </form>
        )}
        <div className="flex items-center gap-2.5 rounded-[10px] bg-surface p-3.5">
          <Lock aria-hidden className="size-4 shrink-0 text-muted" />
          <p className="min-w-px flex-1 text-sm leading-[normal] text-muted">
            Card details go straight to PayPal. AIOAC never sees or stores your
            full card number.
          </p>
        </div>
        <div className="flex items-start justify-between">
          <Button
            variant="outline"
            size="action"
            onClick={() => router.push("/billing/plan")}
          >
            Back
          </Button>
          <Button size="action" className="rounded-[9px]" onClick={next}>
            Continue
          </Button>
        </div>
      </div>
      <OrderSummary
        plan={choice.plan}
        cycle={choice.cycle}
        note="Cancel any time. Your first job hold is separate and only happens when you agree a target."
      />
    </BillingFrame>
  );
}
