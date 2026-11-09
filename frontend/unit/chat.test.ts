import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../lib/api";
import { askedForSearch, cluesView, profileView, resultLines, NO_DATA_MESSAGE, bootChat, cardFacts, cardTitle, chatError, looksLikeId, itemsFromReply, pendingCard, postChat, type ChatItem } from "../lib/chat";

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

const detail = { name: "German credit", source: "OpenML", rows: 1000, columns: 21, license: null, target: "Y", target_meaning: "whether the next payment was missed" };

test("card title is the dataset name; ids fall back to the plain sentence", () => {
  assert.equal(cardTitle({ ...card, detail }), "German credit");
  for (const name of ["350", "uci:350", "hf:scikit-learn/x", "oml:31", "0123456789abcdef0123"]) {
    assert.ok(looksLikeId(name), name);
    assert.equal(cardTitle({ ...card, detail: { ...detail, name } }), card.what);
  }
  assert.equal(cardTitle(card), card.what);
  assert.equal(cardTitle({ ...card, detail: { ...detail, name: null } }), card.what);
  assert.equal(cardTitle({ ...card, detail: { ...detail, name: "scikit-learn/churn-prediction" } }), "scikit-learn/churn-prediction");
});

test("card facts: source, rows, columns, answer column with meaning, license", () => {
  const f = cardFacts({ ...card, detail });
  assert.deepEqual(f.map((x) => x.label), ["Source", "Rows", "Columns", "Answer column", "License"]);
  assert.equal(f[1].value, "1,000");
  assert.equal(f[3].note, "whether the next payment was missed");
  assert.equal(f[4].value, "not stated");
});

test("data-fix card: a plain title and the numbers the server computed", () => {
  const fixCard = {
    what: "Change your data: remove 60 repeated row(s) (1,560 rows to 1,500). The original stays saved.",
    level: 1,
    tool: "apply_data_fix",
    args: { version_id: "v1" },
    detail: { rows_before: 1560, rows_after: 1500, rows_removed: 60, columns_before: 8, columns_after: 7, columns_dropped: ["notes_col"], version_id: "v1" },
  };
  assert.equal(cardTitle(fixCard), "Change your data");
  const f = cardFacts(fixCard);
  assert.deepEqual(f.map((x) => x.label), ["Rows", "Columns", "Columns removed"]);
  assert.equal(f[0].value, "1,560 to 1,500");
  assert.equal(f[0].note, "60 repeated rows removed");
  assert.equal(f[1].value, "8 to 7");
  assert.equal(f[2].value, "notes_col");
  assert.deepEqual(cardFacts({ ...fixCard, detail: null }), []); // a card without numbers shows no facts instead of crashing
});

test("card facts: target_meaning is optional and null is fine", () => {
  const { target_meaning: _omit, ...bare } = detail;
  void _omit;
  assert.equal(cardFacts({ ...card, detail: bare })[3].note, undefined);
  assert.equal(cardFacts({ ...card, detail: { ...detail, target_meaning: null } })[3].note, undefined);
  assert.deepEqual(cardFacts(card), []);
});

test("only the 'no data' choice counts as asking for a search", () => {
  const u = (text: string) => ({ role: "user", text });
  assert.equal(askedForSearch(null), false);
  assert.equal(askedForSearch([u("I want to predict churn")]), false);
  assert.equal(askedForSearch([u("I want to predict churn"), u(NO_DATA_MESSAGE)]), true);
  assert.equal(askedForSearch([u(NO_DATA_MESSAGE), { role: "assistant", text: "ok" }]), true);
  assert.equal(askedForSearch([u(NO_DATA_MESSAGE), u("something else")]), false);
});

