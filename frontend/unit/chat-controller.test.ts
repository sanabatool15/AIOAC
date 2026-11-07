import test from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../lib/api";
import { bootChat } from "../lib/chat";
import { loadDeclined, type KV } from "../lib/declined";
import { ChatController, type ChatDeps } from "../lib/chat-controller";

// Shapes follow specs/api.md A2 and backend/tests/e2e/test_chat_blocks.py (the select_dataset card with `detail`).
const detail = { name: "Credit card default", source: "UCI", rows: 1500, columns: 8, license: "cc-by-4.0", target: "left" };
const card = {
  what: 'Use "Credit card default" (UCI, 1,500 rows) and predict the column "left"',
  level: 1,
  tool: "select_dataset",
  args: { candidate_id: "c1", target: "left" },
  detail,
};
const replyCard = { status: "awaiting_approval" as const, text: "", card, blocks: [] };
const replyText = { status: "reply" as const, text: "Hello", card: null, blocks: [] };
const replyBlocks = {
  status: "reply" as const,
  text: "Done",
  card: null,
  blocks: [{ type: "readiness", grade: "B+", findings: [{ kind: "OK", text: "Enough rows" }], trust: null }],
};
const storedUser = { id: "m1", role: "user" as const, text: "predict churn", kind: "chat", blocks: [] };
const storedCard = { id: "m2", role: "assistant" as const, text: card.what, kind: "card", card, blocks: [] };

type Body = { message?: string; approve?: string[] };
const memoryStore = (): KV & { data: Map<string, string> } => {
  const data = new Map<string, string>();
  return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v) };
};
type Act = { when: string; kind: string; text: string };
function make(
  opts: { stored?: unknown[]; replies?: (object | Error)[]; store?: KV | null; gate?: Promise<void>; postGate?: Promise<void>; activity?: () => Promise<Act[]> } = {},
) {
  const posts: Body[] = [];
  const gets: string[] = [];
  const replies = [...(opts.replies ?? [])];
  let changed = 0;
  let activityCalls = 0;
  const post = async (_id: string, body: Body) => {
    posts.push(body);
    await opts.postGate;
    const r = replies.shift();
    if (r instanceof Error) throw r;
    return (r ?? replyText) as never;
  };
  const get = async (id: string) => {
    gets.push(id);
    return (opts.stored ?? []) as never;
  };
  const deps: ChatDeps = {
    // Same boot as the app, but on the fake network calls (tests the real first-visit rule).
    boot: (id, goal, sendGoal, onGoalSent) => {
      const realFetch = globalThis.fetch;
      globalThis.fetch = (async (url: string, init: RequestInit) => {
        if (String(url).endsWith("/messages")) return json(await get(id));
        await opts.gate;
        posts.push(JSON.parse(String(init.body)));
        const r = replies.shift();
        if (r instanceof Error) return json({ detail: r.message }, (r as ApiError).status ?? 500);
        return json(r ?? replyText);
      }) as typeof fetch;
      return bootChat(id, goal, sendGoal, onGoalSent).finally(() => {
        globalThis.fetch = realFetch;
      });
    },
    getMessages: get,
    getActivity: () => {
      activityCalls++;
      return (opts.activity ?? (async () => []))();
    },
    postChat: post,
  };
  const c = new ChatController("p1", "predict churn", () => void changed++, deps, opts.store === undefined ? memoryStore() : opts.store);
  return { c, posts, gets, changed: () => changed, activityCalls: () => activityCalls };
}
const json = (b: unknown, status = 200) =>
  new Response(JSON.stringify(b), { status, headers: { "content-type": "application/json" } });

test("a new project sends the goal once; opening twice does not send again", async () => {
  const t = make({ replies: [replyCard] });
  await Promise.all([t.c.open("described"), t.c.open("described")]);
  assert.deepEqual(t.posts, [{ message: "predict churn" }]);
  assert.equal(t.c.getState().items?.[1].card?.detail?.name, "Credit card default");
  assert.equal(t.c.getState().busy, false);
});

test("reload with stored messages makes no /chat call and sends nothing", async () => {
  const t = make({ stored: [storedUser, storedCard] });
  await t.c.open("described");
  assert.equal(t.posts.length, 0);
  assert.equal(t.c.getState().items?.length, 2);
});

test("on a later step an empty history is NOT a reason to send the goal", async () => {
  const t = make({ stored: [] });
  await t.c.open("baseline_done");
  assert.equal(t.posts.length, 0);
  assert.deepEqual(t.c.getState().items, []);
});

test("send makes exactly one /chat call, shows the user's words, and re-reads the project after", async () => {
  const t = make({ stored: [storedUser], replies: [replyBlocks] });
  await t.c.open("data_chosen");
  const before = t.changed();
  await Promise.all([t.c.send("check my data"), t.c.send("check my data")]); // a double click
  assert.deepEqual(t.posts, [{ message: "check my data" }]);
  assert.equal(t.changed(), before + 1);
  const items = t.c.getState().items!;
  assert.deepEqual(items.slice(-2).map((i) => i.role), ["user", "assistant"]);
  assert.equal(items[items.length - 1].blocks[0].type, "readiness");
});

