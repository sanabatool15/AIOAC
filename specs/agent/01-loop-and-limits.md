# Loop, limits and guards

Source: `backend/app/services/agent/loop.py`, `guards.py`, `memory.py`, `runlog.py`, `config.py`. Everything in sections 1 to 4 is **BUILT**. Since 2026-10-24 the loop also stores every message (`memory.py`), logs events (`runlog.py`) and refuses a second simultaneous turn; step 6 below describes the older in-memory conversation, now read from the `messages` table each step. Section 5 lists weak spots found by reading the code. Section 6 is **PROPOSED**.

## 1. Step order inside one model step (BUILT, `loop._turn`)

1. Before each model call, check limits: turn tokens, project tokens, model cost.
2. Rebuild the system prompt and the offered tool list from the database.
3. Call `llm.chat`. On `LLMError`: trace `llm_error`, return `status=error`.
4. Add usage to the `AgentRun` row. Trace an `llm` step (tokens, cost, finish reason).
5. No tool calls: run the claim guard, save the reply, return `reply`.
6. Tool calls: append them to the in-memory conversation, then for each call:
   1. Count the signature `name:sorted-args`. More than 3 identical in one turn: stop `repeat`.
   2. Trace `tool_call`.
   3. If the arguments were unreadable: error result to the model.
   4. If the tool is unknown: error result with the offered list.
   5. If the tool is not offered for this status: error result.
   6. `guards.check_args` (required keys present, string args non-empty): error result.
   7. `gate.authorize` (always traces a `gate` step). Then run the tool. Level 0 tools run in a worker thread with a 60 s timeout.
   8. Trace `tool_result` (full result). Add the trimmed result (2,500 characters) to the conversation.
7. After the last step number is used: stop `steps`.

## 2. Termination reasons (BUILT)

| `AgentResult.status` | `reason` | When | User text |
|---|---|---|---|
| `reply` | none | Model gave text with no tool call | The model's text (or corrected text) |
| `awaiting_approval` | none | Gate raised `NeedsApproval` | None. A card is returned |
| `limit` | `steps` | 12 model calls used | `LIMIT_TEXT["steps"]` |
| `limit` | `tokens` | turn tokens >= 80,000 | fixed text |
| `limit` | `project_tokens` | project tokens >= 600,000 | fixed text |
| `limit` | `cost` | project model cost >= USD 1.00 (only if the service reports `usage.cost`) | fixed text |
| `limit` | `repeat` | 4th identical call in a turn | fixed text |
| `limit` | `timeout` | a free tool ran longer than 60 s | fixed text |
| `error` | `llm` | `LLMError` after one retry | "I could not get an answer from my AI service just now. ..." |
| (crash) | `crashed` | exception in the loop | `AgentRun.status="failed"`, exception propagates to the route (HTTP 500) |

Limits are checked before a model call, so one step can overshoot (tokens are known only after the call).

## 3. Error paths inside a tool call (BUILT)

- `NeedsApproval` -> return card immediately. Calls after it in the same reply are not run.
- `GateDenied` -> `{"error": "not allowed: <reason>"}` to the model.
- Timeout -> trace `tool_result {"error": "timed out"}` and stop. The worker thread is not killed.
- Any other exception -> `session.rollback()`, `{"error": "<ExceptionType>: <message>"}` to the model.

## 4. Guards (BUILT, `guards.py`)

**Argument check.** Required keys present. String-typed keys must be non-empty strings. It does not check unknown extra keys, lengths, patterns or enums.

**Claim guard.** Three regexes on the final reply, tested against the project status:
- payment confirmed / "you have paid" / "I have charged": allowed only in `paid, training, done, refunded, failed, stopped`.
- training started/finished/ready: allowed only in `training, done, refunded, failed, stopped`.
- refund sent/issued/processed: allowed only in `done, refunded, failed, stopped`.
A hit replaces the reply with: "I need to correct myself: ... Nothing was charged or started by me. We are at the '<status>' step." and traces `claim_blocked` with the original text.

