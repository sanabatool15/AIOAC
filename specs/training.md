# Training and Infrastructure

## 1. One interface, two backends

Training goes through a single interface so the rest of the system does not care where it runs.

- **Local backend.** Runs the free baseline on the app's own machine. Always costs nothing.
- **SageMaker backend.** Runs the paid CPU job on AWS.

A training request carries: the chosen dataset version, the target, and the spend cap. A result carries: the model, quality measures, runtime and cost, and whether it stopped at the cap.

## 2. The first paid job

- CPU, scikit-learn, classification.
- One fixed instance type from config.
- Sized so a run finishes in roughly 10 to 15 minutes. This keeps each test cheap (see the budget in cost.md).
- Demo note: the dataset and settings must be chosen so the job really takes that long. A tiny dataset finishes in seconds and would make the quote look silly.

GPU is a documented future path, not part of the MVP.

## 2a. AWS architecture (decided 2026-10-23)

- **Account:** brand-new AWS account with $160 of promotional credit. SageMaker was first used on 2026-10-22, so any SageMaker free-tier allowance (50 hours per month of `m4.xlarge` or `m5.xlarge` training for the first two months, as listed on AWS's pricing page; not yet verified against the Billing console) would run from that date. Check the Credits and Free Tier pages in the Billing console for the real expiry dates and exclusions.
- **Where the app runs:** locally. AWS provides only storage and training. No hosted servers.
- **Training:** a SageMaker training job using AWS's own scikit-learn container image and our training script (script mode). No custom Docker image and no ECR.
- **S3 holds everything we need to keep in AWS:** the chosen dataset, the packaged training script, and the trained model and output files. Temporary dataset candidates stay on the app's local storage until one is chosen, so nothing unneeded is uploaded. The database stays local (SQLite).
- **Instance:** one CPU instance (`ml.m5.xlarge`) first. The estimator may later choose the cheapest of a short CPU list that meets a time target. GPU is out of scope for the MVP: scikit-learn does not use it, new accounts typically start with a GPU quota of zero, and it costs about three times as much. It stays a documented future path.
- **Spot training:** not for the MVP. It adds interruption handling and a second time limit.
- **Verified in AWS docs (2026-10-23):**
  - The SageMaker scikit-learn container lists version `1.4-2` (Python 3.10) as supported, with a `1.4-2-py312` variant (end of patch 2026-10-30). The support-policy page also lists `1.9-0` (released 2026-07-16). We should pick a current version and use the same scikit-learn version locally, because a trained model is a pickled file and loading it under a different version can fail or warn. Confirm the exact image is available in our region when we first run a job.
  - A training job's stopping condition ends the job when its time limit is reached. SageMaker sends SIGTERM first and waits up to 120 seconds, so the script can save the model. Those extra seconds may be billed, so the safety margin for the cap must include them.
  - A finished training job reports `BillableTimeInSeconds`, which is what actual cost is computed from.
  - A training job can take an ordered list of up to 5 instance types and starts on the first with capacity. Useful later for hardware choice.
- **Still to verify:** the exact Service Quotas entry for `ml.m5.xlarge` training-job usage (check the Service Quotas console), and the current SDK call shape (SageMaker Python SDK v3 uses model trainers; v2 estimators may be deprecated).
- **Tool access:** the AWS plugins (`aws-core`, `sagemaker-ai`) are installed and can search documentation. They have no AWS credentials in this cloud session, so they cannot touch an account. The `terraform` plugin server failed to connect.

## 3. Infrastructure as code

Terraform describes the long-lived pieces:

- The storage bucket and its expiry rules.
- Access roles for the app and for training jobs.
- Cost monitoring and a budget alert on the AWS account.

Training jobs themselves are started by the application as runtime actions, not defined as permanent infrastructure.

### Rules

- The agent may run a plan. It changes nothing.
- Apply and destroy are run only by the system, never by the model.
- Each paid job ends with a teardown of anything it created.
- A scheduled check looks for leftover resources and reports them, because forgotten resources are the most likely way to waste the budget.

## 4. Running a paid job

1. The server confirms payment.
2. The system starts the job with the cap attached.
3. Progress is reported in plain language.
4. The cap is enforced by AWS itself: the job's maximum runtime is set so it cannot run past the cap. Our own timer is only a backstop.
5. The result is stored; actual cost is recorded in the ledger.
6. Unused money is refunded.
7. Temporary resources are cleaned up.

The user can press Stop at any time. Stopping triggers the same cost recording and refund steps.

## 5. Model output

The trained model is stored with its dataset version and result. The user can try it on one record, run it on an uploaded CSV, download it, or share it. Access is private by default; "public" is an explicit choice.

## 6. Open questions

- Which model families does the first job try?
- Do we give users progress based on real training steps or on time?
- How long are trained models kept?

## 7. Background training, progress and Stop (built 2026-10-24)

1. **Start.** `POST /projects/{id}/train` runs the gate, moves the project to `training`, creates the run (`running`), enqueues it on a `JobRunner` and returns `{run_id, status}` at once. If enqueueing fails, the run is failed and fully refunded and the API answers 503.
2. **Runner.** `app/jobs/`: a `JobRunner` interface (`enqueue(run_id)`, `is_active(run_id)`). `InlineJobRunner` runs the job in a thread (default; synchronous mode is used by all tests). `InngestJobRunner` sends the event `aioac/training.requested` to Inngest Cloud, which calls our function at `/api/inngest`. The function uses `retries=0` on purpose: a retry could start a second paid run for one payment. Selected by `JOB_RUNNER` (`inline` | `inngest`). The job body (`services/training.execute_run`) is the same for both and opens its own database session.
3. **Progress.** The backend calls `on_progress(stage, fraction)`; the run stores stage, fraction and a heartbeat (`updated_at`). `GET /projects/{id}/training` returns stage, fraction, elapsed seconds, spend so far and an ETA range. Spend and ETA are estimates from elapsed time against the quote (low and high ends), not from real steps.
4. **Stop.** `POST /projects/{id}/training/stop` sets `stop_requested` (409 if nothing is running). The backend polls `should_stop()` between stages and returns `TrainingResult(stopped=True)`. The run ends `stopped`, the project `stopped`, cost is what the backend reports, capped at the quote cap, and the normal settle and refund path runs. A stop that arrives after the backend finished does nothing: the run completes as `done`.
5. **Crash safety.** On API start, runs still `running` with no live worker and no heartbeat for `RUN_STALE_SECONDS` (inline runner: immediately; Inngest: 300 s default) are failed and refunded in full through the same settle path.
6. **Exactly-once endings.** Every ending goes through one `UPDATE ... WHERE status='running'`. A duplicate job delivery, a recovery racing a live worker, or a second stop can never finish a run twice, and `payments.settle` is idempotent per run id.
7. **Interface.** `TrainingBackend.run(self, dataset_path, target, cap_cents, on_progress=None, should_stop=None)`. `TrainingResult` gained `stopped: bool = False`. A SageMaker backend should call `StopTrainingJob` when `should_stop()` is true, return `stopped=True` and report billable time as `cost_cents`.

Known limits: the agent's `start_training` tool still calls the blocking `training.run_training` (agent code was out of scope for this change). One Inngest step holds one HTTP request open for the whole job, so the plan's maximum request duration applies (unverified); a long SageMaker job should later become start, then sleep and poll steps. The local backend can only stop between stages. If the refund call fails, a `refund_failed` trace step is written and the ledger keeps the owed usage entry.
