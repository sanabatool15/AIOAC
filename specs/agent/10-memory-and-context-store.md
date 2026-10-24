# Memory: keeping the whole conversation (BUILT 2026-10-24)

Sections 2 to 7 are built (`services/agent/memory.py`, tests in `tests/test_memory.py`); section 9 lists what differs from the design. The summary of the oldest part (section 4) is **not built**: the column exists and is sent if set, but nothing writes it. Section 1 describes the code before this change.

Goal: the agent never loses what happened. Every user message, every model reply, every tool call and its result, every skill it loaded, and every gate decision is stored, and is given back to the model on the next turn, until the work is done.

## 1. What exists today (BUILT, see `models/tables.py`, `services/agent/context.py`)

- `agent_steps` stores each event (`user`, `assistant`, `tool_call`, `tool_result`, `gate`) with `project_id`, `run_id`, `seq`, and a JSON `content`.
- `agent_runs` stores one row per turn (tokens, cost, stop reason).
- When a new turn starts, only the last 20 user and assistant messages are sent back. Tool calls, tool results and skill text are NOT sent back. This is weakness W1: after the approval card the model must recall the target column from text that may not exist.

So the data is mostly stored already. What is missing is giving it back, and a clean separation between "what the model sees" and "what we log".

## 2. Decision: one row per message, not one row per session

Do not append everything into one row per session. Reasons: the row grows without limit, every turn rewrites it, two writers can overwrite each other, and you cannot query or trim it. Use rows.

Proposed tables (names can change; shape matters):

- `conversations`: `id`, `project_id` (nullable, so a conversation can exist before a project), `created_at`, `status` (active, finished), `summary` (text, see section 4), `summary_upto_seq`.
- `messages`: `id`, `conversation_id` (foreign key), `seq` (strictly increasing per conversation, unique with `conversation_id`), `run_id` (the turn that produced it), `role` (`user`, `assistant`, `tool`, `system_note`), `content` (text), `tool_calls` (JSON, for assistant messages), `tool_call_id` and `tool_name` (for tool messages), `kind` (`chat`, `skill`, `card`, `gate`), `tokens` (estimate), `created_at`.
- `agent_runs` (existing): add `conversation_id`. Keep for limits and costs.

`messages` is exactly the list the model API wants (OpenAI style: user, assistant with tool calls, tool results). Replaying is `SELECT ... ORDER BY seq`. `agent_steps` can stay as the audit log (gate decisions, guards, limits), or be folded into `messages` with `kind`. Recommendation: keep `agent_steps` for audit and add `messages` for replay; do not make one table do both jobs.

Project versus session: a conversation links to a project by `project_id`. One project can have one or many conversations. Decide later; the schema allows both.

## 3. What the model sees each step

Rebuilt every step, in this order:

1. Base prompt (rules).
2. Live state block, rebuilt from the database (status, chosen dataset, target, grade, baseline, quote). This is the source of truth for facts; it is never taken from the chat.
3. Conversation summary (if one exists).
4. The recent messages, in full, including tool calls and tool results, from `messages`.
5. Skills the conversation already loaded: keep their text for the rest of the conversation (stored as `kind=skill` messages), do not make the model re-load them.

Rule: state facts come from the state block, chat history gives continuity. If they disagree, the state block wins.

## 4. Keeping it inside the model's limits

Everything is stored forever; only what is sent is limited.

- Budget: send up to N tokens of history (config, start at 30,000). Keep the newest messages first.
- Never cut inside a pair: an assistant message with tool calls and all its tool results go or stay together, or the API rejects the request.
- Old tool results are the first to shrink: replace a large result with a one-line stub ("fetch_dataset result: 7,043 rows, target Churn, stored as candidate c_12") but keep the call and the stub. Stubs are written when the result is first stored, in addition to the full result.
- When history is still too big, write a summary of the oldest part (a model call, or a code-built summary of state changes), store it in `conversations.summary`, set `summary_upto_seq`, and stop sending those messages. The full messages stay in the database.
- Summaries never replace the state block and never carry money facts (those come from state).

## 5. Test runs and notebook runs

