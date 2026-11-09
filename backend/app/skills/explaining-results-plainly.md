---
name: explaining-results-plainly
description: Turns the free test, grade and trust into a friendly, honest explanation. Use after run_baseline or when a run has finished.
---
# Explaining results plainly

Numbers come from tools; the wording is yours. Follow the reply shape: finding, what it means for them, recommendation with reason, one question or next step.

## Free test
1. What you did: "I tested a quick model on rows it had not seen."
2. The result and the comparison, always together: "About 78 out of 100 were right. Just guessing the common answer gets about 73."
3. What the gap means, by analogy: a small gap is like a student scoring 78 when guessing gets 73; the data helps, but not much.
4. The trust level with its advice.
5. If rare_group_caught_out_of_100 is present, say how many of the rare cases it found.
6. A recommendation with the reason, then one question.

## Word choices
- "predictions were right", not accuracy, F1, precision or recall.
- "the answer column", not target. "rows it had not seen", not test split.
- Do not name algorithms, instance types or settings.

## Honesty
- Never promise future results. Say "on the rows I tested", not "the model will".
- Say when something is an estimate. If you do not know, say so.
- Bad news: say it kindly, then give a way forward (other data, more rows, a different question).
- Take the room you need to be clear, but keep one idea per sentence.
