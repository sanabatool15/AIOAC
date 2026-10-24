---
name: data-leakage
description: Spot columns that give away the answer, and explain why they are ignored
---
# Columns that give away the answer (leakage)

A column leaks when it contains the answer, or is only known after the answer happens. A model that sees it looks brilliant
in the test and then fails on real, new cases.

## Warning signs
- A column that is a copy of the answer column (same values, or "Yes/No" versus 1/0). The readiness check reports these.
- Names such as `cancel_date`, `churn_reason`, `outcome`, `result`, `status_after`, `days_until_exit`, `final_*`, `closed_*`.
- A date or amount that only exists once the thing you want to predict has already happened.
- A row ID or a customer ID. It carries no meaning and can accidentally identify the answer.
- A baseline that is almost perfect (see `suspiciously-good-baseline`).

## What to do
1. Look at the column names and the preview from `inspect_candidate` before choosing the answer column.
2. Ask: "Would we know this value at the moment we want to make the prediction?" If no, it should not be used.
3. Tell the user in plain words: "The column `churn_reason` is only filled in after a customer has left, so it would
   give the answer away."
4. The tools already ignore ID-like columns and exact copies of the answer. Other leaks you must point out yourself
   and ask the user whether to keep that dataset. You have no tool that removes a column, so say so honestly.

## Do not
- Do not claim a column is safe because the name looks harmless. Say what you checked.
- Do not hide the issue to keep the flow moving. A NOTE the user understands is better than a good-looking number.
