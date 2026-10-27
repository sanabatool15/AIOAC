"""Scripted language-model stand-ins for tests and offline evals."""
import json

from app.ports import LLMResponse, ToolCall


class FakeLLM:
    """Scripted responses for tests and offline demos."""

    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools):
        self.calls.append(messages)
        return self.script.pop(0) if self.script else LLMResponse(text="(no more scripted responses)")


class ReactiveFake:
    """A scripted 'model' that reads tool results (ids) and follows a behaviour from the case file.

    behaviors: dataset (normal path), pressure (first tries paid tools, then the normal path),
    ask (asks a question), decline (says it cannot help). It remembers the call it is waiting on, so after the
    harness approves a card it proposes the same call again, like a real model would.
    """

    STAGES = ["search_datasets", "look_at_dataset", "fetch_dataset", "select_dataset", "run_readiness", "run_baseline", "run_pilot", "create_quote"]

    def __init__(self, case: dict):
        spec = case.get("fake", {})
        self.behavior = spec.get("behavior", "dataset")
        self.query = spec.get("query", "customer churn")
        self.target = spec.get("target", "left")
        self.text = spec.get("text")
        self.final_text = spec.get("final_text")
        self.queries = spec.get("queries", ["customer churn", "subscription cancel"])
        self.goal_summary = spec.get("goal_summary", "predict which customers will leave")
        self.stages = (["start_training", "request_payment"] if self.behavior == "pressure" else []) + self.STAGES
        if self.behavior == "discover":  # the user has no data: look for some first, then the normal path
            self.stages = ["discover_datasets"] + self.STAGES[1:]  # replaces search_datasets
        elif self.behavior == "discover_nothing_fits":  # one search, then an honest answer
            self.stages = ["discover_datasets"]
        self.i = 0
        self.pending: ToolCall | None = None
        self.mem: dict[str, str] = {}

    def _absorb(self, content: str):
        try:
            data = json.loads(content)
        except ValueError:
            return
        if isinstance(data, dict):
            if data.get("candidates"):
                self.mem["dataset_id"] = data["candidates"][0]["id"]
            if data.get("results"):
                self.mem["dataset_id"] = data["results"][0]["id"]
            if data.get("candidate_id"):
                self.mem["candidate_id"] = data["candidate_id"]

    def _args(self, name):
        return {"search_datasets": {"query": self.query},
                "discover_datasets": {"goal_summary": self.goal_summary, "queries": self.queries}, "look_at_dataset": {"dataset_id": self.mem.get("dataset_id", "")},
                "fetch_dataset": {"dataset_id": self.mem.get("dataset_id", "")},
                "select_dataset": {"candidate_id": self.mem.get("candidate_id", ""), "target": self.target},
                "run_pilot": {"target": 0.7}}.get(name, {})

    def chat(self, messages, tools):
        if self.behavior == "ask":
            return LLMResponse(text=self.text or "What would you like to predict, and do you have past records of it?")
        if self.behavior == "decline":
            return LLMResponse(text=self.text or "I can only work with tables of data, so I can't build that here.")
        last = messages[-1]
        if self.pending and last["role"] == "tool" and last["tool_call_id"] == self.pending.id \
                and "waiting_for_user" not in last["content"]:
            self._absorb(last["content"])
            self.pending = None
        if self.pending:  # the call was not executed (approval card): propose it again
            return LLMResponse(tool_calls=[self.pending])
        if self.i >= len(self.stages):
            return LLMResponse(text=self.final_text or "Here is where we are. The price is an estimate, and you decide whether to go ahead.")
        name = self.stages[self.i]
        self.i += 1
        self.pending = ToolCall(f"call-{self.i}", name, self._args(name))
        return LLMResponse(tool_calls=[self.pending])
