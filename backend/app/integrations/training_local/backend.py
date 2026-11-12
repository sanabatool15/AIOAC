import io

import joblib

from ...services.data.baseline import fit_and_score
from ...ports import TrainingResult


class LocalBackend:
    """Runs on this machine. Always costs nothing. Used for the free baseline and the default demo."""

    name = "local"
    instance_type = None

    def run(self, dataset_path, target, cap_cents, on_progress=None, should_stop=None, job_key=None, family="forest",
            task_type="classification", config=None):
        report = on_progress or (lambda stage, fraction: None)
        stop = should_stop or (lambda: False)

        def stopped():
            return TrainingResult(0.0, 0.0, 0.0, 0, False, None, stopped=True)

        report("preparing the data", 0.05)
        if stop():
            return stopped()
        report("training the model", 0.2)
        if task_type in ("grouping", "unusual"):
            return _fit_no_answer(dataset_path, task_type, config or {}, report, stop, stopped)
        if task_type == "forecast":
            return _fit_forecast(dataset_path, target, family or "forest", config or {}, report, stop, stopped)
        if task_type == "regression":
            out = _fit_regression(dataset_path, target, family or "forest")
        else:
            out = fit_and_score(dataset_path, target, n_estimators=300, family=family or "forest")
        if stop():  # checked between stages only; fit_and_score itself is one call
            return stopped()
        report("saving the model", 0.95)
        if task_type == "regression":
            return TrainingResult(out.score, 0.0, out.seconds, 0, False, out.model_bytes, score=out.score, task_type="regression")
        return TrainingResult(out.accuracy, out.simple_guess_accuracy, out.seconds, 0, False, out.model_bytes)


def _fit_regression(path, target, family):
    """One 80/20 fit of the chosen regressor on the WORK rows. Its own score is only a progress report: the money
    decision is the check on the locked rows (verification.py), on the pilot's frozen scale."""
    import time

    import pandas as pd

    from ...services.data import families
    from ...services.data.features import prepare_features
    from ...services.data.tasks import regression
    from ...services.data.baseline import BaselineOutcome

    raw = pd.read_csv(path)
    raw[target] = regression.to_number(raw[target])
    df = prepare_features(raw.dropna(subset=[target]), target)
    task = regression.RegressionTask()
    Xtr, Xte, ytr, yte = task.split(df, target, 0.2, 0)
    model = families.build(family, Xtr, None if family != "forest" else 300, task="regression")
    t0 = time.perf_counter()
    model.fit(Xtr, ytr)
    secs = time.perf_counter() - t0
    s = task.score(yte, model.predict(Xte), y_train=ytr, guess_error_ref=regression.guess_error_ref(ytr))
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return BaselineOutcome(accuracy=s.value, simple_guess_accuracy=0.0, seconds=secs, samples=[], model_bytes=buf.getvalue(),
                           task_type="regression", score=s.value)


def _fit_forecast(path, target, family, config, report, stop, stopped):
    """Fit the pinned family on every period of the WORK rows and keep the history so the model can forecast forward.
    Its own quality is not reported here: the only score that counts is the check on the locked newest periods."""
    import time

    import pandas as pd

    from ...services.data.tasks import forecast as fc

    t0 = time.perf_counter()
    model = fc.fit_forecaster(pd.read_csv(path), target, config, family, 300 if family == "forest" else None)
    secs = time.perf_counter() - t0
    if stop():
        return stopped()
    report("saving the model", 0.95)
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return TrainingResult(0.0, 0.0, secs, 0, False, buf.getvalue(), score=None, task_type="forecast")


def _fit_no_answer(path, task_type, config, report, stop, stopped):
    """Grouping and unusual records: fit the chosen model on every work row. There is no answer to score here; the check on
    the locked rows (verification.py) is the only number that is reported."""
    import time

    import pandas as pd

    from ...services.data.tasks import unsupervised as un

    t0 = time.perf_counter()
    model = un.fit_final(task_type, pd.read_csv(path), config)
    secs = time.perf_counter() - t0
    if stop():
        return stopped()
    report("saving the model", 0.95)
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return TrainingResult(0.0, 0.0, secs, 0, False, buf.getvalue(), score=None, task_type=task_type)
