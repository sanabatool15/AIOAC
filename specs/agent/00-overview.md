# Agent overview

Labels used in all files in this folder:
- **BUILT** = verified by reading the code (file cited).
- **PROPOSED** = an idea or design. Not in the code.
- **MISMATCH** = the code and an older spec disagree.

Read date: 2026-10-24. Code read: `backend/app/services/agent/*`, `services/gate.py`, `providers/llm/*`, `providers/datasets/*`, `skills/*`, `routes/projects.py`, `backend/evals/`, `backend/notebooks/`.

## 1. What the agent is (BUILT)

A custom tool-calling loop (`services/agent/loop.py`, `run_agent`). One call = one "turn". An LLM (OpenRouter, `providers/llm/openrouter.py`) either answers or asks for tools. The system checks each request, then runs the tool. The loop ends on a text reply, an approval card, a limit, or an error.

The agent never moves money. The gate (`services/gate.py`) and the HTTP routes do that.

## 2. One turn, end to end (BUILT)

```
POST /projects/{id}/chat {message, approve[]}          routes/projects.py
        |
        v
run_agent(ctx, llm, message)                           loop.py
  create AgentRun row; save the user message as a trace step
  history = last 20 user/assistant messages only       loop._history, context.window
        |
        v   repeat up to 12 times ("steps")
  +--------------------------------------------------------------+
  | check limits (turn tokens, project tokens, model cost)       |
  | system prompt = BASE + state block + skill index             |  context.build_system
  | tools offered = TOOLS_BY_STATUS[project.status]              |
  | llm.chat(system + convo, tools)  -> text or tool_calls       |
  +--------------------------------------------------------------+
        |                                   |
   text only                         tool_calls (1..n)
        |                                   |
  claim guard (regex)             for each call:
  save reply, return                repeat guard (>3 same call)
                                    unknown / not offered / bad args -> error to model
                                    gate.authorize(...)  (traced)
                                      NeedsApproval -> return card
                                      GateDenied    -> error to model
                                    run tool (free tools: 60 s timeout)
                                    save tool_result; feed trimmed result back
        |
        v
finally: AgentRun gets status, stop_reason, ended_at;
         gate steps get this run's id
```

Result is `AgentResult(status = reply | awaiting_approval | limit | error)`.

## 3. Components

| Part | File | State |
|---|---|---|
| Loop, limits | `services/agent/loop.py` | BUILT |
| Prompt, state block, tools by status, trimming, window | `services/agent/context.py` | BUILT |
| Claim guard, argument check | `services/agent/guards.py` | BUILT |
| 11 tools | `services/agent/tools.py` | BUILT |
| Permission gate | `services/gate.py` | BUILT |
| Skills loader + 10 skill files | `services/agent/skills.py`, `skills/*.md` | BUILT |
| OpenRouter client, scripted fake | `providers/llm/` | BUILT (OpenRouter never run for real) |
| Dataset source (Hugging Face) | `providers/datasets/` | BUILT |
| Trace tables `agent_runs`, `agent_steps` | `models/tables.py`, `repositories/traces.py` | BUILT |
| Eval harness, 7 cases | `backend/evals/` | BUILT, offline only |
| Notebook | `backend/notebooks/agent_playground.ipynb` | BUILT, fake model unless key set |

## 4. Worked example (illustrative numbers)

User goal: "I run a subscription business and I want to predict which customers will cancel next month."

**Turn 1, step 1.** Status `described`. System prompt state block:
```
Goal: I run a subscription business and I want to predict which customers will cancel next month.
Status: described
Next: Find or receive a dataset, inspect it, and ask the user to approve one.
```
Tools offered: `load_skill, search_datasets, look_at_dataset, fetch_dataset, inspect_candidate, select_dataset`.
Model asks: `load_skill(name="dataset-search")`. Gate: SEARCH allowed.

**Step 2.** Same state. Model asks: `search_datasets(query="customer churn")`. Result: bundled sample first, then Hugging Face hits (id, name, `about`, license, downloads, gated).

**Step 3.** `look_at_dataset(dataset_id="hf:scikit-learn/churn-prediction")` -> rows, tabular, license, columns.

