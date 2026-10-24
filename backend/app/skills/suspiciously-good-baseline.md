---
name: suspiciously-good-baseline
description: What to do when the free test result looks too good to be true
---
# A free test result that looks too good

Real-world prediction is rarely near perfect. If the free test is right about 98 or 99 times out of 100, be suspicious
before celebrating.

## Checks, in order
1. Is it close to a simple guess? Then the data is lopsided, not the model good (see `lopsided-classes`).
2. Is a column a copy of, or a result of, the answer? Re-read the findings and the column names (see `data-leakage`).
3. Are there many repeated rows? The tools remove exact duplicates before training, and the findings say how many.
   If a large share were repeats, the test was easier than real life.
4. Is the dataset very small? A tiny test set can be lucky (see `too-little-data`).
5. Is the data synthetic or cleaned up by its author? Some public datasets are artificially tidy.

## What to say
- Be glad but honest: "This result is higher than I usually see for this kind of question, so I checked why."
- Report what you found, in plain words, and what you could not check.
- Keep the trust level the tool gave. Do not raise it. If you suspect a leak you cannot confirm, say that the result may
  not hold up on new cases and let the user decide.

## Never
- Never say the model "will" reach this result on new data. It was measured on held-out rows, once, on this dataset.
- Never invent a cause. If you do not know why, say you do not know.
