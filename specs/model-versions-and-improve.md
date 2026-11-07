# Design: better results (change model or data) and model versions

Status: DESIGN ONLY, 2026-11-07. Nothing here is built. Open questions for the owner are at the end; no code until they are answered.

## 1. Why

When the free forecast says the target is unlikely (confidence below 0.60), the agent only says "cannot offer a price" and suggests a lower target. The owner wants the agent to be allowed to change the model type or work on the data to lift the forecast. Also, a second training run must show up sensibly as a model version.

## 2. What exists today (read from code)

- `services/data/pilot.py` tries three model types (logistic, forest, boosting) on about 8% of the work rows with successive halving. The winner feeds the forecast only. The paid run always trains a RandomForest (`baseline.py`, `integrations/aws/train_script/train.py`), so the pilot's winner is ignored. The kept family is stored in `Forecast.pilot["kept"]`.
- The Improve round (`routes/forecast.py`, `lifecycle.reopen_for_improvement`) reopens the project at `baseline_done` on the same dataset version and re-runs the same pilot. Nothing about the data or model changes, only the target.
- `features.prepare_features` is fixed: it drops ID-like and answer-copy columns and duplicate rows. `datasets.clean()` exists and no caller uses it. `Action.CLEAN` is level 0 in `gate.py`.
- The locked test split is keyed by dataset version id (`verification.prepare_split`, `split_keys(version_id)`). A cleaned child version would get a NEW split: its locked rows differ, and rows the parent locked can land in the child's work set. This is the main leakage risk of the idea.
- `Model` has no version number, no current flag, no dataset version, forecast or quote link. A second run saves `models/{project}/{run}.joblib` (no overwrite) and adds a row. `runs_repo.latest_model` picks the newest by time, even if it scored worse; older models cannot be reached from the API.
- History lists all runs and quotes but only the latest payment. The public share page shows the newest finished run.
- Storage is local only. S3 is used by the SageMaker backend for job files, not for app data or models (no S3 `Storage` provider).

## 3. Rules that must hold (CLAUDE.md 1, 4, 5, 7)

1. Everything before a quote stays free. Exploring other model types or fixes runs locally in the pilot, never as a paid SageMaker job.
2. Choices of model type or data fix are made only on work rows. The locked rows are fixed ONCE per project (from the root dataset version, for example a stable hash of the row content) and every child version inherits that mask. The locked score is never shown before the paid verification.
3. Forecast and baseline are re-run after any change. The old quote is invalid. The quote pins `dataset_version_id` and the model type, and the gate refuses `start_training` if the project's current version or type differs from the quoted one.
4. A fix that removes rows or columns changes the user's data, so it needs an L1 confirmation card (rows removed, columns dropped, before and after counts). Changing only the model type is internal (L0) but is named on the quote card in plain words.
5. Limit the number of free approach trials per project (for example 3). Keeping the best forecast over many tries inflates confidence.
6. Wording: never "this will lift you to 90". Only "we will test whether this changes the estimate". Every number stays labelled an estimate. Payment code is not changed by this feature.

## 4. Options

| | A. Honest advice and pilot winner | B-small. A plus one guided fix | C. Auto search |
|---|---|---|---|
| What | Paid run uses the pilot's winning family. The agent explains `data_issues` in plain words. | A plus one L1-confirmed fix (drop duplicates, drop mostly-empty columns) creating a child dataset version, root-based locked split. | Agent iterates recipes, feature work, S3-backed versions. |
| Effort | 2 to 3 days | 4 to 5 days | 15+ days |
| Risk | Low. Forecast may rise a few points. | Leakage if the split is not rooted. Forecast selection bias. | High. |

Recommendation for 2026-11-12: A plus B-small plus model versions (section 5). Skip C. Be honest in the demo: on data like the 13% case, cleaning will probably not change the verdict, so it is not shown as a rescue.

