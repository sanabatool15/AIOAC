import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../lib/api";
import { bootChat, chatError, itemsFromReply, pendingCard, postChat, type ChatItem } from "../lib/chat";

// Shapes follow specs/api.md A2 and backend/tests/e2e/test_chat_blocks.py.
const PID = "p1";
const card = {
  what: "The agent wants to select dataset",
  level: 1,
  tool: "select_dataset",
  args: { candidate_id: "c1", target: "default" },
};
const storedUser = { id: "m1", role: "user", text: "predict if a loan will be repaid", kind: "chat", blocks: [], created_at: "2026-11-06T10:00:00Z" };
const storedCard = { id: "m2", role: "assistant", text: card.what, kind: "card", card, blocks: [], created_at: "2026-11-06T10:00:05Z" };
const replyCard = { status: "awaiting_approval", text: "", card, blocks: [] };
const replyPlain = { status: "reply", text: "Hi", card: null, blocks: [] };
const readinessBlock = { type: "readiness", grade: "A", findings: [{ kind: "OK", text: "Enough rows" }], trust: null };

type Call = { url: string; method: string; body: string | null };
let calls: Call[] = [];
const realFetch = globalThis.fetch;
function reply(queue: { status?: number; body?: unknown }[]) {
  calls = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, method: String(init.method), body: (init.body as string) ?? null });
    const n = queue.shift() ?? { status: 500, body: {} };
    return new Response(JSON.stringify(n.body ?? null), { status: n.status ?? 200, headers: { "content-type": "application/json" } });
  }) as typeof fetch;
}
afterEach(() => {
  globalThis.fetch = realFetch;
});
const chatCalls = () => calls.filter((c) => c.url.endsWith("/chat"));

test("first visit with no messages sends the goal exactly once", async () => {
  reply([{ body: [] }, { body: replyCard }]);
  const b = await bootChat(PID, "predict if a loan will be repaid");
  assert.equal(chatCalls().length, 1);
  assert.equal(chatCalls()[0].body, JSON.stringify({ message: "predict if a loan will be repaid" }));
  assert.deepEqual(b.items.map((i) => i.role), ["user", "assistant"]);
  assert.equal(b.items[1].card?.tool, "select_dataset");
  assert.equal(b.error, null);
});

test("reload with stored messages makes no /chat call", async () => {
  reply([{ body: [storedUser, storedCard] }]);
  const b = await bootChat(PID, "predict if a loan will be repaid");
  assert.equal(chatCalls().length, 0);
  assert.equal(calls.length, 1);
  assert.equal(b.items.length, 2);
  assert.equal(b.items[1].card?.args.target, "default");
});

test("two openings at once (strict mode) share one /chat call", async () => {
  reply([{ body: [] }, { body: replyPlain }]);
  const [a, b] = await Promise.all([bootChat(PID, "goal here"), bootChat(PID, "goal here")]);
  assert.equal(chatCalls().length, 1);
  assert.equal(a, b);
});

test("a failed first turn is not retried", async () => {
  reply([{ body: [] }, { status: 500, body: { detail: "x" } }]);
  const b = await bootChat(PID, "goal here");
  assert.equal(chatCalls().length, 1);
  assert.equal(b.items.length, 1);
  assert.match(b.error!.text, /Nothing was charged/);
});

test("approval sends only the card's tool name, and only when called", async () => {
  reply([{ body: { status: "reply", text: "Done.", card: null, blocks: [readinessBlock] } }]);
  assert.equal(calls.length, 0); // nothing is sent until the click handler calls postChat
  const r = await postChat(PID, { approve: [card.tool] });
  assert.equal(chatCalls().length, 1);
  assert.equal(chatCalls()[0].body, JSON.stringify({ approve: ["select_dataset"] }));
  assert.equal(itemsFromReply(r)[0].blocks[0].type, "readiness");
});

test("a card is pending only while it is last and the project is still at the describe step", () => {
  const items: ChatItem[] = [
    { id: "a", role: "user", text: "hi", blocks: [] },
    { id: "b", role: "assistant", text: card.what, card, blocks: [] },
  ];
  assert.equal(pendingCard(items, "described")?.id, "b");
  assert.equal(pendingCard(items, "data_chosen"), null);
  assert.equal(pendingCard([...items, { id: "c", role: "assistant", text: "ok", blocks: [] }], "described"), null);
});

test("errors read as plain words and say what to do", () => {
  const off = chatError(new ApiError("no key", 503));
  assert.equal(off.unavailable, true);
  assert.match(off.text, /not set up/);
  assert.match(off.text, /upload/i);
  const busy = chatError(new ApiError("The assistant is still working on your last message...", 409));
  assert.equal(busy.busy, true);
  assert.match(busy.text, /still working on your last message/);
  assert.match(chatError(new ApiError("x", 500)).text, /Nothing was charged/);
  assert.equal(chatError(new Error("boom")).text, "Something went wrong. Please try again.");
});

test("limit and error replies show their text; an empty text with no card adds nothing", () => {
  assert.equal(itemsFromReply({ status: "limit", text: "I stopped to save time.", card: null, blocks: [] })[0].text, "I stopped to save time.");
  assert.equal(itemsFromReply({ status: "reply", text: "", card: null, blocks: [] }).length, 0);
});
