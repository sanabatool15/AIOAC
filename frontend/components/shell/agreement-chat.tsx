"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, Input } from "@/components/ui/input";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { useAsync } from "@/lib/hooks";
import { createAgreement, getAgreement, holdAgreement } from "@/lib/mock-api";
import type {
  AgreementOffer,
  AgreementTarget,
  AgreementTier,
  Chat,
  Message,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  AgentRow,
  EmptyThread,
  InlineChatFrame,
  UserBubble,
} from "./inline-chat";
import { PayPalWindow } from "./paypal-window";

interface Props {
  chat: Chat;
  messages: Message[];
  onSend: (text: string) => void;
  phase: "agreement" | "pay";
  agreementId?: string;
}

// Screens 5 and 6. Both live at the same chat; /pay adds the PayPal window over the summary.
export function AgreementChat({
  chat,
  messages,
  onSend,
  phase,
  agreementId,
}: Props) {
  const offer = chat.agreement;
  if (!offer) return null;

  return (
    <>
      <InlineChatFrame
        projectName={chat.projectName}
        stepLabel={`Step ${phase === "pay" ? offer.stepIndex + 1 : offer.stepIndex} of ${offer.totalSteps}`}
        wide
        onSend={onSend}
      >
        {phase === "pay" ? (
          <PaySummary chatId={chat.id} agreementId={agreementId} />
        ) : messages.length === 0 ? (
          <EmptyThread />
        ) : (
          messages.map((m) =>
            m.role === "user" ? (
              <UserBubble key={m.id} text={m.text} />
            ) : (
              <div key={m.id} className="contents">
                <AgentRow text={m.text} />
                {m.blocks?.includes("agreement") && (
                  <AgreementCard chatId={chat.id} offer={offer} />
                )}
              </div>
            ),
          )
        )}
      </InlineChatFrame>
      {phase === "pay" && agreementId && (
        <PayPalWindow agreementId={agreementId} />
      )}
    </>
  );
}

// ---------- Screen 6 background: what the user agreed to ----------

function PaySummary({
  chatId,
  agreementId,
}: {
  chatId: string;
  agreementId?: string;
}) {
  const router = useRouter();
  const { data, error, loading, retry } = useAsync(() =>
    agreementId ? getAgreement(agreementId) : Promise.resolve(null),
  );

  useEffect(() => {
    if (!agreementId) router.replace(`/c/${chatId}`);
  }, [agreementId, chatId, router]);

  return (
    <>
      <AgentRow text="Last step before training: authorize up to $40 with PayPal. It is a hold, not a charge." />
      {loading && !data && <Skeleton className="h-[78px] rounded-xl" />}
      {error && !data && <ErrorState message={error.message} onRetry={retry} />}
      {data && (
        <Card
          variant="violet"
          className="gap-1.5 p-[18px] text-sm leading-[normal] shadow-card-tight"
          data-testid="agreement-summary"
        >
          <p className="font-semibold text-ink">
            Target: precision {data.target.precision}%, recall{" "}
            {data.target.minRecall}%
          </p>
          <p className="text-muted">
            Max hold ${data.target.maxUsd.toFixed(2)} · charged only if the
            target is verified
          </p>
        </Card>
      )}
    </>
  );
}

// ---------- Screen 5: the agreement ----------

