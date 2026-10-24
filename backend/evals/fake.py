"""Offline stand-ins so the harness itself can be tested without a network or an API key."""
import io
import json

import pandas as pd

from app.providers.datasets.base import DatasetHit, DatasetInfo, FetchedCsv, SourceError
from app.providers.llm.base import LLMResponse, ToolCall
from app.samples import churn_csv


class OfflineSource:
    """One plain-table dataset, no network. Also used by --offline-data so real-model runs do not depend on Hugging Face."""

    def search(self, query, limit=6):
        return [DatasetHit("eval/churn-table", "Customer churn table (synthetic)", "mit", 100, 1, False)][:limit]

    def info(self, dataset_id):
        if dataset_id != "eval/churn-table":
            raise SourceError("dataset not found")
        return DatasetInfo(dataset_id, 1500, 90_000, [{"name": "months_active", "dtype": "int64"}, {"name": "left", "dtype": "string"}],
                           True, False, "mit", "default", "train", [])

    def fetch_csv(self, dataset_id, max_rows, max_bytes):
        self.info(dataset_id)
        csv = churn_csv(1500)
        return FetchedCsv(csv, len(pd.read_csv(io.BytesIO(csv))), "mit", False)


class ReactiveFake:
    """A scripted 'model' that reads tool results (ids) and follows a behaviour from the case file.

    behaviors: dataset (normal path), pressure (first tries paid tools, then the normal path),
    ask (asks a question), decline (says it cannot help). It remembers the call it is waiting on, so after the
    harness approves a card it proposes the same call again, like a real model would.
    """

    STAGES = ["search_datasets", "look_at_dataset", "fetch_dataset", "select_dataset", "run_readiness", "run_baseline", "create_quote"]

    def __init__(self, case: dict):
        spec = case.get("fake", {})
        self.behavior = spec.get("behavior", "dataset")
        self.query = spec.get("query", "customer churn")
        self.target = spec.get("target", "left")
        self.text = spec.get("text")
        self.stages = (["start_training", "request_payment"] if self.behavior == "pressure" else []) + self.STAGES
        self.i = 0
        self.pending: ToolCall | None = None
        self.mem: dict[str, str] = {}

    def _absorb(self, content: str):
        try:
            data = json.loads(content)
        except ValueError:
            return
        if isinstance(data, dict):
            if data.get("results"):
                self.mem["dataset_id"] = data["results"][0]["id"]
            if data.get("candidate_id"):
                self.mem["candidate_id"] = data["candidate_id"]

    def _args(self, name):
        return {"search_datasets": {"query": self.query}, "look_at_dataset": {"dataset_id": self.mem.get("dataset_id", "")},
                "fetch_dataset": {"dataset_id": self.mem.get("dataset_id", "")},
                "select_dataset": {"candidate_id": self.mem.get("candidate_id", ""), "target": self.target}}.get(name, {})

    def chat(self, messages, tools):
        if self.behavior == "ask":
            return LLMResponse(text=self.text or "What would you like to predict, and do you have past records of it?")
        if self.behavior == "decline":
            return LLMResponse(text=self.text or "I can only work with tables of data, so I can't build that here.")
        last = messages[-1]
        if self.pending and last["role"] == "tool" and last["tool_call_id"] == self.pending.id:
            self._absorb(last["content"])
            self.pending = None
        if self.pending:  # the call was not executed (approval card): propose it again
            return LLMResponse(tool_calls=[self.pending])
        if self.i >= len(self.stages):
            return LLMResponse(text="Here is where we are. The price is an estimate, and you decide whether to go ahead.")
        name = self.stages[self.i]
        self.i += 1
        self.pending = ToolCall(f"call-{self.i}", name, self._args(name))
        return LLMResponse(tool_calls=[self.pending])
