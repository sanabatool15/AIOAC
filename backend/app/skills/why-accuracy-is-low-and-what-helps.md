---
name: why-accuracy-is-low-and-what-helps
description: Explains a weak result and what could help. Use when the test is near the simple guess, the forecast is low, or they ask why it is only about 70.
---
# Why the result is low, and what might help

Read the fields the tools gave you: right_out_of_100, simple_guess_out_of_100, rare_group_caught_out_of_100, learning_curve_out_of_100, models_dropped, summary.

## Pick the branch that fits
- Curve is flat (more rows barely help): "The columns say little about the answer. Think of guessing a person's job from their shoe size." Recommend other columns or a different question.
- Curve is rising: "The more rows it sees, the better it gets, so more rows should help." Recommend a bigger file if one exists.
- Everything sits near the simple guess: "Right now the data does about as well as a coin flip with a lean." The question may not be answerable from this data; say so kindly.
- Rare group: if rare_group_caught_out_of_100 is low, say "it finds only about N of every 100 who really left, even though the overall score looks fine".
- Repeats, gaps, ignored columns in summary: say which columns, and that fixing them might help a little.

- To check the model type, more rows and which columns matter in one go, call compare_models (free). Say "clues, not causes" and that the numbers are estimates.

## End every branch with
1. One recommendation and the reason.
2. An honest "this might not help". Never promise a better number.
3. One question or next step for the user.

Use everyday comparisons. Numbers come only from the tools.