I ran the guard on sample sentences at status `quoted`:

| Sentence | Result |
|---|---|
| "Training starts only after your payment is confirmed." | BLOCKED (false positive) |
| "Once training is complete, any unused money is refunded to you." | BLOCKED (false positive) |
| "The model is ready to be tested with a free check." | BLOCKED (false positive) |
| "Your card has been charged $7." | passes (miss) |
| "I started the job for you." | passes (miss) |
| "Payment received, thanks!" | passes (miss) |

So it is a rough alarm, not a safety control. The gate is the real control.

**Repeat guard.** `REPEAT_LIMIT = 3`. Same name and same sorted args, per turn only.

## 5. Weak spots (adversarial review)

Each item: what happens, evidence, impact. Numbering is used by other files.

**W1. Tool results vanish between turns.** **FIXED 2026-10-24** (see file 10). History now comes from the `messages` table, tool results included; the approval card is stored; the state block shows the pending approval. Original description: `_history` keeps only `user` and `assistant` trace steps (`loop._history`). Search results, previews, findings and the chosen target are not in the next turn's context. The state block only lists fetched candidate ids. After an approval card (turn 2), the model must recall the target column from its own earlier text, and that text may not exist: the card turn saves no assistant message. Impact: wrong or missing `target` on re-proposal; "use the second one" has no ids to refer to.

**W2. Approval is not bound to the thing shown.** `ChatIn.approve` is a list of action names from the client. `ctx.approved` unlocks every `select_dataset` call in that turn, with any `candidate_id` and `target` the model chooses. The card carries args, but the approval does not check that the executed args equal the card args. Also a client can send `approve` with no card pending (pre-approval). Impact: the model could select a different candidate than the one the user saw. Money is not at risk; data choice is.

**W3. The card text is empty of detail.** `what` is "The agent wants to select dataset". The dataset name, rows and target are only in `args` (raw ids). A UI must look them up.

**W4. User changes their mind mid-flow.** `select_dataset` is offered only in `described`. After `data_chosen` there is no tool to change dataset, target, or goal. `Project.goal` is set once and never updated, so the state block keeps showing the old goal. In `quoted`, `create_quote` can be re-run, but nothing can change the data under it. Impact: the only exit is a new project, and the agent has no tool or text telling the user that.

**W5. User switches dataset after a quote.** Same as W4. Also an upload via `POST /projects/{id}/data` after selection creates a candidate that no tool can select (the state block only lists candidates when no dataset is chosen), so it sits until its expiry time.

**W6. Off-topic, ambiguous, abusive input.** The prompt has no scope rule, no refusal rule and no "ask when unclear" rule beyond "One short question at a time". Behaviour is whatever the model does. No intent check exists. In statuses `training`, `done`, `failed`, `stopped`, `refunded`, only `load_skill` is offered and `NEXT_STEP` has no entry for failed/stopped/refunded ("Reply helpfully.").

**W7. Non-English input.** Prompt, skills, claim guard and eval jargon checks are English only. The claim guard cannot see an Urdu or Hindi false claim. The language of the reply is not specified.

**W8. Two turns racing.** **FIXED 2026-10-24.** Per-project turn lock (HTTP 409) and a unique message `seq`. `agent_steps.seq` is also safe inside the lock. Original description: No per-project lock. Two `/chat` calls at once run two loops on one project with separate sessions. `TraceRepository.add` computes `seq` as max+1 then commits: duplicates are possible. The end-of-turn stamp `UPDATE agent_steps SET run_id=... WHERE run_id IS NULL` (project wide) can stamp the other turn's gate steps. Two `create_quote` calls make two quotes. Not tested.

**W9. Claim guard is keyword based.** See the table above. It also checks only the final reply. Text the model writes next to tool calls is neither shown nor checked (it is dropped: not traced, not returned).

**W10. Untrusted text goes into the prompt.** Dataset `description` (200 chars), column names and 3 preview rows come back as tool results, unlabelled and undelimited. The dataset `license` string is stored from Hugging Face `cardData.license` and printed in the state block, which is part of the system message (`context.state_block`). See file 04.

