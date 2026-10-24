# Agent Specification

> Detailed, code-verified agent documentation (BUILT vs PROPOSED, weak spots, logging and test plans) lives in `specs/agent/`. Start at `specs/agent/00-overview.md`. Where it disagrees with this file, it says so.

The agent is the product. This file describes how it behaves, what it may do, and how it is kept safe and affordable.

## 1. Role

The agent turns a plain-language goal into a trained model by doing the technical work a person would otherwise need an ML engineer for. It talks to the user in plain words and never exposes technical choices in the main flow.

## 2. Runtime

A custom tool-calling loop. An LLM is called through OpenRouter with a list of available tools. It either answers the user or requests a tool call. The system runs the tool (after the permission gate) and feeds the result back. The loop ends when the agent reaches a user-facing decision or a final answer.

Why custom: we need our own permission gate, step limits and full traces, and the loop is small enough to build and test ourselves.

### Loop limits (built)

Settings in `config.py`. Every turn is stored as an `agent_runs` row (steps, tokens, model cost in millionths of a dollar, stop reason, end time) and every step carries the run id.

- Maximum steps per user turn (12).
- Maximum model tokens per turn (80,000) and per project (600,000), from the `usage` the model service reports.
- Per-tool timeout (60 seconds) for free tools. Paid tools are never cut off by it. A tool that hangs ends the turn; the abandoned thread cannot be killed.
- A project-level model cost ceiling (USD 1.00), separate from the training budget. Enforced only when the service reports `usage.cost`; without it, only the token limits apply.
- Repeat guard: the same call with the same arguments more than 3 times in one turn ends the turn.

When a limit is hit, the agent stops and tells the user in plain words (`status: limit` with a `reason`). If the model service fails, the turn ends with `status: error` and a plain message. The OpenRouter client retries once on timeouts, rate limits and 5xx errors.

### Memory, logging and turn lock (built 2026-10-24)

- Every message is stored in `conversations` / `messages` (user text, assistant text with tool calls, full tool results with a one-line stub, loaded skills, approval cards). Each model step rebuilds its input from those rows inside a token budget (default 30,000), never splitting a call from its results. Details: `specs/agent/10-memory-and-context-store.md`. A code-built summary of old history is not built.
- `RunLog` (`services/agent/runlog.py`) writes one event stream to console, JSON Lines, a Markdown transcript and `agent_steps`, with secrets scrubbed. View a run: `python -m evals.show <log id or folder>`; from the app database: `python scripts/show_run.py <run or project id>`. Details: `specs/agent/06-observability-and-logging.md`.
- Only one turn per project runs at a time; a second `/chat` gets HTTP 409. Tool crashes give the model a generic message (detail in the log only). Dataset descriptions, column names, sample rows and licenses are wrapped as untrusted data.

### Guards on what the model says (built, cheap, not a security boundary)

- Arguments are checked against the tool's schema before anything runs. Unreadable JSON, missing or wrongly typed arguments, and unknown tools come back to the model as errors.
- A final reply that claims a payment, training or refund that the stored project state does not support is replaced with a plain correction and traced as `claim_blocked`. This is a keyword check and will miss rephrasings. The gate, not this check, is what stops spending.

## 3. Capabilities (tools)

Tools are grouped by risk. The permission level for each group is described in section 4.

### 3.1 Read and research (free)

Status: sections 3.1 to 3.5 are the original design. Section 3.6 lists what actually exists. Not built: web search or browser, the sandboxed analysis-code runner, the Terraform plan tool, the clean tool (cleaning happens inside `features.prepare_features`; `datasets.clean()` has no tool), and a PayPal skill. Treat those as future work.

- **Web search / browser.** Find candidate datasets and read dataset descriptions.
- **Dataset catalog lookup.** Look up open datasets, including those on Hugging Face, and read their size, columns, license.
- **Dataset fetch.** Download a candidate into temporary storage.

### 3.2 Analyze (free, sandboxed)

- **Run analysis code.** Execute short data-analysis scripts in a restricted sandbox against a stored dataset: column types, missing values, duplicates, class balance, row counts.
- **Readiness report.** Produce the readiness grade and plain-language findings from analysis results.
- **Free baseline.** Run the local baseline on held-out data and report a result and timing.
- **Optional second opinion.** Ask a hosted LLM to sanity-check an insight summary. Treated as advice, not as a source of numbers.

### 3.3 Prepare (free, changes stored data)

- **Clean and transform.** Fill missing values, pick the target column, drop duplicates. Always produces a new version; never edits the original.
- **Select dataset.** Mark one candidate as chosen. Triggers cleanup of the others.

### 3.4 Spend (needs approval)

- **Create quote.** Calls the cost estimator and stores a quote with an estimate, range and cap. Free to call; it only prepares the approval screen.
- **Request payment.** Creates a payment request tied to an approved quote. The user pays; the agent cannot.
- **Start training.** Only works after the server has confirmed the payment.
- **Refund unused.** Triggered by the system when training ends, not chosen by the agent.

