"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { dollars, outOf100 } from "@/lib/adapters";
import type { BProject } from "@/lib/api";
import {
  bootChat,
  chatError,
  fromStored,
  getMessages,
  itemsFromReply,
  pendingCard,
  postChat,
  userItem,
  type ChatBlock,
  type ChatCard,
  type ChatItem,
  type FriendlyError,
} from "@/lib/chat";
import { DataStep } from "./steps";

function Avatar() {
  return (
    <div
      aria-hidden
      className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand-gradient-diag text-[13px] font-semibold text-white"
    >
      A
    </div>
  );
}

// ---- blocks (built by the server from tool results; shown in plain words) ----
function Block({ b }: { b: ChatBlock }) {
  if (b.type === "readiness") {
    const r = b as Extract<ChatBlock, { type: "readiness" }>;
    return (
      <Card variant="violet" aria-label="Data check" className="p-4">
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
      <Card variant="violet" aria-label="Free test" className="p-4">
        <h3 className="text-sm font-semibold text-ink">Free test</h3>
        <p className="text-sm leading-5 text-ink-2">
          On data it had not seen, a simple first model got about <strong>{outOf100(r.accuracy)} out of 100</strong>{" "}
          right. Always guessing the most common answer would get about {outOf100(r.simple_guess_accuracy)} out of
          100.
        </p>
        {r.trust && <p className="text-sm text-muted">How much to trust this so far: {r.trust}</p>}
      </Card>
    );
  }
  if (b.type === "quote") {
    const r = b as Extract<ChatBlock, { type: "quote" }>;
    return (
      <Card variant="peach" aria-label="Price estimate" className="p-4">
        <h3 className="text-sm font-semibold text-ink">Price (estimate)</h3>
        <p className="text-sm leading-5 text-ink-2">
          Estimated {dollars(r.estimate_cents)}, most likely between {dollars(r.low_cents)} and {dollars(r.high_cents)}.
          The most you could ever be charged is {dollars(r.cap_cents)}. You approve the price on the payment step.
        </p>
      </Card>
    );
  }
  if (b.type === "pay") {
    const r = b as Extract<ChatBlock, { type: "pay" }>;
    return (
      <Card variant="peach" aria-label="Payment hold" className="p-4">
        <h3 className="text-sm font-semibold text-ink">Payment hold (sandbox)</h3>
        <p className="text-sm leading-5 text-ink-2">
          A hold of up to {dollars(r.hold_cents)} is placed on test PayPal money. Nothing is charged until the run is
          finished. The payment step of this page is where you pay.
        </p>
        {r.approve_url && (
          <a
            href={r.approve_url}
            className="w-fit rounded-[10px] bg-brand px-3 py-2 text-sm font-medium text-white"
          >
            Go to PayPal (sandbox)
          </a>
        )}
      </Card>
    );
  }
  return null;
}

