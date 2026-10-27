# Observability and logging

Sections 1 and 2 describe the code before 2026-10-24. Sections 3 to 9 are now **BUILT** (2026-10-24, `services/agent/runlog.py`) with the deviations listed in section 11. Section 10 and browser events are still proposed.

## 0. How to see a log (BUILT)

- **Live, in a terminal:** `cd backend && python -m evals.run --fake --repeats 1 --cases churn-subscription -v` prints one line per event to stderr (`-vv` adds debug lines such as the state block summary). With a real model: `python -m evals.run --model <id> -v`.
- **A past eval run:** every run writes a folder `backend/logs/eval-<time>/<case>/r<n>/` with `events.jsonl`, `transcript.md` and `conversation.json`, plus `index.json` in the batch folder. Failed runs print their folder at the end of `evals.run`.
  - `python -m evals.show eval-20261101-101500` lists the runs of a batch (PASS or FAIL, folder).
  - `python -m evals.show eval-20261101-101500/churn-subscription/r1 [--tools] [--md] [--raw] [--level WARN|DEBUG]`.
  - `python -m evals.replay <run folder> [--full]` rebuilds, from `conversation.json`, what the model was shown before each reply (no model, no network).
- **A turn from the app database:** `GET /projects/{id}/trace` returns the audit steps (`agent_steps`).
- Logs are git-ignored (`backend/logs/`).


## 1. What exists today (BUILT)

**`agent_steps` table** (`models/tables.py`, written by `repositories/traces.py`): `project_id, run_id (nullable), seq, kind, content (JSON)`. One commit per step. `seq` is per project. Kinds actually written:

| kind | written by | content |
|---|---|---|
| `user` | loop | `{text}` |
| `assistant` | loop | `{text}` (after the claim guard) |
| `llm` | loop | `{tokens, cost_usd, finish_reason}` only if the service reported usage |
| `llm_error` | loop | `{message}` |
| `tool_call` | loop | `{name, args}` (written before validation, so refused calls appear) |
| `gate` | gate.py | `{action, allowed, reason?}`; `run_id` is stamped at the end of the turn |
| `tool_result` | loop | `{name, result}` (full result, not the trimmed one) |
| `claim_blocked` | loop | `{text, problems}` |
| `limit` | loop | `{reason}` |
| `refund_failed` | services/training.py | `{run_id, error}` |

**`agent_runs` table:** `project_id, status, steps_used, tokens_used, llm_cost_micros, stop_reason, ended_at` plus id and created time from the base class.

**Read access:** `GET /projects/{id}/trace` returns `[{seq, kind, content}]` for the whole project (no auth).

## 2. Gaps in what exists (BUILT facts)

1. Not recorded: the prompt sent to the model, the model id, call latency, the state block text, the offered tool list, text the model wrote next to tool calls, the approval card (it is only in the HTTP reply), the step number inside a turn, guard checks that passed.
2. `llm` steps are missing when the service reports no usage.
3. Evals and the notebook use an **in-memory SQLite database**. It is discarded after each case. `evals/run.py` keeps only tool names, gate dicts, turn texts and check results in the report JSON. **Tool arguments and results are lost.** This is why a failed eval cannot be read.
5. Nothing is printed live while an eval runs except `<case> #n: pass/FAIL ...`.
6. Tool results contain real cell values (`inspect_candidate` preview, 3 rows). They are stored in the database trace.

## 3. Requirements (BUILT)

- (a) A live console line per event, with levels.
- (b) For every eval case run and every notebook turn: a JSON Lines file with all events and a Markdown transcript, under a stable run id.
- (c) A command and a notebook helper to view a past run.
- (d) Never log secrets. Log personal data and dataset rows only as a few truncated sample values.
- (e) The same events must map onto `agent_steps` and `agent_runs`, so the web app can show the same log later.

## 4. Design (BUILT)

One small interface, called from the loop at the points where it already writes trace steps:

```python
class RunLog:                      # backend/app/services/agent/runlog.py (new)
    def emit(self, type: str, level: str = "INFO", **fields) -> None: ...
```

