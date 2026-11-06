// Fixtures copied from real backend responses (curl against a local uvicorn with a temp database, 2026-11-04).
// Training and receipt bodies follow specs/api.md A2/A5 and the assertions in backend/tests/e2e.
export const fx = {
  "created": {
    "id": "46ddd82c9f6e4e1cacd8274db21f9f48",
    "status": "described"
  },
  "projectNew": {
    "id": "46ddd82c9f6e4e1cacd8274db21f9f48",
    "goal": "Which customers may stop buying?",
    "status": "described",
    "readiness_grade": null,
    "trust_level": null,
    "baseline": null,
    "quote": null,
    "dataset": null,
    "readiness": null,
    "forecast": null,
    "payment": null,
    "run": null
  },
  "upload": {
    "candidate_id": "a3fc516e1a8d43f38773013301ce8c8b",
    "rows": 1500
  },
  "select": {
    "rows": 1500,
    "target": "churn",
    "status": "data_chosen"
  },
  "readiness": {
    "grade": "A",
    "findings": [
      {
        "kind": "OK",
        "text": "Enough rows to train a useful model"
      },
      {
        "kind": "NOTE",
        "text": "5 duplicate rows found (removed automatically)"
      }
    ],
    "status": "readiness_done"
  },
  "baseline": {
    "accuracy": 0.7290969899665551,
    "simple_guess_accuracy": 0.7391304347826086,
    "trust_level": "Low",
    "status": "baseline_done"
  },
  "forecastIneligible": {
    "forecast_id": "57a9e31065d940718c3c3f76afea6684",
    "metric": "accuracy",
    "target": 0.8,
    "is_estimate": true,
    "predicted_metric": 0.779,
    "band_low": 0.6385,
    "band_high": 0.9195,
    "confidence": 0.385,
    "eligible": false,
    "reason": "We are only about 38% sure the full run would reach your target of 80 out of 100. That is not enough to sell you a run. A lower target or better data would help. We can honestly offer a target of about 76 out of 100.",
    "min_confidence": 0.6,
    "suggested_target": 0.76,
    "issues": [
      "5 duplicate rows found (removed automatically)",
      "The free test barely beats a simple guess, so the data may not hold much signal for this question."
    ]
  },
  "forecastOk": {
    "forecast_id": "99408d005d2f495cbe21a12326e90f80",
    "metric": "accuracy",
    "target": 0.7,
    "is_estimate": true,
    "predicted_metric": 0.779,
    "band_low": 0.6385,
    "band_high": 0.9195,
    "confidence": 0.865,
    "eligible": true,
    "reason": null,
    "pilot": {
      "rows_used": 100,
      "share_of_data": 0.067,
      "rungs": [
        {
          "rows": 25,
          "scores": {
            "logistic": 0.8796,
            "forest": 0.838,
            "boosting": 0.8796
          }
        },
        {
          "rows": 50,
          "scores": {
            "logistic": 0.8002,
            "boosting": 0.8199
          }
        },
        {
          "rows": 100,
          "scores": {
            "boosting": 0.779
          }
        }
      ],
      "kept": "a boosted-trees model",
      "dropped": [
        {
          "model": "a forest of decision trees",
          "dropped_after_rows": 25,
          "score": 0.838
        },
        {
          "model": "a simple linear model",
          "dropped_after_rows": 50,
          "score": 0.8002
        }
      ],
      "learning_curve": [
        {
          "training_rows": 17,
          "accuracy": 0.8796
        },
        {
          "training_rows": 33,
          "accuracy": 0.8199
        },
        {
          "training_rows": 67,
          "accuracy": 0.779
        }
      ],
      "full_run_training_rows": 957,
      "pilot_seconds": 52.22
    },
    "min_confidence": 0.6,
    "suggested_target": null,
    "issues": []
  },
  "quote": {
    "quote_id": "82bc9c09f92f4efb9f23863b2ab7adb2",
    "is_estimate": true,
    "estimate_cents": 56,
    "low_cents": 55,
    "high_cents": 56,
    "cap_cents": 56,
    "compute_estimate_cents": 53,
    "compute_cap_cents": 53,
    "success_fee_estimate_cents": 3,
    "success_fee_max_cents": 3,
    "forecast_confidence": 0.865,
    "target": 0.7,
    "terms": "You pay compute either way. The success fee only if the target is verified."
  },
  "approve": {
    "approved": true,
    "cap_cents": 56
  },
  "order": {
    "payment_id": "7d778b1973af4aebbf071b1960104b0d",
    "hold_cents": 56,
    "compute_max_cents": 53,
    "success_fee_max_cents": 3,
    "approve_url": "https://www.sandbox.paypal.com/checkoutnow?token=01B00918MA8909526",
    "state": "none"
  }
} as const;