function ApprovalCard({
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
  const target = typeof card.args?.target === "string" ? card.args.target : null;
  return (
    <Card variant="amber" aria-label="Approval needed" className="p-4">
      <h3 className="text-sm font-semibold text-ink">{pending ? "Needs your OK" : "Asked for your OK"}</h3>
      <p className="text-sm leading-5 text-ink-2">{card.what}.</p>
      {target && <p className="text-sm text-ink-2">We would predict the column: {target}</p>}
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

interface Props {
  project: BProject;
  onChanged: () => void | Promise<void>;
}

// The describe step: the agent chats first (and finds data when the user has none); uploading is the secondary option.
export function DescribeStep({ project, onChanged }: Props) {
  const [items, setItems] = useState<ChatItem[] | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [busy, setBusy] = useState(true); // true while the chat opens
  const [declined, setDeclined] = useState(false);
  const [draft, setDraft] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const sending = useRef(false); // blocks a second /chat while one is in flight

  // Open the chat: stored messages first; the goal is sent only if there are none (lib/chat.ts bootChat).
  useEffect(() => {
    let live = true;
    void bootChat(project.id, project.goal).then((b) => {
      if (!live) return;
      setItems(b.items);
      setError(b.error);
      if (b.error?.unavailable) setUploadOpen(true);
      setBusy(false);
      if (b.items.length > 0) void onChanged();
    });
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [items, busy]);

  // ONE /chat call per click or Enter. Never from an effect, never retried by itself.
  const turn = useCallback(
    async (body: { message?: string; approve?: string[] }, shown?: ChatItem) => {
      if (sending.current) return;
      sending.current = true;
      setBusy(true);
      setError(null);
      if (shown) setItems((cur) => [...(cur ?? []), shown]);
      try {
        const r = await postChat(project.id, body);
        setItems((cur) => [...(cur ?? []), ...itemsFromReply(r)]);
        setDeclined(false);
        await onChanged(); // the project may have moved on (data chosen): the page then shows the next step
      } catch (e) {
        const f = chatError(e);
        setError(f);
        if (f.unavailable) setUploadOpen(true);
      } finally {
        sending.current = false;
        setBusy(false);
      }
    },
    [project.id, onChanged],
  );

  function send() {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    void turn({ message: text }, userItem(text));
  }

  // Only the click reaches this. The action name is the card's own tool name (specs/api.md A2).
  function approve(card: ChatCard) {
    void turn({ approve: [card.tool] });
  }

  // A GET only: pick up the reply of a turn that was still running when the page loaded.
  async function checkAgain() {
    setBusy(true);
    try {
      const m = await getMessages(project.id);
      if (m.length > 0) setItems(m.map(fromStored));
      setError(null);
      await onChanged();
    } catch (e) {
      setError(chatError(e));
    } finally {
      setBusy(false);
    }
  }

  // The goal went out but no answer came back: the user chooses to send it again (never automatic).
  const goalUnanswered = !!error && !error.busy && !error.unavailable && items?.length === 1 && items[0].role === "user";
  function sendGoalAgain() {
    setItems([]);
    void turn({ message: project.goal }, userItem(project.goal));
  }

  const waiting = items ? pendingCard(items, project.status) : null;

  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Chat with the assistant" className="flex flex-col gap-4">
        {items === null && <p className="text-sm text-muted">Opening your chat…</p>}
        {items?.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="flex flex-col items-end">
              <p className="max-w-[85%] rounded-2xl bg-brand-soft px-4 py-2.5 text-sm leading-5 text-ink">{m.text}</p>
            </div>
          ) : (
            <div key={m.id} className="flex items-start gap-3">
              <Avatar />
              <div className="flex min-w-0 flex-1 flex-col gap-3">
                {m.card ? (
                  <ApprovalCard
                    card={m.card}
                    pending={waiting?.id === m.id && !declined}
                    busy={busy}
                    onApprove={() => approve(m.card!)}
                    onDecline={() => setDeclined(true)}
                  />
                ) : (
                  m.text && <p className="whitespace-pre-wrap text-[15px] leading-[23px] text-ink">{m.text}</p>
                )}
                {m.blocks.map((b, i) => (
                  <Block key={i} b={b} />
                ))}
              </div>
            </div>
          ),
        )}
        {busy && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted">
            <LoaderCircle aria-hidden size={14} className="motion-safe:animate-spin" /> The assistant is working…
          </p>
        )}
        {declined && (
          <p className="text-sm text-muted">No problem. Tell me what you would like instead, or upload your own file below.</p>
        )}
        {error && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-danger">
            <span>{error.text}</span>
            {error.busy && (
              <Button variant="outline" disabled={busy} onClick={() => void checkAgain()}>
                Check again
              </Button>
            )}
            {goalUnanswered && (
              <Button variant="outline" disabled={busy} onClick={sendGoalAgain}>
                Send my goal again
              </Button>
            )}
          </div>
        )}
        <div ref={endRef} />
      </section>

      {!error?.unavailable && (
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <textarea
            aria-label="Message the assistant"
            rows={2}
            value={draft}
            disabled={busy || items === null}
            placeholder="For example: I have no data. Can you find some?"
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            className="min-h-[52px] flex-1 resize-none rounded-xl border border-border bg-white px-3 py-2.5 text-sm text-ink"
          />
          <Button type="submit" size="icon" aria-label="Send" disabled={busy || !draft.trim()}>
            <ArrowUp />
          </Button>
        </form>
      )}

      <div className="flex flex-col gap-3">
        <Button
          variant="outline"
          className="w-fit"
          aria-expanded={uploadOpen}
          onClick={() => setUploadOpen((o) => !o)}
        >
          {uploadOpen ? "Hide the upload option" : "Upload my own CSV"}
        </Button>
        {uploadOpen && <DataStep project={project} onChanged={onChanged} />}
      </div>
    </div>
  );
}
