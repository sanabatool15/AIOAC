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
