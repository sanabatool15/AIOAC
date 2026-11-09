---
name: data-insights
description: Explains readiness findings in plain words. Use right after run_readiness or inspect_candidate.
---
# Explaining the data check

Use the findings and the summary fields (balance, missing_columns, ignored_* lists, duplicates). Quote numbers as the tools give them; never round or estimate.

## For each thing worth saying
- Name the columns: "Two columns, CustomerID and RowNumber, are just labels, so I will ignore them."
- Say what it means: "About 3 in 100 values are missing; I fill them in, so this should not hurt."
- Describe the grade as readiness, not quality: "B+ means the data is ready to try."
- Smaller answer group under 20 in 100 rows: "It is like a class where 95 of 100 students pass. Guessing pass for everyone is right 95 times, so I will compare against that."
- A column that copies the answer: "It gives the answer away, so I leave it out. Otherwise the test would look great and real life would not."
- Trust level (Low, Medium, High) comes from the tools. Add one sentence of advice.

## Shape
Pick the one or two findings that matter most, say what they mean, recommend the next step with the reason, and ask at most one question. Skip the rest unless asked.

If the user asks about one column, or a finding hints at a suspect column, call profile_data. Treat its suspects as clues to check with the user, not proof.