test("empty text sends nothing", async () => {
  const t = make({ stored: [storedUser] });
  await t.c.open("described");
  await t.c.send("   ");
  assert.equal(t.posts.length, 0);
});

test("Approve sends approve:[tool] and no message; Not now sends nothing", async () => {
  const t = make({ stored: [storedUser, storedCard], replies: [replyText] });
  await t.c.open("described");
  t.c.decline(t.c.getState().items![1].id);
  assert.equal(t.c.isDeclined(t.c.getState().items![1].id), true);
  assert.equal(t.posts.length, 0);
  await t.c.approve(card);
  assert.deepEqual(t.posts, [{ approve: ["select_dataset"] }]);
});

test("a reply is never followed by another model call", async () => {
  const t = make({ stored: [storedUser], replies: [replyCard, replyCard] });
  await t.c.open("described");
  await t.c.send("find me data");
  assert.equal(t.posts.length, 1);
});

test("503 hides the input and says the assistant is not set up", async () => {
  const t = make({ stored: [storedUser], replies: [new ApiError("no key", 503)] });
  await t.c.open("described");
  // the fake deps.postChat throws the ApiError directly
  await t.c.send("hello");
  const s = t.c.getState();
  assert.equal(s.unavailable, true);
  assert.match(s.error!.text, /not set up/);
});

test("409 says still working; Check again is a GET only and never a /chat", async () => {
  const t = make({ stored: [storedUser, storedCard], replies: [new ApiError("busy", 409)] });
  await t.c.open("described");
  await t.c.send("hello");
  assert.equal(t.c.getState().error?.busy, true);
  const posts = t.posts.length;
  const gets = t.gets.length;
  await t.c.checkAgain();
  assert.equal(t.posts.length, posts);
  assert.equal(t.gets.length, gets + 1);
  assert.equal(t.c.getState().error, null);
});

test("goal unanswered: the user chooses to send it again, then it is one call", async () => {
  const t = make({ replies: [new ApiError("boom", 500), replyText] });
  await t.c.open("described");
  assert.equal(t.c.goalUnanswered(), true);
  assert.equal(t.posts.length, 1);
  await t.c.sendGoalAgain();
  assert.equal(t.posts.length, 2);
  assert.equal(t.c.goalUnanswered(), false);
});

test("a server error says nothing was charged", async () => {
  const t = make({ stored: [storedUser], replies: [new ApiError("x", 500)] });
  await t.c.open("described");
  await t.c.send("hi");
  assert.match(t.c.getState().error!.text, /Nothing was charged/);
});

test("the first reply (the goal sent on boot) shows the user's goal, busy and a timer from the first second", async () => {
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  const t = make({ replies: [replyText], gate });
  const opening = t.c.open("described");
  await new Promise((r) => setTimeout(r, 20)); // the goal POST is now in flight
  const s = t.c.getState();
  assert.equal(s.busy, true);
  assert.ok(s.busySince !== null && Date.now() - s.busySince < 1000);
  assert.deepEqual(s.items?.map((i) => [i.role, i.text]), [["user", "predict churn"]]); // the screen can show the indicator
  release();
  await opening;
  const done = t.c.getState();
  assert.equal(done.busy, false);
  assert.equal(done.busySince, null);
  assert.equal(done.items?.length, 2);
});

test("history loading alone does not claim the assistant is thinking about the goal", async () => {
  const t = make({ stored: [storedUser, storedCard] });
  await t.c.open("described");
  assert.equal(t.c.getState().busySince, null);
});

test("a normal send also starts the timer", async () => {
  const t = make({ stored: [storedUser], replies: [replyText] });
  await t.c.open("data_chosen");
  const sending = t.c.send("hi");
  assert.ok(t.c.getState().busySince !== null);
  await sending;
  assert.equal(t.c.getState().busySince, null);
});

test("Not now is remembered per project and survives a reload (new controller, same storage)", async () => {
  const store = memoryStore();
  const a = make({ stored: [storedUser, storedCard], store });
  await a.c.open("described");
  const cardId = a.c.getState().items![1].id;
  a.c.decline(cardId);
  assert.equal(a.posts.length, 0);
  assert.equal(loadDeclined("p1", store).length, 1);
  const b = make({ stored: [storedUser, storedCard], store }); // a reload
  await b.c.open("described");
  assert.equal(b.c.isDeclined(b.c.getState().items![1].id), true);
  assert.equal(b.posts.length, 0);
  const other = make({ stored: [storedUser, storedCard], store: memoryStore() }); // another browser/project: asks again
  await other.c.open("described");
  assert.equal(other.c.isDeclined(other.c.getState().items![1].id), false);
});

test("a declined card from a fresh reply is still declined after reload (temporary id vs stored id)", async () => {
  const store = memoryStore();
  const a = make({ replies: [replyCard], store });
  await a.c.open("described"); // goal sent, card comes back with a local id
  const local = a.c.getState().items!.find((i) => i.card)!;
  a.c.decline(local.id);
  const b = make({ stored: [storedUser, storedCard], store });
  await b.c.open("described");
  assert.equal(b.c.isDeclined(storedCard.id), true);
});

