from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class TrainingResult:
    accuracy: float
    simple_guess_accuracy: float
    runtime_seconds: float
    cost_cents: int            # actual cost of the run, never above the cap
    stopped_at_cap: bool = False
    model_bytes: bytes | None = None
    stopped: bool = False      # True when the run ended because should_stop() returned True


class TrainingBackend(Protocol):
    name: str
    instance_type: str | None

    def run(self, dataset_path: str, target: str, cap_cents: int,
            on_progress: Callable[[str, float], None] | None = None,
            should_stop: Callable[[], bool] | None = None, job_key: str | None = None) -> TrainingResult:
        """on_progress(stage, fraction) reports plain-language progress (fraction 0..1).
        should_stop() is polled between stages; when it returns True the backend ends early and returns
        TrainingResult(stopped=True, cost_cents=<used so far>).
        job_key is the training run id. A backend that creates remote jobs must derive the remote job's name from it,
        so that a repeated call for the same run finds the same job instead of starting (and billing) a second one."""
        ...
