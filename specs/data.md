# Data: Search, Storage, Insights

The second most important area after cost. Most testing time goes here.

## 1. Sources

1. **User upload.** A CSV the user provides.
2. **Open datasets.** Found by the agent through web search and dataset catalogs, including Hugging Face.
3. **Curated fallback list.** A short, hand-checked list of datasets (for example the three in the wireframe) so the demo never depends on live search.

## 2. Dataset search

The agent looks for datasets that fit the user's stated goal.

What it checks for each candidate:

- Does the task match (classification first)?
- Is there a clear target column?
- Is the size reasonable (enough rows, not too large for our budget)?
- Is the license stated and usable?
- Does it look like real, tidy tabular data?

It keeps two or three candidates, explains each in one plain sentence, and lets the user choose.

## 3. Storage lifecycle

Candidates are temporary. The chosen dataset is permanent.

1. **Candidates.** Fetched into a temporary area. They expire automatically after a short time (for example 24 hours) even if nothing cleans them up.
2. **Chosen dataset.** When the user selects one, it is copied to the permanent area, versioned, and recorded in the database with its source and license.
3. **Cleanup.** After selection, the other candidates are deleted immediately.
4. **Cleaned versions.** Each cleaning step creates a new version. The original is never edited.

Storage is object storage (S3 in the cloud, a local folder in development) behind one interface, so the code does not care which.

Rule: the database records what exists; storage holds the bytes; a periodic check reports anything stored that the database does not know about.

## 4. Insights

Insights turn a dataset into plain statements the user can act on.

### 4.1 What is measured

- Row and column counts.
- Column types and the likely target column.
- Missing values per column.
- Duplicate rows.
- Class balance (how lopsided the answer column is).
- Obvious problems such as a column that leaks the answer, or constant columns.

### 4.2 How it is produced

The agent writes short analysis scripts and runs them in the sandbox. Numbers always come from running code, never from the model's own claims. The model's job is to choose what to check and to phrase the result.

### 4.3 Readiness grade

A letter grade (such as B+) from a simple, documented scoring of the measurements above, with the reasons listed as OK or NOTE lines. The same input always gives the same grade.

### 4.4 Trust level

Low, Medium or High, shown with one sentence of advice. It combines the readiness grade and the baseline result on held-out data. It is never presented as a guarantee.

## 5. The free baseline

A small, quick model trained locally and tested on data it has not seen. The result is expressed as "about N out of 10 predictions were right" next to what a simple guess would score. It exists to give an honest first signal and to provide the timing the cost estimator needs.

## 6. Sandbox for analysis code

Analysis scripts run in a restricted environment: no network, limited time and memory, only the stored dataset available. This is a safety measure and also keeps results reproducible.

## 7. Open questions

- How many candidates is the right number for the demo?
- Which dataset sizes are acceptable given the budget?
- What do we do when a dataset needs a license the user must accept?
