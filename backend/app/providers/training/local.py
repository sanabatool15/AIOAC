class LocalBaselineBackend:
    """Free baseline run (scikit-learn) on held-out data. Cost is always 0."""

    def run(self, dataset_path, target, spend_cap_cents):
        raise NotImplementedError
