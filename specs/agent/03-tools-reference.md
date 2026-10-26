# Tools reference

Source: `backend/app/services/agent/tools.py` and `context.TOOLS_BY_STATUS`. All 12 tools are **BUILT** (`discover_datasets` added 2026-10-25). Each entry says what the code does. "Logged" always includes the `tool_call` step (name, args), the `gate` step and the `tool_result` step (full result) in `agent_steps` (`loop.py`, `gate.py`).

Common rules (BUILT):
- Schemas are JSON objects. All declared properties are required. Only "string must be non-empty" is checked (`guards.check_args`).
- Gate levels: 0 free, 1 needs user approval, 2 paid (`gate.LEVEL`).
- A tool outside the current status list is refused before the gate (no gate step is written for those).
- Free (level 0) tools run in a worker thread with a 60 s timeout.

## discover_datasets
- Purpose: find datasets for a user who has no data. Gate action `DISCOVER`, level 0. Offered in: `described`. Spec: `11-dataset-discovery.md` sections 3, 4, 7.
- Input: `{goal_summary: string, queries: [2 or 3 short English phrases]}`. The model supplies only these; code does the rest (`services/discovery.py`).
- What the code does: the hand-checked list (`providers/datasets/curated.json`), then UCI, OpenML, Hugging Face in that order (`registry.SEARCH_ORDER`). Hits become one record shape, then pre-filters (gated, not a plain table, not a classification task, under 300 rows), near-copy collapse, ranking, and a plain reason per result. A source that fails is reported in `sources` and never fails the tool; live searches share a 40 s budget.
- Output: `{candidates: [up to 3], sources: {name: "ok, N found" | "unavailable: ..."}, near_copies_removed, next | (nothing_fits: true, advice, sample_option?)}`. Each candidate: `{id (hf:/uci:/oml:/sample-...), name, source, reason, rows, license, notes, answer_column_hint?, about?, hand_checked?, sample_data?}`. Outside text (name, about, answer column hint of non-curated results) is wrapped in `<untrusted_dataset_text>`; licenses go through `sanitise_license`.
- Samples: the bundled sample is added only if a slot is free, or offered separately as `sample_option`; it is always labelled `sample_data` and never counts as a fit.
- Nothing fits: no result reaches relevance 0.30 (and a listed result must reach 60% of the best). Result has `nothing_fits: true` and advice; the agent must say so and offer an upload.
- DB changes: none. Logged: `tool_call`, `gate`, `tool_result`, plus run-log events `discover_source` (per source: ok, found, ms, error) and `discover_ranked` (considered, fits, collapsed, dropped, top ids).
- Failure: bad arguments give `{error}`. No network call can fail the tool.

## search_datasets
- Purpose: find datasets for the goal. Gate action `SEARCH`, level 0.
- Offered in: `described`.
- Input: `{query: string}`.
- Output: `{results: [...up to 8], warning?}`. Each item: bundled `{id, name, source:"bundled sample", license}` or Hugging Face `{id:"hf:<name>", name, source, about (<=200 chars), license, downloads, gated}`. Bundled items come first.
- DB changes: none.
- Failure: Hugging Face down -> bundled results plus `warning`. No error raised.
- Notes: bundled match is a whole-word test on keywords and name words, results carry `sample_data: true` (W13 fixed). `about` is wrapped in `<untrusted_dataset_text>` (W10 mitigated).

## look_at_dataset
- Purpose: preview size, columns and whether it is a plain table before downloading. `SEARCH`, level 0.
- Offered in: `described`.
- Input: `{dataset_id: string}`. Ids carry their source: `hf:owner/name`, `uci:144`, `oml:40945`; bundled ids are plain (`sample-churn`). Resolved through `providers/datasets/registry.py`.
- Output (HF): `{rows, tabular, gated, license, columns:["name (dtype)", up to 25], notes}`. Bundled: `{name, rows, tabular, license}`.
- DB changes: none.
- Failure: `{error}` for unknown id, not found, gated, viewer not ready, rate limit, network.
- Notes: column names are untrusted text.

