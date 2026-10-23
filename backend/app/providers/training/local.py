from ...services.baseline import fit_and_score
from .base import TrainingResult


class LocalBackend:
    """Runs on this machine. Always costs nothing. Used for the free baseline and for the mock demo."""

    name = "local"
    instance_type = None

    def run(self, dataset_path, target, cap_cents):
        out = fit_and_score(dataset_path, target, n_estimators=300)
        return TrainingResult(out.accuracy, out.simple_guess_accuracy, out.seconds, 0, False, out.model_bytes)