**W11. Step budget vs the skill.** `dataset-search` tells the model to search 2 to 3 phrases, look at up to 3, fetch 2 to 3 and inspect each: about 12 to 14 calls, plus `load_skill`. The limit is 12 model steps (several calls in one reply count as one step). A model that follows the skill one call at a time hits `limit: steps`. Not measured.

**W12. Tool timeout shares the session.** Free tools run in a worker thread with the same SQLAlchemy `Session` (`loop._call_with_timeout`). After a timeout the thread keeps running and may still write (for example a slow `fetch_dataset` still creating a candidate). `fetch_dataset` can take over 60 s for a 50 MB table. Sessions are not thread safe.

**W13. Wrong bundled matches.** **FIXED 2026-10-24.** Whole-word matching; results are labelled `sample_data`. Original description: `search_datasets` returns the bundled churn sample first when the query contains any keyword (`churn, customer, leave, stop buying, retention`) as a substring. "customer complaints text" matches "customer". The synthetic sample can be recommended for an unrelated goal.

**W14. Id format traps.** **FIXED 2026-10-24.** The error now says dataset ids start with `hf:`. Original description: Dataset ids need the `hf:` prefix for `look_at_dataset` and `fetch_dataset`. Without it the tool returns "unknown dataset id" with no hint. Models often drop prefixes.

**W15. Target type is not checked.** `inspect_candidate` and `select_dataset` accept any existing column. I found no check that the target is a small set of categories. Only the skill `choosing-the-target-column` says to avoid price-like columns. A numeric target with hundreds of values reaches the baseline, where the model is a classifier.

**W16. Errors leak internals to the model.** **FIXED 2026-10-24.** The model gets a generic message; the detail goes to the run log only. Original description: `f"{type(exc).__name__}: {exc}"` is passed back. It may contain file paths or SQL. The model may repeat it to the user.

**W17. Lost messages after limit/error.** **FIXED 2026-10-24.** `limit` and `error` endings are saved as assistant messages. Original description: On `limit` and `error`, nothing is saved as an assistant message. The next turn may show two user messages in a row.

**W18. Empty first turn.** `run_agent` with `message=None` on a new project sends an empty history (only the system message). Some model providers may reject a request with no user message (not verified).

**W19. Real-model behaviour is unknown.** `OpenRouterClient` has never run for real (`specs/status.md`). No temperature, seed or `max_tokens` is sent. Model id comes from `OPENROUTER_MODEL` (default `anthropic/claude-sonnet-4.5`).

**W20. Spec drift.** See "Spec disagreements" in `00-overview.md`.

## 6. PROPOSED fixes (ordered by value)

1. Per-project turn lock (reject a second `/chat` while one runs: HTTP 409). Fixes W8. **Done 2026-10-24.**
2. Save a compact "tool memory" line per tool result in history, for example `search_datasets -> [hf:a/b (7,043 rows), ...]`. Fixes W1 and the "second one" case. **Done 2026-10-24.**
3. Add the chosen target and any pending approval to the state block. Fixes the W1 re-proposal gap. **Done 2026-10-24.**
4. Bind approvals: the client sends `{action, candidate_id, target}` and the gate compares with the call. Fixes W2.
5. Make the card carry a human sentence built by code from the DB (dataset name, rows, target). Fixes W3.
6. A `change_dataset` / restart path with its own gate rule (only before quote approval). Fixes W4, W5.
7. Replace the claim regexes with a check against state: only block when the reply asserts something and the DB says the opposite, and test both directions with a phrase list (see file 07). Keep it labelled as a rough alarm.
8. Run free tools without the shared session, or give them a fresh session. Fixes W12.
9. Add `reason` plain text to `AgentRun` and save an assistant message for `limit` and `error`. Fixes W17. **Done 2026-10-24.**
10. Tighten search matching (word match, not substring) and mark bundled results as "sample data". Fixes W13. **Done 2026-10-24.**
