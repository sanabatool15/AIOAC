import test, { afterEach, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { authMessage, demoLogin, login, logout, me, signup } from "../lib/api-real";
import { ApiError } from "../lib/api";
import { getRealSnapshot, getRealUser, clearRealUser, safeNext } from "../lib/session";

type Call = { url: string; init: RequestInit };
let calls: Call[] = [];
const realFetch = globalThis.fetch;
const user = { id: "u1", email: "a@b.co", org_id: null };

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
beforeEach(() => clearRealUser());
afterEach(() => {
  globalThis.fetch = realFetch;
});

test("login posts credentials with the cookie and marks the user signed in", async () => {
  reply([{ body: { user } }]);
  await login("a@b.co", "secret123");
  assert.equal(calls[0].url, "http://localhost:8000/auth/login");
  assert.equal(calls[0].init.credentials, "include");
  assert.equal(calls[0].init.body, JSON.stringify({ email: "a@b.co", password: "secret123" }));
  assert.equal(getRealSnapshot(), "in");
  assert.equal(getRealUser()?.email, "a@b.co");
});

test("wrong password gives a plain message and stays signed out", async () => {
  reply([{ status: 401, body: { detail: "wrong email or password" } }]);
  await assert.rejects(login("a@b.co", "nope"), /Wrong email or password/);
  assert.equal(getRealSnapshot(), "out");
});

test("signup errors: email taken, short password, login not set up, too many tries", async () => {
  reply([{ status: 409, body: { detail: "that email is already registered" } }]);
  await assert.rejects(signup("a@b.co", "secret123"), /already registered/);
  reply([{ status: 422, body: { detail: [{ msg: "too short", loc: ["body", "password"] }] } }]);
  await assert.rejects(signup("a@b.co", "short"), /at least 8 characters/);
  reply([{ status: 503, body: { detail: "login is not set up" } }]);
  await assert.rejects(signup("a@b.co", "secret123"), /not set up on this server/);
  reply([{ status: 429, body: { detail: "too many tries" } }]);
  await assert.rejects(login("a@b.co", "secret123"), /Too many tries/);
});

test("signup success and demo login set the user; demo 404 says it is unavailable", async () => {
  reply([{ body: { user } }]);
  await signup("a@b.co", "secret123");
  assert.equal(getRealSnapshot(), "in");
  clearRealUser();
  reply([{ status: 404, body: { detail: "Not Found" } }]);
  await assert.rejects(demoLogin(), /not available/);
  reply([{ body: { user } }]);
  await demoLogin();
  assert.equal(calls[0].url, "http://localhost:8000/auth/demo");
});

test("me: 200 signs in, 401 signs out without redirecting, network failure stays unknown", async () => {
  reply([{ body: { user } }]);
  assert.equal((await me())?.id, "u1");
  reply([{ status: 401, body: { detail: "please sign in" } }]);
  assert.equal(await me(), null);
  assert.equal(getRealSnapshot(), "out");
  clearRealUser();
  globalThis.fetch = (async () => {
    throw new TypeError("offline");
  }) as typeof fetch;
  await assert.rejects(me(), /could not reach/);
});

test("logout clears the user and the per-user browser memory", async () => {
  reply([{ body: { user } }]);
  await login("a@b.co", "secret123");
  reply([{ body: { ok: true } }]);
  await logout();
  assert.equal(calls[0].url, "http://localhost:8000/auth/logout");
  assert.equal(getRealSnapshot(), "out");
  assert.equal(getRealUser(), null);
  // a failed logout call still forgets the user here
  reply([{ body: { user } }]);
  await login("a@b.co", "secret123");
  reply([{ status: 500, body: {} }]);
  await assert.rejects(logout());
  assert.equal(getRealSnapshot(), "out");
});

test("a 401 from another call clears the user and goes to login once; /auth/* does not redirect", async () => {
  const { api } = await import("../lib/api");
  const assigned: string[] = [];
  (globalThis as unknown as { window: unknown }).window = {
    location: { pathname: "/c/p1", search: "?x=1", assign: (u: string) => assigned.push(u) },
  };
  try {
    reply([{ body: { user } }]);
    await login("a@b.co", "secret123");
    reply([{ status: 401, body: { detail: "please sign in" } }]);
    await assert.rejects(api("/projects"), (e: unknown) => e instanceof ApiError && e.status === 401);
    assert.equal(getRealSnapshot(), "out");
    assert.deepEqual(assigned, ["/login?next=%2Fc%2Fp1%3Fx%3D1"]);
    // on the login page itself: no loop
    (globalThis as unknown as { window: { location: { pathname: string } } }).window.location.pathname = "/login";
    reply([{ status: 401, body: { detail: "please sign in" } }]);
    await assert.rejects(api("/projects"));
    assert.equal(assigned.length, 1);
    // /auth/ calls never redirect
    reply([{ status: 401, body: { detail: "wrong email or password" } }]);
    await assert.rejects(api("/auth/login", { body: {} }));
    assert.equal(assigned.length, 1);
  } finally {
    delete (globalThis as unknown as { window?: unknown }).window;
  }
});

test("safeNext keeps only same-site paths; authMessage falls back to the server text", () => {
  assert.equal(safeNext("/c/abc"), "/c/abc");
  assert.equal(safeNext("//evil.com"), "/");
  assert.equal(safeNext("https://evil.com"), "/");
  assert.equal(safeNext(null), "/");
  assert.equal(authMessage(new ApiError("boom", 500)), "boom");
});