function AgreementCard({
  chatId,
  offer,
}: {
  chatId: string;
  offer: AgreementOffer;
}) {
  const router = useRouter();
  const recommended =
    offer.tiers.find((t) => t.id === "recommended") ?? offer.tiers[0];
  const [tierId, setTierId] = useState<AgreementTier["id"]>(recommended.id);
  const [custom, setCustom] = useState<{
    precision: string;
    minRecall: string;
    maxUsd: string;
  } | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tier = offer.tiers.find((t) => t.id === tierId) ?? recommended;
  const target: AgreementTarget = custom
    ? {
        precision: Number(custom.precision),
        minRecall: Number(custom.minRecall),
        maxUsd: Number(custom.maxUsd),
      }
    : {
        precision: tier.precision,
        minRecall: tier.minRecall,
        maxUsd: tier.maxUsd,
      };
  const customValid =
    !custom ||
    (target.precision >= 1 &&
      target.precision <= 99 &&
      target.minRecall >= 1 &&
      target.minRecall <= 99 &&
      target.maxUsd >= 1 &&
      target.maxUsd <= 500);
  const unrealistic =
    custom &&
    customValid &&
    (target.precision >= 90 || target.precision <= offer.baselinePrecision);
  const maxLabel = `$${Number.isInteger(target.maxUsd) ? target.maxUsd : target.maxUsd.toFixed(2)}`;

  const terms: [string, string][] = [
    [
      "Goal",
      `Flag customers who may stop buying, about ${target.precision}% right when flagged, catching at least ${target.minRecall}% of leavers.`,
    ],
    [
      "If target is met",
      `You pay the actual compute used, never above ${maxLabel}.`,
    ],
    ["If we miss", "You pay only the compute used, no success fee. The rest of the hold is released."],
    ["How we verify", "One test on a locked set the model never saw."],
    [
      "Spending control",
      "The backend sets each experiment budget, not the AI.",
    ],
  ];

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      const agreement = await createAgreement(chatId, target);
      const { approvalUrl } = await holdAgreement(agreement.id);
      router.push(approvalUrl);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not start the PayPal authorization. Nothing was held.",
      );
      setBusy(false);
    }
  }

  function toggleCustom() {
    setCustom((c) =>
      c
        ? null
        : {
            precision: String(tier.precision),
            minRecall: String(tier.minRecall),
            maxUsd: String(tier.maxUsd),
          },
    );
    setError(null);
  }

  return (
    <Card
      variant="violet"
      className="gap-3 overflow-clip p-5 shadow-card-tight"
      data-testid="agreement-card"
    >
      <h2 className="text-xl font-semibold leading-[normal] text-ink">
        Performance agreement
      </h2>

      <div className="w-full rounded-[10px] bg-brand-gradient px-4 py-[11px] text-sm font-semibold leading-[normal] text-white shadow-glow">
        You always pay for the compute used; the success fee applies only if the target is verified.
      </div>

      <div
        role="radiogroup"
        aria-label="Target"
        className="flex gap-2.5 leading-[normal]"
      >
        {offer.tiers.map((t) => {
          const selected = !custom && t.id === tierId;
          return (
            <button
              key={t.id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => {
                setTierId(t.id);
                setCustom(null);
              }}
              className={cn(
                "flex min-w-px flex-1 flex-col items-start gap-0.5 overflow-clip rounded-xl p-3 text-left whitespace-nowrap focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
                selected
                  ? "border-2 border-brand bg-surface"
                  : "border border-border bg-white",
              )}
            >
              <span className="text-xs font-semibold text-muted">
                {t.label}
              </span>
              <span className="text-base font-semibold text-ink">
                About {t.precision}% right when flagged
              </span>
              <span className="text-xs text-muted">
                catch at least {t.minRecall}% of leavers
              </span>
              <span className="text-sm font-semibold text-ink">
                Max ${t.maxUsd}
              </span>
            </button>
          );
        })}
      </div>

      {custom && (
        <div
          className="flex flex-col gap-2.5 rounded-xl border border-border bg-white p-3"
          data-testid="custom-target"
        >
          <div className="flex gap-2.5">
            <Field label="Right when flagged %" htmlFor="ct-precision">
              <Input
                id="ct-precision"
                inputMode="decimal"
                value={custom.precision}
                onChange={(e) =>
                  setCustom({ ...custom, precision: e.target.value })
                }
                aria-invalid={!customValid}
              />
            </Field>
            <Field label="Leavers caught, at least %" htmlFor="ct-recall">
              <Input
                id="ct-recall"
                inputMode="decimal"
                value={custom.minRecall}
                onChange={(e) =>
                  setCustom({ ...custom, minRecall: e.target.value })
                }
                aria-invalid={!customValid}
              />
            </Field>
            <Field label="Max price $" htmlFor="ct-max">
              <Input
                id="ct-max"
                inputMode="decimal"
                value={custom.maxUsd}
                onChange={(e) =>
                  setCustom({ ...custom, maxUsd: e.target.value })
                }
                aria-invalid={!customValid}
              />
            </Field>
          </div>
          {!customValid && (
            <p role="alert" className="text-sm text-danger">
              Both targets must be 1 to 99, and max price $1 to $500.
            </p>
          )}
          {unrealistic && (
            <p
              role="status"
              className="flex items-start gap-1.5 text-sm text-ink-2"
            >
              <TriangleAlert
                aria-hidden
                size={16}
                className="mt-0.5 shrink-0 text-danger"
              />
              {target.precision >= 90
                ? `This target is unlikely for your data (baseline is ${offer.baselinePrecision}%). The hold may be voided.`
                : `This is not better than your free baseline (${offer.baselinePrecision}%).`}
            </p>
          )}
        </div>
      )}

      <dl className="flex w-full flex-col text-sm">
        {terms.map(([label, value]) => (
          <div
            key={label}
            className="flex items-start gap-4 border-b border-border py-[9px]"
          >
            <dt className="w-[130px] shrink-0 font-semibold leading-[normal] text-muted">
              {label}
            </dt>
            <dd className="min-w-px flex-1 leading-[19px] text-ink">{value}</dd>
          </div>
        ))}
      </dl>

      <Checkbox id="agree-terms" checked={agreed} onCheckedChange={setAgreed}>
        I understand and agree to these terms.
      </Checkbox>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}

      <div className="flex gap-2.5">
        <Button
          size="action"
          className="rounded-[9px]"
          disabled={!agreed || !customValid || busy}
          onClick={approve}
        >
          {busy ? "Opening PayPal..." : "Approve and authorize with PayPal"}
        </Button>
        <Button
          variant="outline"
          size="action"
          onClick={toggleCustom}
          aria-pressed={!!custom}
        >
          Change target
        </Button>
      </div>
    </Card>
  );
}
