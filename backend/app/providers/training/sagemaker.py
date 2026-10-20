class SageMakerBackend:
    """Paid training job. Must stop at spend_cap_cents."""

    def run(self, dataset_path, target, spend_cap_cents):
        raise NotImplementedError
