# Future Work: Instance Selection and GPU / Deep Learning

Status: NOT BUILT. Notes written 2026-10-26 so the idea is not lost. Nothing here is a commitment. The current system runs one fixed CPU instance and that is what the demo uses. Do this after the core demo path is finished and recorded.

## 1. Where we are today (checked in code, 2026-10-26)

- One instance type only: `ml.m5.xlarge`. `services/cost/prices.py` has a single entry in `INSTANCES` (placeholder price, speed factor and startup time).
- The instance comes from the env value `SAGEMAKER_INSTANCE_TYPE`, read by `integrations/aws/sagemaker.py` and passed to `CreateTrainingJob` as `ResourceConfig.InstanceType`. It does not depend on the dataset.
- `services/cost/cost.py` `estimate_quote(..., instance=DEFAULT_INSTANCE)` is never called with another instance. The cap math (`integrations/aws/sagemaker_cost.py`) uses the hourly price of that one instance.
- Terraform (`infra/terraform/`) has no instance at all. It creates only the S3 bucket, the training role, the app policy and the budget alert. A training job is a runtime action started by the app through boto3, not infrastructure.
- The agent has no tool to choose or change an instance. This matches `cost.md` section 3.5: "the agent does not pick instances".

So today a big dataset and a small dataset run on the same machine. Only the estimated time and money differ.

## 2. Design principle

The agent proposes, the system disposes (`spec1.md` section 4). The model must never write Terraform and never choose the machine. Code chooses the machine from measured numbers, shows the choice and the reason in plain words, and the cap still comes from the quote. Changing a machine is changing one string in a request, not writing infrastructure.

## 3. Step 1: CPU instance selection (small, do first)

Goal: bigger data gets a bigger CPU, smaller data gets a cheaper one.

- `prices.py`: a short list of CPU instances (for example 2 or 3 sizes in the `ml.m5` family), each with hourly price, speed factor and startup seconds. All measured, not guessed (see the calibration plan in `cost.md` section 4a).
- `cost.py`: compute the estimate for every instance in the list and pick the cheapest whose worst case fits the per-job cap and the time target. The chosen instance goes on the quote (the quote already stores `instance_type`).
- `training.py` and the SageMaker backend: use the instance stored on the quote, not the env value. The env value becomes the default only.
- Cap math: already takes the instance as an argument, so it needs no new logic.
- Terraform: the training role must be allowed to run the chosen types (small policy check, no new resources).
- UI and agent wording: say "larger machine because the data is large", never the instance name (hard rule 8).
- Tests: the cheapest-fit choice, a case where nothing fits the cap (quote refused, as today), and that the instance on the quote is the one used for the job and the cap.

Open: the time target (for example 10 to 15 minutes) and the list of sizes.

## 4. Step 2: GPU and deep learning (later, a separate feature)

Changing the instance string to a GPU type is not enough. It would run the same scikit-learn random forest on the CPU of a GPU machine and bill GPU prices for nothing.

What a GPU path needs:

1. **A new training script and model family.** scikit-learn does not use a GPU. Options: XGBoost or LightGBM with GPU, or PyTorch for neural networks. A new script next to `integrations/aws/train_script/train.py`.
2. **A different container image.** A framework image with CUDA instead of the scikit-learn image. `SAGEMAKER_SKLEARN_VERSION` no longer describes the job; a per-family image setting is needed.
3. **A separate cost model.** Our estimate scales a CPU baseline timing by a speed factor. That relationship does not hold for GPU, so the quote range would be wrong. Needs its own samples and calibration jobs.
4. **A different free baseline.** The free local test runs on CPU. For a GPU model the "free test" must be redefined, or it stays a CPU model baseline shown as a reference.
5. **Quota.** New AWS accounts usually have a GPU training quota of zero. Request it early; approval can take time.
6. **Money.** GPU costs roughly three times a CPU instance per hour (to verify). With $160 total and a $7 per-job cap only short jobs fit. The global budget guard applies unchanged.
7. **Honesty.** On tabular data, deep learning often does not beat gradient boosting. Never imply a GPU makes the result better (hard rule 7). The readiness score and held-out baseline remain the honest signal.

What stays the same: the permission gate, the payment flow, the ledger, the cap becoming `MaxRuntimeInSeconds`, the hold, capture and void steps, background run and Stop. These do not care what the machine is.

Fit with the design: `TrainingBackend` is already the swap point. A GPU job can be a new model family behind the same interface rather than a change to the existing backend.

## 5. Hosting (even later)

Model hosting is listed under "Not building" in `spec1.md` section 2.3 (only download and a simple try-it form). A GPU model that needs a GPU to run would raise this again: a hosted endpoint is a continuous cost, unlike a training job that ends. Decide the hosting story before promising GPU models to users.

## 6. Suggested order after the demo

1. Calibrate the one CPU instance with real jobs (smoke script, `training.md` section 2b).
2. Step 1 above (CPU selection).
3. Decide whether GPU is worth it for tabular data at all. If yes, Step 2 as its own spec and plan.
