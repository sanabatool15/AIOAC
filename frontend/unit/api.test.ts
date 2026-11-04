import test, { afterEach, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, detailMessage } from "../lib/api";
import { createOrder, startPayment, startChat } from "../lib/api-real";
import { fx } from "./fixtures";

type Call = { url: string; init: RequestInit };
let calls: Call[] = [];
const realFetch = globalThis.fetch;

function reply(queue: { status?: number; body?: unknown }[]) {
  calls = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const next = queue.shift() ?? { status: 500, body: {} };
    return new Response(JSON.stringify(next.body ?? null), {
      status: next.status ?? 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
}
beforeEach(() => {
  calls = [];
});
afterEach(() => {
  globalThis.fetch = realFetch;
});

test("sends JSON with credentials to the base URL and parses the body", async () => {
  reply([{ body: fx.created }]);
  const r = await startChat("Which customers may stop buying?");
  assert.equal(r.id, fx.created.id);
  assert.equal(calls[0].url, "http://localhost:8000/projects");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.credentials, "include");
  assert.equal(calls[0].init.body, JSON.stringify({ goal: "Which customers may stop buying?" }));
});

test("a 409 shows the backend's plain text, with the status", async () => {
  const detail = "no server-confirmed hold for the current quote";
  reply([{ status: 409, body: { detail } }]);
  await assert.rejects(
    () => api("/projects/x/train", { method: "POST" }),
    (e: unknown) => e instanceof ApiError && e.status === 409 && e.message === detail,
  );
});

test("the real not-eligible quote refusal reads as plain text", async () => {
  const detail = "We are only about 38% sure the full run would reach your target of 80 out of 100.";
  reply([{ status: 409, body: { detail } }]);
  await assert.rejects(() => api("/agreements/x/quote", { method: "POST" }), { message: detail });
});

test("422 list details become one plain sentence; 5xx and network errors are plain", async () => {
  assert.match(detailMessage({ detail: [{ msg: "ensure this value is greater than 0" }] }, 422), /greater than 0/);
  assert.match(detailMessage(null, 500), /Nothing was charged/);
  assert.equal(detailMessage(null, 404), "We could not find that.");
  globalThis.fetch = (async () => {
    throw new TypeError("fetch failed");
  }) as typeof fetch;
  await assert.rejects(() => api("/health"), (e: unknown) => e instanceof ApiError && e.status === 0 && /reach the server/.test(e.message));
});

test("startPayment approves the quote, creates the order, and returns the PayPal link", async () => {
  reply([{ body: fx.approve }, { body: fx.order }]);
  const url = await startPayment("p1");
  assert.equal(url, fx.order.approve_url);
  assert.deepEqual(
    calls.map((c) => [c.init.method, c.url.replace("http://localhost:8000", "")]),
    [
      ["POST", "/projects/p1/quote/approve"],
      ["POST", "/payments/orders"],
    ],
  );
  assert.equal(calls[1].init.body, JSON.stringify({ project_id: "p1" }));
});

test("startPayment stops if the quote cannot be approved (no order is created)", async () => {
  reply([{ status: 400, body: { detail: "this quote has expired; ask for a new one" } }]);
  await assert.rejects(() => startPayment("p1"), { message: "this quote has expired; ask for a new one" });
  assert.equal(calls.length, 1);
});

test("createOrder surfaces a PayPal outage as a plain message", async () => {
  reply([{ status: 502, body: { detail: "The payment service could not be reached. Nothing was charged." } }]);
  await assert.rejects(() => createOrder("p1"), (e: unknown) => e instanceof ApiError && e.status === 502 && /Nothing was charged/.test(e.message));
});
