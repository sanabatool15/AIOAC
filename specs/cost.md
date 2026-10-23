# Cost Estimation and Spend Control

This is the idea that sets the product apart. It is also the least certain part, so it is designed to be measured and improved.

All figures below are placeholders until checked against current AWS pricing. Every number shown to a user is labeled an estimate.

## 1. Goals

1. Quote a price before any money moves, with an honest range.
2. Never spend more than the user approved (the cap).
3. Return whatever was not used.
4. Protect the shared AWS budget of about $160.

## 2. The quote

A quote has four parts:

- **Estimate:** the most likely total.
- **Range:** low to high.
- **Cap:** the most that can ever be charged. Set at the top of the range.
- **Breakdown:** compute, storage, platform fee.

The wireframe example: estimate $5.00, range $4 to $7, cap $7.00.

## 3. Formula

Total estimate = compute + storage and transfer + platform fee.

### 3.1 Compute

Compute is the hard part and has three steps.

**Step 1: measure.** Run the baseline on small samples of the user's data at two or three sizes (for example 5%, 10% and 20% of rows) and record the time of each run.

**Step 2: extrapolate.** Fit how time grows with row count and project to the full dataset. Training time often grows faster than linearly, so the fit allows for that rather than assuming a straight line.

**Step 3: convert to money.**

hours = (projected time x instance speed factor + startup overhead) / 3600

compute cost = hours x hourly price of the chosen instance

- **Instance speed factor:** how much faster or slower the cloud instance is than the machine that ran the sample. Measured once per instance type and stored in config.
- **Startup overhead:** fixed time for the cloud job to start and finish. Measured, not guessed.
- **Hourly price:** from the single prices config file.

### 3.2 Range

- **Low:** projection using the optimistic end of the fit.
- **High:** projection with a margin based on how well the fit matched the samples, with a minimum margin so the range is never falsely tight.
- **Estimate:** the middle value.

### 3.3 Storage and transfer

Small fixed amounts based on dataset size and how long it is stored. Placeholder until measured.

### 3.4 Platform fee

A fixed fee covering our own costs, shown as its own line.

### 3.5 Instance choice

For the MVP: one CPU instance type, chosen in config. The agent does not pick instances. A later version can choose the cheapest instance that meets a time target; this is described here as a future extension, not built.

## 4. Spend control

1. **Cap per job.** Set from the high end of the range, and never above a global per-job maximum.
2. **Hard stop.** The cap is turned into a maximum runtime (cap minus fixed fees, divided by the hourly price, minus a safety margin that includes the 120 seconds SageMaker allows after the stop signal) and given to SageMaker as the job's `MaxRuntimeInSeconds`. AWS ends the job when it is reached, so the stop does not depend on our code running. Our own check on a timer is only a backstop.
3. **Refund.** After the job, any difference between what was charged and the actual cost is refunded through PayPal. The refund is recorded in the ledger.
4. **Global budget guard.** A running total of actual AWS spend. Above a warning level the app warns the team; above a ceiling it refuses to start new paid jobs. This keeps testing money available for the demo.

### Proposed budget policy (to confirm)

| Setting | Proposed |
|---|---|
| Total AWS budget | $160 |
| Per-job maximum cap | $7 |
| Reserve kept untouched for demo and recording | $40 |
| Global ceiling for new paid jobs | $120 spent |
| Concurrent paid jobs | 1 |

## 4a. Calibration plan

Before trusting any number, run three or four real jobs on the smallest instance at different dataset sizes (cents each, possibly free under the free tier). Record the real startup overhead and the real speed relative to the local machine, then replace the guesses in the prices file. Compare the billable seconds SageMaker reports with our projection. The actual cost of a job is billable seconds times the hourly price.

## 5. Making the estimate better over time

Each finished job stores: the estimate, the range, the actual cost, and the dataset size. A simple report compares them. This is how we find out how wrong the estimator is, and it is the main subject of cost testing (see testing.md).

## 6. Known weaknesses

- Training time may not follow the fitted curve for some models.
- Small samples can hide behavior that appears at full size.
- Startup overhead varies on a busy cloud.
- Prices change.

The cap and the refund exist precisely because the estimate can be wrong.
