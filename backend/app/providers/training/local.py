from ...services.baseline import fit_and_score
from .base import TrainingResult


class LocalBackend:
    """Runs on this machine. Always costs nothing. Used for the free baseline and for the mock demo."""

    name = "local"
    instance_type = None

    def run(self, dataset_path, target, cap_cents, on_progress=None, should_stop=None):
        report = on_progress or (lambda stage, fraction: None)
        stop = should_stop or (lambda: False)

        def stopped():
            return TrainingResult(0.0, 0.0, 0.0, 0, False, None, stopped=True)

        report("preparing the data", 0.05)
        if stop():
            return stopped()
        report("training the model", 0.2)
        out = fit_and_score(dataset_path, target, n_estimators=300)
        if stop():  # checked between stages only; fit_and_score itself is one call
            return stopped()
        report("saving the model", 0.95)
        return TrainingResult(out.accuracy, out.simple_guess_accuracy, out.seconds, 0, False, out.model_bytes)
