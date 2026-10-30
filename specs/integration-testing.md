# Integration Testing (live services)

Read this first when testing. `tests/integration/` is the only test folder that touches real outside systems: AWS, the PayPal sandbox, the Azure LLM, the database and live dataset sources. Everything else (`unit/`, `contract/`, `e2e/`) is offline. (Folder was `tests/real/` until 2026-10-30.)

## 1. How to run

From `backend/`, with a real `.env` or exported variables:

| Command | What it does | Cost |
|---|---|---|
| `RUN_REAL=1 pytest tests/integration -v -s` | Read-only checks and tiny calls. Paid tests skip. | Cents at most |
| `RUN_REAL=1 pytest tests/integration/test_aws_setup.py -v -s` | Bucket write probe, role, image tag, quota | Nothing |
| `RUN_REAL=1 RUN_PAID=1 pytest tests/integration/test_sagemaker_training.py -v -s` | One real capped SageMaker job | About 1 cent of AWS compute (cap 60 cents, at most about 7 cents) |
| `python -m evals.run --model <deployment> --repeats 2 --budget-usd 1` | Agent evals against the real model | Model tokens (Azure reports no cost; tokens only) |

`RUN_PAID=1` is a second switch on purpose: a plain `RUN_REAL=1` run can never start a paid job. Never run `test_paypal_sandbox.py` against a real account; it is sandbox only and needs a buyer approval step by a person.

## 2. Files

| File | Proves |
|---|---|
| `test_aws.py` | Credentials work, bucket exists, SageMaker reachable |
| `test_aws_setup.py` | Bucket accepts writes, training role assumable, scikit-learn image tag exists, training quota above zero, role limited to the project bucket (xfail, known gap) |
| `test_sagemaker_training.py` | Paid. One job completes inside the cap, model beats a simple guess, reported cost equals the formula on AWS's billable seconds, no job left running |
| `test_llm.py` | The configured LLM (Azure) answers a tiny prompt |
| `test_database.py` | Database reachable, schema creatable (rolled back) |
| `test_datasets_live.py` | Hugging Face search and the curated list |
| `test_paypal_sandbox.py` | Hold order and the two-capture lifecycle on the sandbox |

## 3. Safety rules for these tests

1. Sandbox money only. Never real cards or PayPal passwords.
2. Every paid test has a hard cap and a second opt-in switch (`RUN_PAID=1`).
3. A test that writes to AWS cleans up after itself (probe objects are deleted).
4. No test reads secrets into output. Print names, never values.
5. Leftover resources are a failure: `test_no_job_left_running`.

## 4. Findings log (live results)

2026-10-30, first full live pass:

- **AWS:** account `097087134314`, user `aioac-dev`, bucket `aioac-097087134314-us-east-1` accepts writes, role `aioac-sagemaker-role` exists, image `1.4-2-cpu-py3` is ACTIVE, `ml.m5.xlarge` training quota is 20.
- **Real price:** `ml.m5.xlarge` training is $0.23/hour; the placeholder in `services/cost/prices.py` is 25 cents (slightly conservative).
- **Real job:** cap 60 cents, 69 billable seconds, accuracy 0.82 against 0.69 for a simple guess, app cost 52 cents (1 compute, 1 storage, 50 platform fee), real AWS compute about 0.44 cents.
- **Known gap, role:** it has `AmazonS3FullAccess` and `AmazonSageMakerFullAccess`. Needs an inline policy for the project bucket and log group `/aws/sagemaker/TrainingJobs*`.
- **Known gap, versions:** the job trains on scikit-learn 1.4.2; the app machine has 1.9.1. A pickled model may warn or fail to load. Pin one version.
- **Cost estimate:** 4,800 rows: projected 2.3 s, measured 2.1 s (300 trees). 20,000 rows: projected 3.0 s, measured 5.8 s. The baseline times 100 trees while the SageMaker script uses 300, so the projection is low for larger data. The platform fee dominates the quote either way.
- **Agent evals, real model (`gpt-5.4-mini` on Azure), 2 repeats, 11 cases:** 6 of 22 passed, 0 safety violations. Causes: (a) cases still expect `search_datasets` first while the agent now uses `discover_datasets`; (b) after the user approves `select_dataset`, the model asks for approval again instead of calling the tool, so the project stays at `described`; (c) a vague goal triggers a search instead of a question; (d) a live `discover_datasets` call timed out at 60 s once (14 s on another run); (e) an Urdu goal did not get an Urdu-script reply.
