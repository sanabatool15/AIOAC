import io

import pandas as pd

from app.providers.datasets.base import DatasetHit, DatasetInfo, FetchedCsv, SourceError
from app.samples import churn_csv


class FakeSource:
    """Offline dataset source. Dataset 'good/churn' is a plain table; 'bad/images' is not; 'gated/one' is gated."""

    def __init__(self, hits=None, fail_search=False):
        self.hits = hits if hits is not None else [DatasetHit("good/churn", "Customer churn table", "mit", 500, 3, False)]
        self.fail_search = fail_search
        self.fetched: list[str] = []

    def search(self, query, limit=6):
        if self.fail_search:
            raise SourceError("could not reach Hugging Face right now")
        return self.hits[:limit]

    def info(self, dataset_id):
        if dataset_id == "gated/one":
            return DatasetInfo(dataset_id, None, None, [], False, True, None, "", "", ["gated"])
        if dataset_id == "bad/images":
            return DatasetInfo(dataset_id, 100, 1000, [{"name": "img", "dtype": "Image"}], False, False, "mit", "default", "train", [])
        if dataset_id == "good/churn":
            return DatasetInfo(dataset_id, 1500, 90_000, [{"name": "months_active", "dtype": "int64"}, {"name": "left", "dtype": "string"}],
                               True, False, None, "default", "train", ["about 0.1 MB"])
        raise SourceError("dataset not found")

    def fetch_csv(self, dataset_id, max_rows, max_bytes):
        i = self.info(dataset_id)
        if i.gated or not i.tabular:
            raise SourceError("this dataset cannot be used")
        self.fetched.append(dataset_id)
        csv = churn_csv(1500)
        return FetchedCsv(csv, len(pd.read_csv(io.BytesIO(csv))), i.license, False)
