import test from "node:test";
import assert from "node:assert/strict";
import type { BPredict, BTraining } from "../lib/api";
import { toForecast } from "../lib/adapters";
import { toResultView } from "../lib/result-view";
import { toPrediction } from "../lib/screens";
import { TASK_CHOICES } from "../components/shell/task-type-chooser";

const T = (x: unknown) => x as BTraining;
const JARGON = /\b(f1|precision|recall|mae|rmse|r2|r-squared|silhouette|k-?means|regression|clustering|train\/test split)\b/i;

test("a number: the final check is the server's words, never 'out of 100 right'", () => {
  const v = toResultView(
    T({
      status: "done",
      result: {
        task_type: "regression",
        final_check_text: "on rows it never saw the model was typically off by about $12,000 (an estimate)",
        verification: { value: 0.7, target: 0.6, passed: true },
      },
    }),
  );
  assert.equal(v.kind, "verified");
  assert.match(v.body, /^On rows it never saw the model was typically off by about \$12,000 \(an estimate\)\./);
  assert.doesNotMatch(v.body, /out of 100 right/);
});

test("a missed number goal still says compute only and no success fee", () => {
  const v = toResultView(
    T({ status: "done", result: { task_type: "forecast", final_check_text: "typically off by about 9 (an estimate)", verification: { value: 0.2, target: 0.6, passed: false } } }),
  );
  assert.equal(v.kind, "missed");
  assert.match(v.body, /compute only, no success fee/);
});

test("groups and unusual records have no success fee and say so", () => {
  for (const task of ["grouping", "unusual"] as const) {
    const v = toResultView(T({ status: "done", result: { task_type: task, final_check_text: "on rows it never saw the groups were about 90 out of 100 steady (an estimate)", verification: { value: 0.9, target: 0.6, passed: true } } }));
    assert.match(v.body, /no success fee for this kind of task/);
    assert.doesNotMatch(v.body, /target/i);
  }
});

test("a yes/no result keeps its old words", () => {
  const v = toResultView(T({ status: "done", result: { verification: { value: 0.84, target: 0.8, passed: true } } }));
  assert.match(v.body, /84 out of 100/);
});

test("predictions: a number is rounded with its typical miss; an unusual record gets a rank; a group is plain text", () => {
  const num = toPrediction({ prediction: 312345.678, probabilities: null, note: "an estimate, not a promise", task_type: "regression", typical_error: 18250.4 } as BPredict);
  assert.equal(num.answer, "312,345.68");
  assert.match(num.extra[0], /usually off by about 18,250/);
  const odd = toPrediction({ prediction: "looks unusual", probabilities: null, note: "n", task_type: "unusual", unusual_score: 0.83, looks_unusual: true } as BPredict);
  assert.equal(odd.answer, "looks unusual");
  assert.match(odd.extra[0], /about 83 out of 100/);
  assert.equal(toPrediction({ prediction: "group 2", probabilities: null, note: "n", task_type: "grouping", group: 2 } as BPredict).extra.length, 0);
  assert.deepEqual(toPrediction({ prediction: "yes", probabilities: { yes: 0.7 }, note: "n" } as BPredict).extra, []);
});

test("the forecast keeps the server's plain words", () => {
  const f = toForecast({ forecast_id: "f", metric: "error_reduction", target: 0.6, is_estimate: true, predicted_metric: 0.7, band_low: 0.5, band_high: 0.8, confidence: 0.8, eligible: true, reason: null, min_confidence: 0.6, suggested_target: null, issues: [], plain: { typical_error_text: "typically off by about $9", band_text: "b", target_text: "t", confidence_text: "c" } });
  assert.equal(f?.plain?.typical_error_text, "typically off by about $9");
});

test("the five kinds are named in plain words and only the first three need an answer column", () => {
  assert.deepEqual(TASK_CHOICES.map((c) => c.id), ["classification", "regression", "forecast", "grouping", "unusual"]);
  assert.deepEqual(TASK_CHOICES.map((c) => c.needsTarget), [true, true, true, false, false]);
  for (const c of TASK_CHOICES) assert.doesNotMatch(`${c.title} ${c.hint}`, JARGON);
});
