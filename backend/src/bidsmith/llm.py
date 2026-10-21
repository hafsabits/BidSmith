"""Thin wrapper over the official Anthropic SDK.

Two call shapes cover every agent:
  - structured(): one request, Pydantic-validated output (client.messages.parse)
  - tool_loop():  manual tool-use loop for agents that call deterministic code
Every call returns a UsageRecord so the UI can show tokens and cost per node.
"""

import json
from typing import Any, Callable, TypeVar

import anthropic
from pydantic import BaseModel

from bidsmith.schemas import UsageRecord
from bidsmith.settings import get_settings

T = TypeVar("T", bound=BaseModel)

# USD per 1M tokens (input, output). Update if pricing changes.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

# Server-side fallback if a request is declined by safety classifiers (Claude API only).
FALLBACK_HEADERS = {"anthropic-beta": "server-side-fallback-2026-07-01"}
FALLBACK_BODY = {"fallbacks": "default"}
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


class LLMRefusal(RuntimeError):
    pass


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return round((input_tokens * price_in + output_tokens * price_out) / 1_000_000, 5)


def _usage(node: str, model: str, usage: Any) -> UsageRecord:
    return UsageRecord(
        node=node,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=_cost(model, usage.input_tokens, usage.output_tokens),
    )


def _merge(records: list[UsageRecord]) -> UsageRecord:
    first = records[0]
    i = sum(r.input_tokens for r in records)
    o = sum(r.output_tokens for r in records)
    return UsageRecord(node=first.node, model=first.model, input_tokens=i, output_tokens=o, cost_usd=_cost(first.model, i, o))


class LLM:
    def __init__(self, client: anthropic.Anthropic | None = None):
        settings = get_settings()
        if client is None:
            # Falls back to ANTHROPIC_API_KEY / other SDK credential sources when .env has no key.
            # With our own key, pin the endpoint so an inherited ANTHROPIC_BASE_URL (e.g. from another tool's
            # shell) can't redirect the key elsewhere.
            client = (
                anthropic.Anthropic(api_key=settings.anthropic_api_key, base_url=settings.anthropic_base_url)
                if settings.anthropic_api_key
                else anthropic.Anthropic()
            )
        self.client = client
        self.settings = settings

    def _extra(self, model: str) -> dict:
        if model in FALLBACK_MODELS:
            return {"extra_headers": FALLBACK_HEADERS, "extra_body": FALLBACK_BODY}
        return {}

    def _effort(self, model: str, effort: str | None) -> dict:
        if effort:
            return {"output_config": {"effort": effort}}
        if model == self.settings.model_smart:
            return {"output_config": {"effort": self.settings.smart_effort}}
        return {}

    def structured(
        self,
        node: str,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: str | None = None,
        max_tokens: int = 16000,
    ) -> tuple[T, UsageRecord]:
        # Streamed so long outputs (the proposal) don't hit the SDK's non-streaming timeout guard.
        with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            thinking={"type": "adaptive"},
            **self._effort(model, effort),
            **self._extra(model),
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason == "refusal":
            raise LLMRefusal(f"{node}: model declined the request")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise RuntimeError(f"{node}: output incomplete (stop_reason={response.stop_reason})")
        return response.parsed_output, _usage(node, model, response.usage)

    def tool_loop(
        self,
        node: str,
        model: str,
        system: str,
        user: str,
        tools: list[dict],
        handlers: dict[str, Callable[[dict], str]],
        on_tool_call: Callable[[str, dict, str], None] | None = None,
        max_turns: int = 6,
        max_tokens: int = 16000,
    ) -> tuple[str, UsageRecord]:
        messages: list[dict] = [{"role": "user", "content": user}]
        usages: list[UsageRecord] = []
        for _ in range(max_turns):
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=tools,
                messages=messages,
                thinking={"type": "adaptive"},
                **self._effort(model, None),
                **self._extra(model),
            )
            usages.append(_usage(node, model, response.usage))
            if response.stop_reason == "refusal":
                raise LLMRefusal(f"{node}: model declined the request")
            # Append the full content (thinking blocks included) to keep the turn valid.
            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if response.stop_reason != "tool_use" or not tool_uses:
                text = "".join(b.text for b in response.content if b.type == "text")
                return text.strip(), _merge(usages)
            results = []
            for block in tool_uses:
                handler = handlers.get(block.name)
                try:
                    output = handler(dict(block.input)) if handler else f"Unknown tool {block.name}"
                    is_error = handler is None
                except Exception as exc:  # report tool failures back to the model
                    output, is_error = f"Error: {exc}", True
                if on_tool_call:
                    on_tool_call(block.name, dict(block.input), output)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error})
            messages.append({"role": "user", "content": results})
        return "Stopped after reaching the tool-call limit.", _merge(usages)


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM()
    return _llm


def set_llm(llm: Any) -> None:
    """Swap in a fake for tests."""
    global _llm
    _llm = llm


def as_json(obj: Any) -> str:
    if isinstance(obj, BaseModel):
        return obj.model_dump_json(indent=2)
    return json.dumps(obj, indent=2, default=str)
