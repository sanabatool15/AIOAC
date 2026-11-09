"use client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { dollars, outOf100 } from "@/lib/adapters";
import { cardFacts, cardTitle, cluesView, profileView, resultLines, type ChatBlock, type ChatCard } from "@/lib/chat";

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
  if (b.type === "profile") {
    const v = profileView(b as Extract<ChatBlock, { type: "profile" }>);
    return (
      <Card variant="blue" aria-label="What I found in your data" className="gap-2 p-4">
        <h3 className="text-sm font-semibold text-ink">What I found in your data</h3>
        {v.summary && <p className="text-sm text-muted">{v.summary}</p>}
        {v.balance && <p className="text-sm leading-5 text-ink-2">The answer column: {v.balance}.</p>}
        {v.suspects.length > 0 ? (
          <ul className="flex flex-col gap-1 text-sm">
            {v.suspects.map((s) => (
              <li key={s.column} className="flex gap-2">
                <span className={s.strong ? "shrink-0 font-semibold text-ink" : "shrink-0 font-semibold text-muted"}>{s.column}</span>
                <span className="text-ink-2">{s.reason}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No column stood out as odd.</p>
        )}
        <p className="text-xs text-muted">These are clues to check with you, not proof.</p>
      </Card>
    );
  }
  if (b.type === "clues") {
    const v = cluesView(b as Extract<ChatBlock, { type: "clues" }>);
    return (
      <Card variant="blue" aria-label="What seems to matter most" className="gap-2 p-4">
        <h3 className="text-sm font-semibold text-ink">What seems to matter most</h3>
        {v.verdict && <p className="text-sm leading-5 text-ink-2">{v.verdict}</p>}
        {v.clues.length > 0 && (
          <ul className="flex flex-col gap-1 text-sm">
            {v.clues.map((c) => (
              <li key={c.column} className="flex gap-2">
                <span className="shrink-0 font-semibold text-ink">{c.column}</span>
                <span className="text-ink-2">
                  {c.howMuch}. {c.effect}
                </span>
              </li>
            ))}
          </ul>
        )}
        {v.moreData && <p className="text-sm leading-5 text-ink-2">{v.moreData}</p>}
        <p className="text-xs text-muted">{v.note} Estimates, not promises.</p>
      </Card>
    );
  }
  if (b.type === "result") {
    const v = resultLines(b as Extract<ChatBlock, { type: "result" }>);
    const ok = (b as Extract<ChatBlock, { type: "result" }>).target_met;
    return (
      <Card variant={ok ? "green" : "plain"} aria-label="Result" className="gap-2 p-4">
        <h3 className="text-sm font-semibold text-ink">{v.title}</h3>
        {v.lines.map((l, i) => (
          <p key={i} className="text-sm leading-5 text-ink-2">
            {l}
          </p>
        ))}
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

function Fact({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 text-sm">
      <dt className="shrink-0 text-muted">{label}</dt>
      <dd className="min-w-0 text-right text-ink">
        {value}
        {note && <span className="text-muted">: {note}</span>}
      </dd>
    </div>
  );
}

// The user's OK for a choice. It names the dataset from `card.detail` and says in plain words that nothing is charged.
export function ApprovalCard({
  card,
  pending,
  declined = false,
  busy,
  onApprove,
  onDecline,
}: {
  card: ChatCard;
  pending: boolean;
  declined?: boolean; // the user chose "Not now": a calm note instead of the buttons
  busy: boolean;
  onApprove: () => void;
  onDecline: () => void;
}) {
  const facts = cardFacts(card);
  const title = cardTitle(card);
  return (
    <Card variant="amber" aria-label="Approval needed" className="gap-3 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{declined ? "You chose not to use this one" : pending ? "Needs your OK" : "Asked for your OK"}</p>
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {title !== card.what && <p className="text-sm leading-5 text-ink-2">{card.what}</p>}
      {facts.length > 0 && (
        <dl aria-label={card.tool === "apply_data_fix" ? "What changes" : "The dataset"} className="flex flex-col gap-1.5 rounded-lg border border-border bg-white p-3">
          {facts.map((f) => (
            <Fact key={f.label} label={f.label} value={f.value} note={f.note} />
          ))}
        </dl>
      )}
      <p className="text-sm text-muted">
        {card.tool === "apply_data_fix"
          ? declined
            ? "Nothing was changed and nothing was charged."
            : "Your original data stays saved and the rows we keep aside for the final check do not change. We will test whether this changes the estimate; it may not. Nothing is charged."
          : declined
            ? "Nothing was chosen and nothing was charged."
            : "This only picks the data to work with. Nothing is charged."}
      </p>
      {pending && !declined && (
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