## fetch_dataset
- Purpose: download into temporary storage. `FETCH`, level 0.
- Offered in: `described`.
- Input: `{dataset_id: string}`.
- Output: `{candidate_id, rows, truncated, license, suggested_target?}` for HF, UCI and OpenML (the hint is only given when it is a real column); bundled `{candidate_id, rows, suggested_target}`.
- DB changes: new `DatasetCandidate` row (expires after `candidate_ttl_hours`) and a file `candidates/<project>/<id>.csv`.
- Limits: 50,000 rows, 50 MB (`config.py`). Gated, non-table and too large are refused with a plain message.
- Failure: `{error}`. A timeout over 60 s ends the turn (W12) and the thread may still finish the download.
- Not capped per project: the model can fetch many candidates (bounded by 12 steps).

## load_skill
- Purpose: return a playbook. `SEARCH`, level 0.
- Offered in: every status.
- Input: `{name: string}`. Output: `{playbook: text}` or `{error, available names}`.
- DB changes: none. See file 05.

## inspect_candidate
- Purpose: grade, findings and a 3-row preview of a fetched candidate. `ANALYZE`, level 0.
- Offered in: `described`.
- Input: `{candidate_id, target}` (exact column name, case sensitive).
- Output: `{grade, findings, preview: 3 rows as dicts}`.
- DB changes: none.
- Failure: `{error:"unknown candidate"}` (also if it belongs to another project); `{error:"column 'x' not found", columns:[...]}`.
- Notes: the preview puts real cell values into the model context and the trace (see file 06 on redaction).

## select_dataset
- Purpose: choose the dataset. Deletes the other candidates. `SELECT_DATASET`, **level 1**.
- Offered in: `described`.
- Input: `{candidate_id, target}`.
- Gate: without `ctx.approved` containing `select_dataset`, raises `NeedsApproval`. The turn ends with the card.
- Output: `{rows, target, other_candidates:"deleted"}`.
- DB changes: new `DatasetVersion` (`datasets/<project>/v1.csv`), other candidates set `discarded` and their files deleted, `project.chosen_dataset_version_id`, status -> `data_chosen`.
- Failure: `DatasetError` (unknown dataset, column not found) comes back as `{error:"DatasetError: ..."}`.
- Notes: approval is not tied to args (W2). No check that the target is a category column (W15).

## run_readiness
- Purpose: grade and findings for the chosen dataset. `ANALYZE`, level 0.
- Offered in: `data_chosen`.
- Input: none. Output: `{grade, findings}`.
- DB changes: `InsightReport` row, `project.readiness_grade`, status -> `readiness_done`.
- Failure: any exception -> a generic error text; the detail goes to the run log only (W16 fixed).

## run_baseline
- Purpose: free test on held-out rows; also saves the timings used by the quote. `BASELINE`, level 0.
- Offered in: `readiness_done`.
- Input: none. Output: `{accuracy, simple_guess_accuracy, trust_level}`.
- DB changes: `BaselineRun` row, `project.baseline_result`, `project.trust_level`, status -> `baseline_done`.
- Failure: exception -> error result. Runs 5%, 10%, 20% samples plus the main fit; large data could exceed 60 s (W12).

## run_pilot
- Purpose: free pilot on about 5-10% of the data (never the locked rows), then a forecast of the full-run result against the user's target (a number from 0 to 1, for example 0.8). Gate `PILOT`, level 0.
- Offered in: `baseline_done`.
- Input: `{target}`. Output: the forecast with confidence, band and eligibility, plus a reason when not eligible. All values are estimates.
- If confidence is below 0.60 the run is not sold ("Not eligible"). The agent then explains the data issues in plain words, asks the lowest result the user would accept, offers a suggested target, and may re-run the pilot. The "change of engineering approach" step is to be designed (`payments.md` section 2a).

## create_quote
- Purpose: compute estimate, range, cap (estimate includes the 5% success fee, which is charged only if the result is verified). Refused unless the forecast is eligible. Gate `CREATE_QUOTE`, level 0 (it only prepares the approval screen).
- Offered in: `baseline_done`, `quoted`.
- Input: none. Output: `{quote_id, estimate_cents, range_cents:[lo,hi], cap_cents, label:"estimate", next}`.
- DB changes: new `Quote` (expires after `quote_ttl_minutes`), status -> `quoted`. Calling again in `quoted` makes another quote.
- Failure: `{error}` (no baseline, too expensive, or any exception).

