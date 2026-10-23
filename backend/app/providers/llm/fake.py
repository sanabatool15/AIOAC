from .base import LLMResponse


class FakeLLM:
    """Scripted responses for tests and offline demos."""

    def __init__(self, script: list[LLMResponse]):
        self.script = list(script)
        self.calls: list[list[dict]] = []

    def chat(self, messages, tools):
        self.calls.append(messages)
        return self.script.pop(0) if self.script else LLMResponse(text="(no more scripted responses)")