test("a data-fix card can be approved in chat while the price is not approved; other cards stay describe-only", () => {
  const fix = { what: "Change your data", level: 1, tool: "apply_data_fix", args: {} };
  const items: ChatItem[] = [{ id: "f", role: "assistant", text: fix.what, card: fix, blocks: [] }];
  assert.equal(pendingCard(items, "baseline_done")?.id, "f");
  assert.equal(pendingCard(items, "quoted")?.id, "f");
  for (const st of ["described", "awaiting_payment", "paid", "training", "done", "failed", "stopped", "voided"]) assert.equal(pendingCard(items, st), null);
  const pick: ChatItem[] = [{ id: "p", role: "assistant", text: "x", card, blocks: [] }];
  assert.equal(pendingCard(pick, "baseline_done"), null);
});

test("result block reads in out-of-100 words, with no money and no promise", () => {
  const hit = resultLines({ type: "result", outcome: "done", verified_out_of_100: 82, target_out_of_100: 80, simple_guess_out_of_100: 70, target_met: true, model_type: "a forest of decision trees" });
  assert.equal(hit.title, "Target reached");
  const text = hit.lines.join(" ");
  assert.match(text, /about 82 out of 100/);
  assert.match(text, /target was 80 out of 100/);
  assert.match(text, /about 70/);
  assert.match(text, /not a promise/);
  assert.doesNotMatch(text, /\$|cents|0\.\d/);
  const miss = resultLines({ type: "result", outcome: "done", verified_out_of_100: 61, target_out_of_100: 80, simple_guess_out_of_100: 60, target_met: false, model_type: null });
  assert.equal(miss.title, "Target not reached");
  assert.equal(resultLines({ type: "result", outcome: "failed", verified_out_of_100: null, target_out_of_100: null, simple_guess_out_of_100: null, target_met: null, model_type: null }).title, "The run did not finish");
  assert.match(resultLines({ type: "result", outcome: "stopped", verified_out_of_100: null, target_out_of_100: null, simple_guess_out_of_100: null, target_met: null, model_type: null }).lines[0], /no success fee/);
});

test("profile block shows at most five clues and tolerates missing fields", () => {
  const many = Array.from({ length: 8 }, (_, i) => ({ column: `c${i}`, reason: "gives the answer away", strength: (i % 2 ? "strong" : "weak") as "strong" | "weak" }));
  const v = profileView({ type: "profile", rows: 12000, columns_total: 9, target: { name: "left", balance: "yes 30 in 100, no 70 in 100" }, suspects: many });
  assert.equal(v.suspects.length, 5);
  assert.equal(v.summary, "12,000 rows, 9 columns");
  assert.equal(v.suspects[1].strong, true);
  const bare = profileView({ type: "profile", rows: null, columns_total: null, target: undefined as never, suspects: undefined as never });
  assert.deepEqual(bare, { summary: "", balance: "", suspects: [] });
});

test("an unknown block type is carried through and ignored by the reply mapper", () => {
  const items = itemsFromReply({ status: "reply", text: "Hi", card: null, blocks: [{ type: "something_new", x: 1 }] });
  assert.equal(items[0].blocks[0].type, "something_new");
});

test("clues block shows at most five columns, a plain size word each, and the not-causes note", () => {
  const many = Array.from({ length: 8 }, (_, i) => ({ column: `c${i}`, how_much: (i === 0 ? "a lot" : i === 1 ? "weird" : "some") as never, plain_effect: "about 4 fewer answers in 100 are right." }));
  const v = cluesView({ type: "clues", verdict: "The three kinds score within 2 points of each other.", more_data: "More rows barely helped.", clues: many, note: "These are clues, not causes.", is_estimate: true });
  assert.equal(v.clues.length, 5);
  assert.equal(v.clues[0].howMuch, "a lot");
  assert.equal(v.clues[1].howMuch, "a little");
  assert.match(v.note, /clues, not causes/);
  const bare = cluesView({ type: "clues", verdict: undefined as never, more_data: undefined as never, clues: undefined as never, note: "", is_estimate: true });
  assert.deepEqual(bare, { verdict: "", moreData: "", clues: [], note: "These are clues, not causes." });
  const items = itemsFromReply({ status: "reply", text: "Hi", card: null, blocks: [{ type: "clues", verdict: "v", more_data: "", clues: [], note: "n", is_estimate: true }] });
  assert.equal(items[0].blocks[0].type, "clues");
});
