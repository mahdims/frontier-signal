from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ValidationError

import frontier_signal.llm as llm


class Result(BaseModel):
    value: int


class FakeCompletions:
    def __init__(self, content: str, finish_reason: str = "stop"):
        self.content = content
        self.finish_reason = finish_reason
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                    finish_reason=self.finish_reason,
                )
            ],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
        )


def gateway_with_response(content: str, finish_reason: str = "stop"):
    completions = FakeCompletions(content, finish_reason)
    gateway = llm.DeepSeekGateway.__new__(llm.DeepSeekGateway)
    gateway.client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions),
    )
    gateway.routing = {
        "pricing_per_million_tokens_usd": {
            "model": {"input_cache_miss": 1, "output": 1}
        },
        "routes": {
            "extract": {
                "model": "model",
                "thinking": "disabled",
                "max_tokens": 100,
            }
        },
    }
    return gateway, completions


def test_invalid_json_is_charged_once_and_not_blindly_retried(monkeypatch):
    gateway, completions = gateway_with_response('{"value":')
    usage = []
    monkeypatch.setattr(llm, "today_cost", lambda: 0)
    monkeypatch.setattr(llm, "log_usage", lambda *args: usage.append(args))

    with pytest.raises(ValidationError):
        gateway.call_json("extract", "Return JSON", {}, Result)

    assert completions.calls == 1
    assert len(usage) == 1


def test_truncated_response_is_charged_and_reported_without_retry(monkeypatch):
    gateway, completions = gateway_with_response('{"value":', finish_reason="length")
    usage = []
    monkeypatch.setattr(llm, "today_cost", lambda: 0)
    monkeypatch.setattr(llm, "log_usage", lambda *args: usage.append(args))

    with pytest.raises(llm.TruncatedResponse):
        gateway.call_json("extract", "Return JSON", {}, Result)

    assert completions.calls == 1
    assert len(usage) == 1
