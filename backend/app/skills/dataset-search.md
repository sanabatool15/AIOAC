---
name: dataset-search
description: How to find, compare and choose a dataset for the user's goal
---
# Finding a dataset

1. Turn the goal into 2 or 3 short search phrases (for example "customer churn", "telco churn"). Search each. Do not search the user's whole sentence.
2. Look at up to 3 promising results with `look_at_dataset` before fetching anything.
3. A dataset fits only if ALL are true:
   - it is a plain table (`tabular` is true) with a column that can be the answer (the thing to predict);
   - it has at least 1,000 rows (300 is the absolute minimum; say it is small);
   - it is not gated and is small enough to fetch;
   - one row means the same thing the user cares about (one customer, one transaction).
4. A missing license is a NOTE, not a blocker. Tell the user plainly: "the license is not stated".
5. Fetch at most 2 or 3 candidates. Run `inspect_candidate` on each with your best guess for the answer column.
6. Recommend one in one sentence, with the reason. Offer the others. The user decides; selecting needs their approval.

If search finds nothing good, say so and offer the bundled sample or an upload. Never invent a dataset name.
