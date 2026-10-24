---
name: choosing-the-target-column
description: How to pick the answer column, or ask the user, before selecting a dataset
---
# Choosing the answer column (the target)

The answer column holds what the user wants to predict. `inspect_candidate` and `select_dataset` both need its exact name.

## Steps
1. Restate the goal as a question with a short answer: "Will this customer leave?" The answer column is the one that
   holds that answer for past rows.
2. Look at the column names from `look_at_dataset` or the preview from `inspect_candidate`. Good targets:
   - have a small number of distinct values (two for yes/no, a few for categories);
   - sit at the row level: one value per customer, loan or patient;
   - are known for the past rows.
3. Names to try: the goal's own words (`churn`, `default`, `left`, `fraud`, `outcome`, `label`, `class`, `target`, `status`).
4. If exactly one column fits, say which one and why in one sentence, then continue.
5. If two or more fit, or none do, ask ONE short question: "Which of these is the thing you want to predict: A or B?"
6. If the only candidate has hundreds of different numbers (a price, an amount), say this tool predicts categories
   such as yes/no, not exact numbers, and offer another dataset. This product starts with yes/no and category questions.

## Do not
- Do not choose an ID, name, date or free-text column.
- Do not choose a column that is only known after the fact (see `data-leakage`).
- Use the exact name as written, including capitals. A wrong name returns an error with the real column names; use them.