- A test case or notebook session creates a conversation with `source = "eval"` or `"notebook"` and the eval case id in its metadata, so the same store and replay code is used as in production. A test can be re-opened and continued, or replayed from a stored conversation without the model (replay test).
- Every `messages` row carries the `run_id`, so one turn can be shown on its own, and `06-observability-and-logging.md` console and file logs are views of the same rows.

## 6. Safety rules for stored context

- Text that came from outside (dataset descriptions, column names, preview rows, licenses) is stored and replayed wrapped and labelled as data, never as instructions (threat T4 in file 04).
- No secrets are stored. User text and previews are stored; `LOG_USER_TEXT=false` applies to log files, not to the conversation the user is having.
- Writes are append-only per message; a turn lock per conversation stops two simultaneous turns from interleaving (weakness W8).
- Deleting a project deletes its conversations after the retention period (open question).

## 7. How we will know it works

- A scripted test: turn 1 fetches data and picks a target; turn 2 (after approval) uses the target without calling the tool again. This passes only if tool results come back.
- A replay test: store a conversation, rebuild the model input from the database, and check it equals the original input byte for byte.
- A long-conversation test: 200 messages with a small token budget still produces valid tool-call pairs and keeps the state block.
- A restart test: stop the process, start it again, send a message; the agent continues with the full context.

## 8. Open questions

1. One conversation per project, or many? Recommendation: many allowed, one active.
2. Keep full tool results in `messages` forever, or only stubs after the project ends? Recommendation: forever for evals, 30 days for users.
3. Summaries by model call or by code? Recommendation: code first (state changes list), model summary later.

## 9. Built: what differs from the design (2026-10-24)

- **Tables:** `conversations` (`project_id`, `source` app|eval|notebook, `meta` JSON, `status`, `summary`, `summary_upto_seq`), `messages` (`conversation_id`, `seq` unique per conversation, `run_id`, `role`, `content`, `tool_calls`, `tool_call_id`, `tool_name`, `kind` chat|skill|card|note, `stub`, `tokens`), and `agent_runs.conversation_id`. `agent_steps` stays the audit log. Delete any old local `aioac.db`.
- **What is stored:** every user message; each assistant message with its tool calls and any text; each tool result in full, plus a one-line `stub`; loaded skills as `kind=skill`; the approval card as the result of the waiting call (`kind=card`); calls that were not run (because an earlier call in the same step needed approval, or the turn was stopped) get a `kind=note` result so the history never has an unanswered call. `limit` and `error` endings are saved as assistant messages with `kind=note` (W17).
- **Each step's input:** base prompt, state block (now with the pending approval and the approvals given this turn; the chosen answer column was already there), optional summary, then history within `agent_history_token_budget` (default 30,000 estimated tokens, 4 characters per token). Over budget: old large tool results become stubs (oldest first), then the oldest whole groups are dropped, and the history always opens on a user message. The newest user turn is always sent. A loaded playbook is never stubbed; if its group has to be dropped, its text moves into the system message. Tool results are still trimmed to 2,500 characters when sent (8,000 for playbooks).
- **Repair:** a call with no stored result is given an error result when the input is built; a result with no call is not sent.
- **Seq safety:** `seq` is max+1 inside the per-project turn lock; the unique key plus a retry is the backstop for several processes.
- **Evals and notebook** use the same store (`source` eval or notebook, `meta.case_id`). The eval runner exports `conversation.json` per run; `python -m evals.replay <folder>` rebuilds the model input before each reply without a model, and `memory.ReplayLLM` plays the stored assistant messages back through `run_agent`.
- **Removed:** `context.window()` (the 20-message window). Fallback is not needed because history always comes from `messages`.
- **Turn lock (W8):** a process-local lock per project (`loop.TurnInProgress`; `/chat` answers HTTP 409). It does not help across several API processes.
- **Untrusted text:** dataset descriptions, column names and sample rows reach the model inside `<untrusted_dataset_text>` blocks, and the base prompt says they are data. Licenses are reduced to a single short tag or "unrecognised license text" before storing (T4). Residual risk: readiness findings and error messages can contain column names, which are not wrapped.
