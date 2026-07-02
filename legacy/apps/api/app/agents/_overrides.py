"""Per-request overrides plumbing for quick_create.

quick_create stuffs an Overrides JSON blob into `CalendarEntry.reason` after a
` | ` separator (so the human-readable reason stays scannable). This module
parses it out and exposes helpers the agents call at their LLM call site.

If no overrides are present, defaults apply and the agents behave exactly as
before (back-compat for calendar-driven drafts).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.pipeline.llm_gateway import LLMTier


@dataclass
class Overrides:
    tone: str | None = None
    length: str | None = None       # "short" | "medium" | "long"
    model: str | None = None        # "auto" | "drafting" | "reasoning"
    custom_instructions: str | None = None


def parse(entry_reason: str | None) -> Overrides:
    """Find the JSON blob after the last ' | ' in the entry's reason field."""
    if not entry_reason or " | " not in entry_reason:
        return Overrides()
    last = entry_reason.rsplit(" | ", 1)[-1].strip()
    if not last.startswith("{"):
        return Overrides()
    try:
        d = json.loads(last)
        return Overrides(
            tone=(d.get("tone") or None),
            length=(d.get("length") or None),
            model=(d.get("model") or None),
            custom_instructions=(d.get("custom_instructions") or None),
        )
    except json.JSONDecodeError:
        return Overrides()


def max_tokens_for(default: int, length: str | None) -> int:
    """Scale max_tokens by the user's length preference."""
    if length == "short":
        return max(200, default // 2)
    if length == "long":
        return default * 2
    return default


def tier_for(default_tier: str, model: str | None) -> str:
    """Map override.model → LLMTier value, with 'auto' = default."""
    if model == "reasoning":
        return LLMTier.REASONING
    if model == "drafting":
        return LLMTier.DRAFTING
    return default_tier


def apply_to_system(system: str, ov: Overrides) -> str:
    """Append override tone + custom instructions to the agent's system prompt.
    No-op when both are blank."""
    extras: list[str] = []
    if ov.tone:
        extras.append(f"\nADDITIONAL TONE OVERRIDE (this request only): {ov.tone}")
    if ov.custom_instructions:
        extras.append(f"\nADDITIONAL INSTRUCTIONS (this request only): {ov.custom_instructions}")
    return system + "".join(extras) if extras else system