### 3.5 Infrastructure (system-controlled)

- **Plan infrastructure.** May run a Terraform plan. A plan changes nothing.
- **Apply and destroy** are performed only by the system, only for an approved and paid job, and always followed by teardown.

### 3.6 Implemented dataset tools (MVP)

- `search_datasets`: bundled samples plus Hugging Face. Hugging Face is searched twice (tagged as tabular classification first, then untagged) and merged, because good datasets are often untagged.
- `look_at_dataset`: size, columns, and whether it is a plain table, before anything is downloaded.
- `fetch_dataset`: download into temporary storage, within row and size limits. Gated, non-table and oversized datasets are refused with a plain explanation.
- `inspect_candidate`, `select_dataset`, `run_readiness`, `run_baseline`, `create_quote`, `request_payment`, `start_training`, `load_skill`.
- Everything else in section 3 does not exist yet (see the status note under 3.1).

Hugging Face is called directly through its public API, not through MCP. The runtime agent needs tools that are easy to test offline and that pass through our permission gate. MCP servers (Hugging Face, Kaggle) remain useful for developers working with Claude Code, and an MCP client can be added later behind the same tool interface. Kaggle is not part of the MVP.

## 4. Permission model

Three levels, enforced by code outside the model.

| Level | Meaning | Examples | Who approves |
|---|---|---|---|
| L0 Free | No cost, no lasting change | search, analyze, baseline | Nobody; runs automatically |
| L1 Confirm | Changes the user's data or commits the project to a choice | select dataset, delete candidates | The user, with a plain card |
| L2 Paid | Spends or could spend money | request payment, start training | The user *and* a verified PayPal capture |

### 4.1 The approval card

Whenever the agent reaches L1 or L2, the user sees one card that states, in plain words:

- what the agent wants to do,
- the estimated cost, labeled as an estimate,
- the maximum it can charge (the cap),
- what is refunded if the job finishes cheaper.

### 4.2 Rules the gate enforces

1. No L2 tool runs without an approved quote that has not expired.
2. Start training requires a payment marked verified by the server.
3. The amount spent can never exceed the cap on the quote.
4. The gate looks at stored state, never at what the model says happened.
5. Every gate decision, allowed or refused, is logged.

## 5. Skills

Skills are short written playbooks the agent loads when needed, instead of carrying everything in every prompt. Each skill is one file with a clear purpose.

Built (in `backend/app/skills/`, one file each, under 60 lines):

- **dataset-search**, **data-insights**, **cost-quote**, **plain-language**.
- **data-leakage**, **lopsided-classes**, **choosing-the-target-column**, **suspiciously-good-baseline**, **too-little-data**, **explaining-results-plainly**. Data-science playbooks: what to look for, what to say, what the tools cannot do.

Not built: **PayPal**.

Rule: skills hold judgment and wording only. Rules about money (approval, caps, verified payment, refunds) live in code, in the permission gate, because a model can ignore or misread a playbook. A test checks that the data-science skills contain no payment or refund rules.

## 5.1 Context engineering

The agent works from a small, rebuilt-every-step context instead of the full history:

1. **Short base prompt** with the rules.
2. **Live state block** (status, chosen dataset, grade, free test result, quote, and the next step) rebuilt from the database on every step, so the model never has to remember it.
3. **Skill index only.** Skill bodies load on demand with `load_skill`.
4. **Tools offered by status.** Only the tools relevant to the project's current step are shown. The gate still enforces everything, so a tool outside the list is refused even if the model asks for it.
5. **Trimmed tool results.** Long lists are cut to 5 items and long text is cut, with a note.
6. **Stored history within a token budget.** Recent messages from the `messages` table (tool calls and results included), old large results shrunk to stubs, never splitting a call from its results (replaces the old 20-message window).

## 6. Conversation behavior

- Ask at most one short question at a time.
- Explain what was found, not how.
- Never promise accuracy. Show a readiness grade, a real baseline result on held-out data, and a labeled estimate.
- When unsure, say so and give the user the choice.

## 6a. Evaluating against a real model

`backend/evals/` holds 7 cases (data files), a runner and a report. `python -m evals.run --model <id> --repeats 3` runs the real OpenRouter client; `--fake` runs a scripted model offline and is what the tests use. The harness uses the mock payment provider, local training and a throwaway database, never approves a quote, and only approves dataset selection. Per run it checks: no paid work ran, no false claims, plain language, no accuracy promise, tool order, forbidden tools, dataset and target choice, limits respected. Reports go to `backend/evals/reports/` (git-ignored). Real-model pass rates do not exist yet.

## 7. Observability

Every step (model call, tool call, gate decision, result) is stored as a trace for the project. Traces power the live log on the training screen, the testing described in testing.md, and our debugging.

## 8. Failure behavior

- A tool fails: retry once if it is safe, then tell the user in plain words and offer a fallback (for example, a curated dataset).
- A limit is hit: stop, summarize, hand control back.
- Anything unexpected near money: stop, do not proceed, record it.
