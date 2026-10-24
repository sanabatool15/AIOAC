---
name: too-little-data
description: What to say and do when a dataset has few rows or few examples per answer
---
# Too little data

Models learn from examples. With few rows the free test is noisy: a lucky or unlucky split can move the result a lot.

## Rough guide (use the tool's numbers, not your own)
- Under 300 rows: very small. Say so clearly and suggest finding a bigger dataset first.
- 300 to 1,000 rows: usable but shaky. Warn that the result could easily be a few points different next time.
- Over 1,000 rows: usually fine for simple yes/no questions.
- Count the rare answer too: fewer than about 100 rows with the rarer answer is a problem even if the table is large.
- Many columns and few rows is also a problem; more columns than rows makes the result very unreliable.

## What to say
- "There are only 240 rows. With so few, the free test result can swing a lot, so treat it as a rough hint."
- Offer choices: look for a larger dataset, upload more of the user's own records, or continue knowing the result is shaky.
- If search returned a larger dataset on the same topic, offer it as the first alternative.

## Notes
- The fetch tool cuts very large tables to a row limit and tells you it did (`truncated`). Mention it if relevant.
- A small dataset also finishes quickly, so the quote will be mostly fixed fees. Explain that if the user asks why
  the price barely changes.
- Never promise that more data would fix it. Say it usually helps.