test("asking again about the same dataset gives a new card that is not declined", async () => {
  const store = memoryStore();
  const t = make({ stored: [storedUser, storedCard], replies: [replyCard], store });
  await t.c.open("described");
  t.c.decline(storedCard.id);
  await t.c.send("show me that one again");
  const cards = t.c.getState().items!.filter((i) => i.card);
  assert.equal(cards.length, 2);
  assert.equal(t.c.isDeclined(cards[0].id), true);
  assert.equal(t.c.isDeclined(cards[1].id), false);
});

test("without working storage everything still runs", async () => {
  const broken: KV = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  const t = make({ stored: [storedUser, storedCard], store: broken });
  await t.c.open("described");
  t.c.decline(storedCard.id);
  assert.equal(t.c.isDeclined(storedCard.id), true); // lasts until reload
});

// ---- live steps (GET /activity polled every 2 s while a turn runs) ----
const tick = async (t: { mock: { timers: { tick: (ms: number) => void } } }, ms = 2000) => {
  t.mock.timers.tick(ms);
  await new Promise((r) => setImmediate(r)); // setImmediate is not mocked: lets the poll's promise chain settle
};
const settle = () => new Promise((r) => setImmediate(r));
// Wait until the goal has gone out (the controller shows the turn as running), so the poll timer exists.
const turnStarted = async (c: ChatController) => {
  for (let i = 0; i < 50 && c.getState().busySince === null; i++) await settle();
};
const line = (text: string, kind = "search", when = Date.now() + 1000): Act => ({ when: new Date(when).toISOString(), kind, text });

test("polling starts with a turn, shows only new lines (max 5, no user/reply lines), and stops and clears at the end", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  const old = line("Searched open datasets for old stuff", "search", Date.now() - 60_000);
  const lines = [old, line("You said: x", "you"), ...[1, 2, 3, 4, 5, 6].map((n) => line(`Step ${n}`)), line("The assistant replied", "reply")];
  const m = make({ activity: async () => lines, gate });
  const open = m.c.open("described"); // sends the goal: the turn is running
  await turnStarted(m.c);
  await tick(t);
  assert.deepEqual(m.c.getState().liveSteps, ["Step 2", "Step 3", "Step 4", "Step 5", "Step 6"]);
  assert.equal(m.activityCalls(), 1);
  release();
  await open;
  assert.deepEqual(m.c.getState().liveSteps, []);
  assert.equal(m.c.getState().busy, false);
  const after = m.activityCalls();
  await tick(t, 10_000);
  assert.equal(m.activityCalls(), after, "no polling after the turn ended");
});

test("a tick is skipped while the previous activity fetch is still in flight", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  let release!: () => void;
  const slow = new Promise<void>((r) => (release = r));
  let calls = 0;
  let endTurn!: () => void;
  const m = make({
    gate: new Promise<void>((r) => (endTurn = r)), // the turn runs until the end of the test (bootChat shares one call per project)
    activity: async () => {
      calls++;
      await slow;
      return [];
    },
  });
  const open = m.c.open("described");
  await turnStarted(m.c);
  await tick(t);
  await tick(t);
  await tick(t);
  assert.equal(calls, 1);
  release();
  await tick(t);
  await tick(t);
  assert.equal(calls, 2);
  endTurn();
  await open;
});

test("poll errors are ignored: no error state, polling continues; polling makes no extra POST", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  let n = 0;
  const m = make({
    gate,
    activity: async () => {
      if (++n === 1) throw new Error("database is locked");
      return [line("Looking at a dataset…", "working")];
    },
  });
  const open = m.c.open("described");
  await turnStarted(m.c);
  await tick(t);
  assert.equal(m.c.getState().error, null);
  assert.deepEqual(m.c.getState().liveSteps, []);
  await tick(t);
  assert.deepEqual(m.c.getState().liveSteps, ["Looking at a dataset…"]);
  release();
  await open;
  assert.deepEqual(m.posts, [{ message: "predict churn" }], "exactly one POST /chat for the goal");
});

test("a send starts polling and clears the live lines when the reply arrives; an idle chat does not poll", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval"] });
  let release!: () => void;
  const postGate = new Promise<void>((r) => (release = r));
  const m = make({ stored: [storedUser], replies: [replyText], postGate, activity: async () => [line("Checking data readiness…", "working")] });
  await m.c.open("data_chosen");
  await tick(t, 10_000);
  assert.equal(m.activityCalls(), 0, "an idle chat does not poll");
  const sending = m.c.send("hello");
  await tick(t);
  assert.deepEqual(m.c.getState().liveSteps, ["Checking data readiness…"]);
  release();
  await sending;
  assert.deepEqual(m.c.getState().liveSteps, []);
  assert.deepEqual(m.posts, [{ message: "hello" }], "polling adds no POST");
  const after = m.activityCalls();
  await tick(t, 10_000);
  assert.equal(m.activityCalls(), after);
});
