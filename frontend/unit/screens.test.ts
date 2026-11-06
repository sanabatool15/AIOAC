import test from "node:test";
import assert from "node:assert/strict";
import { formatWhen, overviewLine, paymentStateLabel, runStatusLabel, toActivity, toHistory } from "../lib/screens";
import type { BActivityItem, BHistory } from "../lib/api";
import { sx } from "./fixtures-screens";

const history = sx.history as unknown as BHistory;

test("formatWhen reads a zone-less server time as UTC and tolerates junk", () => {
  assert.equal(formatWhen("2026-11-06T17:13:05.323855", "UTC"), "Nov 6, 17:13");
  assert.equal(formatWhen("2026-11-06T17:13:06.699071+00:00", "UTC"), "Nov 6, 17:13");
  assert.equal(formatWhen(null), "");
  assert.equal(formatWhen("not a date"), "");
});

test("payment states are said in plain words", () => {
  assert.equal(paymentStateLabel("released", 0), "Nothing charged, hold released");
  assert.equal(paymentStateLabel("released", 12), "Finished: the rest was released");
  assert.equal(paymentStateLabel("fee_skipped"), "Finished: compute only, no success fee");
  assert.equal(paymentStateLabel("voided"), "Cancelled, nothing charged");
  assert.equal(paymentStateLabel("weird_state"), "weird state");
});

test("run statuses", () => {
  assert.equal(runStatusLabel("done"), "Finished");
  assert.equal(runStatusLabel("stopped"), "Stopped by you");
});

test("history from the real body: dollars, out of 100, no raw ids as text", () => {
  const v = toHistory(history);
  assert.equal(v.versions.length, 1);
  assert.match(v.versions[0].detail, /1,500 rows, 5 columns, predicting "left"/);
  assert.match(v.runs[0].result, /about 85 out of 100 right, target 70 out of 100\. Target reached\./);
  assert.equal(v.runs[0].passed, true);
  assert.equal(v.runs[0].cost, "$0.00");
  assert.equal(v.quotes[0].estimate, "$0.56");
  assert.equal(v.quotes[0].range, "$0.55 to $0.56");
  assert.equal(v.payment?.held, "$0.56");
  assert.equal(v.payment?.state, "Nothing charged, hold released");
  assert.equal(v.payment?.released, "$0.56");
});

test("history of a new project is empty and well formed", () => {
  const v = toHistory({ versions: [], runs: [], quotes: [], payment: null });
  assert.deepEqual(v, { versions: [], runs: [], quotes: [], payment: null });
  assert.deepEqual(toHistory(null).runs, []);
});

test("a run with no verification still reads honestly", () => {
  const h = { ...history, runs: [{ ...history.runs[0], result: { accuracy: 0.8 } }] } as BHistory;
  assert.match(toHistory(h).runs[0].result, /About 80 out of 100 right \(an estimate\)/);
  const none = { ...history, runs: [{ ...history.runs[0], result: null }] } as BHistory;
  assert.equal(toHistory(none).runs[0].result, "No result saved.");
});

test("activity keeps the server sentences and adds a time", () => {
  const a = toActivity(sx.activity as unknown as BActivityItem[]);
  assert.equal(a.length, 12);
  assert.equal(a[0].text, 'You said: "Which subscription customers will leave?"');
  assert.ok(a[0].when.length > 0);
  assert.equal(new Set(a.map((x) => x.key)).size, 12);
  assert.deepEqual(toActivity(undefined), []);
});

test("overview line covers every status", () => {
  for (const s of ["described", "data_chosen", "readiness_done", "baseline_done", "quoted", "awaiting_payment", "paid", "training", "done", "stopped", "voided", "failed"])
    assert.ok(overviewLine(s).length > 10, s);
  assert.equal(overviewLine("???"), "");
});

import { batchProblem, buildRecord, cellText, csvRowCount, fileSize, sklearnNote, tabFromQuery, toPrediction } from "../lib/screens";
import type { BBatch, BModel, BPredict } from "../lib/api";

const model = sx.model as unknown as Extract<BModel, { available: true }>;

test("buildRecord drops empty fields and turns number columns into numbers", () => {
  const r = buildRecord(model.columns, { months_active: " 12 ", plan: "basic", days_since_last_purchase: "" });
  assert.deepEqual(r, { record: { months_active: 12, plan: "basic" }, error: null });
});

test("buildRecord says what is wrong in plain words", () => {
  assert.match(buildRecord(model.columns, { months_active: "lots" }).error ?? "", /"months_active" needs a number/);
  assert.equal(buildRecord(model.columns, {}).error, "Fill in at least one field.");
  assert.equal(buildRecord(model.columns, { plan: "   " }).error, "Fill in at least one field.");
});

test("the real model body has the shape the form needs", () => {
  assert.equal(model.available, true);
  assert.ok(model.columns.some((c) => c.kind === "text" && (c.choices ?? []).length > 0));
  assert.ok(model.columns.some((c) => c.kind === "number" && c.example !== null));
});

test("prediction shows 'about N out of 100', biggest first, with the note", () => {
  const v = toPrediction(sx.predict as unknown as BPredict);
  assert.equal(v.answer, "No");
  assert.deepEqual(v.rows.map((r) => r.text), ["about 82 out of 100", "about 18 out of 100"]);
  assert.equal(v.note, "an estimate, not a promise");
  const none = toPrediction({ prediction: 3, probabilities: null, note: "" });
  assert.equal(none.answer, "3");
  assert.deepEqual(none.rows, []);
  assert.equal(none.note, "an estimate, not a promise");
});