## request_payment
- Purpose: create the PayPal hold order for the approved quote (the hold is not a charge). `REQUEST_PAYMENT`, **level 2**.
- Offered in: `awaiting_payment`.
- Input: none. Output: `{payment_id, amount_cents, approve_url, next}`.
- Gate (`gate.py`): a quote exists, is approved, not expired. The `approve` list is not used for level 2.
- DB changes: `Payment` row (amount = quote cap). If a payment for the quote already exists it is returned (no second order). `payments.create_order` calls the gate again, so two `gate` steps appear.
- The user approves the hold in PayPal. The server confirms the hold (`POST /payments/{id}/authorize`) and captures at the end; never this tool.

## start_training
- Purpose: run paid training. `START_TRAINING`, **level 2**.
- Offered in: `paid`.
- Input: none. Output: `{status, cost_cents, result}`.
- Gate: a server-confirmed hold for the current quote, status `paid`, global budget has room.
- DB changes: via `training.run_training`: training run, model, ledger entries, capture and void (settle). It blocks until done (MISMATCH with the background design in `training.md` section 7).
- Not covered here: the HTTP route `POST /projects/{id}/train` is the normal path.

## PROPOSED new tools

| Tool | Purpose | Recommendation |
|---|---|---|
| `set_plan` | Store a structured plan card (goal summary, task type, data needed) | **Build now.** Cheap, helps every later step, matches wireframe 1 |
| `ask_user` (structured question with 2 to 4 options) | Turn a free-text question into buttons; store the pending question | **Later.** Needs the web app. Until then plain text questions work |
| `use_uploaded_file` / list uploads | Let the agent see candidates created by `POST /projects/{id}/data` and inspect them like fetched ones | **Build now.** Uploads are in the wireframes; today the agent only notices an upload via the state block next turn (W5) |
| `clean_dataset` (wrap `datasets.clean`) | Drop duplicates, make a new version | **Later.** Cleaning already happens in `features.prepare_features`; a visible tool mainly improves explanations |
| `drop_column` / `change_target` | Fix leaks the skill tells the agent to only point out | **Later**, behind level 1 approval and a new dataset version. Needed for the leak case in file 07 |
| `restart_project` / `change_dataset` | Let the user change their mind before a quote is approved | **Build now.** Fixes W4, W5 |
| `kaggle_search`, `kaggle_fetch` | Second dataset source | **Later**, after real credentials exist. See file 08 |
| `fetch_from_url` (paste-a-link) | Download a CSV from a user-provided link | **Later.** Needs SSRF protection (block private addresses), size limit, content check |
| `web_search` | Find datasets outside Hugging Face | **Superseded (2026-10-24) by the Playwright tools below.** The paid search API (Tavily and similar) is no longer the plan; an API search may be added later if browser search is unreliable. See `11-dataset-discovery.md` section 12 |
| `browse(url)` (simplified 2026-10-24: one tool, see file 11 section 5) | Find and read web pages (search pages, dataset cards, READMEs) with a headless Chromium; live view for the UI. | **Later (after the safety steps in file 04).** Level 0, gate action `BROWSE`, offered in `described`, limits per turn and per project, page text returned as untrusted and capped at 1,500 tokens. Tested live on 2026-10-24: Kaggle, Hugging Face, UCI and data.gov search pages work; DuckDuckGo, Google and Brave block; OpenML blocks the browser. Details in `11-dataset-discovery.md` section 12 |
| `run_analysis_code` (sandbox) | Model-written analysis scripts | **Never for the MVP.** Fixed functions are testable and safe |
| `explain_result` (read stored result) | Give the agent training results in `done` | **Build now** (read-only). Today only `load_skill` is offered in `done`, so the agent cannot read the result |
| `settle` (capture, void), `apply_infrastructure` | Money or cloud actions | **Never as agent tools.** The system does these (`agent.md` section 4) |
