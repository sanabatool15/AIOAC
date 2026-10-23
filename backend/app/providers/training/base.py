from dataclasses import dataclass
from typing import Protocol


@dataclass
class TrainingResult:
    accuracy: float
    simple_guess_accuracy: float
    runtime_seconds: float
    cost_cents: int            # actual cost of the run, never above the cap
    stopped_at_cap: bool = False
    model_bytes: bytes | None = None


class TrainingBackend(Protocol):
    name: str
    instance_type: str | None

    def run(self, dataset_path: str, target: str, cap_cents: int) -> TrainingResult: ...