- `run_agent(ctx, llm, message, log=None)`. `None` means a no-op logger, so existing tests do not change.
- Sinks: `ConsoleSink` (one line per event), `JsonlSink`, `MarkdownSink`, `DbSink` (writes `agent_steps` rows, i.e. wraps `TraceRepository.add`). The app uses `DbSink`; evals and the notebook use all four.
- Because `DbSink` is the existing trace, the web app can later render the same events from `GET /projects/{id}/trace`.

### Stable run id

- App turn: `AgentRun.id` (already exists, a string).
- Eval case run: `eval-<UTC stamp>/<case-id>/r<n>` (folder path).
- Notebook turn: `nb-<UTC stamp>/t<n>`.
- Every event carries `project_id`, `agent_run_id` and `log_id` (the folder-style id). A multi-turn eval case has one `log_id` and several `agent_run_id`s.

### Files

```
backend/logs/                              (git-ignored)
  eval-20261101-101500/
    index.json                             pass/fail per case run + links
    churn-subscription/r1/events.jsonl
    churn-subscription/r1/transcript.md
  nb-20261101-103000/t1/events.jsonl
                      t1/transcript.md
```

## 5. Event schema (BUILT, version 1)

One JSON object per line. Common fields on every event:

| field | type | meaning |
|---|---|---|
| `v` | int | schema version, 1 |
| `ts` | string | UTC ISO 8601 with milliseconds |
| `n` | int | event counter within the log, from 1 |
| `log_id` | string | stable run id above |
| `project_id` | string | |
| `agent_run_id` | string or null | `AgentRun.id` of the turn |
| `turn` | int | turn number within the log, from 1 |
| `step` | int or null | model step inside the turn, from 1 |
| `level` | string | `DEBUG` `INFO` `WARN` `ERROR` |
| `type` | string | see below |

Per type (extra fields). Column "agent_steps kind" says how it is stored in the database today.

| `type` | level | extra fields | agent_steps kind |
|---|---|---|---|
| `turn_start` | INFO | `status_before`, `message_chars`, `approved: [str]`, `model` | none (new) |
| `user_message` | INFO | `text` (see redaction) | `user` |
| `context` | DEBUG | `state_block` (text), `tools_offered: [str]`, `history_messages: int`, `prompt_sha256` | none (new) |
| `llm_call` | INFO | `model`, `ms`, `prompt_tokens`, `completion_tokens`, `cost_usd` (nullable), `finish_reason`, `text` (if any), `tool_calls: [{id,name,args}]` | `llm` (extend content) |
| `llm_error` | ERROR | `message`, `retryable` | `llm_error` |
| `tool_call` | INFO | `call_id`, `name`, `args` | `tool_call` |
| `tool_refused` | WARN | `call_id`, `name`, `why` (`unknown_tool`, `not_offered`, `bad_args`, `unreadable_args`) , `detail` | none (new; today it appears as a `tool_result` with `error`) |
| `gate` | INFO or WARN | `action`, `level_num`, `allowed`, `reason` | `gate` |
| `approval_card` | INFO | `tool`, `args`, `what` | none (new) |
| `tool_result` | INFO or WARN | `call_id`, `name`, `ms`, `ok` (bool), `summary` (one line), `result` (redacted, truncated to 2,000 chars) | `tool_result` |
| `guard` | WARN | `guard` (`claim`, `repeat`, `schema`), `detail`, `original_text` | `claim_blocked` for claim |
| `limit` | WARN | `reason`, `steps_used`, `tokens_used`, `cost_usd` | `limit` |
| `assistant_reply` | INFO | `text`, `corrected` (bool) | `assistant` |
| `turn_end` | INFO | `status` (reply, awaiting_approval, limit, error), `reason`, `steps_used`, `tokens_used`, `cost_usd`, `status_after`, `ms` | none (new; same data lives in `agent_runs`) |
| `run_end` | INFO | `turns`, `final_status`, `tokens`, `cost_usd`, `tools_called: {name: count}` | none |
| `browser_navigate`, `browser_blocked`, `browser_error`, `browser_excerpt`, `browser_screenshot` | INFO or WARN | PROPOSED with the browser tool: url, domain, title, http status, ms, text tokens, block reason, a 300-character excerpt, screenshot id. See `11-dataset-discovery.md` section 5 (simplified; field list to be written when built). They feed the UI "Live view" tab. Never log cookies or headers; screenshots are files, not database rows | new kinds (no migration) |

