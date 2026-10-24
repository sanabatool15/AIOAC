---
name: lopsided-classes
description: What to say when far more rows have one answer than the other
---
# Lopsided answers (class imbalance)

Example: 95 of 100 customers stayed and 5 left. A model that always says "stays" is right 95 times out of 100 and
is useless. That is why the free test is always shown next to what a simple guess scores.

## How to read it
- Look at `accuracy` and `simple_guess_accuracy` from `run_baseline`. Only the gap between them means something.
- If the smaller group is under 20% of rows, say the result may lean toward the bigger group.
- If the smaller group is under 5% of rows, or has fewer than about 100 rows, say plainly that the model will have
  little to learn from and the result will be shaky.

## How to explain it
- Say: "Far more customers stayed than left, so a simple guess is already right about 73 times out of 100.
  The model got 78. That is a small step up."
- Never say "the model is 78% accurate" without the simple-guess number next to it.
- Use the tool's trust level (Low, Medium, High) and add one sentence of advice. Low is an honest answer, not a failure.

## Options to offer
- Use a different dataset where the two answers are closer to even.
- Collect more examples of the rare answer.
- Go ahead anyway, knowing the result is a modest improvement. The user decides.

You cannot rebalance the data yourself with the tools available. Do not claim you did.
