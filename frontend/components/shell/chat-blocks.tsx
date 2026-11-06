"use client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { dollars, outOf100 } from "@/lib/adapters";
import type { ChatBlock, ChatCard } from "@/lib/chat";

// Blocks are built by the server from tool results (specs/api.md A2). Plain words, every estimate labelled.
// The chat never moves money: the pay block only links to PayPal when the server sent a link.
export function ChatBlockView({ b }: { b: ChatBlock }) {
  if (b.type === "readiness") {
    const r = b as Extract<ChatBlock, { type: "readiness" }>;
    return (
      <Card variant="green" aria-label="Data check" className="gap-2 p-4">
        <h3 className="text-sm font-semibold text-ink">Data check: grade {r.grade}</h3>
        <ul className="flex flex-col gap-1 text-sm">
          {r.findings.map((f, i) => (
            <li key={i} className="flex gap-2">
              <span className={f.kind === "OK" ? "font-semibold text-success" : "font-semibold text-muted"}>{f.kind}</span>
              <span className="text-ink-2">{f.text}</span>
            </li>
          ))}
        </ul>
        {r.trust && <p className="text-sm text-muted">How much to trust this so far: {r.trust}</p>}
      </Card>
    );
  }
  if (b.type === "baseline") {
    const r = b as Extract<ChatBlock, { type: "baseline" }>;
    return (
      <Card variant="blue" aria-label="Free test" className="gap-2 p-4">
        <h3 className="text-sm font-semibold text-ink">Free test</h3>
        <p className="text-sm leading-5 text-ink-2">
          On data it had not seen, a simple first model got about <strong>{outOf100(r.accuracy)}</strong> right. Always
          guessing the most common answer would get about {outOf100(r.simple_guess_accuracy)}. This is a first signal, not a
          promise.
        </p>
        {r.trust && <p className="text-sm text-muted">How much to trust this so far: {r.trust}</p>}
      </Card>
    );
  }
  if (b.type === "quote") {
    const r = b as Extract<ChatBlock, { type: "quote" }>;
    return (
      <Card variant="peach" aria-label="Price estimate" className="gap-2 p-4">
        <h3 className="text-sm font-semibold text-ink">Price (estimate)</h3>
        <p className="text-sm leading-5 text-ink-2">
          Estimated {dollars(r.estimate_cents)}, most likely between {dollars(r.low_cents)} and {dollars(r.high_cents)}. The most
          you could ever be charged is {dollars(r.cap_cents)}. You approve the price and pay on the payment step of this page.
        </p>
      </Card>
    );
  }
  if (b.type === "pay") {
    const r = b as Extract<ChatBlock, { type: "pay" }>;
    return (
      <Card variant="peach" aria-label="Payment hold" className="gap-2 p-4">
        <h3 className="text-sm font-semibold text-ink">Payment hold (PayPal sandbox)</h3>
        <p className="text-sm leading-5 text-ink-2">
          A hold of up to {dollars(r.hold_cents)} is placed on test PayPal money. Nothing is charged until the run is
          finished. The payment step of this page is where you pay.
        </p>
        {r.approve_url && (
          <a href={r.approve_url} className="w-fit rounded-[10px] bg-brand px-3 py-2 text-sm font-medium text-white">
            Go to PayPal (sandbox)
          </a>
        )}
      </Card>
    );
  }
  return null;
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 text-sm">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 truncate text-right text-ink">{value}</dd>
    </div>
  );
}

// The user's OK for a choice. It names the dataset from `card.detail` and says in plain words that nothing is charged.
export function ApprovalCard({
  card,
  pending,
  busy,
  onApprove,
  onDecline,
}: {
  card: ChatCard;
  pending: boolean;
  busy: boolean;
  onApprove: () => void;
  onDecline: () => void;
}) {
  const d = card.detail;
  const hasDetail = !!d && d.name !== null;
  return (
    <Card variant="amber" aria-label="Approval needed" className="gap-3 p-4">
      <h3 className="text-sm font-semibold text-ink">{pending ? "Needs your OK" : "Asked for your OK"}</h3>
      <p className="text-sm leading-5 text-ink-2">{card.what}</p>
      {hasDetail && (
        <dl aria-label="The dataset" className="flex flex-col gap-1.5 rounded-lg border border-border bg-white p-3">
          <Fact label="Dataset" value={d.name} />
          {d.source && <Fact label="From" value={d.source} />}
          {d.rows !== null && <Fact label="Rows" value={d.rows.toLocaleString()} />}
          {d.columns !== null && <Fact label="Columns" value={d.columns} />}
          {d.target && <Fact label="We will predict" value={d.target} />}
          <Fact label="License" value={d.license ?? "not stated"} />
        </dl>
      )}
      <p className="text-sm text-muted">This only picks the data to work with. Nothing is charged.</p>
      {pending && (
        <div className="flex gap-2">
          <Button size="md" disabled={busy} onClick={onApprove}>
            Approve
          </Button>
          <Button size="md" variant="outline" disabled={busy} onClick={onDecline}>
            Not now
          </Button>
        </div>
      )}
    </Card>
  );
}