Example lines:

```json
{"v":1,"ts":"2026-11-01T10:15:00.123Z","n":6,"log_id":"eval-20261101-101500/churn-subscription/r1","project_id":"p1","agent_run_id":"a9","turn":1,"step":2,"level":"INFO","type":"tool_call","call_id":"call_x","name":"search_datasets","args":{"query":"customer churn"}}
{"v":1,"ts":"2026-11-01T10:15:01.040Z","n":8,"log_id":"...","project_id":"p1","agent_run_id":"a9","turn":1,"step":2,"level":"INFO","type":"tool_result","call_id":"call_x","name":"search_datasets","ms":912,"ok":true,"summary":"6 results (1 bundled, 5 Hugging Face)","result":{"results":["...redacted/truncated..."]}}
```

### Mapping to existing tables

- `agent_steps.content` is free JSON and `kind` is a free string, so new kinds need no migration. Keep today's kinds for the first six rows of the table above; add `step`, `call_id`, `ms` inside `content`.
- `agent_runs` already has steps, tokens, cost, stop reason, end time. PROPOSED new columns: `model` (string), `turn_ms` (int). The repo rule today is "delete the old local `aioac.db`" when columns change (`specs/status.md`), so batch such changes.
- `context`, `turn_start`, `turn_end`, `run_end`, `tool_refused` need not be stored in the DB. Files are enough for evals; the app can derive them from `agent_runs`.
- Fixes needed so the DB trace is usable as the source: write the model's side text, stamp gate steps with the run id at write time (pass `run_id` into `gate.authorize`), record the approval card.

## 6. Console format (BUILT)

One line, fixed columns, so it can be read live and `grep`-ed. Default level `INFO`; `-v` shows `DEBUG`.

```
10:15:00.1 INFO  t1.s1 MODEL  claude-sonnet-4.5  1,203 in / 41 out  $0.0041  1.4s  -> load_skill(name="dataset-search")
10:15:00.2 INFO  t1.s1 GATE   search            allowed
10:15:00.3 INFO  t1.s1 TOOL   load_skill        ok  playbook 1,190 chars  3 ms
10:15:01.9 INFO  t1.s2 MODEL  claude-sonnet-4.5  2,480 in / 38 out  $0.0079  1.1s  -> search_datasets(query="customer churn")
10:15:02.8 INFO  t1.s2 TOOL   search_datasets   ok  6 results (1 bundled, 5 Hugging Face)  912 ms
10:15:09.0 WARN  t1.s6 GATE   select_dataset    needs user approval
10:15:09.0 INFO  t1.s6 CARD   select_dataset(candidate_id="3f2a", target="Churn")
10:15:20.4 WARN  t2.s3 GUARD  claim             reply said payment confirmed; status is quoted; reply replaced
10:15:31.0 WARN  t2.s12 LIMIT steps             12 model steps used
10:15:31.1 INFO  t2     END    status=limit reason=steps  tokens 31,200  $0.0980
```

Levels: DEBUG = context, full prompts (if enabled). INFO = normal events. WARN = refusals, guard hits, limits, approvals, tool errors the model can recover from. ERROR = model service failure, tool crash, harness crash.

## 7. Transcript (BUILT, `transcript.md`)

Readable by a person with no code open. Per turn: a heading, the user text, then for each step a short block.

```
# churn-subscription r1  (eval-20261101-101500)   result: PASS   cost $0.04   tokens 31,200

## Turn 1  status described -> data_chosen
**User:** I run a subscription business and I want to predict ...

**State at step 1**
    Goal: ... / Status: described / Next: Find or receive a dataset ...
**Step 1** model asked for 1 tool (1,203 in, 41 out, $0.0041)
- load_skill(name="dataset-search")  -> allowed -> ok (playbook, 1,190 chars)
**Step 2** ...
- search_datasets(query="customer churn")  -> ok: 6 results
  - hf:scikit-learn/churn-prediction  (license not stated, 5,000 downloads)
**Agent:** (reply text)
**Guards:** none fired
```

## 8. How to view a past run (BUILT)

