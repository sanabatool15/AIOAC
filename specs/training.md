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
4. A timer checks accumulated cost; at the cap the job is stopped.
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
