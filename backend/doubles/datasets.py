"""Offline dataset source for tests and evals (no network)."""
import io

import pandas as pd

from app.ports import DatasetHit, DatasetInfo, FetchedCsv, SourceError
from app.services.data.samples import churn_csv


class OfflineSource:
    """One plain-table dataset, no network. Also used by --offline-data so real-model runs do not depend on Hugging Face."""

    def search(self, query, limit=6):
        return [DatasetHit("eval/churn-table", "Customer churn table (synthetic)", "mit", 100, 1, False)][:limit]

    def info(self, dataset_id):
        if dataset_id not in ("eval/churn-table", "scikit-learn/churn-prediction"):  # the second is the hand-checked list's churn entry
            raise SourceError("dataset not found")
        return DatasetInfo(dataset_id, 1500, 90_000, [{"name": "months_active", "dtype": "int64"}, {"name": "left", "dtype": "string"}],
                           True, False, "mit", "default", "train", [])

    def fetch_csv(self, dataset_id, max_rows, max_bytes):
        self.info(dataset_id)
        csv = churn_csv(1500)
        return FetchedCsv(csv, len(pd.read_csv(io.BytesIO(csv))), "mit", False)