- Command: `python -m evals.show <log_id or folder> [--tools] [--md] [--raw] [--level WARN]`. `--tools` prints only tool calls and results. Reads `events.jsonl`.
- App database: `GET /projects/{id}/trace` returns `agent_steps`.
- The notebook's `Watching` wrapper is replaced by passing a `RunLog` with the console sink, so tool calls and gate decisions print live, not only model replies.
- Eval runner: `--log-dir` (default `backend/logs/`) and `-v`. The summary table prints the folder of every failed run.

## 9. Redaction rules (BUILT)

1. **Secrets never enter an event.** Events are built from fields listed in the schema, not from raw HTTP objects. No request headers, no environment values, no `settings` dump. A final scrub on every string removes patterns: `sk-[A-Za-z0-9_-]{16,}`, `Bearer \S+`, `eyJ[A-Za-z0-9_-]{20,}`, `AKIA[0-9A-Z]{16}`, 13 to 19 digit runs (cards). A unit test feeds fake keys through every sink and asserts they never appear.
2. **Dataset rows:** `preview` and any list of row dicts keep at most 3 rows, each value cut to 40 characters, and the file notes `"rows_truncated": true`. Whole tables are never logged.
3. **Prompts:** the full message list is not logged by default (it contains the user goal and previews). Log `prompt_sha256` and the state block only. `--log-prompts` turns full prompts on for local debugging and writes them to a separate `prompts.jsonl`.
4. **User text:** logged as sent in local evals (our own cases). For real users, `LOG_USER_TEXT=false` replaces it with its length and a hash.
5. **Files are git-ignored.** Add `backend/logs/` to `.gitignore` (the repo is public).
6. **The web trace endpoint** (`GET /projects/{id}/trace`) must apply the same redaction before any public use.

## 10. Build notes (PROPOSED)

- Smallest first version: `RunLog` with console and JSONL sinks, hooked at the existing `trace.add` calls in `loop.py` plus `llm_call` timing. About 150 lines. Then the Markdown sink and `show`.
- Do not change gate decisions or tool behaviour. Logging must never raise: wrap every sink call in try/except and drop the event.
- Test: run the fake-model eval; assert `events.jsonl` has one `tool_call` per entry of `result["tools"]`, every `tool_call` has a matching `tool_result` or `approval_card`, and no fake secret appears.

## 11. Built: deviations from the design above (2026-10-24)

- `RunLog.emit(type, level, **fields)` with sinks `ConsoleSink`, `JsonlSink`, `MarkdownSink`, `DbSink`. `run_agent(..., log=None)` defaults to a log with no sinks. Every redaction and sink call is wrapped; a failure drops the event and never reaches the turn. The log also keeps its events in `log.events` (used by tests and the notebook).
- `DbSink` writes only the events that have no other trace row: `approval_card` and `tool_refused` become `agent_steps` rows. The loop still writes the other rows itself (`user`, `llm`, `tool_call`, `tool_result`, `gate`, `assistant`, `claim_blocked`, `limit`), so nothing is stored twice. The `llm` row gained `step` and `ms`.
- The `guard` event is written for the reply (claim) guard. The repeat guard shows up as a `limit` event and bad arguments as `tool_refused`.
- `tool_result` events carry `error_detail` (type and message of a crashed tool, secrets scrubbed, paths kept). The model and the stored trace get only a generic message (W16).
- The console hides `tool_call` lines (the `MODEL` line already shows the call) unless the level is DEBUG.
- `agent_runs` did not get `model` or `turn_ms` columns; the model id and turn time are in the `turn_start` and `turn_end` events.
- `run_end` is emitted by the eval runner and the notebook (`log.run_end(final_status)`), not by the loop.
- Settings: `LOG_USER_TEXT` (default true). Full prompts: `RunLog(log_prompts=True)` or `evals.run --log-prompts`, written to `prompts.jsonl`.
- Secret scrub: the patterns in section 9 plus any non-empty secret value in settings (OpenRouter, PayPal secret, Hugging Face, Inngest) and `api_key=`, `secret:`, `password=` pairs. The 13 to 19 digit rule can hit long numeric ids; that is accepted.
- Not built: browser events, redaction on `GET /projects/{id}/trace` (still needed before any public use), the PROPOSED `model` and `turn_ms` columns.
- Tests: `tests/test_runlog.py`.
