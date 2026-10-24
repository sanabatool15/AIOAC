# Data sources and Kaggle

> **Note (2026-10-24):** Finding data for the user is a core feature. See `11-dataset-discovery.md` for the source ranking, web search, pipeline and safety design. Where this file conflicts: Kaggle is now ranked after the curated list, UCI, OpenML and Hugging Face (section 6 below is superseded), and `web_search` is no longer "never" (it becomes a capped late fallback, see file 11 section 4). The Kaggle facts here still stand.

Sections 1 and 2 are **BUILT**. Sections 3 onward are **PROPOSED**. Kaggle facts in section 3 come from the Kaggle API docs read on 2026-10-24 (source files in the `Kaggle/kaggle-api` GitHub repo). Anything not found there is marked UNVERIFIED.

## 1. Current state (BUILT)

- Sources: Hugging Face (`providers/datasets/huggingface.py`), the bundled synthetic churn sample (`samples.CATALOG`), and CSV upload through `POST /projects/{id}/data` (`routes/projects.py`).
- Kaggle: not built. Google Drive: not built. Paste-a-link: not built.
- The agent can use Hugging Face and the bundled sample. It has **no tool for uploads** (file 03). The upload route creates a candidate; the agent learns of it only from the state block on the next turn, and only while no dataset is chosen.
- Limits (`config.py`): 50,000 rows, 50 MB per fetch. Gated and non-table datasets are refused. Missing license is allowed and flagged.

## 2. The interface in code (BUILT, `providers/datasets/base.py`)

The Protocol is called `DatasetSource` (not `DatasetProvider`):

```python
class DatasetSource(Protocol):
    def search(self, query: str, limit: int = 6) -> list[DatasetHit]: ...
    def info(self, dataset_id: str) -> DatasetInfo: ...
    def fetch_csv(self, dataset_id: str, max_rows: int, max_bytes: int) -> FetchedCsv: ...
```

- `DatasetHit(id, description, license, downloads, likes, gated)`.
- `DatasetInfo(id, rows, bytes, columns[{name,dtype}], tabular, gated, license, config, split, notes)`.
- `FetchedCsv(csv_bytes, rows, license, truncated)`.
- Errors: `SourceError` with a plain-language message.
- Factory: `get_dataset_source()` returns one `HuggingFaceSource` (cached). `deps.get_ctx_factory` puts that single source in `ToolContext.source`.

Hard-coded Hugging Face assumptions in `tools.py`: ids are checked with `startswith("hf:")`; `fetch_dataset` writes the candidate with source "Hugging Face" and a Hugging Face URL. A second source needs a dispatch step first.

## 3. Kaggle: what the docs say (verified 2026-10-24)

From `docs/README.md` (authentication):
- Create a token at `https://www.kaggle.com/settings/api` ("Generate New Token").
- Option 1: `kaggle auth login` (web-based OAuth).
- Option 2: environment variable `KAGGLE_API_TOKEN`.
- Option 3: token file `~/.kaggle/access_token`.
- Option 4 (legacy): `~/.kaggle/kaggle.json` from "Create Legacy API Key". The page does not mention `KAGGLE_USERNAME` or `KAGGLE_KEY`, so do not assume them.

From the main README: install with `pip install kaggle`; the tool can list, create, update, download and delete datasets.

From `docs/datasets.md`:
- `kaggle datasets list`: `-s/--search`, `--sort-by` (`hottest|votes|updated|active`), `--file-type` (`all|csv|sqlite|json|bigQuery`), `--license` (`all|cc|gpl|odb|other`), `--tags`, `--min-size`, `--max-size` (bytes).
- `kaggle datasets files`: `-v/--csv`, `--page-token`, `--page-size` (default 20, max 200).
- `kaggle datasets download`: `-f/--file`, `-p/--path`, `--unzip`. Large files are served in a zip of the same name.
- `kaggle datasets metadata`: `-p/--path`, `--update` (writes `dataset-metadata.json`).

UNVERIFIED (not in the pages read; read again before coding): rate limits; terms of use for programmatic access and for redistributing data; how license info is returned by `list` or `metadata` (field names); whether any dataset needs rule acceptance (the Kaggle docs page `https://www.kaggle.com/docs/api` is script-rendered and returned no text to my fetch); the Python class and method names if we call the library instead of the CLI; error codes for private or removed datasets; whether the REST endpoints behind the CLI are documented for direct use.

Before coding, the human or agent must open the current docs in a browser (or fetch `docs/README.md`, `docs/datasets.md`, and the Python API section) and record the exact calls here. Do not write code from this summary alone.

## 4. Proposed design for Kaggle

