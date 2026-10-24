# Skills

Source: `services/agent/skills.py`, `skills/*.md`. **BUILT** unless marked.

## 1. Mechanism (BUILT)

- Each skill is a Markdown file in `backend/app/skills/` with front matter `name:` and `description:` between `---` lines, then the body.
- `skills._load()` (cached with `lru_cache`) reads all `*.md` files at first use. It splits on `---` and reads front matter lines with `line.split(":", 1)`. A skill file with broken front matter would raise on first use and break every turn.
- `skills.index()` returns `- name: description` for all 10 skills. It is part of the system message in every step, in every status (`context.build_system`).
- The model calls `load_skill(name)`. The result is `{playbook: body}` or an error with the available names. The body then lives only in that turn's conversation. It is not kept in the next turn (history drops tool results).
- `load_skill` is offered in every status (`context.TOOLS_BY_STATUS`).
- Nothing checks that the model loaded a skill before acting. The prompt only says "Load a skill with load_skill before doing something it covers."
- No skill is loaded automatically. There is no matching of skills to status.

Tests: `tests/test_context.py` checks that skills load, are listed, and that the data-science skills contain no money rules (`test_skills_hold_no_money_rules`).

## 2. Existing skills (BUILT; line counts 10 to 27)

1. **dataset-search.** Turn the goal into 2 to 3 short phrases; look at up to 3 results; a dataset fits only if tabular, has a usable answer column, at least 1,000 rows (300 minimum), not gated, small enough, one row means what the user cares about. Missing license is a note. Fetch 2 to 3, inspect each, recommend one, user decides. If nothing fits, offer the bundled sample or an upload. Weak point: its step count can exceed the 12-step limit (W11).
2. **data-insights.** Quote tool numbers exactly, explain each finding, call the grade "readiness", warn when the smaller group is under 20%, say ignored copy-of-answer columns, always add one sentence of advice to the trust level.
3. **cost-quote.** Every price is an estimate; give estimate, range and cap; explain the refund; training stops at the cap; the agent cannot take payment. It repeats payment facts in words. That is allowed (wording), but the rules are enforced in code.
4. **plain-language.** A table of jargon replaced by plain phrases; one question at a time; no tool or model names.
5. **data-leakage.** Warning signs (copy of answer, after-the-fact names, IDs, near-perfect baseline) and what to say. Admits there is no tool to remove a column.
6. **lopsided-classes.** Always show the simple-guess number next to the result; thresholds 20% and 5% / 100 rows; options to offer; cannot rebalance.
7. **choosing-the-target-column.** Restate the goal as a question; pick a column with few distinct values at row level; if two or none fit, ask one question; a price-like column means this product predicts categories; use exact names.
8. **suspiciously-good-baseline.** If 98-99% right: check lopsidedness, leakage, duplicates, tiny data, synthetic data; keep the tool's trust level; never invent a cause.
9. **too-little-data.** Row thresholds (300, 1,000), rare-class count, many columns few rows; what to say; offer choices.
10. **explaining-results-plainly.** Pattern for the free test: what was tested, the result in "N out of 10", the simple-guess comparison, what the gap means, trust level; word choices; honesty rules; keep it to 3 or 4 sentences.

Observations:
- Skills 5 to 10 contain numeric thresholds (20%, 5%, 300, 1,000). These duplicate the readiness code (`insights.py`) and can drift. Not checked here for equality.
- `choosing-the-target-column` tells the model to refuse numeric targets. The tools do not (W15).
- No skill exists for: handling unsupported tasks (images, text, numbers), changing mind, refusing, off-topic, non-English, uploads, the approval card, or the post-training state.

## 3. PROPOSED rules for writing skills

1. One purpose per file, under 60 lines (existing rule). Front matter has `name`, `description` (one line, says WHEN to load it).
2. A skill holds **judgment and wording**. It may name tools and fields. It must not contain money rules, limits or permissions.
3. Every number in a skill must say where the real number comes from (a tool field) or be marked "rough guide". Prefer "use the tool's number".
4. Every tool name in a skill must exist. A test should parse backticked names and check them against `TOOLS` (PROPOSED test).
5. Each skill ends with "Do not" lines for the top failure.
6. Add 1 or 2 short example exchanges in skills that handle odd input. Mark them as examples, vary the wording.
7. Language: write skills in English. Tell the model (in the base prompt) to reply in the user's language.

## 4. PROPOSED: base prompt vs skill vs code

| Put it in... | When | Examples |
|---|---|---|
| **Code** (gate, tools, services) | Anything involving money, permissions, limits, data validity, or that must be true every time | approval, caps, verified payment, target must be a category, ids validated, claim checks against state |
| **Base prompt** | Short rules needed in every step; under about 15 lines | scope, language, plain words, untrusted-text rule, "numbers come from tools" |
| **State block** (per-status text) | What to do in this exact step | `NEXT_STEP`, allowed actions, pending question |
| **Skill** | Judgment for a situation that comes up sometimes; examples; wording | leakage, lopsided data, unsupported task handling |

Rule of thumb: if breaking it could cost money or lose the user's data, it is code. If it is about how to explain or when to ask, it is a skill. If it applies to every sentence, it is the base prompt.

## 5. PROPOSED: loading skills more reliably

- Add a status-to-skill hint in the state block ("Before this step, load: data-insights"). Cheap, keeps skills out of the prompt otherwise.
- Count in the trace whether a skill was loaded before the first relevant tool, and report it in evals (not as a hard failure at first).
