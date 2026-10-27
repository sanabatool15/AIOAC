"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { useAsync } from "@/lib/hooks";
import { authorizeHold, cancelHold, getAgreement } from "@/lib/mock-api";

// Screen 6: stand-in for PayPal's own approval page (Sandbox only).
// In production this is a redirect to PayPal's approval_url; we come back through the return URL.
export function PayPalWindow({ agreementId }: { agreementId: string }) {
  const router = useRouter();
  const { data, error, loading, retry } = useAsync(() =>
    getAgreement(agreementId),
  );
  const [busy, setBusy] = useState<"authorize" | "cancel" | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function authorize() {
    setBusy("authorize");
    setFailure(null);
    try {
      const { nextChatId } = await authorizeHold(agreementId);
      router.push(`/c/${nextChatId}`);
    } catch (e) {
      setFailure(
        e instanceof Error
          ? e.message
          : "Could not authorize. Nothing was held.",
      );
      setBusy(null);
    }
  }

  async function cancel() {
    setBusy("cancel");
    const { chatId } = await cancelHold(agreementId);
    router.push(`/c/${chatId}`);
  }

  const amount = data ? `$${data.target.maxUsd.toFixed(2)}` : "";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-overlay p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="paypal-title"
        className="flex w-[440px] max-w-full flex-col gap-3.5 rounded-2xl bg-white p-7"
      >
        <div className="flex items-center gap-2.5">
          <h2
            id="paypal-title"
            className="text-[28px] font-semibold leading-[normal] text-ink"
          >
            PayPal
          </h2>
          <Tag>SANDBOX</Tag>
        </div>

        {loading && !data && (
          <div
            aria-busy="true"
            aria-label="Loading authorization"
            className="flex flex-col gap-3.5"
          >
            <Skeleton className="h-[22px]" />
            <Skeleton className="h-[90px]" />
            <Skeleton className="h-11" />
          </div>
        )}

        {error && !data && (
          <ErrorState
            message={error.message}
            onRetry={retry}
            className="py-6"
          />
        )}

        {data && (
          <>
            <p className="text-base font-semibold leading-[22px] text-ink">
              AIOAC wants to hold up to {amount}
            </p>
            <div className="flex justify-between border-t border-border py-[9px] text-sm leading-[normal]">
              <span className="text-muted">Authorization hold</span>
              <span className="text-ink">{amount}</span>
            </div>
            <div className="flex justify-between border-t border-border py-[9px] text-sm font-semibold leading-[normal] text-ink">
              <span>Charged today</span>
              <span>$0.00</span>
            </div>
            {failure && (
              <p role="alert" className="text-sm text-danger">
                {failure}
              </p>
            )}
            <Button
              size="lg"
              className="rounded-[9px]"
              onClick={authorize}
              disabled={busy !== null}
            >
              {busy === "authorize"
                ? "Authorizing..."
                : "Authorize with PayPal"}
            </Button>
            <p className="text-center text-sm leading-[normal] text-muted">
              Test mode. No real money is used.
            </p>
            <button
              type="button"
              onClick={cancel}
              disabled={busy !== null}
              className="text-center text-sm font-medium leading-[normal] text-muted hover:text-ink disabled:opacity-50"
            >
              Cancel and return
            </button>
          </>
        )}
      </div>
    </div>
  );
}