### 4.1 Credentials flow

1. The user (the developer, for the demo) creates their own token on Kaggle.
2. The token goes into `backend/.env` as `KAGGLE_API_TOKEN` (gitignored). `.env.example` gets only a placeholder like `KAGGLE_API_TOKEN=your-kaggle-token`.
3. `config.py` reads it. Startup prints `kaggle: configured` or `kaggle: not configured` (never the value).
4. If not configured, the agent does not offer Kaggle (the tool list omits `kaggle_*`), and says so honestly if asked.
5. The token is never put in prompts, tool results, traces, logs, the database or the browser. The scrub rules in file 06 must include the token pattern. A test sets a fake token and asserts it appears nowhere in events or trace.
6. Shared use by many users is out of scope: one server token means all users share one Kaggle quota and identity. Per-user OAuth is a later design.

### 4.2 Fit behind the existing interface

- New `providers/datasets/kaggle.py` with a `KaggleSource` implementing `DatasetSource`:
  - `search` -> `datasets list -s <q> --file-type csv --sort-by votes` (or the library equivalent). Map to `DatasetHit` (id `owner/slug`).
  - `info` -> `datasets files` for the file list and sizes, plus metadata for license and description. `tabular` is true only if a CSV file exists. Choose the largest CSV under the byte limit; put the choice in `notes`.
  - `fetch_csv` -> download that one file (`-f`) to a temporary folder, unzip, read with pandas, apply the same `max_rows` and `max_bytes` checks, return `FetchedCsv`.
- Ids: `kg:owner/slug`. Validate with a strict regex (like `ID_RE`) before they reach a process call or URL. Never build a shell string; if the CLI is used, pass an argument list.
- Replace the `startswith("hf:")` checks in `tools.py` with a small registry `{"hf": HuggingFaceSource, "kg": KaggleSource}`; `ToolContext.source` becomes a router. `fetch_dataset` records the right `source` and URL. Existing tool names and schemas stay the same, so the skills and evals keep working.
- Same limits and refusals: size, rows, non-table, gated (here: private or removed), license shown (`not stated` when absent). Same plain error text style. Same level 0 gate action `FETCH`.
- Untrusted text rules apply (file 04): Kaggle titles, descriptions and column names are untrusted.
- Offline tests: a `FakeKaggleSource` and recorded sample responses, in the same style as `tests/test_hf_source.py`. Real calls only in a manual script.

### 4.3 License and terms handling

- Show the license string in the tool result and the state block (after the sanitising rule in file 04).
- Policy to decide (file 09): allow all with a note, or refuse licenses outside an allow-list. UNVERIFIED which license names Kaggle returns; fill the list after seeing real output.
- Do not claim data may be used commercially. Say "check the license on the dataset page".

## 5. The wireframe sources (PROPOSED mapping)

The user reports the wireframes show Kaggle and Google Drive as connected sources, an upload dropzone and a paste-a-link field. I have not opened the Figma file.

| UI element | Maps to | Notes |
|---|---|---|
| Upload dropzone | Existing `POST /projects/{id}/data` + new agent tool `use_uploaded_file` | Cheapest and most reliable. Must add size limit and encoding checks to the route (none visible today) |
| Paste a link | New tool `fetch_from_url` | https only; block private and loopback addresses (SSRF); size and time limits; content-type check; no cookies; max redirects. Treat Kaggle dataset page links as `kg:owner/slug` |
| Kaggle connected source | `KaggleSource` above | Needs the token. For the demo "connected" can mean "configured on the server" |
| Google Drive connected source | A Drive picker or file id fetch using Google OAuth | Not researched. Requires reading Google's current docs, an OAuth app and consent screen. **Do not build before the video.** A public share link may work through `fetch_from_url` (UNVERIFIED how Drive serves large files) |
| Hugging Face (not in the wireframe list as given) | Exists | Stays the default |

## 6. Recommended order

1. **Agent tool for uploads** (already has a route). Unblocks the most likely demo path and the user's own data.
2. **Source registry refactor** (no new source). Small, tested offline, prepares 3 and 4.
3. **Paste-a-link** with strict limits.
4. **Kaggle**, after real docs are read and a real token exists.
5. **Google Drive**: later, probably after the hackathon.

## 7. What only real credentials can verify

- Kaggle: that the token works, the real response fields for search and files, license field names and values, real download time for a 50 MB file (vs the 60 s tool timeout), rate limit behaviour, private or deleted dataset errors, terms.
- Google Drive: the whole OAuth flow and file download behaviour.
- Hugging Face at scale: rate limits without a token (`specs/status.md` known gap 12).
