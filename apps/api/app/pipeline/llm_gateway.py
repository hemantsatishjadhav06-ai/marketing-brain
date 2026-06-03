"""ONE gateway for every LLM call. Cost-logged. No agent should call httpx directly.

Spec § 23: "One LLM gateway; cheap model for drafting, strong model only for
orchestration/critic."
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


# ─── price book — keep in sync with the providers' pricing pages ──────────────
# usd per 1k tokens — input / output
PRICE_PER_1K = {
    "anthropic/claude-sonnet-4.5": (0.003, 0.015),
    "anthropic/claude-haiku-4.5": (0.001, 0.005),
    "anthropic/claude-opus-4.6": (0.015, 0.075),
    "openai/gpt-4o-mini": (0.00015, 0.0006),
}


@dataclass
class LLMResult:
    content: str
    json_data: Optional[dict]
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    raw: dict


class LLMTier:
    REASONING = "reasoning"  # orchestrator, critic, calendar
    DRAFTING = "drafting"    # specialist agents drafting content


def _model_for(tier: str) -> str:
    if tier == LLMTier.REASONING:
        return settings.OPENROUTER_MODEL_REASONING
    return settings.OPENROUTER_MODEL_DRAFTING


def _cost(model: str, tokens_in: int, tokens_out: int) -> float:
    in_p, out_p = PRICE_PER_1K.get(model, (0.003, 0.015))
    return round((tokens_in / 1000) * in_p + (tokens_out / 1000) * out_p, 6)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
def complete(
    *,
    tier: str,
    system: str,
    user: str,
    temperature: float = 0.6,
    max_tokens: int = 2000,
    json_mode: bool = False,
    extra_messages: Optional[list[dict]] = None,
) -> LLMResult:
    """Synchronous chat completion via OpenRouter.

    `json_mode=True` enforces JSON return where the provider supports it.
    """
    if not settings.OPENROUTER_API_KEY:
        # graceful dev fallback so the app still boots without keys
        stub = {"note": "OPENROUTER_API_KEY unset; this is a stub"}
        return LLMResult(
            content=json.dumps(stub),
            json_data=stub,
            model="stub",
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
            raw={},
        )
    model = _model_for(tier)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if extra_messages:
        messages.extend(extra_messages)

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=120) as client:
        r = client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://marketing-brain.local",
                "X-Title": "Marketing Brain",
            },
            json=payload,
        )
        r.raise_for_status()
        raw = r.json()

    content = raw["choices"][0]["message"]["content"]
    usage = raw.get("usage", {})
    tokens_in = int(usage.get("prompt_tokens", 0))
    tokens_out = int(usage.get("completion_tokens", 0))
    cost = _cost(model, tokens_in, tokens_out)

    json_data: Optional[dict] = None
    if json_mode:
        try:
            json_data = json.loads(content)
        except json.JSONDecodeError:
            pass

    return LLMResult(
        content=content,
        json_data=json_data,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        raw=raw,
    )
