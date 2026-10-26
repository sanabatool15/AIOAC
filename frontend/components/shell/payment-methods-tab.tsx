"use client";
import { useState } from "react";
import { CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useToast } from "@/components/ui/toast";
import { useAsync } from "@/lib/hooks";
import {
  getPaymentMethods,
  makeDefaultMethod,
  removeMethod,
  saveBillingDetails,
} from "@/lib/mock-api";
import type { BillingDetails, PaymentMethod } from "@/lib/types";
import { ConfirmDialog } from "./confirm-dialog";

const link =
  "rounded text-sm leading-[normal] whitespace-nowrap outline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-brand";

// Screen 33: Payment methods tab of Billing and invoices.
export function PaymentMethodsTab() {
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(() => getPaymentMethods());
  const [methods, setMethods] = useState<PaymentMethod[] | null>(null);
  const [removing, setRemoving] = useState<PaymentMethod | null>(null);
  const [form, setForm] = useState<BillingDetails | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  if (loading && !data)
    return (
      <div
        aria-busy="true"
        aria-label="Loading payment methods"
        className="flex gap-4"
      >
        <div className="flex flex-1 flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[72px]" />
          ))}
        </div>
        <Skeleton className="h-[416px] w-[340px]" />
      </div>
    );
  if (error || !data)
    return (
      <ErrorState
        message={error?.message ?? "Payment methods unavailable."}
        onRetry={retry}
      />
    );

  const list = methods ?? data.methods;
  const values = form ?? data.details;

  async function makeDefault(m: PaymentMethod) {
    try {
      await makeDefaultMethod(m.id);
      setMethods(list.map((x) => ({ ...x, isDefault: x.id === m.id })));
      toast(`${m.title} is now your default.`);
    } catch (e) {
      toast((e as Error).message, "error");
    }
  }
  async function save() {
    setSaving(true);
    setSaveError(null);
    try {
      await saveBillingDetails(values);
      toast("Billing details saved.");
    } catch (e) {
      setSaveError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  const set =
    (k: keyof BillingDetails) => (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm({ ...values, [k]: e.target.value });

  return (
    <div className="flex items-start gap-4">
      <div className="flex min-w-px flex-1 flex-col gap-3">
        {list.length === 0 ? (
          <EmptyState
            icon={<CreditCard />}
            title="No saved payment methods"
            body="Add one to hold funds for agreed jobs."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {list.map((m) => (
              <li key={m.id}>
                <Card
                  className="flex-row items-center gap-3.5 overflow-clip p-4"
                  aria-label={m.title}
                >
                  <span
                    aria-hidden
                    className="h-8 w-12 shrink-0 rounded-md border border-border bg-surface"
                  />
                  <div className="flex min-w-px flex-1 flex-col gap-0.5 text-sm leading-[normal] whitespace-nowrap">
                    <p className="font-semibold text-ink">{m.title}</p>
                    <p className="text-muted">{m.detail}</p>
                  </div>
                  {m.isDefault && <Tag variant="brand">DEFAULT</Tag>}
                  {m.expiresSoon && <Tag>EXPIRES SOON</Tag>}
                  {m.isDefault ? (
                    <button
                      type="button"
                      className={`${link} font-semibold text-ink`}
                      onClick={() =>
                        toast(
                          "Editing a card opens PayPal's hosted form (mocked).",
                        )
                      }
                    >
                      Edit<span className="sr-only"> {m.title}</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      className={`${link} font-semibold text-ink`}
                      onClick={() => makeDefault(m)}
                    >
                      Make default<span className="sr-only"> {m.title}</span>
                    </button>
                  )}
                  <button
                    type="button"
                    className={`${link} text-muted`}
                    onClick={() => setRemoving(m)}
                  >
                    Remove<span className="sr-only"> {m.title}</span>
                  </button>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
      <Card
        variant="violet"
        className="w-[340px] shrink-0 gap-3 overflow-clip"
        aria-label="Billing details"
      >
        <h2 className="text-xs font-semibold leading-[normal] text-muted">
          BILLING DETAILS
        </h2>
        <Field label="Name" htmlFor="bd-name">
          <Input id="bd-name" value={values.name} onChange={set("name")} />
        </Field>
        <Field label="Email for invoices" htmlFor="bd-email">
          <Input
            id="bd-email"
            type="email"
            value={values.email}
            onChange={set("email")}
          />
        </Field>
        <Field label="Country" htmlFor="bd-country">
          <Input
            id="bd-country"
            value={values.country}
            onChange={set("country")}
          />
        </Field>
        <Field label="Company or tax ID (optional)" htmlFor="bd-tax">
          <Input
            id="bd-tax"
            placeholder="Add if needed"
            value={values.taxId}
            onChange={set("taxId")}
          />
        </Field>
        {saveError && (
          <p role="alert" className="text-xs leading-[normal] text-danger">
            {saveError}
          </p>
        )}
        <Button
          size="md"
          className="self-start rounded-[9px]"
          disabled={saving}
          onClick={save}
        >
          {saving ? "Saving…" : "Save details"}
        </Button>
      </Card>
      {removing && (
        <ConfirmDialog
          title={`Remove ${removing.title}?`}
          body={
            removing.isDefault
              ? "This is your default method. Choose another default first."
              : "You can add it again later. Jobs in progress are not affected."
          }
          confirmLabel="Remove"
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            const m = removing;
            try {
              await removeMethod(m.id);
              setMethods(list.filter((x) => x.id !== m.id));
              toast(`${m.title} removed.`);
            } catch (e) {
              toast((e as Error).message, "error");
            }
            setRemoving(null);
          }}
        />
      )}
    </div>
  );
}
