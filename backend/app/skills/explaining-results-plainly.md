---
name: explaining-results-plainly
description: How to turn the free test, grade and trust level into honest plain sentences
---
# Explaining results plainly

Use after `run_readiness`, `run_baseline` or when training is finished. Numbers come from tools; the wording is yours.

## Pattern for the free test
1. What was tested: "I tested a quick model on rows it had not seen."
2. The result: "About 8 out of 10 predictions were right." Use the tool's number, written as "N out of 10" or "N out of 100".
3. The comparison: "A simple guess would be right about 7 out of 10." Always include this.
4. The meaning: "So the model adds something, but not a lot." Say how big the gap is: tiny, modest or clear.
5. The trust level and its advice sentence.

## Word choices
- "predictions were right", not accuracy, F1, precision or recall.
- "the answer column", not target. "tested on data it had not seen", not test split.
- Do not name algorithms, instance types or settings.

## Honesty rules
- Never promise future accuracy. Say "on the rows I tested" not "the model will".
- Say when something is an estimate, especially prices and times.
- If a result is bad, say so kindly and give a next step: other data, more rows, a different question.
- If you do not know, say you do not know. Do not fill gaps with confident guesses.
- Keep it short: three or four sentences, then one question or one next step. Offer details only if asked.