### A in detail
- New `services/data/models.py`: one pipeline factory per family, used by `pilot.py` (`_model` moves there), `baseline.py` and `train.py`, so they cannot drift. The SageMaker script gets a `family` hyperparameter. Only scikit-learn estimators (logistic, random forest, HistGradientBoosting): no new container image.
- Partial-save on SIGTERM works only for the forest (25-tree batches). Boosting and logistic are short; the script saves at the end.
- The cost estimate must time the CHOSEN family, otherwise the quote is wrong.
- Quote stores `family`. Pilot, Not-eligible and quote cards name the model type in plain words.

### B-small in detail
- `services/data/fixes.py` with a fixed whitelist. `POST /chats/{id}/fix` proposes (returns what would change), a confirm call applies it: new `DatasetVersion` with `parent_id` and `notes`, `projects.chosen_dataset_version_id` points to it, then a free pilot re-run.
- `Action.CLEAN` becomes level 1.
- The root locked mask lives with the root version (`verification.prepare_split` changes: split computed from the root, children inherit).

## 5. Model versions

Data (new columns, nullable adds, `python -m app.db.init --upgrade --yes`):
- `models`: `version_no` (1..n per project), `dataset_version_id`, `forecast_id`, `quote_id`, `family`, `is_current`, `verified_value`, `passed`.
- `training_runs`: `dataset_version_id`.
- Exactly one `is_current` per project. Default: the newest model that passed verification, or the best verified value if none passed. A worse new model does not replace a better one automatically. Owner action `POST /projects/{id}/model/{model_id}/use` (free).
- Old rows: fill `version_no` by creation time, newest `is_current`.

Screens:
- Model tab: list "Version 1, Version 2" with date, data note, model type in plain words, verified score against the target ("out of 100 right on rows it never saw"), badge "In use", buttons "Use this version" and "Download" (`?model_id=`), and a compare line ("version 2 is 3 points better, an estimate from held-back rows"). Try-it uses the current version, with an optional selector.
- History: one timeline entry per attempt (pilot and forecast, quote, payment, run, resulting model version). Show all payments, not only the latest. Label Improve rounds "Round 1, Round 2".
- Public share page: only the current version's verified result and its number. Never other versions or any cost.

What breaks and must change: `model_use.current_model`, `describe`, `predict_one`, `predict_batch`, `download` and the four routes in `routes/screens.py`; `share.public_result` (`latest_finished`); `history.project_history` (one payment); `training.execute_run` (set version and current, do not auto-promote a worse model); tests that assume the latest model (grep `latest_model`); frontend `model-tab.tsx`, `result-step.tsx`, `project-detail.tsx`. Comparing versions is only valid when they share the same locked rows, which is why the root-based split is required.

## 6. Gate and layers summary

- Routes: fix propose/confirm, model use, download by id.
- Services: `data/models.py`, `data/fixes.py`, `verification` (root split), `training` (versions), `quotes` (pin version and family), `gate` (refuse on mismatch, `CLEAN` to L1), `history`, `share`.
- Repositories: models, training_runs, datasets, quotes (all SQL here).
- Integrations: SageMaker script gets `family`.
- Frontend: Not-eligible card ("Try a fix" button), confirm card, forecast card shows version before and after, quote card names version and model type, Model tab, History.
- Human review (CLAUDE.md): gate change and quote pinning are payment-adjacent. Small commits, plain explanations.

## 7. Open questions for the owner

1. May a fix remove rows or columns, or only add derived information? (Removing rows changes what is measured.)
2. Keep the original locked test rows fixed even if the data shrinks? (Recommended: yes.)
3. Does a second paid run pay full compute again? May the user keep an older model "in use" when a newer one scored higher?
4. Maximum free approach trials per project?
5. Is an S3 `Storage` provider in scope before 2026-11-12, or is local storage acceptable for the demo?
6. How should the quote card name the model type in plain words without implying a better result?
