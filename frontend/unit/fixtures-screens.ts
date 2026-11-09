// Fixtures copied from real JSON: the browser test server (backend/tests/browser_server.py) after a full run to a finished
// project, 2026-11-06. Shapes follow specs/api.md section D and backend/tests/e2e/test_screens.py.
export const sx = {
  "pid": "a4ae4b3e34f54543a30d8386ab0a48b3",
  "history": {
    "versions": [
      {
        "id": "566bfe08f52646f7b88f298821bde011",
        "parent_id": null,
        "rows": 1500,
        "columns": 5,
        "target_column": "left",
        "source": "Hugging Face",
        "license": "mit",
        "notes": null,
        "created_at": "2026-11-06T17:13:03.184425"
      }
    ],
    "runs": [
      {
        "id": "2ff2c3e61df7409c8aa06e30870c96a3",
        "status": "done",
        "backend": "local",
        "cost_cents": 0,
        "started_at": "2026-11-06T17:13:05.323855",
        "finished_at": "2026-11-06T17:13:05.937175",
        "result": {
          "accuracy": 0.8242677824267782,
          "simple_guess_accuracy": 0.694560669456067,
          "verification": {
            "value": 0.8494983277591973,
            "target": 0.7,
            "passed": true
          }
        }
      }
    ],
    "quotes": [
      {
        "id": "e5383cd12a5341f58952e14aa268230c",
        "estimate_cents": 56,
        "low_cents": 55,
        "high_cents": 56,
        "cap_cents": 56,
        "approved": true,
        "created_at": "2026-11-06T17:13:05.264146"
      }
    ],
    "payment": {
      "payment_id": "507170ee6ad6457c87c2b553fe4e4802",
      "state": "released",
      "hold_cents": 56,
      "compute_captured_cents": 0,
      "fee_captured_cents": 0,
      "released_cents": 56,
      "total_charged_cents": 0
    }
  },
  "activity": [
    {
      "when": "2026-11-06T17:13:03.035594",
      "kind": "you",
      "text": "You said: \"Which subscription customers will leave?\""
    },
    {
      "when": "2026-11-06T17:13:03.063485",
      "kind": "search",
      "text": "Searched open datasets for customer churn, subscription cancel"
    },
    {
      "when": "2026-11-06T17:13:03.081099",
      "kind": "look",
      "text": "Looked at \"hf:scikit-learn/churn-prediction\" (1,500 rows)"
    },
    {
      "when": "2026-11-06T17:13:03.116492",
      "kind": "download",
      "text": "Downloaded a dataset (1,500 rows)"
    },
    {
      "when": "2026-11-06T17:13:03.133316",
      "kind": "approval",
      "text": "Waited for your approval"
    },
    {
      "when": "2026-11-06T17:13:03.165521",
      "kind": "you",
      "text": "You said: \"yes\""
    },
    {
      "when": "2026-11-06T17:13:03.179089",
      "kind": "approved",
      "text": "Allowed to choose the dataset"
    },
    {
      "when": "2026-11-06T17:13:03.193213",
      "kind": "choose",
      "text": "Chose the dataset (1,500 rows) to predict \"left\""
    },
    {
      "when": "2026-11-06T17:13:03.208498",
      "kind": "reply",
      "text": "The assistant replied"
    },
    {
      "when": "2026-11-06T17:13:05.247071",
      "kind": "forecast",
      "text": "Forecast ready: about 98% chance of reaching your target; this run can be sold"
    },
    {
      "when": "2026-11-06T17:13:05.286348",
      "kind": "approved",
      "text": "Allowed to ask for the payment hold"
    },
    {
      "when": "2026-11-06T17:13:05.319758",
      "kind": "approved",
      "text": "Allowed to start training"
    }
  ],
  "model": {
    "available": true,
    "trained_at": "2026-11-06T17:13:05.947014",
    "target": "left",
    "accuracy": 0.8242677824267782,
    "simple_guess_accuracy": 0.694560669456067,
    "is_estimate_note": "Accuracy figures are estimates from held-back test rows. They are not a promise about future results.",
    "sklearn_version": "1.9.1",
    "size_bytes": 7714763,
    "usable": true,
    "unusable_reason": null,
    "columns": [
      {
        "name": "months_active",
        "label": "Months as a customer",
        "kind": "number",
        "example": 31.0,
        "choices": null
      },
      {
        "name": "days_since_last_purchase",
        "label": null,
        "kind": "number",
        "example": 62.5,
        "choices": null
      },
      {
        "name": "orders_this_year",
        "label": null,
        "kind": "number",
        "example": 6.0,
        "choices": null
      },
      {
        "name": "plan",
        "label": null,
        "kind": "text",
        "example": "basic",
        "choices": [
          "basic",
          "plus",
          "pro"
        ]
      }
    ],
    "classes": [
      "No",
      "Yes"
    ]
  },
  "usage": {
    "projects": 1,
    "training_runs": 1,
    "compute_charged_cents": 0,
    "success_fees_cents": 0,
    "released_cents": 56,
    "llm_tokens": 0,
    "llm_cost_micros": 0,
    "recent_activity": [
      {
        "when": "2026-11-06T17:13:05.937175",
        "kind": "training",
        "text": "Training finished for \"Which subscription customers will leave?\""
      },
      {
        "when": "2026-11-06T17:13:05.290005",
        "kind": "payment",
        "text": "Held $0.56 for \"Which subscription customers will leave?\" (nothing charged)"
      },
      {
        "when": "2026-11-06T17:13:03.006343",
        "kind": "project",
        "text": "Started \"Which subscription customers will leave?\""
      }
    ]
  },
  "payments": [
    {
      "payment_id": "507170ee6ad6457c87c2b553fe4e4802",
      "state": "released",
      "hold_cents": 56,
      "compute_captured_cents": 0,
      "fee_captured_cents": 0,
      "released_cents": 56,
      "total_charged_cents": 0,
      "project_id": "a4ae4b3e34f54543a30d8386ab0a48b3",
      "goal": "Which subscription customers will leave?",
      "created_at": "2026-11-06T17:13:05.290005"
    }
  ],
  "predict": {
    "prediction": "No",
    "probabilities": {
      "No": 0.8167,
      "Yes": 0.1833
    },
    "note": "an estimate, not a promise"
  },
  "batch": {
    "rows": 25,
    "columns": [
      "months_active",
      "days_since_last_purchase",
      "prediction",
      "confidence"
    ],
    "preview": [
      {
        "months_active": 0,
        "days_since_last_purchase": 3,
        "prediction": "No",
        "confidence": 0.9833
      },
      {
        "months_active": 1,
        "days_since_last_purchase": 4,
        "prediction": "No",
        "confidence": 0.9833
      },
      {
        "months_active": 2,
        "days_since_last_purchase": 5,
        "prediction": "No",
        "confidence": 0.9867
      }
    ],
    "csv_text": "months_active,days_since_last_purchase,prediction,confidence\n0,3,No,0.9833\n1,4,No,0.9833\n2,5,No,0.9867\n"
  },
  "share": {
    "token": "dlOqE5JUsc6rJHf6kVP8-DTfbMAjKUXReAMyJso88-E",
    "url_path": "/s/dlOqE5JUsc6rJHf6kVP8-DTfbMAjKUXReAMyJso88-E",
    "created_at": "2026-11-06T17:13:06.699071+00:00"
  },
  "public": {
    "goal": "Which subscription customers will leave?",
    "status": "done",
    "dataset": {
      "name": "scikit-learn/churn-prediction",
      "rows": 1500,
      "target": "left"
    },
    "baseline": {
      "accuracy": 0.8595317725752508,
      "simple_guess_accuracy": 0.6956521739130435
    },
    "verification": {
      "value": 0.8494983277591973,
      "target": 0.7,
      "passed": true
    },
    "finished_at": "2026-11-06T17:13:05.937175",
    "is_estimate_note": "These numbers are estimates from held-back test rows, not a promise about future results."
  }
} as const;
