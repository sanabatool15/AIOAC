# Open questions and build plan

> Dataset discovery is a core feature, not an extra. Its design, decisions and build plan are in `11-dataset-discovery.md`. That file supersedes Step 7 below (source order) and decisions 12 and 13 where they differ: UCI and OpenML (no keys) come before Kaggle, and web search is now done by a Playwright browser tool, not a search API (section 12 of that file; the user decided on 2026-10-24).

Everything here is **PROPOSED**. Weak-spot ids (W1 to W20) are in file 01. Threat ids (T1 to T19) are in file 04.

## 1. Decisions needed from you

Each has my recommendation.

1. **Which model for real runs?** Config default is `anthropic/claude-sonnet-4.5` (`config.py`). Recommend: pick one strong model for the first measurement, then test one cheaper model. Needs an OpenRouter key and credit.
2. **Model spend budget for evals.** Recommend the tiers in file 07 section 8 (smoke USD 0.50, standard USD 5, release USD 15). OK?
3. **Reply language.** Reply in the user's language, or always English? Recommend: reply in the user's language, keep English internals, and test Urdu and Hindi in the eval set. If you want English only, say so and the agent should say it only speaks English.
4. **What if the user changes their mind after choosing data?** Recommend: add a `restart_project`/`change_dataset` path allowed before quote approval; after a verified payment, no change (new project).
5. **Should the approval card carry details?** Recommend yes: code-built sentence with dataset name, rows, target, and bound to the exact args.
6. **Ask or assume?** Recommend: ask at most one question, only when there is no outcome to predict or the outcome is a number; otherwise proceed with a stated assumption.
7. **Unsupported requests** (images, text, numbers). Recommend: decline in one sentence and offer a table-based version, as in cases 05 and 06. Confirm that "numbers" (regression) stays out of scope for the demo.
8. **License policy.** Allow everything with a visible note (current), or only an allow-list? Recommend: keep allowing, show the note, and store a sanitised license string.
9. **Real-data eval tier.** Allow manual runs against live Hugging Face (non-deterministic, rate limits) in addition to the offline datasets? Recommend yes, small, labelled "live".
10. **Logging of user text.** Fine to log full user text and previews (3 truncated rows) locally for our own tests? Recommend yes for evals, `LOG_USER_TEXT=false` for any real users.
11. **Agent `start_training` tool.** Keep it (blocking) or remove it and let the UI call `/train` only? Recommend remove it from the agent after the web app exists; training start is a user action, not an agent action. Needs your call because it changes the demo.
12. **Kaggle token.** Will you create a Kaggle token and add it yourself to `backend/.env`? I will never ask for it in chat. Recommend: yes, after the upload and link tools. Note: the browser tool can read Kaggle search and dataset pages (tested 2026-10-24) but cannot download data, so the token is still needed for fetching.
13. **Google Drive.** Recommend: skip before the video; show it as "coming soon" or hide it.
14. **Auth.** Anyone can approve quotes and read traces today. Recommend: keep deferred, but do not expose the API publicly.
15. **Spec cleanup.** Fix the stale items listed at the end of file 00 (status.md 6a and duplicate rows). Recommend yes, small separate change.
16. **Browser tool decisions.** Search order, optional install, JavaScript, domain policy, limits, live view. Listed with recommendations in `11-dataset-discovery.md` section 12.8.

## 2. Build plan

Each step is small. "Works" says how we will know.

### Step 1. Logging (file 06) — value: you can see what the agent does
- Change: add `RunLog` with console and JSONL sinks, hooked into `loop.py`; pass `run_id` into the gate; add `llm_call` fields (model, ms, text, tool calls with args). Then Markdown sink, `show` command, notebook helper, `.gitignore` entry, secret-scrub test.
- Works when: the fake-model eval writes a folder per case run; every `tool_call` has a matching result or card; the notebook prints tool calls live; a fake key never appears in any file; `pytest` still passes.

### Step 2. First real measurement — value: replace guesses with numbers
- Change: none in code. Run the smoke tier with a real key, `--offline-data`, repeats 3. Read the transcripts.
- Works when: we have a first pass table and at least 3 transcripts read by a human; failures are listed as W-ids or new ids.

### Step 3. Robustness test set (file 07) — value: answers the "one prompt, one dataset" worry
- Change: add `backend/evals/datasets/` generators and an offline source keyed by id; add the paraphrase families for 2 goals first; extend checks (tool set equality across a group, no tool call for off-topic, language). Add the guard phrase table test and injection test with `poisoned-meta`.
- Works when: offline tests pass in CI; a real run produces per-family rates with intervals; at least one failing family is found and written down.

### Step 4. Fix what Steps 2 and 3 found in code — value: removes brittleness that prompts cannot fix
- Candidates in order: license sanitising (T4), turn lock (W8), approval bound to args and detailed card (W2, W3), tool-memory line and target in state block (W1), target-type check (W15), generic tool errors (W16), id format hint errors (W14), step budget vs skill (W11), search matching (W13), claim guard against state with tests (W9).
- Works when: each fix has a replay or unit test written from the failure; the relevant eval family improves on the next run.

### Step 5. Prompt and context improvements (file 02 section 7)
- Change in this order: scope and language rules, untrusted-data rule and wrapping, clarifying-question policy, per-status instructions, new skill `handling-odd-requests` with examples, `set_plan` tool.
- Works when: off-topic, vague, unsupported and non-English families reach their targets over 5 repeats, and no previously passing family drops.

### Step 6. Tools that unblock flows (file 03)
- Change: `use_uploaded_file`, `explain_result` (read-only), `restart_project` / `change_dataset`, then `fetch_from_url` with SSRF protection. The browser tools (`browser_search`, `browser_open`, `browser_screenshot`) follow the steps B1 to B9 in `11-dataset-discovery.md` section 12.7; they need the safety work of Step 4 and the URL policy shared with `fetch_from_url` first.
- Works when: eval cases exist for each (upload path, change of mind, link path) and pass; gate tests prove the restart cannot run after a verified payment.

### Step 7. Source registry, then Kaggle (file 08)
- Change: registry refactor (no behaviour change), then read the current Kaggle docs and write the exact calls into file 08, then `KaggleSource` with offline fakes, then one manual real run.
- Works when: all old tests unchanged and green after the refactor; `FakeKaggleSource` tests pass; a manual run fetches one real dataset within limits; the token appears nowhere in logs.

### Step 8. Demo hardening
- Change: pick the demo dataset and goal; run the Release tier on that path 10 times; freeze the prompt and skills; record the demo.
- Works when: 10 of 10 runs reach `quoted` with correct explanations; zero safety violations.

## 3. Order rationale

Logging first because every later step needs to be seen. Real measurement second because it is cheap and replaces opinion with data. Tests third so each fix has a target. Code fixes before prompt work because code fixes are testable and do not depend on model wording. New tools and Kaggle last because they add surface that needs the earlier safety and test work.
