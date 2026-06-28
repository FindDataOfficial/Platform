"""LLM provider abstraction (research R1, T011).

A thin protocol returning a normalized result. Two adapters ship in v1:
OpenAI-compatible and Anthropic. The agent loop talks only to BaseProvider.
"""

from __future__ import annotations

import abc
import json
from dataclasses import dataclass, field

import httpx

from src.llm.secrets import decrypt
from src.models.entities import LlmModel, LlmProvider, ProviderType


@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict


@dataclass
class LlmUsage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class LlmResult:
    text: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    usage: LlmUsage | None = None
    cost_usd: float | None = None
    finish_reason: str | None = None


def _cost(model: LlmModel, usage: LlmUsage) -> float | None:
    if model.input_price_per_1m is None or model.output_price_per_1m is None:
        return None
    return round(
        usage.prompt_tokens * float(model.input_price_per_1m) / 1_000_000
        + usage.completion_tokens * float(model.output_price_per_1m) / 1_000_000,
        6,
    )


class BaseProvider(abc.ABC):
    """Normalized LLM interface the agent loop depends on."""

    @abc.abstractmethod
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LlmResult:
        ...


class OpenAICompatibleProvider(BaseProvider):
    """Covers OpenAI, Ollama, vLLM, OpenRouter, Groq, etc. via base_url (R1)."""

    def __init__(self, provider: LlmProvider, model: LlmModel) -> None:
        self.base_url = provider.base_url.rstrip("/")
        self.api_key = decrypt(provider.api_key_ciphertext)
        self.model = model.model_name
        self._model = model  # for cost lookup

    async def complete(self, messages, tools=None) -> LlmResult:
        body: dict = {"model": self.model, "messages": messages}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})
        u = LlmUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        tool_calls = [
            ToolCallRequest(
                id=tc["id"],
                name=tc["function"]["name"],
                arguments=json.loads(tc["function"]["arguments"] or "{}"),
            )
            for tc in (choice.get("tool_calls") or [])
        ]
        return LlmResult(
            text=choice.get("content") or "",
            tool_calls=tool_calls,
            usage=u,
            cost_usd=_cost(self._model, u),
            finish_reason=data["choices"][0].get("finish_reason"),
        )


class AnthropicProvider(BaseProvider):
    def __init__(self, provider: LlmProvider, model: LlmModel) -> None:
        self.base_url = (provider.base_url or "https://api.anthropic.com").rstrip("/")
        self.api_key = decrypt(provider.api_key_ciphertext)
        self.model = model.model_name
        self._model = model

    async def complete(self, messages, tools=None) -> LlmResult:
        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        conv = [m for m in messages if m["role"] != "system"]
        body: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": conv,
        }
        if system_msgs:
            body["system"] = "\n\n".join(system_msgs)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages",
                json=body,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        text_parts = [
            b["text"] for b in data.get("content", []) if b.get("type") == "text"
        ]
        usage = data.get("usage", {})
        u = LlmUsage(
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
        )
        return LlmResult(
            text="".join(text_parts),
            usage=u,
            cost_usd=_cost(self._model, u),
            finish_reason=data.get("stop_reason"),
        )


def build_provider(provider: LlmProvider, model: LlmModel) -> BaseProvider:
    if provider.type == ProviderType.openai_compatible:
        return OpenAICompatibleProvider(provider, model)
    if provider.type == ProviderType.anthropic:
        return AnthropicProvider(provider, model)
    raise ValueError(f"unsupported provider type: {provider.type}")
