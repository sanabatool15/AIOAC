# Agent Specification

The agent is the product. This file describes how it behaves, what it may do, and how it is kept safe and affordable.

## 1. Role

The agent turns a plain-language goal into a trained model by doing the technical work a person would otherwise need an ML engineer for. It talks to the user in plain words and never exposes technical choices in the main flow.

## 2. Runtime

A custom tool-calling loop. An LLM is called through OpenRouter with a list of available tools. It either answers the user or requests a tool call. The system runs the tool (after the permission gate) and feeds the result back. The loop ends when the agent reaches a user-facing decision or a final answer.

Why custom: we need our own permission gate, step limits and full traces, and the loop is small enough to build and test ourselves.

### Loop limits (proposed)

- Maximum steps per user turn.
- Maximum tokens per project.
- Per-tool timeout.
- A project-level LLM cost ceiling, separate from the training budget.

When a limit is hit, the agent stops and tells the user what it did, in plain words.

## 3. Capabilities (tools)

Tools are grouped by risk. The permission level for each group is described in section 4.

### 3.1 Read and research (free)

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

Planned skills:

- **Dataset search.** How to find, compare and choose datasets; what makes a dataset suitable.
- **Data insights.** How to inspect a dataset and how to phrase findings plainly.
- **Cost quote.** How to call the estimator and explain the result honestly.
- **Plain language.** Word choices for the user-facing flow.
- **PayPal.** Payment rules, taken from PayPal's toolkit documentation.

## 5.1 Context engineering

The agent works from a small, rebuilt-every-step context instead of the full history:

1. **Short base prompt** with the rules.
2. **Live state block** (status, chosen dataset, grade, free test result, quote, and the next step) rebuilt from the database on every step, so the model never has to remember it.
3. **Skill index only.** Skill bodies load on demand with `load_skill`.
4. **Tools offered by status.** Only the tools relevant to the project's current step are shown. The gate still enforces everything, so a tool outside the list is refused even if the model asks for it.
5. **Trimmed tool results.** Long lists are cut to 5 items and long text is cut, with a note.
6. **Windowed history.** Only the last 20 messages are kept, starting on a user turn.

## 6. Conversation behavior

- Ask at most one short question at a time.
- Explain what was found, not how.
- Never promise accuracy. Show a readiness grade, a real baseline result on held-out data, and a labeled estimate.
- When unsure, say so and give the user the choice.

## 7. Observability

Every step (model call, tool call, gate decision, result) is stored as a trace for the project. Traces power the live log on the training screen, the testing described in testing.md, and our debugging.

## 8. Failure behavior

- A tool fails: retry once if it is safe, then tell the user in plain words and offer a fallback (for example, a curated dataset).
- A limit is hit: stop, summarize, hand control back.
- Anything unexpected near money: stop, do not proceed, record it.