**Step 4.** `fetch_dataset(dataset_id="hf:scikit-learn/churn-prediction")` -> `candidate_id`. State block now has an extra line:
```
Fetched candidate: id 3f2a..., scikit-learn/churn-prediction, 7,043 rows, license not stated
```

**Step 5.** `inspect_candidate(candidate_id="3f2a...", target="Churn")` -> grade, findings, 3 preview rows.

**Step 6.** `select_dataset(candidate_id="3f2a...", target="Churn")`. This is level 1. Gate raises `NeedsApproval`. The turn ends with status `awaiting_approval` and a card `{what: "The agent wants to select dataset", level: 1, tool, args}`. No assistant text is saved.

**Turn 2** (client sends `{approve: ["select_dataset"]}`, no message). The model sees only the saved user/assistant messages plus the state block, so it re-proposes `select_dataset` with the same args (it must remember the target from earlier text). Gate allows. Status becomes `data_chosen`. Next step the state block reads:
```
Goal: ...
Status: data_chosen
Dataset: Hugging Face, 7,043 rows, answer column 'Churn', license not stated
Next: Run the readiness check.
```
Tools offered now: `load_skill, run_readiness`. Model: `run_readiness` -> status `readiness_done`; then `run_baseline` -> `baseline_done`; then `create_quote` -> `quoted`. State block at `quoted`:
```
Readiness grade: B
Free test: 0.78 right vs 0.73 for a simple guess; trust Low
Quote (estimate): 53c, range 52-53c, cap 53c, not approved yet
Next: Wait for the user to approve the quote on screen.
```
The model writes a plain reply and the turn ends (`reply`).

**After that.** The user approves the quote through `POST /projects/{id}/quote/approve` (not through the agent). Status `awaiting_payment`. The agent may call `request_payment`. PayPal capture and `POST /train` happen over HTTP routes. See `04-permissions-and-safety.md`.

## 5. Where this can break (short list, details in file 01)

1. Tool results are not saved between turns. Only text is. Step 6 -> turn 2 depends on the model remembering the target column.
2. The approval card says only "select dataset". It does not name the dataset. (MISMATCH with `specs/agent.md` 4.1.)
3. Once the dataset is chosen, no tool can change it. A user who changes their mind has no path except a new project.
4. The false-claim guard blocks honest sentences (tested: "Training starts only after your payment is confirmed.") and misses real lies ("Your card has been charged.").
5. Text from Hugging Face goes unfiltered into tool results and (the license field) into the system prompt.
6. Nothing in the repo has run against a real model. Every pass rate is unknown.

## 6. Index

| File | Content |
|---|---|
| `00-overview.md` | this file |
| `01-loop-and-limits.md` | loop, limits, guards, weak spots |
| `02-prompt-and-context.md` | exact prompt, state block, brittleness plan |
| `03-tools-reference.md` | every tool, plus proposed tools |
| `04-permissions-and-safety.md` | gate, approvals, threats |
| `05-skills.md` | skills mechanism and rules |
| `06-observability-and-logging.md` | proposed logging design |
| `07-testing-and-evaluation.md` | proposed robustness test plan |
| `08-data-sources-kaggle.md` | data sources, Kaggle design |
| `09-open-questions-and-plan.md` | decisions needed, build plan |
| `10-memory-and-context-store.md` | memory and context store |
| `11-dataset-discovery.md` | PROPOSED: finding datasets for the user's goal (sources, web search, pipeline, safety, evals, fallback list) |

## 7. Spec disagreements found (MISMATCH)

- `specs/status.md` section 6a says token, cost and timeout limits are not implemented. `loop.py` implements them and `agent.md` says so. Status 6a is stale.
- `specs/status.md` summary table has duplicate rows with conflicting states (PayPal provider, SageMaker, training backends). Layout section says "90 tests", summary says 195.
- `specs/agent.md` 4.1 says the approval card shows estimated cost, cap and refund. The only card the code builds is the level 1 card (`gate.py`): `{what, level}` plus tool and args. Level 2 actions never create a card; they are checked against stored state.
- `specs/agent.md` 7 says traces power a live log. No live log exists.