test("csv checks: empty, header only, too many rows", () => {
  assert.equal(csvRowCount("a,b\n1,2\n\n3,4\n"), 2);
  assert.match(batchProblem("") ?? "", /Paste CSV text/);
  assert.match(batchProblem("a,b\n") ?? "", /at least one row/);
  assert.equal(batchProblem("a\n1\n2"), null);
  const big = "a\n" + Array.from({ length: 5001 }, (_, i) => String(i)).join("\n");
  assert.match(batchProblem(big) ?? "", /5,001 rows\. The limit is 5,000/);
  assert.equal(batchProblem("a\n" + Array.from({ length: 5000 }, (_, i) => String(i)).join("\n")), null);
});

test("the batch body from the server renders as cells", () => {
  const b = sx.batch as unknown as BBatch;
  assert.deepEqual(b.columns, ["months_active", "days_since_last_purchase", "prediction", "confidence"]);
  assert.equal(cellText(b.preview[0].confidence), "0.9833");
  assert.equal(cellText(null), "");
  assert.equal(cellText(12), "12");
  assert.match(b.csv_text, /^months_active,/);
});

test("file size and scikit-learn note", () => {
  assert.equal(fileSize(500), "500 bytes");
  assert.equal(fileSize(7714763), "7.4 MB");
  assert.match(sklearnNote("1.9.1"), /scikit-learn 1\.9\.1/);
  assert.match(sklearnNote(null), /same scikit-learn version/);
});

test("?tab= picks a tab and falls back to Overview", () => {
  assert.equal(tabFromQuery("model"), "Model");
  assert.equal(tabFromQuery("History"), "History");
  assert.equal(tabFromQuery("nonsense"), "Overview");
  assert.equal(tabFromQuery(undefined), "Overview");
});

import { llmCostText, toBilling, toUsage } from "../lib/screens";
import type { BAccountPayment, BUsage } from "../lib/api";

test("usage from the real body: counts, dollars, tokens, no AI cost when zero", () => {
  const v = toUsage(sx.usage as unknown as BUsage);
  assert.ok(v);
  const t = Object.fromEntries(v.tiles.map((x) => [x.label, x.value]));
  assert.equal(t["Projects"], "1");
  assert.equal(t["Training runs"], "1");
  assert.equal(t["Compute charged"], "$0.00");
  assert.equal(t["Released back to you"], "$0.56");
  assert.equal(t["AI assistant tokens"], "0");
  assert.equal(v.llmCost, null);
  assert.equal(v.tiles.find((x) => x.label === "AI assistant tokens")?.note, undefined);
  assert.equal(v.activity.length, 3);
  assert.equal(toUsage(null), null);
});

test("AI cost shows only above zero, as an estimate", () => {
  assert.equal(llmCostText(0), null);
  assert.equal(llmCostText(null), null);
  assert.equal(llmCostText(1234), "$0.0012");
  assert.equal(llmCostText(250_000), "$0.25");
  const u = { ...(sx.usage as unknown as BUsage), llm_tokens: 12345, llm_cost_micros: 1234 };
  const tile = toUsage(u)?.tiles.find((x) => x.label === "AI assistant tokens");
  assert.equal(tile?.value, "12,345");
  assert.equal(tile?.note, "Estimated cost $0.0012");
});

test("billing rows from the real body link to the project and use plain states", () => {
  const rows = toBilling(sx.payments as unknown as BAccountPayment[]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].projectId, sx.pid);
  assert.equal(rows[0].goal, "Which subscription customers will leave?");
  assert.equal(rows[0].state, "Nothing charged, hold released");
  assert.deepEqual([rows[0].held, rows[0].compute, rows[0].fee, rows[0].released, rows[0].total], ["$0.56", "$0.00", "$0.00", "$0.56", "$0.00"]);
  assert.deepEqual(toBilling([]), []);
  assert.deepEqual(toBilling(null), []);
});

import { PUBLIC_NOT_AVAILABLE, shareLink, toPublic } from "../lib/screens";
import type { BPublicResult } from "../lib/api";

test("share link is built from the page origin", () => {
  assert.equal(shareLink("http://localhost:3000", "abc"), "http://localhost:3000/s/abc");
  assert.equal(shareLink("https://x.example/", "abc"), "https://x.example/s/abc");
  assert.match(shareLink("http://h", sx.share.token), /^http:\/\/h\/s\/[A-Za-z0-9_-]{43}$/);
  assert.equal(sx.share.url_path, `/s/${sx.share.token}`);
});

test("public view reads the real public body: out of 100, estimate note, nothing else", () => {
  const v = toPublic(sx.public as unknown as BPublicResult);
  assert.equal(v.goal, "Which subscription customers will leave?");
  assert.equal(v.dataset, "scikit-learn/churn-prediction (1,500 rows)");
  assert.equal(v.answerColumn, "left");
  assert.equal(v.freeTest, "about 86 out of 100 right, a simple guess gets 70 out of 100");
  assert.deepEqual(v.verified, { value: "85 out of 100", target: "70 out of 100", passed: true });
  assert.match(v.note, /estimates/);
  const text = JSON.stringify(v);
  assert.doesNotMatch(text, /\$|@|payment|email|cents/i);
  assert.deepEqual(Object.keys(v).sort(), ["answerColumn", "dataset", "finished", "freeTest", "goal", "note", "verified"]);
});

test("public view copes with a project that has not finished", () => {
  const v = toPublic({ goal: "g", status: "described", dataset: null, baseline: null, verification: null, finished_at: null, is_estimate_note: "" });
  assert.equal(v.dataset, null);
  assert.equal(v.verified, null);
  assert.equal(v.freeTest, null);
  assert.match(v.note, /estimates/);
  assert.equal(PUBLIC_NOT_AVAILABLE, "This link is not available");
});
