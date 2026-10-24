"""Run ONE tiny real SageMaker job and compare the estimate with the actual billable cost.

For a human with real AWS credentials (named profile or env vars) and the Terraform-created bucket and role.
Never run by tests or by an agent. It refuses to run without --yes and prints the maximum possible cost first.

    SAGEMAKER_BUCKET=... SAGEMAKER_ROLE_ARN=... python scripts/sagemaker_smoke.py --cap-cents 150 --yes
"""
import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.providers.training.sagemaker import SageMakerBackend, SageMakerJobError, local_sklearn_matches_container  # noqa: E402
from app.samples import churn_csv  # noqa: E402
from app.services import sagemaker_cost as costs  # noqa: E402
from app.services.baseline import run_baseline  # noqa: E402
from app.services.cost import estimate_quote  # noqa: E402
from app.services.cost_report import CostRecord, cost_accuracy_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap-cents", type=int, default=150, help="hard spend cap for this one job (default 150)")
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument("--yes", action="store_true", help="required: confirms you accept spending up to the cap")
    args = ap.parse_args()

    b = SageMakerBackend()
    try:
        max_secs = costs.max_runtime_seconds(args.cap_cents, b.instance_type)
    except costs.CapTooSmall as e:
        print(f"Refusing: {e}")
        return 2
    print(f"Instance {b.instance_type} in {b.region}, bucket {b.bucket or '(not set)'}")
    print(f"MAXIMUM POSSIBLE COST: {args.cap_cents} cents (about ${args.cap_cents / 100:.2f}). "
          f"AWS stops the job after {max_secs} seconds of training.")
    if not local_sklearn_matches_container(b.image_version):
        print("WARNING: local scikit-learn differs from the container version; models may not load locally.")
    if not args.yes:
        print("Not running. Re-run with --yes to start a real, billed job.")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "smoke.csv"
        path.write_bytes(churn_csv(rows=args.rows))
        base = run_baseline(str(path), "left")
        q = estimate_quote(base.samples, args.rows, args.cap_cents, b.instance_type)
        print(f"Estimate: {q.estimate_cents} cents (range {q.low_cents} to {q.high_cents})")
        try:
            res = b.run(str(path), "left", args.cap_cents,
                        on_progress=lambda stage, elapsed, spend: print(f"  {stage:<18} {elapsed:6.0f}s  spend so far {spend} cents"))
        except SageMakerJobError as e:
            print(f"Job failed ({e.kind}): {e}. Billable cost reported: {e.cost_cents} cents")
            return 3
    print(f"Actual cost: {res.cost_cents} cents. Stopped at cap: {res.stopped_at_cap}. "
          f"Held-out accuracy {res.accuracy:.3f} vs simple guess {res.simple_guess_accuracy:.3f}. Warnings: {b.last_warnings or 'none'}")
    print(cost_accuracy_report([CostRecord(q.estimate_cents, q.low_cents, q.high_cents, res.cost_cents)]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
