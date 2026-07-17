from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar, Type
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import load_model_routing
from .db import log_usage, today_cost
from .settings import settings

T = TypeVar("T", bound=BaseModel)


class BudgetExceeded(RuntimeError):
    pass


class DeepSeekGateway:
    def __init__(self) -> None:
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for analysis")
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.routing = load_model_routing()

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        p = self.routing["pricing_per_million_tokens_usd"][model]
        return (input_tokens / 1_000_000) * p["input_cache_miss"] + (
            output_tokens / 1_000_000
        ) * p["output"]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=20),
        retry=retry_if_exception_type((ValidationError, json.JSONDecodeError, RuntimeError)),
        reraise=True,
    )
    def call_json(
        self,
        task: str,
        system_prompt: str,
        payload: dict,
        response_model: Type[T],
    ) -> T:
        if today_cost() >= settings.max_daily_llm_cost_usd:
            raise BudgetExceeded("Daily LLM budget reached")

        route = self.routing["routes"][task]
        model = route["model"]
        kwargs = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"{system_prompt}\n\n"
                        "Return a valid JSON object that matches the requested schema."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "max_tokens": route["max_tokens"],
            "response_format": {"type": "json_object"},
        }

        thinking = route.get("thinking", "disabled")
        kwargs["extra_body"] = {"thinking": {"type": thinking}}
        if thinking == "enabled":
            kwargs["reasoning_effort"] = route.get("reasoning_effort", "high")
        else:
            kwargs["temperature"] = 0.1

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or "{}"
        result = response_model.model_validate_json(content)

        usage = response.usage
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        cost = self._estimate_cost(model, input_tokens, output_tokens)
        log_usage(task, model, input_tokens, output_tokens, cost)
        return result


def read_prompt(name: str) -> str:
    return (settings.prompt_dir / f"{name}.md").read_text(encoding="utf-8")
