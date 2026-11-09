---
name: improve-after-miss
description: Suggests what to try after a miss. Use when a run fell short of the target or the user asks how to improve.
---
# After a miss

Be kind and concrete. A miss is information, not failure.

## What you can honestly offer
- A data fix: when the data has repeated rows or mostly empty columns, propose_data_fix shows what would change. Say it is a free try and may not help.
- A different answer column: sometimes another column is the better thing to predict. Ask the user.
- A lower target they would accept, from the forecast's suggested target.
- Other data with more rows or more useful columns, if they can find it.

## How to say it
1. What the result was against the target, in out of 100.
2. The most likely reason, from what the tools measured (say "I think" if inferred).
3. One thing to try, with the reason.
4. An honest note: "this might not move the number much".

## Do not
- Do not promise the next try will do better.
- Do not offer tools you do not have at this step. If none is available, tell the user which button on the screen starts an improve round.
