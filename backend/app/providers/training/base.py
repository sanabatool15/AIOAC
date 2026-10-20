from dataclasses import dataclass
from typing import Protocol


@dataclass
class TrainingResult:
    metrics: dict
    runtime_seconds: float
    cost_cents: int
    stopped_at_cap: bool = False


class TrainingBackend(Protocol):
    def run(self, dataset_path: str, target: str, spend_cap_cents: int) -> TrainingResult: ...