export const projectQuoted = {
  id: "46ddd82c9f6e4e1cacd8274db21f9f48",
  goal: "Which customers may stop buying?",
  status: "awaiting_payment",
  readiness_grade: "A",
  trust_level: "Low",
  baseline: { accuracy: 0.7290969899665551, simple_guess_accuracy: 0.7391304347826086 },
  quote: {
    id: "82bc9c09f92f4efb9f23863b2ab7adb2",
    estimate_cents: 56,
    low_cents: 55,
    high_cents: 56,
    cap_cents: 56,
    success_fee_max_cents: 3,
    approved: true,
  },
  dataset: { rows: 1500, columns: 4, target: "churn", source: "upload", license: null },
  readiness: {
    grade: "A",
    findings: [
      { kind: "OK", text: "Enough rows to train a useful model" },
      { kind: "NOTE", text: "5 duplicate rows found (removed automatically)" },
    ],
  },
  forecast: null,
  payment: {
    payment_id: "7d778b1973af4aebbf071b1960104b0d",
    state: "none",
    approve_url: "https://www.sandbox.paypal.com/checkoutnow?token=01B00918MA8909526",
    hold_cents: 56,
  },
  run: null,
};

export const trainingNotStarted = { status: "not_started" } as const;
export const trainingRunning = {
  run_id: "r1",
  status: "running",
  stage: "training the model",
  fraction: 0.5,
  elapsed_seconds: 42,
  spend_so_far_cents: 12,
  spend_is_estimate: true,
  cap_cents: 53,
  eta: { low_seconds: 30, high_seconds: 150, is_estimate: true },
  stop_requested: false,
  result: null,
} as const;
export const trainingDoneMissed = {
  run_id: "r1",
  status: "done",
  stage: "done",
  fraction: 1,
  elapsed_seconds: 90,
  spend_so_far_cents: 40,
  spend_is_estimate: true,
  cap_cents: 53,
  eta: null,
  stop_requested: false,
  result: {
    accuracy: 0.72,
    simple_guess_accuracy: 0.7,
    runtime_seconds: 88,
    verification: { value: 0.72, target: 0.8, passed: false },
  },
} as const;
export const receiptMissed = {
  payment_id: "7d778b1973af4aebbf071b1960104b0d",
  project_id: "46ddd82c9f6e4e1cacd8274db21f9f48",
  state: "released",
  hold_cents: 56,
  compute_captured_cents: 40,
  fee_captured_cents: 0,
  released_cents: 16,
  total_charged_cents: 40,
  approve_url: null,
} as const;

// Verified run (backend/tests/e2e/test_payments_and_demo.py: target met, compute + fee captured, rest released).
export const trainingDoneVerified = {
  ...trainingDoneMissed,
  result: {
    accuracy: 0.84,
    simple_guess_accuracy: 0.7,
    runtime_seconds: 88,
    verification: { value: 0.84, target: 0.8, passed: true },
  },
} as const;
export const receiptVerified = {
  ...receiptMissed,
  compute_captured_cents: 40,
  fee_captured_cents: 2,
  released_cents: 14,
  total_charged_cents: 42,
} as const;
export const receiptPendingSettle = { ...receiptMissed, state: "compute_captured", released_cents: 0, total_charged_cents: 40 } as const;
export const trainingStopped = { ...trainingDoneMissed, status: "stopped", result: { stopped_by_user: true } } as const;
export const trainingFailed = { ...trainingDoneMissed, status: "failed", result: { error: "training failed" } } as const;
